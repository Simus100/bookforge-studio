"""Loopback-only web app. No remote AI calls or manuscript uploads."""
from __future__ import annotations

import argparse
import json
import mimetypes
import re
import secrets
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from core import Store, Problem, find_chapter, digest
from tts import Speech, sentences

APP = Path(__file__).resolve().parent


class Handler(BaseHTTPRequestHandler):
    server_version = "BookForgeStudio/0.1"

    def log_message(self, fmt, *args):
        # Do not write manuscript text or requests to logs.
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))

    def valid_host(self):
        return self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

    def send(self, status, body, content_type="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store" if not content_type.startswith("audio/") else "private, max-age=86400")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def error(self, exc):
        try:
            self.send(exc.status if isinstance(exc, Problem) else 500,
                      {"error": str(exc) if isinstance(exc, Problem) else "Operazione non riuscita. Il manoscritto salvato è al sicuro. " + type(exc).__name__})
        except (ConnectionError, BrokenPipeError):
            pass

    def do_GET(self):
        try:
            if not self.valid_host():
                raise Problem("Host non consentito.", 403)
            path = urllib.parse.urlsplit(self.path).path
            if path == "/api/state":
                return self.send(200, {"state": self.server.store.read(), "token": self.server.token})
            if path == "/api/voices":
                return self.send(200, self.server.speech.status())
            if path == "/api/history":
                return self.send(200, {"history": self.server.store.history()})
            if path == "/api/sentences":
                query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                chapter = find_chapter(self.server.store.read(), query.get("chapter_id", [""])[0])
                return self.send(200, {"sentences": sentences(chapter["text"]), "sha256": digest(chapter["text"])})
            if path.startswith("/audio/") and re.fullmatch(r"/audio/[a-f0-9]{64}\.wav", path):
                file = self.server.speech.cache / path.rsplit("/", 1)[-1]
                if not file.is_file():
                    raise Problem("Audio da rigenerare.", 404)
                return self.send(200, file.read_bytes(), "audio/wav")
            name = {"/": "index.html", "/app.js": "app.js", "/styles.css": "styles.css", "/polish.css": "polish.css", "/favicon.svg": "favicon.svg"}.get(path)
            if name:
                file = APP / "web" / name
                return self.send(200, file.read_bytes(), mimetypes.guess_type(name)[0] or "application/octet-stream")
            raise Problem("Risorsa non trovata.", 404)
        except Exception as exc:
            self.error(exc)

    def do_POST(self):
        try:
            if not self.valid_host() or not secrets.compare_digest(self.headers.get("X-BookForge-Token", ""), self.server.token):
                raise Problem("Richiesta non autorizzata. Ricarica l'app.", 403)
            origin = self.headers.get("Origin")
            if origin and origin not in (f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"):
                raise Problem("Origine non consentita.", 403)
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 25_000_000:
                raise Problem("Il file supera il limite di 25 MB.", 413)
            try:
                payload = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeError):
                raise Problem("JSON non valido.")
            if not isinstance(payload, dict):
                raise Problem("Formato richiesta non valido.")
            route = urllib.parse.urlsplit(self.path).path
            operations = {"/api/chapter/add": self.server.store.add_chapter,
                          "/api/chapter/save": self.server.store.save_chapter,
                          "/api/settings": self.server.store.settings,
                          "/api/request/add": self.server.store.add_request,
                          "/api/batch/export": self.server.store.export_batch,
                          "/api/response/import": self.server.store.import_response,
                          "/api/request/resolve": self.server.store.resolve,
                          "/api/undo": self.server.store.undo,
                          "/api/project/restore": self.server.store.restore}
            if route in operations:
                return self.send(200, operations[route](payload))
            if route == "/api/shutdown":
                self.send(200, {"stopped": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            if route == "/api/voice/install":
                return self.send(200, self.server.speech.install(payload.get("voice")))
            if route == "/api/speech":
                chapter = find_chapter(self.server.store.read(), payload.get("chapter_id"))
                if payload.get("sha256") != digest(chapter["text"]):
                    raise Problem("Il testo è cambiato. Riavvia l'ascolto.", 409)
                units = sentences(chapter["text"])
                index = payload.get("index")
                if type(index) is not int or not 0 <= index < len(units):
                    raise Problem("Frase non valida.")
                return self.send(200, self.server.speech.synthesize(units[index]["text"], payload.get("voice", "paola")))
            if route == "/api/backup":
                self.server.store.backup()
                return self.send(200, {"project": self.server.store.read()})
            raise Problem("Operazione non trovata.", 404)
        except Exception as exc:
            self.error(exc)


def create_server(data, port=0):
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.token = secrets.token_urlsafe(32)
    server.store = Store(data)
    server.speech = Speech(data)
    return server


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=APP / "dati")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--open", action="store_true")
    args = parser.parse_args()
    server = create_server(args.data, args.port)
    server.store.backup()
    url = f"http://127.0.0.1:{server.server_port}"
    (args.data / "server.json").write_text(json.dumps({"url": url, "pid": __import__("os").getpid()}), encoding="utf-8")
    print("BookForge Studio: " + url, flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.speech.close()
        server.server_close()


if __name__ == "__main__":
    main()
