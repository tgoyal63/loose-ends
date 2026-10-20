#!/usr/bin/env python3
"""Serve Loose Ends on loopback. Notes remain in memory for one request."""

from __future__ import annotations

import argparse
import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from loose_ends.extraction import InvalidModelOutput, MAX_NOTES, parse_proposals, valid_unicode, validate_proposals
from loose_ends.model import LocalModel, ModelResponseError, ModelUnavailable

ROOT = Path(__file__).resolve().parent
MAX_BODY = 65_536
DEFAULT_MODEL = "default_model"


class AppServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, model):
        self.model = model
        self.inference = threading.BoundedSemaphore(1)
        super().__init__(address, Handler)
        port = self.server_address[1]
        self.hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        self.origins = {f"http://{host}" for host in self.hosts}


class Handler(BaseHTTPRequestHandler):
    server: AppServer

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, format, *args):
        # Avoid writing user notes, query strings or model output to access logs.
        pass

    def reply(self, status: int, body: bytes, content_type: str):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; base-uri 'none'; "
            "form-action 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def json_reply(self, status: int, result: dict):
        self.reply(status, json.dumps(result, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def error(self, status: int, code: str, message: str):
        self.json_reply(status, {"error": {"code": code, "message": message}})

    def trusted_host(self) -> bool:
        if self.headers.get("Host") not in self.server.hosts:
            self.error(403, "invalid_host", "Open Loose Ends using its local address.")
            return False
        return True

    def do_GET(self):
        if not self.trusted_host():
            return
        path = urlsplit(self.path).path
        if path == "/api/status":
            try:
                ready = self.server.model.ready()
            except (ModelUnavailable, ModelResponseError):
                ready = False
            self.json_reply(
                200,
                {
                    "ready": ready,
                    "model": self.server.model.label,
                    "message": "Local model ready." if ready else "Start the local model service, then check again.",
                },
            )
            return
        allowed = {"/": "index.html", "/index.html": "index.html", "/styles.css": "styles.css", "/app.js": "app.js"}
        if path not in allowed:
            self.error(404, "not_found", "This page does not exist.")
            return
        file = ROOT / "web" / allowed[path]
        try:
            data = file.read_bytes()
        except OSError:
            self.error(503, "assets_unavailable", "The interface files are unavailable.")
            return
        mime = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        self.reply(200, data, mime + "; charset=utf-8")

    def do_POST(self):
        if not self.trusted_host():
            return
        if urlsplit(self.path).path != "/api/plan":
            self.error(404, "not_found", "This endpoint does not exist.")
            return
        if self.headers.get("Origin") not in self.server.origins:
            self.error(403, "invalid_origin", "Only the local interface may request a plan.")
            return
        if self.headers.get_content_type() != "application/json":
            self.error(415, "invalid_content_type", "Send notes as JSON.")
            return
        if self.headers.get("Transfer-Encoding"):
            self.error(400, "invalid_body", "Chunked request bodies are not supported.")
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self.error(411, "missing_length", "A valid content length is required.")
            return
        if not 1 <= length <= MAX_BODY:
            self.error(413, "body_too_large", "The note is too large.")
            return
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("Incomplete body")
            document = json.loads(raw)
        except (ValueError, UnicodeDecodeError, RecursionError, TimeoutError):
            self.error(400, "invalid_json", "The note could not be read. Please try again.")
            return
        notes = document.get("notes") if isinstance(document, dict) else None
        if (
            not isinstance(notes, str)
            or not notes.strip()
            or len(notes) > MAX_NOTES
            or "\x00" in notes
            or not valid_unicode(notes)
        ):
            self.error(400, "invalid_notes", f"Enter a note between 1 and {MAX_NOTES:,} characters.")
            return
        if not self.server.inference.acquire(blocking=False):
            self.error(429, "busy", "A note is already being processed. Please wait and try again.")
            return
        try:
            content = self.server.model.propose(notes)
            tasks, rejected = validate_proposals(notes, parse_proposals(content))
            self.json_reply(200, {"tasks": tasks, "rejected_count": rejected, "model": self.server.model.label})
        except ModelUnavailable:
            self.error(503, "model_unavailable", "The local model could not be reached. Check its status and try again.")
        except (ModelResponseError, InvalidModelOutput):
            self.error(502, "invalid_model_output", "The model could not produce a usable draft. Try a shorter note.")
        finally:
            self.server.inference.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=62140)
    parser.add_argument("--model-base-url", default="http://127.0.0.1:62141/v1")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--model-label", help="Display name for the model you actually started.")
    args = parser.parse_args()
    model = LocalModel(args.model_base_url, args.model, label=args.model_label)
    server = AppServer(("127.0.0.1", args.port), model)
    print(f"Loose Ends: http://127.0.0.1:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
