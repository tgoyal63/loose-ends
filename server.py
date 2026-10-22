#!/usr/bin/env python3
"""Serve Loose Ends on loopback. Notes remain in memory for one request."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from loose_ends.extraction import InvalidModelOutput, MAX_NOTES, parse_proposals, valid_unicode, validate_proposals
from loose_ends.model import (
    LocalModel, ModelEmptyResponse, ModelInvalidJSON, ModelOutputLimit, ModelResponseError,
    ModelTimeout, ModelUnavailable,
)
from loose_ends.transcript import parse_turns
from loose_ends.hosted import (
    HOSTED_LABEL, HostedHTTPError, HostedModel, ModelAuthentication,
    ModelInputLimit, ModelRateLimit, ModelRequestRejected,
)

ROOT = Path(__file__).resolve().parent
# JSON may encode each supplementary Unicode character as two \\uXXXX escapes.
MAX_BODY = MAX_NOTES * 12 + 4096
DEFAULT_MODEL = "default_model"


class AppServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, model, hosted_model=None):
        self.model = model
        self.hosted_model = hosted_model
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

    def error(self, status: int, code: str, message: str, details: dict | None = None):
        error = {"code": code, "message": message}
        if details:
            error["details"] = details
        self.json_reply(status, {"error": error})

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
            modes = parse_qs(urlsplit(self.path).query, keep_blank_values=True).get("mode", ["local"])
            if len(modes) != 1 or modes[0] not in ("local", "hosted"):
                self.error(400, "invalid_mode", "Choose local or hosted processing.")
                return
            mode = modes[0]
            model = self.server.model if mode == "local" else self.server.hosted_model
            message = "Start the local model service, then check again." if mode == "local" else (
                "Check the Groq API key, connection and model permissions." if model else "Add a Groq API key to use hosted processing."
            )
            try:
                ready = model is not None and model.ready()
            except (ModelUnavailable, ModelResponseError):
                ready = False
            self.json_reply(
                200,
                {
                    "ready": ready,
                    "model": model.label if model else HOSTED_LABEL,
                    "mode": mode, "configured": model is not None,
                    "message": ("Local model ready." if mode == "local" else "Hosted model ready.") if ready else message,
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
        path = urlsplit(self.path).path
        if path not in ("/api/plan", "/api/hosted"):
            self.error(404, "not_found", "This endpoint does not exist.")
            return
        if self.headers.get("Origin") not in self.server.origins:
            self.error(403, "invalid_origin", "Only the local interface may make this request.")
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
        if not 1 <= length <= (4096 if path == "/api/hosted" else MAX_BODY):
            message = "The key setup request is too large." if path == "/api/hosted" else f"Notes and transcripts must fit within {MAX_NOTES:,} characters."
            self.error(413, "body_too_large", message)
            return
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("Incomplete body")
            document = json.loads(raw)
        except (ValueError, UnicodeDecodeError, RecursionError, TimeoutError):
            self.error(400, "invalid_json", "The request could not be read. Please try again.")
            return
        if path == "/api/hosted":
            self.configure_hosted(document)
            return
        mode = document.get("mode", "local") if isinstance(document, dict) else "local"
        if not isinstance(mode, str) or mode not in ("local", "hosted"):
            self.error(400, "invalid_mode", "Choose local or hosted processing.")
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
            model = self.server.model if mode == "local" else self.server.hosted_model
            if model is None:
                self.error(503, "hosted_not_configured", "Add a Groq API key before using hosted processing.")
                return
            content = model.propose(notes)
            tasks, rejected = validate_proposals(notes, parse_proposals(content))
            self.json_reply(200, {
                "tasks": tasks, "rejected_count": rejected, "model": model.label, "mode": mode,
                "input_kind": "transcript" if parse_turns(notes) else "notes",
            })
        except ModelTimeout:
            self.error(504, "model_timeout", "The selected model took too long to finish. Wait a moment, then try again.")
        except ModelAuthentication as exc:
            self.error(503, "hosted_authentication", "Groq rejected the API key or model permissions. Check hosted setup.", exc.details)
        except ModelRateLimit as exc:
            self.error(429, "hosted_rate_limit", "Groq has limited this request. Check your account usage and try later.", exc.details)
        except ModelInputLimit as exc:
            self.error(413, "hosted_input_limit", "Groq rejected this full input as too large. Check the provider request limits; your text has not been shortened.", exc.details)
        except ModelRequestRejected as exc:
            self.error(502, "hosted_request_rejected", "Groq rejected the input or request settings. Check the app configuration before retrying.", exc.details)
        except HostedHTTPError as exc:
            self.error(503, "model_unavailable", "Groq rejected the request. Check its status and your account limits.", exc.details)
        except ModelUnavailable:
            self.error(503, "model_unavailable", "The selected model is unavailable. Check its status and try again.")
        except ModelOutputLimit:
            self.error(502, "model_output_limit", "The model reached its output limit before finishing the draft. Please try again.")
        except ModelEmptyResponse:
            self.error(502, "model_empty_response", "The model finished without returning a draft. Please try again.")
        except (ModelInvalidJSON, InvalidModelOutput):
            self.error(502, "invalid_model_json", "The model returned a draft in an unreadable format. Please try again.")
        except ModelResponseError:
            self.error(502, "invalid_model_output", "The model returned an incomplete or invalid response. Please try again.")
        finally:
            self.server.inference.release()

    def configure_hosted(self, document):
        key = document.get("api_key") if isinstance(document, dict) else None
        if not isinstance(key, str):
            self.error(400, "invalid_key", "Enter a valid API key.")
            return
        try:
            model = HostedModel(key) if key else None
        except ValueError:
            self.error(400, "invalid_key", "Enter a valid API key without spaces.")
            return
        if not self.server.inference.acquire(blocking=False):
            self.error(429, "busy", "Processing is still active. Wait before changing hosted setup.")
            return
        try:
            self.server.hosted_model = model
            self.json_reply(200, {"configured": model is not None})
        finally:
            self.server.inference.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=62140)
    parser.add_argument("--model-base-url", default="http://127.0.0.1:62141/v1")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--model-label", help="Display name for the model you actually started.")
    parser.add_argument("--hosted-groq", action="store_true", help="Load GROQ_API_KEY from the process environment; requests still default to local.")
    args = parser.parse_args()
    model = LocalModel(args.model_base_url, args.model, label=args.model_label)
    hosted_model = None
    if args.hosted_groq:
        try:
            hosted_model = HostedModel(os.environ.get("GROQ_API_KEY", ""))
        except ValueError:
            parser.error("--hosted-groq requires a valid GROQ_API_KEY in the process environment.")
    server = AppServer(("127.0.0.1", args.port), model, hosted_model)
    print(f"Loose Ends: http://127.0.0.1:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
