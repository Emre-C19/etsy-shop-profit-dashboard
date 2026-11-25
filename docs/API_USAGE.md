# Etsy API usage

## Authorization

- OAuth 2.0 authorization-code flow with PKCE, as required by Etsy Open API v3.
- Requested scopes: `transactions_r listings_r shops_r`. No write scopes.
- Only the shop owner authorizes the app. The redirect URI points to a local address on the owner's machine (`http://localhost:3003/callback`).
- Access tokens are refreshed with the refresh token before they expire.

## Endpoints

| Endpoint | Why | Typical calls per daily sync |
|---|---|---|
| `GET /v3/application/users/me` | find the owner's `shop_id` once | 1 |
| `GET /v3/application/shops/{shop_id}/payment-account/ledger-entries` | sales, every fee type, ads, refunds, deposits | 1–5 |
| `GET /v3/application/shops/{shop_id}/payment-account/ledger-entries/payments` | gross / fees / net per order payment | 1–10 |
| `GET /v3/application/shops/{shop_id}/receipts` | orders and sold items | 1–10 |
| `GET /v3/application/shops/{shop_id}/listings` | titles for grouping products | 1–10 |

A first full sync of one year of history is a one-off of a few hundred requests. Daily syncs after that only fetch the last few days (with overlap, to pick up refunds and late fees).

## Request behaviour

- Every request sends `x-api-key: {keystring}:{shared_secret}` and `Authorization: Bearer {access_token}`.
- Pagination uses `limit=100` and `offset`.
- Time ranges use `min_created` / `max_created` (ledger) and `min_created` / `max_created` (receipts).
- On HTTP 429 the client waits (honouring `Retry-After` when present) and retries with exponential backoff, at most 5 times.
- At most 4 requests per second, well under the default limit.
- A `User-Agent` header identifies the app: `etsy-shop-profit-dashboard/0.1 (personal read-only reporting)`.

## Ledger entry types

Ledger entries are grouped into reporting categories in [`src/etsy_profit/profit.py`](../src/etsy_profit/profit.py) (`LEDGER_CATEGORIES`): sales, refunds, transaction fees, processing fees, listing fees, regulatory fees, Etsy Ads, Offsite Ads, shipping labels, taxes collected by Etsy, deposits and other. Types the code does not recognise are reported as "other" so totals always reconcile with the payment account balance.
