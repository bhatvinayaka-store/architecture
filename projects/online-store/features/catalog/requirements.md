# Catalog & Search - Requirements

**Status:** Draft v0.1 · **Owner:** Catalog team · **Last updated:** 2026-11-14

## Goal
Show customers what they can buy, at what price, with fast browsing and search; let merchandisers manage products and images.

## User stories
Each story becomes one Jira story in project `STORE`; start the Jira summary with the story ID (e.g. `INV-01: ...`).

| ID | Story | Acceptance criteria | Priority |
|---|---|---|---|
| CAT-01 | As a customer, I only see products sold by the store that serves my delivery address | Every browse/search call is scoped to a storeId; products the store does not list are never shown | P0 |
| CAT-02 | As a customer, products my store has run out of are shown greyed out with 'Notify me' | Out-of-stock but listed items visible, not addable to cart (decision pending) | P1 |
| CAT-03 | As a customer, I can view product details with images | Thumbnail + full image served via CDN | P0 |
| CAT-04 | As a merchandiser, I can create/edit products and upload images | Admin role only; image uploaded directly to S3 via presigned URL | P0 |
| CAT-05 | As a customer, I can search with keyword, filters and autocomplete | Results < 500 ms; typo tolerant | P1 (R2) |
| CAT-06 | As the system, product changes reach search within seconds | Index lag < 5 s p95; full reindex job exists | P1 (R2) |
| CAT-07 | As a customer, popular product pages load fast under load | Cache-aside in Redis; invalidated on ProductUpdated | P1 (R2) |

## Non-functional requirements
- Browse p99 < 300 ms (cached), < 800 ms (uncached)
- Search p99 < 500 ms
- Handle 300 req/s on product pages in load test

## Out of scope
- Personalised recommendations
- Reviews and ratings
- Per-store pricing (R1 uses one city-wide price; decision pending)

## Open questions
- Out-of-stock items in the serving store: show greyed out with 'Notify me' (proposed) or hide?
- Prices: one city-wide price (proposed for R1) or per store?
