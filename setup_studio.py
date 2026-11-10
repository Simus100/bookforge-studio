"""Explicit, isolated download/setup of the optional GPU narrator."""
import json
import os
import subprocess
import sys
import venv
from pathlib import Path

APP = Path(__file__).resolve().parent


def main():
    target = Path(sys.argv[1]).resolve()
    env_dir = APP / ".studio"
    if sys.version_info[:2] != (3, 12):
        raise SystemExit("Per Studio avvia l'app con Python 3.12.")
    if not env_dir.exists():
        venv.create(env_dir, with_pip=True)
    python = env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run([str(python), "-m", "pip", "install", "torch==2.10.0", "torchaudio==2.10.0", "--index-url", "https://download.pytorch.org/whl/cu128"], check=True)
    subprocess.run([str(python), "-m", "pip", "install", "qwen-tts==0.1.1"], check=True)
    check = subprocess.run([str(python), "-c", "import torch; print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'GPU NVIDIA/CUDA non disponibile'); raise SystemExit(0 if torch.cuda.is_available() else 2)"], check=False)
    if check.returncode:
        raise SystemExit("GPU NVIDIA compatibile non disponibile. I modelli Studio non sono stati scaricati. Usa Piper.")
    target.mkdir(parents=True, exist_ok=True)
    script = "from huggingface_hub import snapshot_download; import sys; snapshot_download('Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice', local_dir=sys.argv[1], ignore_patterns=['*.bin','*.msgpack','*.h5'])"
    subprocess.run([str(python), "-c", script, str(target)], check=True)
    # Warm up using local files only: readiness is recorded only after real GPU inference.
    env = os.environ.copy()
    env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    warmup = "import sys,torch,soundfile as sf; from qwen_tts import Qwen3TTSModel; m=Qwen3TTSModel.from_pretrained(sys.argv[1],device_map='cuda:0',dtype=torch.float16,attn_implementation='sdpa',local_files_only=True); w,s=m.generate_custom_voice(text='La lettura del libro comincia qui.',language='Italian',speaker='Ryan',max_new_tokens=1024); sf.write(sys.argv[2],w[0],s,subtype='PCM_16')"
    subprocess.run([str(python), "-c", warmup, str(target), str(target / "prova-italiano.wav")], check=True, env=env, timeout=600)
    (target / "ready.json").write_text(json.dumps({"model": "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice", "local": True, "gpu_tested": True}), encoding="utf-8")


if __name__ == "__main__":
    main()
