# Etsy Shop Profit Dashboard

A personal, **read-only** reporting tool for a single Etsy shop. The shop owner uses it to see real profit per order, product, product theme and month, by combining Etsy sales and fee data with print-on-demand production costs.

> The term "Etsy" is a trademark of Etsy, Inc. This application uses the Etsy API but is not endorsed or certified by Etsy, Inc.

---

## Contents

- [Why this exists](#why-this-exists)
- [Who uses it](#who-uses-it)
- [What it does](#what-it-does)
- [What it does not do](#what-it-does-not-do)
- [Etsy API usage](#etsy-api-usage)
- [How it works](#how-it-works)
- [How profit is calculated](#how-profit-is-calculated)
- [Data handling and privacy](#data-handling-and-privacy)
- [Running it](#running-it)
- [Project layout](#project-layout)
- [Status](#status)

More detail: [docs/API_USAGE.md](docs/API_USAGE.md) · [docs/DATA_HANDLING.md](docs/DATA_HANDLING.md) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## Why this exists

The shop sells print-on-demand apparel. Each order involves two companies:

- **Printify** prints and ships the item, and reports what it cost to make and ship.
- **Etsy** takes the payment, and charges listing fees, transaction fees, payment processing fees, regulatory fees and advertising (Etsy Ads, Offsite Ads).

Neither side shows the full picture. Etsy's own reports show sales and fees but not production cost; Printify shows production cost but not what the buyer paid or what Etsy kept. Today the owner has to download monthly statement spreadsheets by hand and match them up. This tool does that matching automatically, using the Etsy API for the Etsy half.

## Who uses it

| | |
|---|---|
| **Users** | One person: the owner of the shop. |
| **Shops** | One shop: the owner's own, authorized by the owner through Etsy OAuth 2.0. |
| **Interface** | A private dashboard only the owner can open. No public pages. |
| **Distribution** | Not offered, sold or licensed to other sellers. |

## What it does

1. **Reads** the shop's payment-account ledger (sales, fees, ads, refunds, deposits), orders and listing titles from the Etsy Open API v3.
2. **Removes buyer personal data** from every response before anything is saved (see [Data handling](#data-handling-and-privacy)).
3. **Matches** each Etsy order to its Printify production cost using the order number Printify already stores.
4. **Calculates** net profit per order, product, product theme and month.
5. **Shows** the results in a private dashboard with a date filter (day, month, year) so the owner can answer:
   - What did I actually earn this month after Etsy fees, ads and production costs?
   - Which products and themes are profitable, and which only look busy?
   - How much do I spend on each type of Etsy fee and on ads, and how is that changing?

## What it does not do

- It **never writes** to Etsy: no creating, editing or deleting listings, orders, messages or settings.
- It does **not** access any shop other than the owner's.
- It does **not** scrape Etsy web pages; it uses only the documented API.
- It does **not** store or display buyer names, emails, addresses or messages.
- It does **not** sell, publish or share Etsy data with anyone.
- It does **not** use Etsy data to train, fine-tune, evaluate or benchmark any AI model.

## Etsy API usage

Only **read** endpoints and **read-only scopes** are used.

| Purpose | Endpoint | Scope |
|---|---|---|
| Sales, fees, ads, refunds, deposits | `GET /v3/application/shops/{shop_id}/payment-account/ledger-entries` | `transactions_r` |
| Gross, fees and net per order payment | `GET /v3/application/shops/{shop_id}/payment-account/ledger-entries/payments` | `transactions_r` |
| Orders and sold items | `GET /v3/application/shops/{shop_id}/receipts` | `transactions_r` |
| Listing titles (to group products) | `GET /v3/application/shops/{shop_id}/listings` | `listings_r` |
| Resolve the owner's shop id | `GET /v3/application/users/me` | `shops_r` |

**Volume:** one sync per day, typically under 200 requests, paginated at 100 items per request. The client backs off on HTTP 429 and respects the daily limit. See [docs/API_USAGE.md](docs/API_USAGE.md).

## How it works

```
 ┌───────────────────────────┐
 │  Etsy Open API v3         │  read-only, owner's OAuth token
 └─────────────┬─────────────┘
               │ ledger entries, receipts, listings
               ▼
 ┌───────────────────────────┐
 │  etsy_profit (this repo)  │  1. fetch   2. strip personal data
 │                           │  3. join with Printify costs  4. aggregate
 └─────────────┬─────────────┘
               │ aggregated, personal-data-free tables
               ▼
 ┌───────────────────────────┐
 │  Private dashboard        │  owner only
 └───────────────────────────┘
```

The owner also uses an AI assistant (Claude) to run the sync on request and to summarize the results. The assistant reaches the API only through a private connector that holds the owner's token, acts only on the owner's instructions and only on the owner's shop, and works with the same read-only calls listed above. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## How profit is calculated

For each order (Etsy receipt):

```
net profit = item sales − discounts + shipping charged to buyer
           − Etsy fees linked to the order (transaction, processing, regulatory, offsite ads)
           − Printify production cost − Printify shipping cost
```

Shop-level costs that are not tied to one order (listing fees, Etsy Ads, subscriptions) are reported per month and, in product views, spread across orders in proportion to their sales. Sales tax and VAT collected by Etsy are excluded from revenue because Etsy remits them. All amounts are in the shop currency.

## Data handling and privacy

Short version (full policy in [docs/DATA_HANDLING.md](docs/DATA_HANDLING.md)):

- **Buyer personal data is dropped immediately** after each API response is received, in memory, before anything is written to disk. The code that does this is [`src/etsy_profit/privacy.py`](src/etsy_profit/privacy.py) and it is covered by tests.
- **What is kept:** order id, order date, listing id, item title, variation (size/colour), quantity, prices, fees, buyer country.
- **Credentials** (API keystring, shared secret, OAuth tokens) live only in environment variables or the connector's secret store. They are never committed. [`.gitignore`](.gitignore) excludes `.env` and token files.
- **No sharing, no selling, no AI training.**
- **Revocation:** if the owner revokes access in Etsy, the stored token is deleted and no further calls are made. `etsy-profit purge` deletes all stored data.

## Running it

Requires Python 3.10+ and no third-party packages (standard library only).

```bash
pip install -e .                # installs the package (no third-party dependencies)
cp .env.example .env            # fill in your own app keystring and shared secret
python -m etsy_profit auth      # opens Etsy's consent page; stores the token locally
python -m etsy_profit sync --since 2025-01-01
python -m etsy_profit report --by month
python -m etsy_profit purge     # delete all stored data and the token
```

Printify costs are read from a JSON export of the owner's Printify orders (`--printify orders.json`).

Run the tests:

```bash
python -m unittest discover -s tests
```

## Project layout

```
src/etsy_profit/
  config.py      settings from environment variables
  oauth.py       OAuth 2.0 authorization-code flow with PKCE, token refresh
  client.py      read-only HTTP client: pagination, rate limiting, retries
  fetch.py       ledger entries, receipts, listings
  privacy.py     removes buyer personal data from API responses
  printify.py    reads Printify order costs from an export
  profit.py      joins Etsy and Printify data and calculates profit
  report.py      aggregates by day, month, year, product and theme
  __main__.py    command-line interface
tests/           unit tests with synthetic, made-up data only
docs/            API usage, data handling, architecture
```

## Status

In development, waiting for Etsy API personal access. Until access is granted the owner uses Etsy's monthly statement CSV downloads for the same report. This repository documents the purpose and design of the app for Etsy's review.

## License

[MIT](LICENSE)
