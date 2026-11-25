"""Read Printify production and shipping costs from an export of the owner's Printify orders.

Printify stores the Etsy order number as metadata.shop_order_id, which is the Etsy receipt id.
Personal fields in the export (address_to) are never read.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PrintifyCost:
    receipt_id: str
    production: float   # currency units, e.g. USD
    shipping: float


def _orders(data) -> list[dict]:
    # Accept a plain list, {"data": [...]}, or Printify's paginated {"data": {"data": [...]}}.
    while isinstance(data, dict):
        data = data.get("data", [])
    return data


def load_costs(path: str | Path) -> dict[str, PrintifyCost]:
    """Return production and shipping cost per Etsy receipt id. Canceled Printify orders are skipped."""
    costs: dict[str, PrintifyCost] = {}
    for order in _orders(json.loads(Path(path).read_text(encoding="utf-8"))):
        if order.get("status") == "canceled":
            continue
        receipt = str((order.get("metadata") or {}).get("shop_order_id") or "")
        if not receipt:
            continue
        items = order.get("line_items", [])
        production = sum((li.get("cost") or 0) * (li.get("quantity") or 1) for li in items) / 100
        shipping = (order.get("total_shipping") or 0) / 100
        if receipt in costs:  # an Etsy order split into several Printify orders
            production += costs[receipt].production
            shipping += costs[receipt].shipping
        costs[receipt] = PrintifyCost(receipt, round(production, 2), round(shipping, 2))
    return costs
