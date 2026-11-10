import json
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parent
config = json.loads((root / "dati" / "server.json").read_text(encoding="utf-8"))
url = config["url"]
if not url.startswith("http://127.0.0.1:") or not url.rsplit(":", 1)[1].isdigit():
    raise SystemExit("Indirizzo locale non valido.")
try:
    with urllib.request.urlopen(url + "/api/state", timeout=3) as response:
        token = json.load(response)["token"]
    request = urllib.request.Request(url + "/api/shutdown", data=b"{}", headers={"Content-Type": "application/json", "X-BookForge-Token": token}, method="POST")
    with urllib.request.urlopen(request, timeout=5) as response:
        print("BookForge Studio arrestato. Il progetto è salvato.")
except OSError:
    print("Il servizio è già chiuso o non risponde.")
