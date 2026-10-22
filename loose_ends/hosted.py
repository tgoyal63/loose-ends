"""Explicit, optional Groq inference. Credentials remain in server memory."""

from __future__ import annotations

import json
import socket
import threading
import time
from http.client import HTTPSConnection, HTTPException

from .extraction import SYSTEM_PROMPT, InvalidModelOutput, parse_proposals
from .model import (
    MAX_RESPONSE, ModelEmptyResponse, ModelInvalidJSON, ModelOutputLimit,
    ModelResponseError, ModelTimeout, ModelUnavailable, _positive_timeout,
)
from .transcript import TRANSCRIPT_PROMPT, parse_turns

HOSTED_MODEL = "openai/gpt-oss-120b"
HOSTED_LABEL = "GPT-OSS 120B · Groq"
HOSTED_TRANSCRIPT_PROMPT = TRANSCRIPT_PROMPT + """
Input format: turns is an ordered object. Each key is a turn ID; each value is
an unmodified source block starting with the original speaker and timestamp.
The examples above illustrate a turn's fields; the actual input supplies its
original transcript text. Read every block, including the final discussion.
Before returning JSON, internally inventory every distinct explicit commitment
in chronological order, including multiple work items from the same speaker.
Reconcile later updates with the SPECIFIC action and object they concern.
Completing or cancelling one item does not resolve other items by that person.
An unmet prerequisite or a statement that an item must wait does not cancel it.
Keep those conditional commitments, with no invented deadline. A missing mention
in the closing recap does not cancel an earlier promise. Check that each
inventoried commitment is either represented or excluded for supported reasons
about that same work item. Return only the requested tasks JSON, not the inventory
or explanations.
"""
# A system resolver may ignore socket timeouts. Bound stranded setup threads
# as well as callers' waiting time; none of these workers sends HTTP data.
_CONNECT_SLOTS = threading.BoundedSemaphore(4)
_MAX_ERROR_RESPONSE = 65_536
_ERROR_CODES = frozenset({
    "json_validate_failed", "context_length_exceeded", "rate_limit_exceeded",
    "invalid_request_error", "invalid_value", "model_not_found",
})


def _error_metadata(response) -> dict:
    """Best-effort classification; never retain or reflect arbitrary provider text."""
    try:
        raw = response.read(_MAX_ERROR_RESPONSE + 1)
        if len(raw) > _MAX_ERROR_RESPONSE:
            return {}
        document = json.loads(raw)
    except (OSError, HTTPException, ValueError, RecursionError):
        return {}
    error = document.get("error") if isinstance(document, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    if isinstance(code, str) and code in _ERROR_CODES:
        return {"provider_code": code}
    return {}


class HostedHTTPError(ModelUnavailable):
    def __init__(self, message="Groq rejected the request.", *, status=None, headers=None):
        super().__init__(message)
        self.details = {}
        if isinstance(status, int) and 100 <= status <= 599:
            self.details["provider_status"] = status
        # Allow only numeric operational headers. Never reflect arbitrary
        # headers, request identifiers, organization identifiers or keys.
        for header, field in (
            ("x-ratelimit-limit-tokens", "tokens_per_minute_limit"),
            ("x-ratelimit-remaining-tokens", "remaining_tokens"),
            ("retry-after", "retry_after_seconds"),
        ):
            value = headers.get(header) if headers is not None else None
            if isinstance(value, str) and 1 <= len(value) <= 12 and value.isascii() and value.isdigit():
                self.details[field] = int(value)


class ModelAuthentication(HostedHTTPError):
    pass


class ModelRateLimit(HostedHTTPError):
    pass


class ModelInputLimit(HostedHTTPError):
    pass


class ModelRequestRejected(HostedHTTPError):
    pass


def _connect_before_deadline(connection, deadline: float):
    if not _CONNECT_SLOTS.acquire(blocking=False):
        raise ModelUnavailable("Hosted connection setup is busy. Try later.")
    complete = threading.Event()
    abandoned = threading.Event()
    errors = []

    def connect():
        try:
            # Only DNS, TCP and TLS. Authorization and source text are sent by
            # the caller, after this worker completes within the deadline.
            connection.connect()
        except Exception as exc:
            errors.append(exc)
        finally:
            try:
                if abandoned.is_set() or time.monotonic() >= deadline:
                    connection.close()
            finally:
                _CONNECT_SLOTS.release()
                complete.set()

    worker = threading.Thread(target=connect, daemon=True)
    try:
        worker.start()
    except RuntimeError:
        _CONNECT_SLOTS.release()
        raise ModelUnavailable("Hosted connection setup could not start.") from None
    if not complete.wait(max(0, deadline - time.monotonic())):
        abandoned.set()
        raise ModelTimeout("The hosted connection exceeded its deadline.")
    if time.monotonic() >= deadline:
        raise ModelTimeout("The hosted connection exceeded its deadline.")
    if errors:
        raise errors[0]


def action_schema(transcript: bool) -> dict:
    nullable = {"type": ["string", "null"]}
    properties = {
        "title": {"type": "string"},
        "owner": nullable,
        "due": nullable,
    }
    if transcript:
        properties["turn_id"] = {"type": "string"}
    else:
        properties.update(quote={"type": "string"}, condition=nullable)
    return {
        "type": "object",
        "properties": {"tasks": {"type": "array", "items": {
            "type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False,
        }}},
        "required": ["tasks"], "additionalProperties": False,
    }


class HostedModel:
    model = HOSTED_MODEL
    label = HOSTED_LABEL

    def __init__(self, api_key: str, timeout: float = 150):
        if not isinstance(api_key, str) or not 20 <= len(api_key) <= 512 or any(
            not 33 <= ord(character) <= 126 for character in api_key
        ):
            raise ValueError("Enter a valid API key without spaces.")
        self._api_key = api_key
        self.timeout = _positive_timeout(timeout)

    def request(self, path: str, body: dict | None = None, timeout: float | None = None) -> dict:
        # No configurable destinations, redirects, proxy handling or key-bearing URLs.
        if path not in ("/models", "/chat/completions"):
            raise ValueError("Unsupported hosted endpoint.")
        duration = _positive_timeout(self.timeout if timeout is None else timeout)
        deadline = time.monotonic() + duration
        connection = HTTPSConnection("api.groq.com", 443, timeout=duration)
        expired = threading.Event()
        active_socket = None
        response = None

        def interrupt():
            expired.set()
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
            _connect_before_deadline(connection, deadline)
            active_socket = connection.sock
            if expired.is_set() or time.monotonic() >= deadline:
                raise ModelTimeout()
            connection.request(
                "GET" if body is None else "POST", "/openai/v1" + path,
                body=payload, headers={
                    "Content-Type": "application/json", "Accept": "application/json",
                    "Authorization": "Bearer " + self._api_key,
                },
            )
            response = connection.getresponse()
            if response.status in (401, 403):
                raise ModelAuthentication("Check the Groq API key and model permissions.", status=response.status, headers=response.headers)
            if response.status == 429:
                raise ModelRateLimit("Groq has limited this request. Check your usage and try later.", status=response.status, headers=response.headers)
            if response.status == 413:
                raise ModelInputLimit("This request exceeds Groq's size limit.", status=response.status, headers=response.headers)
            if response.status in (400, 422):
                error = ModelRequestRejected("Groq rejected the input or request settings.", status=response.status, headers=response.headers)
                # These failures can describe settings or failed generation.
                # A short timer bounds this optional diagnostic read separately
                # from the absolute request deadline. Closing the socket is safe:
                # this error response will never be reused for inference.
                diagnostic_timer = threading.Timer(min(3.0, max(0, deadline - time.monotonic())), interrupt)
                diagnostic_timer.daemon = True
                diagnostic_timer.start()
                try:
                    error.details.update(_error_metadata(response))
                finally:
                    diagnostic_timer.cancel()
                raise error
            if not 200 <= response.status < 300:
                # Error bodies may contain submitted text. Never read or reflect them.
                raise HostedHTTPError(status=response.status, headers=response.headers)
            raw = response.read(MAX_RESPONSE + 1)
            if expired.is_set() or time.monotonic() >= deadline:
                raise ModelTimeout()
            if len(raw) > MAX_RESPONSE:
                raise ModelResponseError("The hosted response exceeded the size limit.")
            try:
                result = json.loads(raw)
            except (ValueError, RecursionError) as exc:
                raise ModelResponseError("The hosted response was invalid.") from exc
            if not isinstance(result, dict):
                raise ModelResponseError("The hosted response was invalid.")
            return result
        except (OSError, HTTPException, ModelUnavailable, ModelResponseError) as exc:
            if isinstance(exc, HostedHTTPError):
                # Once an HTTP error is known, an optional diagnostic read must
                # not replace it with a generic connection or timeout error.
                raise
            if expired.is_set() or time.monotonic() >= deadline or isinstance(exc, TimeoutError):
                raise ModelTimeout("The hosted request exceeded its deadline.") from exc
            if isinstance(exc, (ModelUnavailable, ModelResponseError)):
                raise
            raise ModelUnavailable("The hosted connection was interrupted.") from exc
        finally:
            watchdog.cancel()
            if response is not None:
                response.close()
            connection.close()

    def ready(self) -> bool:
        result = self.request("/models", timeout=8)
        models = result.get("data")
        return isinstance(models, list) and any(
            isinstance(item, dict) and item.get("id") == self.model for item in models
        )

    def propose(self, notes: str) -> str:
        turns = parse_turns(notes)
        source = {"notes": notes}
        if turns:
            # Preserve all characters, including separators and empty-header
            # gaps, while avoiding repeated field names and duplicated headers.
            # Existing parsed IDs and validation/source attachment stay intact.
            source = {"preamble": notes[:turns[0].start], "turns": {
                turn.id: notes[turn.start:turns[index + 1].start if index + 1 < len(turns) else len(notes)]
                for index, turn in enumerate(turns)
            }}
        result = self.request("/chat/completions", {
            "model": self.model,
            "messages": [
                {"role": "system", "content": HOSTED_TRANSCRIPT_PROMPT if turns else SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(source, ensure_ascii=False, separators=(",", ":"))},
            ],
            "temperature": 1.0, "top_p": 1.0,
            "reasoning_effort": "high", "include_reasoning": False,
            "max_completion_tokens": 16384, "stream": False,
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "action_drafts", "strict": True, "schema": action_schema(bool(turns)),
            }},
        })
        try:
            choices = result["choices"]
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError
            choice = choices[0]
            if choice.get("index") != 0:
                raise ValueError
            if choice.get("finish_reason") == "length":
                raise ModelOutputLimit("The hosted model reached its output limit.")
            if choice.get("finish_reason") != "stop":
                raise ValueError
            message = choice["message"]
            if message.get("tool_calls") or message.get("refusal"):
                raise ValueError
            content = message["content"]
            if not isinstance(content, str):
                raise ValueError
        except (KeyError, AttributeError, TypeError, ValueError) as exc:
            raise ModelResponseError("The hosted model returned an incomplete or invalid response.") from exc
        if not content.strip():
            raise ModelEmptyResponse("The hosted model returned empty text.")
        try:
            parse_proposals(content)
        except InvalidModelOutput as exc:
            raise ModelInvalidJSON("The hosted model returned an unreadable draft.") from exc
        # No automatic paid retries, no local/cloud fallback, no source truncation.
        return content
