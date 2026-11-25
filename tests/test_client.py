"""The client must only ever send GET requests, paginate, and back off on rate limits."""
import io
import json
import unittest
import urllib.error

from etsy_profit.client import AuthorizationRevoked, EtsyClient


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class ClientTest(unittest.TestCase):
    def make(self, responses):
        self.requests = []

        def opener(req, timeout):
            self.requests.append(req)
            r = responses.pop(0)
            if isinstance(r, Exception):
                raise r
            return FakeResponse(json.dumps(r).encode())

        return EtsyClient("key:secret", lambda: "token", opener=opener, sleep=lambda s: None)

    def test_only_get_requests(self):
        c = self.make([{"count": 1, "results": [{"id": 1}]}])
        list(c.paginate("/shops/1/receipts"))
        self.assertTrue(all(r.get_method() == "GET" for r in self.requests))
        self.assertEqual(self.requests[0].get_header("X-api-key"), "key:secret")

    def test_pagination(self):
        c = self.make([{"count": 150, "results": [{"i": i} for i in range(100)]},
                       {"count": 150, "results": [{"i": i} for i in range(100, 150)]}])
        self.assertEqual(len(list(c.paginate("/x"))), 150)
        self.assertIn("offset=100", self.requests[1].full_url)

    def test_rate_limit_retry(self):
        err = urllib.error.HTTPError("u", 429, "Too Many", {"Retry-After": "1"}, None)
        c = self.make([err, {"ok": True}])
        self.assertEqual(c.get("/x"), {"ok": True})
        self.assertEqual(len(self.requests), 2)

    def test_revoked_token(self):
        err = urllib.error.HTTPError("u", 401, "Unauthorized", {}, None)
        c = self.make([err])
        with self.assertRaises(AuthorizationRevoked):
            c.get("/x")


if __name__ == "__main__":
    unittest.main()
