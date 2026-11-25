"""A small read-only client for Etsy Open API v3.

Only GET requests are possible through this class: it has no method that can change data.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Iterator

from . import USER_AGENT
from .config import API_BASE

MAX_RETRIES = 5
MIN_INTERVAL = 0.25  # at most 4 requests per second
PAGE_SIZE = 100


class AuthorizationRevoked(Exception):
    """Raised when Etsy rejects the token, for example after the owner revokes access."""


class EtsyClient:
    def __init__(self, api_key_header: str, access_token: Callable[[], str], base_url: str = API_BASE,
                 opener: Callable = urllib.request.urlopen, sleep: Callable[[float], None] = time.sleep):
        self._api_key = api_key_header
        self._token = access_token
        self._base = base_url.rstrip("/")
        self._open = opener
        self._sleep = sleep
        self._last = 0.0
        self.request_count = 0

    def get(self, path: str, params: dict | None = None) -> dict:
        query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v is not None}, doseq=True)
        url = f"{self._base}{path}" + (f"?{query}" if query else "")
        for attempt in range(MAX_RETRIES + 1):
            wait = MIN_INTERVAL - (time.monotonic() - self._last)
            if wait > 0:
                self._sleep(wait)
            req = urllib.request.Request(url, method="GET", headers={
                "x-api-key": self._api_key,
                "Authorization": f"Bearer {self._token()}",
                "Accept": "application/json",
                "User-Agent": USER_AGENT,
            })
            self._last = time.monotonic()
            self.request_count += 1
            try:
                with self._open(req, timeout=60) as resp:
                    return json.load(resp)
            except urllib.error.HTTPError as err:
                if err.code in (401, 403):
                    raise AuthorizationRevoked(f"Etsy refused the token (HTTP {err.code}).") from None
                if err.code == 429 or err.code >= 500:
                    if attempt == MAX_RETRIES:
                        raise
                    retry_after = err.headers.get("Retry-After") if err.headers else None
                    self._sleep(float(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt)
                    continue
                raise
        raise RuntimeError("unreachable")

    def paginate(self, path: str, params: dict | None = None) -> Iterator[dict]:
        """Yield every item of a paginated list endpoint (limit/offset)."""
        offset = 0
        while True:
            page = self.get(path, {**(params or {}), "limit": PAGE_SIZE, "offset": offset})
            results = page.get("results", [])
            yield from results
            offset += len(results)
            if not results or offset >= int(page.get("count", 0)):
                return
