"""Aggregate order profit by period and by product. Output contains no personal data."""
from __future__ import annotations

from collections import defaultdict

from .profit import OrderProfit


def period_key(day: str, by: str) -> str:
    return {"day": day, "month": day[:7], "year": day[:4]}[by]


def by_period(orders: list[OrderProfit], shop_level: dict[str, dict[str, float]], by: str = "month") -> list[dict]:
    rows: dict[str, dict] = defaultdict(lambda: defaultdict(float))
    for o in orders:
        row = rows[period_key(o.date, by)]
        row["orders"] += 1
        row["revenue"] += o.revenue
        row["etsy_fees"] += o.fees
        row["production"] += o.production
        row["fulfillment_shipping"] += o.fulfillment_shipping
    for month, costs in shop_level.items():
        # Shop-level costs are monthly; for daily reports they are booked on the first of the month.
        key = period_key(month + "-01", by)
        rows[key]["shop_costs"] += sum(costs.values())
    out = []
    for key in sorted(rows):
        r = rows[key]
        net = r["revenue"] - r["etsy_fees"] - r["shop_costs"] - r["production"] - r["fulfillment_shipping"]
        out.append({
            "period": key,
            "orders": int(r["orders"]),
            "revenue": round(r["revenue"], 2),
            "etsy_fees": round(r["etsy_fees"], 2),
            "shop_costs": round(r["shop_costs"], 2),
            "production": round(r["production"], 2),
            "fulfillment_shipping": round(r["fulfillment_shipping"], 2),
            "net_profit": round(net, 2),
            "margin_pct": round(net / r["revenue"] * 100, 1) if r["revenue"] else 0.0,
        })
    return out


def fee_breakdown(orders: list[OrderProfit], shop_level: dict[str, dict[str, float]]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for o in orders:
        for k, v in o.etsy_fees.items():
            totals[k] += v
    for costs in shop_level.values():
        for k, v in costs.items():
            totals[k] += v
    return {k: round(v, 2) for k, v in sorted(totals.items(), key=lambda kv: -kv[1])}


def by_product(orders: list[OrderProfit], shop_level: dict[str, dict[str, float]]) -> list[dict]:
    """Split each order's profit across its items by price; spread shop-level costs by share of revenue."""
    total_revenue = sum(o.revenue for o in orders) or 1.0
    total_shop = sum(sum(c.values()) for c in shop_level.values())
    rows: dict[str, dict] = defaultdict(lambda: defaultdict(float))
    for o in orders:
        item_total = sum(i["amount"] for i in o.items) or 1.0
        order_net = o.net_profit - total_shop * (o.revenue / total_revenue)
        for i in o.items:
            share = i["amount"] / item_total
            row = rows[i["title"]]
            row["units"] += i["quantity"]
            row["revenue"] += o.revenue * share
            row["net_profit"] += order_net * share
    return sorted(({"title": t, "units": int(r["units"]), "revenue": round(r["revenue"], 2),
                    "net_profit": round(r["net_profit"], 2)} for t, r in rows.items()),
                  key=lambda r: -r["net_profit"])
