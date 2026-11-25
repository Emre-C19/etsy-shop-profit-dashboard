"""All data in these tests is made up."""
import json
import tempfile
import unittest
from pathlib import Path

from etsy_profit.printify import load_costs
from etsy_profit.profit import build_orders, categorize
from etsy_profit.report import by_period, by_product, fee_breakdown

TS_JAN = 1767268800  # 2026-01-01 12:00 UTC

RECEIPTS = [
    {"receipt_id": 1, "status": "Completed", "created_timestamp": TS_JAN,
     "subtotal": {"amount": 3000, "divisor": 100}, "discount_amt": {"amount": 300, "divisor": 100},
     "total_shipping_cost": {"amount": 500, "divisor": 100},
     "transactions": [{"transaction_id": 11, "listing_id": 100, "title": "Tee A", "quantity": 1,
                       "price": {"amount": 3000, "divisor": 100}, "variations": []}]},
    {"receipt_id": 2, "status": "Canceled", "created_timestamp": TS_JAN,
     "subtotal": {"amount": 3000, "divisor": 100}, "transactions": []},
]
LEDGER = [
    {"entry_id": 1, "ledger_type": "transaction", "reference_type": "transaction", "reference_id": "11",
     "amount": -195, "created_timestamp": TS_JAN},
    {"entry_id": 2, "ledger_type": "PAYMENT_PROCESSING_FEE", "reference_type": "payment", "reference_id": "900",
     "amount": -120, "created_timestamp": TS_JAN},
    {"entry_id": 3, "ledger_type": "listing", "reference_type": "listing", "reference_id": "100",
     "amount": -20, "created_timestamp": TS_JAN},
    {"entry_id": 4, "ledger_type": "prolist", "reference_type": "shop", "reference_id": "0",
     "amount": -100, "created_timestamp": TS_JAN},
    {"entry_id": 5, "ledger_type": "Payment", "reference_type": "payment", "reference_id": "900",
     "amount": 3200, "created_timestamp": TS_JAN},
]
PAYMENTS = [{"payment_id": 900, "receipt_id": 1}]
PRINTIFY = {"data": {"data": [
    {"status": "fulfilled", "metadata": {"shop_order_id": "1"}, "total_shipping": 475,
     "line_items": [{"cost": 726, "quantity": 1}], "address_to": {"first_name": "ignored"}},
    {"status": "canceled", "metadata": {"shop_order_id": "2"}, "total_shipping": 475,
     "line_items": [{"cost": 726, "quantity": 1}]},
]}}


class ProfitTest(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "printify.json"
            p.write_text(json.dumps(PRINTIFY))
            self.costs = load_costs(p)
        self.orders, self.shop = build_orders(RECEIPTS, LEDGER, PAYMENTS, self.costs)

    def test_categories(self):
        self.assertEqual(categorize("transaction"), "transaction_fee")
        self.assertEqual(categorize("PAYMENT_PROCESSING_FEE"), "processing_fee")
        self.assertEqual(categorize("prolist"), "etsy_ads")
        self.assertEqual(categorize("offsite_ads_fee"), "offsite_ads")
        self.assertEqual(categorize("DISBURSE2"), "deposit")
        self.assertEqual(categorize("something_new"), "other")

    def test_canceled_orders_skipped(self):
        self.assertEqual([o.receipt_id for o in self.orders], ["1"])
        self.assertNotIn("2", self.costs)

    def test_order_profit(self):
        o = self.orders[0]
        self.assertAlmostEqual(o.revenue, 30 - 3 + 5)
        self.assertEqual(o.etsy_fees, {"transaction_fee": 1.95, "processing_fee": 1.2})
        self.assertAlmostEqual(o.production, 7.26)
        self.assertAlmostEqual(o.fulfillment_shipping, 4.75)
        self.assertAlmostEqual(o.net_profit, 32 - 3.15 - 7.26 - 4.75)

    def test_shop_level_costs_by_month(self):
        self.assertEqual(self.shop, {"2026-01": {"listing_fee": 0.2, "etsy_ads": 1.0}})

    def test_period_report(self):
        (row,) = by_period(self.orders, self.shop, "month")
        self.assertEqual(row["period"], "2026-01")
        self.assertAlmostEqual(row["net_profit"], round(32 - 3.15 - 1.2 - 7.26 - 4.75, 2))

    def test_fee_breakdown_and_products(self):
        fees = fee_breakdown(self.orders, self.shop)
        self.assertAlmostEqual(sum(fees.values()), 1.95 + 1.2 + 0.2 + 1.0)
        (product,) = by_product(self.orders, self.shop)
        self.assertEqual(product["title"], "Tee A")
        self.assertAlmostEqual(product["net_profit"], round(32 - 3.15 - 1.2 - 7.26 - 4.75, 2))


if __name__ == "__main__":
    unittest.main()
