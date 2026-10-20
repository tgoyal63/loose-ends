"""A bounded, loopback-only OpenAI-compatible client. No credentials are needed."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .extraction import SYSTEM_PROMPT
from .transcript import TRANSCRIPT_PROMPT, parse_turns

MAX_RESPONSE = 512_000


class ModelUnavailable(RuntimeError):
    pass


class ModelResponseError(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class LocalModel:
    def __init__(self, base_url: str, model: str, timeout: float = 120, label: str | None = None):
        parsed = urlsplit(base_url)
        if (
            parsed.scheme != "http"
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
        self.timeout = timeout
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, path: str, body: dict | None = None, timeout: float | None = None) -> dict:
        payload = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="GET" if body is None else "POST",
        )
        try:
            with self.opener.open(request, timeout=timeout or self.timeout) as response:
                raw = response.read(MAX_RESPONSE + 1)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise ModelUnavailable("The local model service is unavailable or timed out.") from exc
        if len(raw) > MAX_RESPONSE:
            raise ModelResponseError("The local model response exceeded the size limit.")
        try:
            result = json.loads(raw)
        except (ValueError, RecursionError) as exc:
            raise ModelResponseError("The local model returned an invalid response.") from exc
        if not isinstance(result, dict):
            raise ModelResponseError("The local model returned an invalid response.")
        return result

    def ready(self) -> bool:
        result = self.request("/models", timeout=3)
        models = result.get("data")
        return isinstance(models, list) and any(
            isinstance(item, dict) and item.get("id") == self.model for item in models
        )

    def propose(self, notes: str) -> str:
        turns = parse_turns(notes)
        source = {"notes": notes}
        if turns:
            # Preserve any preamble and every original turn in one bounded
            # request. No silent truncation or independent chunk extraction.
            source = {"preamble": notes[:turns[0].start], "turns": [turn.for_model() for turn in turns]}
        result = self.request(
            "/chat/completions",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": TRANSCRIPT_PROMPT if turns else SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(source, ensure_ascii=False)},
                ],
                "temperature": 0,
                "max_tokens": 4800 if turns else 2400,
                "stream": False,
            },
        )
        try:
            choice = result["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelResponseError("The local model response has no generated text.") from exc
        if choice.get("finish_reason") == "length":
            raise ModelResponseError("The model reached its output limit. Try a shorter note.")
        if not isinstance(content, str) or not content.strip():
            raise ModelResponseError("The local model returned empty text.")
        return content
