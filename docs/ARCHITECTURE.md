# Architecture

## Components

1. **Etsy Open API v3.** The only source of Etsy data. Called with the owner's OAuth token and read-only scopes.
2. **`etsy_profit` package (this repository).** Standard-library Python. Fetches, strips personal data, joins with Printify costs and aggregates.
3. **Printify cost export.** A JSON file of the owner's Printify orders. Printify stores the Etsy order number (`shop_order_id`) on each order, which is the join key to the Etsy receipt id.
4. **Private dashboard.** Shows only aggregated, personal-data-free tables: totals by day, month and year; by product; by product theme; by fee type.
5. **Private connector and AI assistant.** The owner can ask an AI assistant (Claude) to run a sync or explain the numbers. The assistant reaches Etsy only through a private connector holding the owner's token, using the same read-only calls.

## Data flow

```
owner authorizes (OAuth 2.0 + PKCE, read-only scopes)
        │
        ▼
fetch.py ──► client.py ──► Etsy API
   │   pages of ledger entries, payments, receipts, listings
   ▼
privacy.py   drop buyer personal data (in memory)
   │
   ▼
profit.py    categorise ledger entries, join receipts with Printify costs,
   │         calculate profit per order
   ▼
report.py    aggregate by period, product, theme and fee type
   │
   ▼
dashboard    owner only
```

## Why there is no server

The app runs for a single owner on demand or on a daily schedule. There is no hosted service, no database shared between users and no public endpoint, which keeps the attack surface and the amount of stored data as small as possible.
