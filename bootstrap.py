"""Find Python 3.12 and prepare a private, reusable local runtime."""
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def find_python():
    options = [[sys.executable]]
    if shutil.which("py"):
        options.append(["py", "-3.12"])
    if os.name == "nt":
        program = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        try:
            options.extend([[str(p)] for p in (program / "WindowsApps").glob("OpenAI.CodexPrimaryRuntime.*/dependencies/python/python.exe")])
        except OSError:
            pass
    for command in options:
        try:
            result = subprocess.run(command + ["-c", "import sys; print(sys.executable); raise SystemExit(0 if sys.version_info[:2]==(3,12) else 1)"], capture_output=True, text=True, timeout=20)
            if result.returncode == 0:
                return result.stdout.strip().splitlines()[-1]
        except (OSError, subprocess.SubprocessError):
            continue
    raise RuntimeError("Installa Python 3.12 da https://www.python.org/downloads/ e riapri Avvia.cmd. L'app utilizza un ambiente isolato.")


def main():
    os.chdir(ROOT)
    running = ROOT / "dati" / "server.json"
    if running.is_file():
        try:
            config = json.loads(running.read_text(encoding="utf-8"))
            url = config["url"]
            if not url.startswith("http://127.0.0.1:") or not url.rsplit(":", 1)[1].isdigit():
                raise ValueError("invalid loopback")
            with urllib.request.urlopen(url + "/api/state", timeout=2) as response:
                if "state" in json.load(response):
                    webbrowser.open(url)
                    return
        except Exception:
            pass
    environment = ROOT / ".runtime"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        print("Preparazione dell'ambiente locale (solo al primo avvio)…", flush=True)
        subprocess.run([find_python(), "-m", "venv", str(environment)], check=True)
    check = subprocess.run([str(python), "-c", "from piper import PiperVoice"], capture_output=True)
    if check.returncode:
        print("Installazione del motore vocale locale…", flush=True)
        subprocess.run([str(python), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], check=True)
    subprocess.run([str(python), str(ROOT / "server.py"), "--open"], check=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\nAvvio non riuscito: " + str(exc), file=sys.stderr)
        raise SystemExit(1)
