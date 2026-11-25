"""Remove buyer personal data from Etsy API responses.

This runs in memory on every response before anything is stored, logged or passed on.
"""
from __future__ import annotations

from typing import Any

# Fields Etsy returns on receipts and payments that identify or locate a buyer.
PERSONAL_FIELDS = frozenset({
    "buyer_user_id", "buyer_email", "seller_email", "name", "first_line", "second_line",
    "city", "state", "zip", "formatted_address", "phone", "message_from_buyer",
    "message_from_seller", "message_from_payment", "gift_message", "gift_note",
    "buyer_note", "shipping_address", "billing_address",
})

# Any key containing one of these fragments is treated as personal, so fields Etsy adds later are not kept by accident.
PERSONAL_FRAGMENTS = ("name", "email", "address", "phone", "zip", "message", "note")

# Keys that contain a fragment above but are not personal data.
ALLOWED_KEYS = frozenset({
    "title", "formatted_name", "formatted_value", "property_name", "shop_name",
    "country_iso", "shipping_method", "shipping_carrier",
})


def is_personal(key: str) -> bool:
    k = key.lower()
    if k in ALLOWED_KEYS:
        return False
    return k in PERSONAL_FIELDS or any(fragment in k for fragment in PERSONAL_FRAGMENTS)


def strip_personal(value: Any) -> Any:
    """Return a copy of an API response with every personal field removed, at any depth."""
    if isinstance(value, dict):
        return {k: strip_personal(v) for k, v in value.items() if not is_personal(k)}
    if isinstance(value, list):
        return [strip_personal(v) for v in value]
    return value
