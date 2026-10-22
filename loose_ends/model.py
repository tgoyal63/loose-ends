"""A bounded, loopback-only OpenAI-compatible client. No credentials are needed."""

from __future__ import annotations

import json
import math
import socket
import threading
import time
from contextlib import contextmanager
from http.client import HTTPConnection, HTTPException
from urllib.parse import urlsplit

from .extraction import SYSTEM_PROMPT, InvalidModelOutput, parse_proposals
from .transcript import TRANSCRIPT_PROMPT, parse_turns

MAX_RESPONSE = 512_000
MAX_STREAM_BYTES = 4_000_000
MAX_STREAM_LINE = 64_000
MAX_STREAM_EVENT = 128_000
MAX_STREAM_EVENTS = 12_000
FORMAT_REMINDER = (
    'Return only the complete JSON object {"tasks": [...]} required above. '
    'Do not add explanations. If there are no qualifying actions, return {"tasks": []}. '
    "Keep the same source, extraction rules and provenance requirements."
)


class ModelUnavailable(RuntimeError):
    pass


class ModelResponseError(RuntimeError):
    pass


class ModelTimeout(ModelUnavailable):
    pass


class ModelOutputLimit(ModelResponseError):
    pass


class ModelEmptyResponse(ModelResponseError):
    pass


class ModelInvalidJSON(ModelResponseError):
    pass


def _positive_timeout(value: float) -> float:
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Model timeout must be positive and finite.")
    return value


def _read_stream(response) -> str:
    """Assemble bounded SSE data; accept only a completed single choice."""
    raw_size = event_size = event_count = content_size = 0
    data_lines = []
    fragments = []
    finished = False
    while True:
        line = response.readline(MAX_STREAM_LINE + 1)
        raw_size += len(line)
        event_size += len(line)
        if len(line) > MAX_STREAM_LINE or event_size > MAX_STREAM_EVENT or raw_size > MAX_STREAM_BYTES:
            raise ModelResponseError("The local model stream exceeded the size limit.")
        if not line or not line.endswith(b"\n"):
            raise ModelResponseError("The local model stream ended before completion.")
        line = line.rstrip(b"\r\n")
        if line:
            if line.startswith(b"data:"):
                value = line[5:]
                data_lines.append(value[1:] if value.startswith(b" ") else value)
            elif line.startswith(b":") or line.startswith((b"event:", b"id:", b"retry:")):
                continue
            else:
                raise ModelResponseError("The local model returned an invalid stream event.")
            continue
        event_size = 0
        if not data_lines:
            continue
        event_count += 1
        if event_count > MAX_STREAM_EVENTS:
            raise ModelResponseError("The local model stream exceeded the event limit.")
        data = b"\n".join(data_lines)
        data_lines = []
        if data == b"[DONE]":
            if not finished:
                raise ModelResponseError("The local model stream has no completed response.")
            content = "".join(fragments)
            if not content.strip():
                raise ModelEmptyResponse("The local model returned empty text.")
            return content
        if finished:
            raise ModelResponseError("The local model returned data after completion.")
        try:
            packet = json.loads(data)
            choices = packet["choices"]
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError
            choice = choices[0]
            if not isinstance(choice, dict) or choice.get("index") != 0:
                raise ValueError
            delta = choice["delta"]
            if not isinstance(delta, dict) or delta.get("tool_calls") or delta.get("refusal"):
                raise ValueError
            content = delta.get("content")
            if content is not None:
                if not isinstance(content, str):
                    raise ValueError
                content_size += len(content.encode("utf-8"))
                if content_size > MAX_RESPONSE:
                    raise ModelResponseError("The local model text exceeded the size limit.")
                fragments.append(content)
            reason = choice["finish_reason"]
            if reason == "length":
                raise ModelOutputLimit("The model reached its output limit.")
            if reason is not None:
                if reason != "stop":
                    raise ValueError
                finished = True
        except (KeyError, TypeError, ValueError, RecursionError) as exc:
            raise ModelResponseError("The local model returned an invalid stream event.") from exc


class LocalModel:
    def __init__(self, base_url: str, model: str, timeout: float = 150, label: str | None = None):
        parsed = urlsplit(base_url)
        if (
            any(ord(char) <= 32 for char in base_url)
            or parsed.scheme != "http"
            or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path.rstrip("/") != "/v1"
        ):
            raise ValueError("Model URL must be an HTTP loopback address ending in /v1.")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.label = label or model
        self.timeout = _positive_timeout(timeout)
        # Pin localhost to loopback rather than consulting DNS or proxy settings.
        self.host = "127.0.0.1" if parsed.hostname == "localhost" else parsed.hostname
        self.port = parsed.port or 80

    @contextmanager
    def _response(self, path: str, body: dict | None, timeout: float | None, accept: str):
        if not path.startswith("/") or path.startswith("//") or any(char in path for char in "\r\n?#"):
            raise ValueError("Model request path must be a plain relative path.")
        duration = _positive_timeout(self.timeout if timeout is None else timeout)
        deadline = time.monotonic() + duration
        connection = HTTPConnection(self.host, self.port, timeout=duration)
        expired = threading.Event()
        active_socket = None
        response = None

        def interrupt():
            expired.set()
            # HTTPConnection may detach its socket after close-delimited headers.
            # Retain that same socket so the deadline also interrupts body reads.
            current_socket = active_socket or connection.sock
            if current_socket is not None:
                try:
                    current_socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

        watchdog = threading.Timer(duration, interrupt)
        watchdog.daemon = True
        payload = None if body is None else json.dumps(body).encode("utf-8")
        watchdog.start()
        try:
            connection.connect()
            active_socket = connection.sock
            if expired.is_set() or time.monotonic() >= deadline:
                raise ModelTimeout("The local model exceeded the request deadline.")
            connection.request(
                "GET" if body is None else "POST",
                "/v1" + path,
                body=payload,
                headers={"Content-Type": "application/json", "Accept": accept},
            )
            response = connection.getresponse()
            if not 200 <= response.status < 300:
                # Never follow redirects or include upstream error bodies in errors.
                raise ModelUnavailable("The local model service rejected the request.")
            yield response
            if expired.is_set() or time.monotonic() >= deadline:
                raise ModelTimeout("The local model exceeded the request deadline.")
        except (OSError, HTTPException, ModelResponseError, ModelUnavailable) as exc:
            if expired.is_set() or time.monotonic() >= deadline or isinstance(exc, TimeoutError):
                raise ModelTimeout("The local model exceeded the request deadline.") from exc
            if isinstance(exc, (ModelResponseError, ModelUnavailable)):
                raise
            raise ModelUnavailable("The local model connection was interrupted.") from exc
        finally:
            watchdog.cancel()
            if response is not None:
                response.close()
            connection.close()

    def request(self, path: str, body: dict | None = None, timeout: float | None = None) -> dict:
        with self._response(path, body, timeout, "application/json") as response:
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ModelResponseError("The local model response exceeded the size limit.")
        try:
            result = json.loads(raw)
        except (ValueError, RecursionError) as exc:
            raise ModelResponseError("The local model returned an invalid response.") from exc
        if not isinstance(result, dict):
            raise ModelResponseError("The local model returned an invalid response.")
        return result

    def _stream_completion(self, body: dict, timeout: float) -> str:
        with self._response("/chat/completions", body, timeout, "text/event-stream") as response:
            if response.headers.get_content_type() != "text/event-stream":
                raise ModelResponseError("The local model did not return a stream.")
            return _read_stream(response)

    def ready(self) -> bool:
        result = self.request("/models", timeout=3)
        models = result.get("data")
        return isinstance(models, list) and any(
            isinstance(item, dict) and item.get("id") == self.model for item in models
        )

    def propose(self, notes: str) -> str:
        deadline = time.monotonic() + self.timeout
        turns = parse_turns(notes)
        source = {"notes": notes}
        if turns:
            # Keep explicit field names: small models can confuse positional
            # rows with the output schema. Include every turn and preamble.
            source = {"preamble": notes[:turns[0].start], "turns": [turn.for_model() for turn in turns]}
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": TRANSCRIPT_PROMPT if turns else SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(source, ensure_ascii=False, separators=(",", ":"))},
            ],
            "temperature": 0,
            "max_tokens": 4800 if turns else 2400,
            "stream": True,
        }
        for attempt in range(2):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ModelTimeout("The local model exceeded the request deadline.")
            try:
                content = self._stream_completion(body, remaining)
                try:
                    parse_proposals(content)
                except InvalidModelOutput as exc:
                    raise ModelInvalidJSON("The local model did not return a complete action document.") from exc
                return content
            except (ModelEmptyResponse, ModelInvalidJSON):
                if attempt:
                    raise
                # Retry only a completed malformed/empty document. Preserve the
                # entire source and rules, with no generated text fed back in.
                body["messages"][0]["content"] += "\n\n" + FORMAT_REMINDER
