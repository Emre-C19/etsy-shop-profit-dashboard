"""Join Etsy ledger and receipt data with Printify costs, and calculate profit per order."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .printify import PrintifyCost

# Ledger entry types are matched case-insensitively, first match wins.
# Anything not recognised is reported as "other" so totals still reconcile with the payment account.
LEDGER_CATEGORIES: list[tuple[str, tuple[str, ...]]] = [
    ("deposit", ("disburse", "deposit")),
    ("refund", ("refund",)),
    ("tax_collected", ("sales_tax", "vat", "gst", "tax")),
    ("offsite_ads", ("offsite_ads",)),
    ("etsy_ads", ("prolist", "etsy_ads", "promoted")),
    ("processing_fee", ("processing",)),
    ("transaction_fee", ("transaction",)),
    ("listing_fee", ("listing", "renew")),
    ("regulatory_fee", ("regulatory",)),
    ("shipping_label", ("shipping_label", "postage")),
    ("subscription", ("subscription", "etsy_plus")),
    ("sale", ("payment", "sale")),
]
FEE_CATEGORIES = ("transaction_fee", "processing_fee", "listing_fee", "regulatory_fee", "etsy_ads",
                  "offsite_ads", "shipping_label", "subscription", "other")


def categorize(ledger_type: str | None, description: str | None = None) -> str:
    text = f"{ledger_type or ''} {description or ''}".lower()
    for category, needles in LEDGER_CATEGORIES:
        if any(n in text for n in needles):
            return category
    return "other"


def money(value) -> float:
    """Etsy money objects look like {"amount": 2500, "divisor": 100}; ledger amounts are plain integers in cents."""
    if value is None:
        return 0.0
    if isinstance(value, dict):
        return value.get("amount", 0) / (value.get("divisor") or 100)
    return value / 100


def day_of(ts: int | None) -> str:
    return datetime.fromtimestamp(ts or 0, tz=timezone.utc).strftime("%Y-%m-%d")


@dataclass
class OrderProfit:
    receipt_id: str
    date: str
    sales: float
    discount: float
    shipping_charged: float
    etsy_fees: dict[str, float] = field(default_factory=dict)
    production: float = 0.0
    fulfillment_shipping: float = 0.0
    items: list[dict] = field(default_factory=list)
    has_printify_cost: bool = False

    @property
    def revenue(self) -> float:
        return self.sales - self.discount + self.shipping_charged

    @property
    def fees(self) -> float:
        return sum(self.etsy_fees.values())

    @property
    def net_profit(self) -> float:
        return round(self.revenue - self.fees - self.production - self.fulfillment_shipping, 2)


def build_orders(receipts: list[dict], ledger: list[dict], payments: list[dict],
                 costs: dict[str, PrintifyCost]) -> tuple[list[OrderProfit], dict[str, dict[str, float]]]:
    """Return (profit per order, shop-level costs per month that are not tied to one order)."""
    # Map every reference Etsy may use on a ledger entry back to its receipt.
    to_receipt: dict[tuple[str, str], str] = {}
    for r in receipts:
        rid = str(r["receipt_id"])
        to_receipt[("receipt", rid)] = rid
        for t in r.get("transactions", []):
            to_receipt[("transaction", str(t.get("transaction_id")))] = rid
    for p in payments:
        if p.get("receipt_id"):
            to_receipt[("payment", str(p.get("payment_id")))] = str(p["receipt_id"])

    orders: dict[str, OrderProfit] = {}
    for r in receipts:
        if r.get("status", "").lower() in ("canceled", "cancelled"):
            continue
        rid = str(r["receipt_id"])
        cost = costs.get(rid)
        orders[rid] = OrderProfit(
            receipt_id=rid,
            date=day_of(r.get("created_timestamp") or r.get("create_timestamp")),
            sales=money(r.get("subtotal")),
            discount=money(r.get("discount_amt")),
            shipping_charged=money(r.get("total_shipping_cost")),
            production=cost.production if cost else 0.0,
            fulfillment_shipping=cost.shipping if cost else 0.0,
            has_printify_cost=bool(cost),
            items=[{
                "listing_id": t.get("listing_id"),
                "title": t.get("title", ""),
                "variation": ", ".join(v.get("formatted_value", "") for v in t.get("variations", [])),
                "quantity": t.get("quantity", 1),
                "amount": money(t.get("price")) * (t.get("quantity") or 1),
            } for t in r.get("transactions", [])],
        )

    shop_level: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for e in ledger:
        category = categorize(e.get("ledger_type"), e.get("description"))
        if category not in FEE_CATEGORIES:
            continue  # sales, refunds, taxes and deposits come from receipts or are not costs
        amount = -money(e.get("amount"))  # fees are debits (negative) in the ledger; store as positive cost
        ref = (str(e.get("reference_type", "")).lower(), str(e.get("reference_id", "")))
        rid = to_receipt.get(ref)
        if rid in orders:
            fees = orders[rid].etsy_fees
            fees[category] = round(fees.get(category, 0.0) + amount, 2)
        else:
            month = day_of(e.get("created_timestamp") or e.get("create_date"))[:7]
            shop_level[month][category] += amount
    return list(orders.values()), {m: dict(v) for m, v in shop_level.items()}
