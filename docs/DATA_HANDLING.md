# Data handling

This document describes exactly what data the app reads from Etsy, what it keeps, and how it is protected. It applies to every part of the app, including the private connector the owner's AI assistant uses.

## Principles

1. **Read only what the report needs.** Only the endpoints in [API_USAGE.md](API_USAGE.md) are called, with read-only scopes.
2. **Drop personal data first.** Buyer personal data is removed in memory right after a response arrives, before anything is stored, logged or passed on.
3. **Keep it private.** Data is used only by the shop owner, for the owner's own bookkeeping and decisions.
4. **No secondary use.** No selling, sharing, publishing, profiling of buyers, or AI model training.

## What is read, kept and dropped

| Source | Kept | Dropped before storage |
|---|---|---|
| Ledger entries | entry id, date, type, description, amount, currency, reference type and id | — (ledger entries contain no buyer data) |
| Ledger payments | receipt id, gross, fees, net, currency, date | buyer user id |
| Receipts | receipt id, date, status, country, subtotal, discount, shipping, tax, items (listing id, title, variation, quantity, price) | buyer user id, name, email, all address lines, city, state, zip, phone, message from buyer, gift message, gift note |
| Listings | listing id, title, tags, state | — |

The list of dropped fields is the `PERSONAL_FIELDS` set in [`src/etsy_profit/privacy.py`](../src/etsy_profit/privacy.py). Unknown fields that look like personal data (any key containing `name`, `email`, `address`, `phone`, `zip`, `message` or `note`, except item titles) are also dropped, so new fields Etsy adds later are not kept by accident. Tests in [`tests/test_privacy.py`](../tests/test_privacy.py) check this.

## Storage

- Data is stored as local files on the owner's machine or in the owner's private dashboard storage.
- Only aggregated, personal-data-free tables reach the dashboard.
- Nothing is written to logs except request counts and errors (no response bodies).

## Credentials

- The Etsy keystring, shared secret and OAuth tokens are read from environment variables (`.env`) or the connector's secret store.
- They are never committed to this repository; `.gitignore` excludes `.env` and `*.token.json`.
- Refresh tokens are used to keep access; if refresh fails, the owner must authorize again.

## Freshness and retention

- Each sync replaces previously stored figures for the same period with current API data, so refunds and adjustments are reflected.
- Data is kept only as long as the owner needs it for bookkeeping. `python -m etsy_profit purge` deletes all stored data and the token.

## Revocation

If the owner revokes the app's access in Etsy, the next API call fails with an authorization error. The app then deletes the stored token and stops calling the API until the owner authorizes again.

## AI assistant use

The owner uses an AI assistant (Claude) to run syncs and summarize results on request.

- The assistant reaches the Etsy API only through a private connector holding the owner's token, and only with the read-only calls in [API_USAGE.md](API_USAGE.md).
- It acts only when the owner asks, and only on the owner's own shop.
- Etsy data is not used to train, fine-tune, evaluate or benchmark any AI model.
- Where Etsy asks automated agents to identify themselves, requests carry a `User-Agent` naming this app and its purpose.
