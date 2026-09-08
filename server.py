from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
import json
import os

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8000"))
DATA_FILE = Path(__file__).with_name("ranking.json")
PARTICIPATION_FILE = Path(__file__).with_name("participation_events.json")
DATA_LOCK = Lock()


def read_ranking():
    if not DATA_FILE.exists():
        return []
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def write_ranking(entries):
    DATA_FILE.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def read_participation():
    if not PARTICIPATION_FILE.exists():
        return []
    try:
        return json.loads(PARTICIPATION_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def write_participation(entries):
    PARTICIPATION_FILE.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


class AppHandler(SimpleHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/ranking":
            with DATA_LOCK:
                entries = sorted(read_ranking(), key=lambda item: (-item["points"], -item["correct"], item["created_at"]))
            self.send_json(200, entries)
            return
        if self.path == "/api/participation":
            with DATA_LOCK:
                entries = read_participation()
            self.send_json(200, entries)
            return
        super().do_GET()

    def do_POST(self):
        if self.path not in ("/api/ranking", "/api/participation"):
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            name = str(payload.get("name", "")).strip()[:30]
            points = int(payload.get("points", 0))
            correct = int(payload.get("correct", 0))
        except (ValueError, TypeError, json.JSONDecodeError):
            self.send_json(400, {"error": "Datos invalidos"})
            return
        from datetime import datetime, timezone
        if self.path == "/api/participation":
            session_id = str(payload.get("session_id", "")).strip()
            status = str(payload.get("status", "")).strip()
            question_number = int(payload.get("question_number", 0))
            if len(name) < 2 or not session_id or status not in ("registered", "completed", "abandoned") or not 0 <= question_number <= 10:
                self.send_json(400, {"error": "Participacion invalida"})
                return
            with DATA_LOCK:
                entries = read_participation()
                if status == "registered" and any(item["name"].casefold() == name.casefold() for item in entries):
                    self.send_json(409, {"error": "Nombre ya registrado"})
                    return
                entry = {"session_id": session_id, "name": name, "status": status, "question_number": question_number, "created_at": datetime.now(timezone.utc).isoformat()}
                entries.append(entry)
                write_participation(entries)
            self.send_json(201, entry)
            return
        if len(name) < 2 or not 0 <= points <= 100 or not 0 <= correct <= 10:
            self.send_json(400, {"error": "Resultado invalido"})
            return
        entry = {"name": name, "points": points, "correct": correct, "created_at": datetime.now(timezone.utc).isoformat()}
        with DATA_LOCK:
            entries = read_ranking()
            entries.append(entry)
            write_ranking(entries)
        self.send_json(201, entry)


if __name__ == "__main__":
    print(f"Quimio disponible en http://localhost:{PORT}/index.html")
    print("Para estudiantes usa la IP local de este computador, por ejemplo: http://192.168.1.61:8000/index.html")
    ThreadingHTTPServer((HOST, PORT), AppHandler).serve_forever()
