"""Read the data the report needs. Every call is a GET, and every result is stripped of personal data."""
from __future__ import annotations

from datetime import datetime, timezone

from .client import EtsyClient
from .privacy import strip_personal


def _ts(day: str) -> int:
    return int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp())


def shop_id(client: EtsyClient) -> int:
    me = client.get("/users/me")
    return int(me["shop_id"])


def ledger_entries(client: EtsyClient, shop: int, since: str, until: str) -> list[dict]:
    path = f"/shops/{shop}/payment-account/ledger-entries"
    params = {"min_created": _ts(since), "max_created": _ts(until)}
    return [strip_personal(e) for e in client.paginate(path, params)]


def ledger_payments(client: EtsyClient, shop: int, entry_ids: list[int]) -> list[dict]:
    path = f"/shops/{shop}/payment-account/ledger-entries/payments"
    out: list[dict] = []
    for i in range(0, len(entry_ids), 100):
        page = client.get(path, {"ledger_entry_ids": entry_ids[i:i + 100]})
        out.extend(strip_personal(p) for p in page.get("results", []))
    return out


def receipts(client: EtsyClient, shop: int, since: str, until: str) -> list[dict]:
    path = f"/shops/{shop}/receipts"
    params = {"min_created": _ts(since), "max_created": _ts(until)}
    return [strip_personal(r) for r in client.paginate(path, params)]


def listings(client: EtsyClient, shop: int) -> list[dict]:
    keep = ("listing_id", "title", "tags", "state")
    return [{k: item.get(k) for k in keep}
            for item in client.paginate(f"/shops/{shop}/listings", {"state": "active"})]
