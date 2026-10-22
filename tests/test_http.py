import http.client
import json
import threading
import unittest
from unittest.mock import patch

from loose_ends.model import (
    ModelEmptyResponse, ModelInvalidJSON, ModelOutputLimit, ModelResponseError, ModelTimeout, ModelUnavailable,
)
from loose_ends.extraction import MAX_NOTES
from loose_ends.hosted import HostedHTTPError, ModelAuthentication, ModelInputLimit, ModelRateLimit, ModelRequestRejected
from server import AppServer, MAX_BODY


class FakeModel:
    model = "test-model"
    label = "Synthetic test model"

    def __init__(self):
        self.output = '{"tasks":[]}'
        self.available = True
        self.fail = False
        self.calls = 0

    def ready(self):
        return self.available

    def propose(self, notes):
        self.calls += 1
        if self.fail:
            raise ModelUnavailable()
        return self.output


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = FakeModel()
        cls.server = AppServer(("127.0.0.1", 0), cls.model)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        self.server.hosted_model = None
        self.model.output = '{"tasks":[]}'
        self.model.available = True
        self.model.fail = False
        self.model.calls = 0

    def request(self, path="/api/plan", body=None, headers=None, method="POST"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        default_headers = {
            "Origin": f"http://127.0.0.1:{self.port}",
            "Content-Type": "application/json",
        }
        default_headers.update(headers or {})
        data = json.dumps({"notes": "Send the draft."} if body is None else body).encode()
        conn.request(method, path, body=data if method == "POST" else None, headers=default_headers)
        response = conn.getresponse()
        status, result, response_headers = response.status, response.read(), dict(response.getheaders())
        conn.close()
        return status, result, response_headers

    def test_success_returns_only_verified_tasks(self):
        note = "Priya will send the draft on Friday."
        self.model.output = json.dumps({"tasks": [
            {"title": "send the draft", "quote": note, "owner": "Priya", "due": "Friday", "condition": None},
            {"title": "charge the customer", "quote": note},
        ]})
        status, data, headers = self.request(body={"notes": note})
        result = json.loads(data)
        self.assertEqual(status, 200)
        self.assertEqual(len(result["tasks"]), 1)
        self.assertEqual(result["rejected_count"], 1)
        self.assertEqual(result["input_kind"], "notes")
        self.assertNotIn("source", result["tasks"][0])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_foreign_origin_never_reaches_model(self):
        status, _, _ = self.request(headers={"Origin": "https://attacker.example"})
        self.assertEqual(status, 403)
        self.assertEqual(self.model.calls, 0)

    def test_absent_origin_is_rejected(self):
        status, _, _ = self.request(headers={"Origin": ""})
        self.assertEqual(status, 403)

    def test_rebinding_host_is_rejected(self):
        status, _, _ = self.request(headers={"Host": f"attacker.example:{self.port}"})
        self.assertEqual(status, 403)
        self.assertEqual(self.model.calls, 0)

    def test_form_posts_are_rejected(self):
        status, _, _ = self.request(headers={"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(status, 415)
        self.assertEqual(self.model.calls, 0)

    def test_note_validation(self):
        for body in [{"notes": ""}, {"notes": " "}, {"notes": []}, {"notes": "x" * (MAX_NOTES + 1)}, [], {}]:
            with self.subTest(body=str(body)[:40]):
                self.assertEqual(self.request(body=body)[0], 400)
        self.assertEqual(self.model.calls, 0)

    def test_unpaired_unicode_note_is_a_client_error(self):
        status, _, _ = self.request(body={"notes": "Send the draft.\ud800"})
        self.assertEqual(status, 400)
        self.assertEqual(self.model.calls, 0)

    def test_request_body_size_limit(self):
        # The server rejects the advertised length before reading an oversized
        # body. Send headers only to avoid a client-side broken-pipe race.
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            conn.putrequest("POST", "/api/plan")
            conn.putheader("Origin", f"http://127.0.0.1:{self.port}")
            conn.putheader("Content-Type", "application/json")
            conn.putheader("Content-Length", str(MAX_BODY + 1))
            conn.endheaders()
            response = conn.getresponse()
            self.assertEqual(response.status, 413)
            self.assertIn("60,000", json.loads(response.read())["error"]["message"])
            self.assertEqual(self.model.calls, 0)
        finally:
            conn.close()

    def test_full_unicode_character_limit_is_accepted_without_truncation(self):
        for character in ("a", "é", "😀"):
            with self.subTest(character=character):
                status, data, _ = self.request(body={"notes": character * MAX_NOTES})
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(data)["tasks"], [])
        self.assertEqual(self.model.calls, 3)

    def test_transcript_contract_has_exact_source_and_attribution(self):
        note = "Mira Shah 09:10:00\nI will\nsend the sample on Friday."
        self.model.output = json.dumps({"tasks": [{
            "turn_id": "turn-1", "title": "send the sample", "owner": "Mira Shah",
            "due": "Friday", "condition": None,
        }]})
        status, data, _ = self.request(body={"notes": note})
        result = json.loads(data)
        self.assertEqual(status, 200)
        self.assertEqual(result["input_kind"], "transcript")
        self.assertEqual(result["tasks"][0]["quote"], note)
        self.assertEqual(result["tasks"][0]["source"], {
            "speaker": "Mira Shah", "timestamp": "09:10:00", "context": note,
        })

    def test_long_transcript_reaches_model_without_old_twelve_thousand_limit(self):
        note = "Mira Shah 09:10:00\n" + "Background discussion. " * 800 + "\nI will send the sample."
        self.assertGreater(len(note), 12_000)
        self.assertEqual(self.request(body={"notes": note})[0], 200)
        self.assertEqual(self.model.calls, 1)

    def test_inference_busy_is_explicit(self):
        self.server.inference.acquire()
        try:
            self.assertEqual(self.request()[0], 429)
            self.assertEqual(self.model.calls, 0)
        finally:
            self.server.inference.release()

    def test_invalid_model_json_is_an_error(self):
        self.model.output = '{"tasks":'
        status, data, _ = self.request()
        self.assertEqual(status, 502)
        self.assertEqual(json.loads(data)["error"]["code"], "invalid_model_json")
        self.assertEqual(self.request()[0], 502)  # semaphore released after the first error

    def test_generation_failures_have_specific_safe_errors_and_release_inference(self):
        cases = [
            (ModelTimeout, 504, "model_timeout"),
            (ModelOutputLimit, 502, "model_output_limit"),
            (ModelEmptyResponse, 502, "model_empty_response"),
            (ModelInvalidJSON, 502, "invalid_model_json"),
            (ModelResponseError, 502, "invalid_model_output"),
            (ModelUnavailable, 503, "model_unavailable"),
        ]
        for error_type, expected_status, expected_code in cases:
            with self.subTest(error=error_type.__name__):
                with patch.object(self.model, "propose", side_effect=error_type("PRIVATE UPSTREAM CONTENT")):
                    status, data, _ = self.request()
                error = json.loads(data)["error"]
                self.assertEqual(status, expected_status)
                self.assertEqual(error["code"], expected_code)
                self.assertNotIn("PRIVATE UPSTREAM CONTENT", data.decode())
                self.assertNotIn("shorter note", error["message"])
                self.assertEqual(self.request()[0], 200)

    def test_model_outage_is_not_fake_success(self):
        self.model.fail = True
        status, data, _ = self.request()
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(data)["error"]["code"], "model_unavailable")

    def test_status_reports_availability(self):
        self.model.available = False
        status, data, _ = self.request(path="/api/status", method="GET")
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(data)["ready"])

    def test_hosted_mode_is_explicit_and_never_falls_back(self):
        hosted = FakeModel()
        hosted.label = "Hosted test model"
        self.server.hosted_model = hosted
        self.assertEqual(self.request()[0], 200)
        self.assertEqual(self.model.calls, 1)
        self.assertEqual(hosted.calls, 0)
        status, data, _ = self.request(body={"notes": "Send the draft.", "mode": "hosted"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["model"], hosted.label)
        self.assertEqual(json.loads(data)["mode"], "hosted")
        self.assertEqual(hosted.calls, 1)
        self.model.fail = True
        self.assertEqual(self.request()[0], 503)
        self.assertEqual(hosted.calls, 1)
        hosted.fail = True
        local_calls = self.model.calls
        self.assertEqual(self.request(body={"notes": "Send the draft.", "mode": "hosted"})[0], 503)
        self.assertEqual(self.model.calls, local_calls)

    def test_unconfigured_hosted_request_cannot_use_local_model(self):
        status, data, _ = self.request(body={"notes": "Send the draft.", "mode": "hosted"})
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(data)["error"]["code"], "hosted_not_configured")
        self.assertEqual(self.model.calls, 0)
        status, data, _ = self.request(path="/api/status?mode=hosted", method="GET")
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(data)["configured"])
        self.assertFalse(json.loads(data)["ready"])

    def test_invalid_modes_fail_before_inference(self):
        for mode in (None, [], {}, "", "groq", "LOCAL"):
            with self.subTest(mode=mode):
                self.assertEqual(self.request(body={"notes": "Send the draft.", "mode": mode})[0], 400)
        for query in ("mode=", "mode=unknown", "mode=local&mode=hosted"):
            self.assertEqual(self.request(path="/api/status?" + query, method="GET")[0], 400)
        self.assertEqual(self.model.calls, 0)

    def test_hosted_setup_and_disconnect_do_not_submit_notes_or_return_keys(self):
        key = "synthetic-test-key-never-valid"
        with patch("server.HostedModel") as factory:
            hosted = factory.return_value
            hosted.label = "Hosted test model"
            hosted.ready.return_value = True
            status, data, _ = self.request(path="/api/hosted", body={"api_key": key})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(data), {"configured": True})
            self.assertNotIn(key, data.decode())
            factory.assert_called_once_with(key)
            hosted.ready.assert_not_called()
            hosted.propose.assert_not_called()
            self.assertIs(self.server.hosted_model, hosted)
            status, data, _ = self.request(path="/api/status?mode=hosted", method="GET")
            self.assertEqual(status, 200)
            self.assertNotIn(key, data.decode())
            self.assertTrue(json.loads(data)["ready"])
            status, data, _ = self.request(path="/api/hosted", body={"api_key": ""})
            self.assertEqual(status, 200)
            self.assertIsNone(self.server.hosted_model)
            self.assertEqual(json.loads(data), {"configured": False})
        self.assertEqual(self.model.calls, 0)

    def test_hosted_setup_rejects_foreign_origin_host_and_form_posts(self):
        for headers in ({"Origin": "https://other.example"}, {"Host": "other.example"},
                        {"Origin": ""}, {"Content-Type": "application/x-www-form-urlencoded"}):
            with self.subTest(headers=headers), patch("server.HostedModel") as factory:
                self.assertIn(self.request(path="/api/hosted", body={"api_key": "synthetic-test-key-never-valid"}, headers=headers)[0], (403, 415))
                factory.assert_not_called()
        self.assertIsNone(self.server.hosted_model)

    def test_hosted_setup_validation_preserves_previous_configuration(self):
        previous = FakeModel()
        self.server.hosted_model = previous
        for key in (None, [], "short", "x" * 513, "x" * 24 + "\r\n", "x" * 24 + "\ud800"):
            with self.subTest(key=repr(key)[:30]):
                self.assertEqual(self.request(path="/api/hosted", body={"api_key": key})[0], 400)
                self.assertIs(self.server.hosted_model, previous)

    def test_hosted_setup_cannot_change_configuration_while_processing(self):
        previous = FakeModel()
        self.server.hosted_model = previous
        self.server.inference.acquire()
        try:
            self.assertEqual(self.request(path="/api/hosted", body={"api_key": ""})[0], 429)
            self.assertIs(self.server.hosted_model, previous)
        finally:
            self.server.inference.release()

    def test_hosted_setup_body_limit_preserves_configuration(self):
        previous = FakeModel()
        self.server.hosted_model = previous
        status, data, _ = self.request(path="/api/hosted", body={"api_key": "x" * 4100})
        self.assertEqual(status, 413)
        self.assertEqual(json.loads(data)["error"]["code"], "body_too_large")
        self.assertIs(self.server.hosted_model, previous)

    def test_hosted_output_still_requires_exact_source_provenance(self):
        hosted = FakeModel()
        self.server.hosted_model = hosted
        notes = "Mira Shah 09:10:00\nOnce access works, I will send the sample on Friday."
        hosted.output = json.dumps({"tasks": [
            {"turn_id": "turn-1", "title": "send the sample", "owner": "Mira Shah", "due": "Friday"},
            {"turn_id": "turn-1", "title": "charge the customer", "owner": "Mira Shah", "due": "Friday"},
            {"turn_id": "turn-99", "title": "send the sample", "owner": "Mira Shah", "due": "Friday"},
        ]})
        status, data, _ = self.request(body={"notes": notes, "mode": "hosted"})
        result = json.loads(data)
        self.assertEqual(status, 200)
        self.assertEqual(result["rejected_count"], 2)
        self.assertEqual(len(result["tasks"]), 1)
        task = result["tasks"][0]
        self.assertEqual(task["quote"], notes)
        self.assertIn("Once access works", task["condition"])
        self.assertEqual(task["source"]["context"], notes)
        self.assertEqual(self.model.calls, 0)

    def test_hosted_errors_are_specific_and_do_not_expose_upstream_content(self):
        hosted = FakeModel()
        self.server.hosted_model = hosted
        for error, status, code in ((ModelAuthentication, 503, "hosted_authentication"),
                                    (ModelRateLimit, 429, "hosted_rate_limit"),
                                    (ModelInputLimit, 413, "hosted_input_limit"),
                                    (ModelRequestRejected, 502, "hosted_request_rejected"),
                                    (HostedHTTPError, 503, "model_unavailable")):
            with patch.object(hosted, "propose", side_effect=error("PRIVATE CONTENT AND KEY")):
                actual_status, data, _ = self.request(body={"notes": "Send the draft.", "mode": "hosted"})
            self.assertEqual(actual_status, status)
            self.assertEqual(json.loads(data)["error"]["code"], code)
            self.assertNotIn("PRIVATE", data.decode())
            self.assertEqual(self.model.calls, 0)
            self.assertEqual(self.request()[0], 200)
            self.model.calls = 0

    def test_hosted_limit_details_are_safe_and_do_not_replace_the_key(self):
        hosted = FakeModel()
        self.server.hosted_model = hosted
        error = ModelInputLimit("PRIVATE UPSTREAM", status=413, headers={
            "x-ratelimit-limit-tokens": "8000", "retry-after": "PRIVATE", "x-request-id": "PRIVATE",
        })
        with patch.object(hosted, "propose", side_effect=error):
            status, data, _ = self.request(body={"notes": "Send the draft.", "mode": "hosted"})
        self.assertEqual(status, 413)
        result = json.loads(data)["error"]
        self.assertEqual(result["details"], {"provider_status": 413, "tokens_per_minute_limit": 8000})
        self.assertIn("not been shortened", result["message"])
        self.assertNotIn("PRIVATE", data.decode())
        self.assertIs(self.server.hosted_model, hosted)
        self.assertEqual(self.model.calls, 0)

    def test_unknown_files_and_traversal_not_exposed(self):
        for path in ["/server.py", "/.env", "/../server.py", "/%2e%2e/server.py", "/logs/model.log"]:
            with self.subTest(path=path):
                self.assertEqual(self.request(path=path, method="GET")[0], 404)

    def test_api_response_has_security_headers(self):
        _, _, headers = self.request(path="/api/status", method="GET")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")


if __name__ == "__main__":
    unittest.main()
