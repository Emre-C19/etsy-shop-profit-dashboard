"""OAuth 2.0 authorization-code flow with PKCE, as Etsy Open API v3 requires.

Only the shop owner authorizes the app, and only read-only scopes are requested.
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import json
import secrets
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

from . import USER_AGENT
from .config import AUTH_URL, SCOPES, TOKEN_URL, Settings


def make_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) using S256."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def authorization_url(settings: Settings, state: str, challenge: str) -> str:
    query = {
        "response_type": "code",
        "client_id": settings.keystring,
        "redirect_uri": settings.redirect_uri,
        "scope": " ".join(SCOPES),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(query, quote_via=urllib.parse.quote)}"


def _post_token(form: dict[str, str]) -> dict:
    req = urllib.request.Request(
        TOKEN_URL,
        data=urllib.parse.urlencode(form).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": USER_AGENT},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        token = json.load(resp)
    token["expires_at"] = int(time.time()) + int(token.get("expires_in", 3600)) - 60
    return token


def exchange_code(settings: Settings, code: str, verifier: str) -> dict:
    return _post_token({
        "grant_type": "authorization_code",
        "client_id": settings.keystring,
        "redirect_uri": settings.redirect_uri,
        "code": code,
        "code_verifier": verifier,
    })


def refresh(settings: Settings, refresh_token: str) -> dict:
    return _post_token({
        "grant_type": "refresh_token",
        "client_id": settings.keystring,
        "refresh_token": refresh_token,
    })


def save_token(path: Path, token: dict) -> None:
    path.write_text(json.dumps(token), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def load_token(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def delete_token(path: Path) -> None:
    path.unlink(missing_ok=True)


def valid_access_token(settings: Settings) -> str:
    """Return a non-expired access token, refreshing it when needed."""
    token = load_token(settings.token_path)
    if not token:
        raise SystemExit("Not authorized yet. Run: python -m etsy_profit auth")
    if token.get("expires_at", 0) <= time.time():
        token = refresh(settings, token["refresh_token"])
        save_token(settings.token_path, token)
    return token["access_token"]


def interactive_authorize(settings: Settings) -> None:
    """Open Etsy's consent page and catch the redirect on localhost."""
    verifier, challenge = make_pkce_pair()
    state = secrets.token_urlsafe(16)
    result: dict[str, str] = {}
    redirect = urllib.parse.urlparse(settings.redirect_uri)

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            result.update(params)
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Authorization received. You can close this tab.")

        def log_message(self, *args):  # keep the console free of request details
            pass

    server = http.server.HTTPServer((redirect.hostname or "localhost", redirect.port or 3003), Handler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    url = authorization_url(settings, state, challenge)
    print("Opening Etsy's consent page. If it does not open, visit:\n" + url)
    webbrowser.open(url)
    thread.join(timeout=300)
    server.server_close()

    if result.get("state") != state or "code" not in result:
        raise SystemExit("Authorization was not completed.")
    save_token(settings.token_path, exchange_code(settings, result["code"], verifier))
    print("Authorized. Token saved locally.")
