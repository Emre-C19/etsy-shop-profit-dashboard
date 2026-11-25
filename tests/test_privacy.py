"""All data in these tests is made up."""
import unittest

from etsy_profit.privacy import strip_personal

SAMPLE_RECEIPT = {
    "receipt_id": 1001,
    "buyer_user_id": 42,
    "buyer_email": "someone@example.com",
    "name": "Example Buyer",
    "first_line": "1 Example Street",
    "second_line": "Flat 2",
    "city": "Exampletown",
    "state": "EX",
    "zip": "00000",
    "formatted_address": "Example Buyer\n1 Example Street",
    "country_iso": "US",
    "message_from_buyer": "Please gift wrap",
    "gift_message": "Happy birthday",
    "status": "Paid",
    "subtotal": {"amount": 2800, "divisor": 100, "currency_code": "USD"},
    "transactions": [{
        "transaction_id": 5001,
        "title": "Example Tee",
        "buyer_user_id": 42,
        "variations": [{"formatted_name": "Size", "formatted_value": "M"}],
    }],
    "shipments": [{"receipt_shipping_id": 1, "buyer_note": "x", "new_future_contact_name_field": "y"}],
}


class StripPersonalTest(unittest.TestCase):
    def setUp(self):
        self.clean = strip_personal(SAMPLE_RECEIPT)

    def test_buyer_identity_and_address_removed(self):
        for key in ("buyer_user_id", "buyer_email", "name", "first_line", "second_line", "city",
                    "state", "zip", "formatted_address", "message_from_buyer", "gift_message"):
            self.assertNotIn(key, self.clean)

    def test_nested_personal_fields_removed(self):
        self.assertNotIn("buyer_user_id", self.clean["transactions"][0])
        self.assertNotIn("buyer_note", self.clean["shipments"][0])

    def test_unknown_future_personal_fields_removed(self):
        self.assertNotIn("new_future_contact_name_field", self.clean["shipments"][0])

    def test_reporting_fields_kept(self):
        self.assertEqual(self.clean["receipt_id"], 1001)
        self.assertEqual(self.clean["country_iso"], "US")
        self.assertEqual(self.clean["transactions"][0]["title"], "Example Tee")
        self.assertEqual(self.clean["transactions"][0]["variations"][0]["formatted_value"], "M")

    def test_no_personal_values_anywhere(self):
        text = repr(self.clean)
        for value in ("someone@example.com", "Example Buyer", "Example Street", "Exampletown", "gift wrap"):
            self.assertNotIn(value, text)


if __name__ == "__main__":
    unittest.main()
