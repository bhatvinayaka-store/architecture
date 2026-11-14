# Catalog & Search - High-Level Design

**Status:** Draft v0.1 - in review · **Owner:** Catalog team · **Last updated:** 2026-11-14
**Requirements:** [requirements.md](requirements.md) · **Builds on:** [system HLD platform defaults](../../system-hld.md#3-platform-defaults)

## 1. Summary
Catalog owns the product master (one per city), each store's assortment, and a copy of each
store's availability. Every customer-facing read is **scoped to a store**, so customers never see
products their store does not sell. R2 adds OpenSearch search and a Redis cache, justified by
load-test numbers.

## 2. Goals and non-goals
**Goals (R1):** CAT-01 to CAT-04 (store-scoped browsing, out-of-stock display, product pages,
admin + images). **(R2):** CAT-05 to CAT-07 (search, index freshness, caching).
**Non-goals:** per-store pricing, recommendations, reviews.

## 3. Context
```
 Web app ── /stores/{storeId}/... ──> Catalog API (Lambda) ──> Aurora PostgreSQL "catalog"
 Admin UI ── /admin/... ────────────>      |    \
                                           |     └─ presigned URL -> S3 images -> thumbnail Lambda
 Checkout ── /internal/prices (IAM) ──────>|
                                           ├── publishes ProductUpdated, PriceChanged, AssortmentChanged
 Inventory ── StockLevelChanged ──> SQS ──>┘ (availability copy)
 R2: ProductUpdated / AssortmentChanged / StockLevelChanged -> indexer -> OpenSearch
```

## 4. What drives the design
| Driver | Consequence |
|---|---|
| Relational data: category tree, product-store assortment, admin queries with joins | PostgreSQL (the feature that teaches RDS/Aurora) |
| Read-heavy customer traffic | Simple indexed queries in R1; cache + search index in R2 **only if** load tests show the need |
| Customers must only see their store's products | `storeId` is part of every public route and every query |
| Stock changes often; product data changes rarely | Availability is a small separate table updated from events |

## 5. Architecture
| Component | Choice | Why |
|---|---|---|
| API | Spring Boot on Lambda (SnapStart), public + internal + admin routes | Platform default |
| Database | Aurora PostgreSQL database `catalog` via Data API | ADR-0011; relational fit |
| Images | S3 (presigned PUT from browser) -> S3 event -> thumbnail Lambda (Java, ImageIO/Thumbnailator) -> CloudFront | Browser uploads directly; no image bytes through our API |
| Availability consumer | SQS queue subscribed to `StockLevelChanged` -> Lambda (batch, idempotent upsert) | Absorbs bursts, retries, DLQ |
| R2 search | OpenSearch domain (smallest size), one document per (store, product); indexer Lambda from events; full reindex job | Typo-tolerant search + filters; rebuildable read model |
| R2 cache | ElastiCache (Redis/Valkey) cache-aside for product list/detail, keys include storeId | Only after a load test shows DB latency is the bottleneck |

**Local vs AWS database access:** code talks to a repository interface; locally it uses JDBC
against Postgres in Docker, in AWS the Data API. Same SQL in both.

## 6. Data model
**PostgreSQL `catalog`**
| Table | Key columns | Notes |
|---|---|---|
| `categories` | id, parent_id, name, sort | Tree (max 3 levels) |
| `products` | id (UUID), sku, name, brand, unit ("1 L"), description, category_id, price_paise, status (`ACTIVE`/`INACTIVE`), image_key, updated_at, version | One price city-wide in R1 |
| `store_assortment` | (store_id, product_id), listed, sort_rank, listed_at | Which products a store sells |
| `store_availability` | (store_id, product_id), in_stock, few_left, source_event_id, updated_at | Copy from Inventory events |
| `processed_events` | event_id, processed_at | De-duplication of consumed events |

Indexes: `store_assortment(store_id, listed)`, `products(category_id, status)`.
Browse query = assortment JOIN products LEFT JOIN availability, filtered by store and category,
keyset pagination on (sort_rank, product_id).

## 7. Interfaces
See the [README](README.md). Design rules:
- There is **no public, store-less product endpoint**; product pages are always `/stores/{storeId}/...`.
- Out-of-stock but listed products are returned with `inStock: false` (shown greyed out; decision pending).
- `POST /internal/prices` is the **only** price source for Checkout; the price shown in the app is
  informational and re-checked at checkout.
- `AssortmentChanged` is the contract that makes Inventory create stock records for new listings.

## 8. Key flows
**8.1 Browse**
```
GET /stores/BLR-S-04/products?category=dairy -> query (store-scoped) -> items with price + availability
```
**8.2 Stock change reaches the catalog**
```
Inventory -> StockLevelChanged{BLR-S-04, milk, inStock:false} -> SQS -> consumer
 -> upsert store_availability (skip if event already processed or older than current)
 -> (R2) invalidate cache key + update search document
```
**8.3 Merchandiser adds a product to two stores**
```
POST /admin/products -> ProductCreated
POST image-upload-url -> browser PUTs image to S3 -> thumbnail Lambda -> image_key set
PUT /admin/stores/BLR-S-04/assortment {add:[id]} -> AssortmentChanged -> Inventory creates stock (0)
```
**8.4 Checkout price check**
```
Checkout -> POST /internal/prices {storeId, productIds} -> {productId, pricePaise, listed}[]
```

## 9. Failure handling
| Failure | Handling |
|---|---|
| Aurora paused / resuming | First request may wait several seconds; Lambda timeout set accordingly; app shows a loading state. Keep minimum capacity > 0 during demos and load tests |
| Duplicate or out-of-order `StockLevelChanged` | `processed_events` + compare `updated_at`; older events ignored |
| Thumbnail generation fails | Retries via S3 event -> Lambda async retries + DLQ; product shows the original image |
| (R2) Search index out of sync | Full reindex job from PostgreSQL; index is never the source of truth |

## 10. Non-functional design
| Concern | Design |
|---|---|
| Latency | Indexed store-scoped queries; R2 cache-aside if load tests demand |
| Consistency | Availability copy is eventually consistent (seconds); Checkout relies on Inventory, not this copy |
| Security | Admin routes need `merchandiser`; uploads only via short-lived presigned URLs with content-type and size limits; images bucket private (CloudFront origin access control) |
| Cost | Aurora auto-paused when idle; OpenSearch and ElastiCache only during R2 learning stints |
| Observability | Metrics: browse latency by route, DB time per request, availability consumer lag, DLQ depth, thumbnail failures. **Alarms:** p99 > 500 ms, 5xx > 1%, DLQ > 0, consumer age of oldest message > 60 s |

## 11. Alternatives considered
| Option | Decision |
|---|---|
| DynamoDB for the catalog | Possible, but category trees + assortment joins + admin reporting fit SQL better, and this is where you learn RDS |
| Search with PostgreSQL full-text (no OpenSearch) | A valid simpler option for R2; OpenSearch chosen for the learning goal; decide at R2 planning |
| Read stock live from Inventory on every browse | Rejected: couples browsing to Inventory's availability and load |

## 12. Risks and open questions
1. Out-of-stock display: greyed out with "Notify me" (proposed) or hidden?
2. Prices: one city-wide price (proposed) or per store?
3. Data API cold resume time on Aurora: measure; may need a small minimum capacity in prod.

## Change log
Record every design change here with its reason ([scope control](../../scope-control.md)).

| Date | Change | Why (story / requirement) | Approved |
|---|---|---|---|
| 2026-11-14 | v0.1 first draft | - | Pending review |
