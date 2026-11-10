"""Offline speech engines. Network is used only by explicit model installation."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import wave
from pathlib import Path

from core import Problem, digest

APP = Path(__file__).resolve().parent
VOICES = {
    "paola": {"name": "Paola", "engine": "piper", "description": "Italiano · voce femminile · CPU", "profile": "Leggera",
              "model": "it_IT-paola-medium", "repo_path": "it/it_IT/paola/medium", "download_mb": 64},
    "riccardo": {"name": "Riccardo", "engine": "piper", "description": "Italiano · voce maschile · CPU", "profile": "Essenziale",
                 "model": "it_IT-riccardo-x_low", "repo_path": "it/it_IT/riccardo/x_low", "download_mb": 28},
    "studio": {"name": "Narratore Studio", "engine": "qwen", "description": "Qwen3-TTS 1.7B · GPU NVIDIA", "profile": "Studio",
               "model": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice", "download_mb": 6000},
}
NARRATOR = "Una voce italiana adulta, calda e naturale, da audiolibro. Dizione chiara, ritmo calmo ma scorrevole, pause sobrie. Leggi fedelmente il testo senza aggiunte."


def sentences(text):
    """Code-point offsets into the exact manuscript, never a normalized copy."""
    result, start, i = [], 0, 0
    abbreviations = {"sig", "sig.ra", "sig.na", "dott", "dott.ssa", "prof", "prof.ssa", "dr", "ing", "avv", "pag", "cap", "n", "art", "ecc", "es"}
    while i < len(text):
        c = text[i]
        boundary, end = False, i + 1
        if c == "\n":
            boundary, end = True, i
        elif c in ".!?…":
            while end < len(text) and text[end] in '.!?…»”"\')]' :
                end += 1
            if end == len(text) or text[end].isspace():
                word = re.search(r"([\w.]+)$", text[start:i])
                token = word.group(1).lower() if word else ""
                boundary = not (c == "." and (token in abbreviations or len(token) == 1 and token.isalpha()))
        if boundary:
            a, b = start, end
            while a < b and text[a].isspace():
                a += 1
            while b > a and text[b-1].isspace():
                b -= 1
            if a < b:
                # Break exceptional unpunctuated blocks without inventing wording.
                while b - a > 900:
                    cut = text.rfind(" ", a + 400, a + 900)
                    if cut < 0:
                        cut = a + 900
                    result.append({"start": a, "end": cut, "text": text[a:cut]})
                    a = cut
                    while a < b and text[a].isspace():
                        a += 1
                if a < b:
                    result.append({"start": a, "end": b, "text": text[a:b]})
            start = end
            i = max(i, end - 1)
        i += 1
    if start < len(text) and text[start:].strip():
        a = start
        while a < len(text) and text[a].isspace():
            a += 1
        b = len(text.rstrip())
        while b - a > 900:
            cut = text.rfind(" ", a + 400, a + 900)
            if cut < 0:
                cut = a + 900
            result.append({"start": a, "end": cut, "text": text[a:cut]})
            a = cut
            while a < b and text[a].isspace():
                a += 1
        if a < b:
            result.append({"start": a, "end": b, "text": text[a:b]})
    return result


class Speech:
    def __init__(self, root):
        self.root = Path(root)
        self.models = self.root / "voci"
        self.cache = self.root / "audio"
        self.models.mkdir(parents=True, exist_ok=True)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.install_lock = threading.Lock()
        self.loaded = {}
        self.jobs = {}
        self.worker = None
        self.last_rtf = None
        self.metrics_path = self.root / "prestazioni-voci.json"
        try:
            self.metrics = json.loads(self.metrics_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.metrics = {}
        self.studio_python = APP / ".studio" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    def installed(self, key):
        info = VOICES[key]
        if info["engine"] == "piper":
            return all((self.models / (info["model"] + ext)).is_file() for ext in (".onnx", ".onnx.json", ".ready"))
        return (self.models / "studio" / "ready.json").is_file() and self.studio_python.is_file()

    def status(self):
        recommended = "paola"
        if self.installed("studio") and self.metrics.get("studio", {}).get("samples", 0) >= 2 and self.metrics.get("studio", {}).get("rtf", 99) < .85:
            recommended = "studio"
        elif self.installed("riccardo") and (not self.installed("paola") or self.metrics.get("paola", {}).get("samples", 0) >= 2 and self.metrics.get("paola", {}).get("rtf", 0) > .8):
            recommended = "riccardo"
        return {"voices": [{"id": k, **v, "installed": self.installed(k), "job": self.jobs.get(k)} for k, v in VOICES.items()],
                "cpu_threads": os.cpu_count(), "last_rtf": self.last_rtf,
                "recommendation": recommended, "offline": True,
                "note": "La voce Studio richiede una GPU NVIDIA compatibile. La fluidità viene misurata durante la lettura."}

    def install(self, key):
        if key not in VOICES:
            raise Problem("Voce non riconosciuta.")
        if self.installed(key):
            return self.status()
        with self.install_lock:
            if any(j.get("status") == "running" for j in self.jobs.values()):
                raise Problem("È già in corso un download. Attendi che finisca.", 409)
            self.jobs[key] = {"status": "running", "message": "Preparazione del download…", "progress": 0}
        threading.Thread(target=self._install, args=(key,), daemon=True).start()
        return self.status()

    def _download(self, url, path, job):
        tmp = path.with_name(path.name + ".part")
        req = urllib.request.Request(url, headers={"User-Agent": "BookForgeStudio/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=120) as response, open(tmp, "wb") as target:
                total = int(response.headers.get("Content-Length", 0))
                received = 0
                while chunk := response.read(1024 * 512):
                    target.write(chunk)
                    received += len(chunk)
                    job.update(message=f"Scaricati {received / 1024**2:.1f} MB", progress=int(received * 100 / total) if total else 0)
            tmp.replace(path)
        finally:
            tmp.unlink(missing_ok=True)

    def _install(self, key):
        job = self.jobs[key]
        info = VOICES[key]
        try:
            if info["engine"] == "piper":
                # The upstream voice manifest includes integrity hashes for every file.
                manifest = json.load(urllib.request.urlopen("https://huggingface.co/rhasspy/piper-voices/resolve/main/voices.json", timeout=60))
                files = manifest[info["model"]]["files"]
                for ext in (".onnx.json", ".onnx"):
                    relative = f'{info["repo_path"]}/{info["model"]}{ext}'
                    target = self.models / (info["model"] + ext)
                    self._download("https://huggingface.co/rhasspy/piper-voices/resolve/main/" + relative, target, job)
                    expected = files.get(relative, {}).get("md5_digest")
                    if not expected or hashlib.md5(target.read_bytes()).hexdigest() != expected:
                        target.unlink(missing_ok=True)
                        raise RuntimeError("Integrità del download non verificata. Riprova.")
                card = self.models / (info["model"] + ".MODEL_CARD")
                self._download("https://huggingface.co/rhasspy/piper-voices/resolve/main/" + info["repo_path"] + "/MODEL_CARD", card, job)
                (self.models / (info["model"] + ".ready")).write_text("verified", encoding="utf-8")
            else:
                job.update(message="Installazione del motore Studio. Può richiedere diversi minuti e diversi GB.", progress=0)
                log = self.root / "installazione-studio.log"
                with open(log, "w", encoding="utf-8") as handle:
                    process = subprocess.run([sys.executable, str(APP / "setup_studio.py"), str(self.models / "studio")],
                                             stdout=handle, stderr=subprocess.STDOUT, timeout=7200,
                                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if process.returncode:
                    tail = log.read_text(encoding="utf-8", errors="replace")[-2000:]
                    raise RuntimeError("Installazione Studio non completata. " + tail)
            job.update(status="done", message="Voce scaricata. Pronta anche senza Internet.", progress=100)
        except Exception as exc:
            job.update(status="error", message=str(exc), progress=0)

    def synthesize(self, text, key):
        if key not in VOICES or not self.installed(key):
            raise Problem("Scarica prima la voce nelle impostazioni di ascolto.")
        if not text.strip() or len(text) > 1000:
            raise Problem("Brano audio vuoto o troppo lungo.")
        cache_id = digest("bookforge-tts-v1\0" + key + "\0" + NARRATOR + "\0" + text)
        path = self.cache / (cache_id + ".wav")
        # A single resident engine per voice; no model reload between sentences.
        with self.lock:
            if not path.is_file():
                started = time.perf_counter()
                temp = path.with_suffix(".tmp.wav")
                try:
                    if VOICES[key]["engine"] == "piper":
                        from piper import PiperVoice, SynthesisConfig
                        if key not in self.loaded:
                            import onnxruntime
                            from piper.config import PiperConfig
                            options = onnxruntime.SessionOptions()
                            options.intra_op_num_threads = min(4, max(1, (os.cpu_count() or 2) // 2))
                            options.inter_op_num_threads = 1
                            model = self.models / (VOICES[key]["model"] + ".onnx")
                            config = json.loads(Path(str(model) + ".json").read_text(encoding="utf-8"))
                            self.loaded[key] = PiperVoice(session=onnxruntime.InferenceSession(str(model), sess_options=options, providers=["CPUExecutionProvider"]),
                                                          config=PiperConfig.from_dict(config), download_dir=self.models)
                        with wave.open(str(temp), "wb") as wav:
                            self.loaded[key].synthesize_wav(text, wav, syn_config=SynthesisConfig(length_scale=1.03))
                    else:
                        self._studio_synthesize(text, temp)
                    with wave.open(str(temp), "rb") as wav:
                        duration = wav.getnframes() / wav.getframerate()
                    if duration <= 0:
                        raise RuntimeError("Il motore ha generato un file vuoto.")
                    self.last_rtf = round((time.perf_counter() - started) / duration, 3)
                    prior = self.metrics.get(key, {})
                    # Keep the best observed real-time factor so a cold load does not
                    # downgrade a fast machine. A failed engine is never recommended.
                    self.metrics[key] = {"rtf": min(self.last_rtf, prior.get("rtf", self.last_rtf)), "samples": prior.get("samples", 0) + 1}
                    metrics_tmp = self.metrics_path.with_suffix(".tmp")
                    metrics_tmp.write_text(json.dumps(self.metrics), encoding="utf-8")
                    metrics_tmp.replace(self.metrics_path)
                    temp.replace(path)
                    self._trim_cache()
                finally:
                    temp.unlink(missing_ok=True)
            with wave.open(str(path), "rb") as wav:
                duration = wav.getnframes() / wav.getframerate()
        return {"url": "/audio/" + path.name, "duration": duration, "cached": True, "rtf": self.last_rtf}

    def _studio_synthesize(self, text, path):
        if self.worker is None or self.worker.poll() is not None:
            env = os.environ.copy()
            env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HOME=str(self.models / "hf-cache"))
            log = open(self.root / "studio.log", "a", encoding="utf-8")
            self.worker = subprocess.Popen([str(self.studio_python), str(APP / "studio_worker.py"), str(self.models / "studio")],
                                           stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
                                           text=True, encoding="utf-8", env=env,
                                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            log.close()
        self.worker.stdin.write(json.dumps({"text": text, "output": str(path), "instruct": NARRATOR}, ensure_ascii=False) + "\n")
        self.worker.stdin.flush()
        # Inference runs in a worker; a deadline prevents a hung GPU from locking the app.
        response, finished = [], threading.Event()
        def read():
            response.append(self.worker.stdout.readline())
            finished.set()
        threading.Thread(target=read, daemon=True).start()
        if not finished.wait(240):
            self.worker.kill()
            self.worker = None
            raise Problem("Studio ha impiegato troppo tempo. Usa la voce leggera su questo PC.", 503)
        try:
            data = json.loads(response[0])
        except (ValueError, IndexError):
            raise Problem("Il motore Studio non si è avviato. Consulta studio.log o usa Paola.", 503)
        if not data.get("ok"):
            raise Problem(data.get("error", "Errore del motore Studio."), 503)

    def _trim_cache(self):
        # Keep recent speech up to 512 MB; deleting audio never touches the manuscript.
        files = sorted(self.cache.glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True)
        total = 0
        for path in files:
            total += path.stat().st_size
            if total > 512 * 1024**2:
                path.unlink(missing_ok=True)

    def close(self):
        if self.worker and self.worker.poll() is None:
            self.worker.terminate()
