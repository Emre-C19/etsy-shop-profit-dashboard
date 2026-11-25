"""Command-line interface: auth, sync, report, purge."""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import date, timedelta
from pathlib import Path

from . import fetch, oauth, report
from .client import AuthorizationRevoked, EtsyClient
from .config import load_settings
from .printify import load_costs
from .profit import build_orders


def _client(settings) -> EtsyClient:
    return EtsyClient(settings.api_key_header, lambda: oauth.valid_access_token(settings))


def cmd_auth(args) -> None:
    oauth.interactive_authorize(load_settings(args.env))


def cmd_sync(args) -> None:
    settings = load_settings(args.env)
    client = _client(settings)
    until = (date.today() + timedelta(days=1)).isoformat()
    try:
        shop = fetch.shop_id(client)
        ledger = fetch.ledger_entries(client, shop, args.since, until)
        payment_entry_ids = [e["entry_id"] for e in ledger if "payment" in str(e.get("ledger_type", "")).lower()]
        payments = fetch.ledger_payments(client, shop, payment_entry_ids)
        receipts = fetch.receipts(client, shop, args.since, until)
    except AuthorizationRevoked as err:
        oauth.delete_token(settings.token_path)
        raise SystemExit(f"{err} The stored token was deleted. Run `auth` again if you want to reconnect.")
    out = settings.data_dir / "etsy.json"
    out.write_text(json.dumps({"ledger": ledger, "payments": payments, "receipts": receipts}), encoding="utf-8")
    print(f"Saved {len(ledger)} ledger entries and {len(receipts)} orders ({client.request_count} requests).")


def cmd_report(args) -> None:
    settings = load_settings(args.env)
    etsy = json.loads((settings.data_dir / "etsy.json").read_text(encoding="utf-8"))
    costs = load_costs(args.printify) if args.printify else {}
    orders, shop_level = build_orders(etsy["receipts"], etsy["ledger"], etsy["payments"], costs)
    result = {
        "by_period": report.by_period(orders, shop_level, args.by),
        "fees": report.fee_breakdown(orders, shop_level),
        "by_product": report.by_product(orders, shop_level)[:50],
        "orders_without_printify_cost": sum(1 for o in orders if not o.has_printify_cost),
    }
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"Report written to {args.out}")
    else:
        print(text)


def cmd_purge(args) -> None:
    settings = load_settings(args.env)
    shutil.rmtree(settings.data_dir, ignore_errors=True)
    print("All stored data and the token were deleted.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="etsy_profit", description="Personal, read-only Etsy profit reporting.")
    parser.add_argument("--env", default=".env", help="path to the settings file")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("auth", help="authorize the app for your shop (read-only scopes)").set_defaults(func=cmd_auth)
    p = sub.add_parser("sync", help="fetch ledger entries and orders")
    p.add_argument("--since", default=(date.today() - timedelta(days=7)).isoformat(), help="YYYY-MM-DD")
    p.set_defaults(func=cmd_sync)
    p = sub.add_parser("report", help="calculate profit")
    p.add_argument("--by", choices=("day", "month", "year"), default="month")
    p.add_argument("--printify", help="path to a Printify orders export (JSON)")
    p.add_argument("--out", help="write the report to this file instead of printing it")
    p.set_defaults(func=cmd_report)
    sub.add_parser("purge", help="delete all stored data and the token").set_defaults(func=cmd_purge)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
