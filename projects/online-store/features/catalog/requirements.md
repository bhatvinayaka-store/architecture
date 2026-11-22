# Catalog & Search - Requirements

**Status:** Draft v0.4 (round-3 fixes) · **Owner:** Catalog team · **Last updated:** 2026-11-22

## Goal
Show customers what they can buy in their store, at their city's price, with clear stock badges and purchase limits; let merchandisers manage products, prices, images and store listings.

## User stories
Each story becomes one Jira story in project `STORE`; start the Jira summary with the story ID (e.g. `CAT-01: ...`).

| ID | Story | Acceptance criteria | Priority |
|---|---|---|---|
| CAT-01 | As a customer, I only see products sold by the store that serves my delivery address | Every browse call is scoped to a storeId; products the store does not list, inactive products and stores in `SETUP`/`CLOSED` are never shown | P0 |
| CAT-02 | As a customer, I see whether a product is in stock, has only a few left, or is out of stock | Badge comes from Inventory events; "Only N left" when available < `maxPerOrder`; out-of-stock items cannot be added; shown in place with a dimmed image and the label ([UX design §4](../../ux-design.md#4-state-matrix)) | P0 |
| CAT-03 | As a customer, I can view product details with images | Thumbnail + full image served via CDN | P0 |
| CAT-04 | As a merchandiser, I can create/edit products and categories and upload images | Soft delete only (inactive); image uploaded directly to S3 via presigned URL; R1 through the admin API with operator scripts (screens with the staff side) | P0 |
| CAT-05 | As a customer, I can search with keyword, filters and autocomplete | Results < 500 ms; typo tolerant | P1 (later) |
| CAT-06 | As the system, product changes reach search within seconds | Index lag < 5 s p95; full reindex job exists | P1 (later) |
| CAT-07 | As a customer, popular pages load fast under load | Public browse responses cached by CloudFront (60 s) | P1 |
| CAT-08 | As a customer, I see my city's price | Price per (product, city); a product is listed only where its city has a price | P0 |
| CAT-09 | As a customer, I cannot add more of a product than allowed | `maxPerOrder` per store + product shown on the product; cart allows at most `min(maxPerOrder, availableQty)` | P0 |
| CAT-10 | As a merchandiser, I can choose which products each store sells | List / unlist one product or in bulk; unlisted products disappear from browsing; listing creates stock records in Inventory | P0 |
| CAT-11 | As a customer, I see the MRP and my saving on packaged goods | `mrpPaise` on the product; selling price can never be set above MRP (422) | P0 |
| CAT-12 | As a customer, my cart shows current prices and stock when I open it | Batch lookup of up to 35 products by id | P0 |

## Non-functional requirements
- Browse p99 < 300 ms (cached), < 800 ms (uncached)
- Handle 300 req/s on browse pages in a `dev` load test; prod public routes are throttled at 20 req/s (burst 40) for cost
- Data model works for ~3,000 stores and 45-80K products without redesign

## Out of scope
- Personalised recommendations, reviews and ratings
- Store details (name, address, hours): owned by Stores (Store Network)

## Open questions
- ~~Display of out-of-stock items~~: decided, shown in place with a dimmed image ([UX design §4](../../ux-design.md#4-state-matrix))
- ~~Admin auth~~: R1 operator scripts with IAM (D10); staff side after R1
