# Catalog ADR-0001: DynamoDB with two tables (not Aurora PostgreSQL)

**Status:** Accepted · **Date:** 2026-11-15 (two-table layout agreed 2026-11-20)

## Context
The v0.1 HLD put the catalog in Aurora PostgreSQL, partly so the project had a feature that
teaches RDS. On review:
- Every product type has different attributes (milk: volume, fat %; shampoo: ml, hair type).
- Customer reads are key-based: a store's category page, one product, prices for a list of ids.
- Traffic is read-heavy and identical for every customer of a store, so it caches well.
- The budget is ~$20/month, and Aurora auto-pause is unverified.

## Decision
- **DynamoDB**, in two tables:
  - `catalog-products` (master data): products (attributes as a map), **city prices**, categories.
  - `catalog-store-listings` (per store): which products a store sells, `maxPerOrder`, the stock
    badge copy, category counts, and a copy of the store's status and city.
- Product data is stored **once**; listing rows do not copy name or price, so a price change is one write.
- Browsing uses the index `byStoreCategory` with a hierarchical sort key (`subcategory#rank#productId`).
- Public browse responses are cached in **CloudFront** (60 s). No Redis.
- **Principle:** choose the database that fits the data, never one just to learn it. RDS is learned
  where data is truly relational (e.g. Procurement).

## Consequences
- Flexible attributes, no idle database cost, single-digit-millisecond reads.
- Filtering across attributes is done in the Lambda per category page; full-text search needs
  OpenSearch (later).
- Cached pages can be up to 60 s old; Checkout always re-checks prices and Inventory re-checks stock.
- System ADR-0011 (shared Aurora) no longer covers Catalog.
