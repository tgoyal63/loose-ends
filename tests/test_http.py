import http.client
import json
import threading
import unittest

from loose_ends.model import ModelUnavailable
from server import AppServer


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
        for body in [{"notes": ""}, {"notes": " "}, {"notes": []}, {"notes": "x" * 12001}, [], {}]:
            with self.subTest(body=str(body)[:40]):
                self.assertEqual(self.request(body=body)[0], 400)
        self.assertEqual(self.model.calls, 0)

    def test_unpaired_unicode_note_is_a_client_error(self):
        status, _, _ = self.request(body={"notes": "Send the draft.\ud800"})
        self.assertEqual(status, 400)
        self.assertEqual(self.model.calls, 0)

    def test_request_body_size_limit(self):
        self.assertEqual(self.request(body={"notes": "x" * 70000})[0], 413)

    def test_inference_busy_is_explicit(self):
        self.server.inference.acquire()
        try:
            self.assertEqual(self.request()[0], 429)
            self.assertEqual(self.model.calls, 0)
        finally:
            self.server.inference.release()

    def test_invalid_model_json_is_an_error(self):
        self.model.output = '{"tasks":'
        self.assertEqual(self.request()[0], 502)
        self.assertEqual(self.request()[0], 502)  # semaphore released after the first error

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
