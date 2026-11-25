"""Settings, read from environment variables (or a local .env file that is never committed)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

API_BASE = "https://api.etsy.com/v3/application"
AUTH_URL = "https://www.etsy.com/oauth/connect"
TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"
SCOPES = ("transactions_r", "listings_r", "shops_r")  # read-only, nothing else


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    keystring: str
    shared_secret: str
    redirect_uri: str
    data_dir: Path

    @property
    def token_path(self) -> Path:
        return self.data_dir / "etsy.token.json"

    @property
    def api_key_header(self) -> str:
        # Etsy expects "keystring:shared_secret" in the x-api-key header.
        return f"{self.keystring}:{self.shared_secret}"


def load_settings(env_file: str | os.PathLike = ".env") -> Settings:
    _load_dotenv(Path(env_file))
    missing = [k for k in ("ETSY_KEYSTRING", "ETSY_SHARED_SECRET") if not os.environ.get(k)]
    if missing:
        raise SystemExit(f"Missing settings: {', '.join(missing)}. Copy .env.example to .env and fill them in.")
    data_dir = Path(os.environ.get("ETSY_PROFIT_DATA_DIR", "data")).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        keystring=os.environ["ETSY_KEYSTRING"],
        shared_secret=os.environ["ETSY_SHARED_SECRET"],
        redirect_uri=os.environ.get("ETSY_REDIRECT_URI", "http://localhost:3003/callback"),
        data_dir=data_dir,
    )
