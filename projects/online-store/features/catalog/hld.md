# Catalog & Search - High-Level Design

**Status:** Draft v0.6 - agreed in design review; round-3 fixes 2026-11-22 for review · **Owner:** Catalog team · **Last updated:** 2026-11-22
**Requirements:** [requirements.md](requirements.md) · **LLD:** [lld.md](lld.md) · **Builds on:** [system HLD platform defaults](../../system-hld.md#3-platform-defaults) · **Decisions:** [design review log](../../design-review-log.md#3-catalog)

## 1. Summary
Catalog owns the product master (city-wide), **prices per city**, the category tree, and each
store's listings: which products a store sells, the per-order limit (`maxPerOrder`) and a copy of
the stock badge received from Inventory. Data lives in **two DynamoDB tables**; public browse
responses are cached by **CloudFront**. Every customer-facing read is **scoped to a store**, so
customers never see products their store does not sell.

R1 starts with **one store** (`BLR-S-01`). The design is sized for ~3,000 stores and 45-80K
products (section 10); opening a store only adds listing rows.

## 2. Goals and non-goals
**Goals (R1):** CAT-01 to CAT-04, CAT-07 to CAT-10. **Later:** CAT-05, CAT-06 (search).
**Non-goals:** recommendations, reviews, product variants grouping ([parking lot](../../parking-lot.md)).

## 3. Context
```
 Web app (catalog UI) ── /stores/{storeId}/... ──> CloudFront (60 s) ──> Catalog API (Lambda) ──> catalog-products
 Operator scripts ───── /admin/... ─────────────────────────────────────>        |                  catalog-store-listings
 Ordering ───────────── /internal/prices ───────────────────────────────>        |
                                                                                 ├─ S3 images -> thumbnail Lambda
                                          publishes ProductCreated/Updated, PriceChanged, AssortmentChanged, ListingUpdated
 Inventory: StockLevelChanged ─┐
 Stores: StoreCreated/Updated, ├─> SQS ──> event consumer ──> catalog-store-listings
         StoreStatusChanged ───┘
```

## 4. What drives the design
| Driver | Consequence |
|---|---|
| Every product type has **different attributes** | Schemaless product items: attributes stored as a map |
| Access is **key-based** (store + category page, one product, prices for ids) | DynamoDB with two indexes; every read is a `Query`, `GetItem` or `BatchGetItem` |
| **Read-heavy**, same list for every customer of a store | CloudFront caches public GET responses |
| Customers only see their store's products | `storeId` in every public route and every listing key |
| Prices differ by city | A price item per (product, city); the store's city decides which price is shown |
| The purchase limit must be visible while adding to the cart | `maxPerOrder` on the listing, returned with every product ([ADR-0017](../../adr/0017-stock-badge-ownership.md)) |
| Stock changes often, product data rarely | Badge lives on the small listing row (updated from events); product data on the product row |

## 5. Architecture
| Component | Choice | Why |
|---|---|---|
| API | Spring Boot 3 on Lambda (SnapStart): one jar deployed as **seven functions** with separate IAM roles: three APIs (public read-only, admin, internal read-only) plus the event consumer, stream publisher, thumbnail worker and nightly count rebuild ([LLD §1](lld.md#1-code-and-repository-structure)); on the team's own API URL | [ADR-0016](../../adr/0016-spring-boot-on-lambda.md), [ADR-0002](../../adr/0002-polyrepo-and-team-ownership.md) |
| Data | DynamoDB `catalog-products-<stage>` and `catalog-store-listings-<stage>`, on-demand, PITR on | [Catalog ADR-0001](adr/0001-dynamodb-two-tables.md) |
| Cache | CloudFront in front of public `GET /stores/...`, TTL 60 s, cache key = path + `category`, `subcategory`, `cursor`, `limit`, `ids`, each validated first (fixed `limit`, signed `cursor`, sorted `ids`) | Admin and internal routes are never cached |
| Images | Presigned S3 upload from the browser -> S3 event -> thumbnail Lambda -> served by **Catalog's own CloudFront distribution** (thumbnails only) | No image bytes through the API |
| Event publishing | DynamoDB Streams on both tables -> publisher Lambda -> EventBridge (outbox) | Events always match what was saved |
| Event consumer | SQS subscribed to `StockLevelChanged`, `StoreCreated`, `StoreUpdated`, `StoreStatusChanged` -> Lambda (conditional updates) | Retries, DLQ |
| In-memory cache | Category tree cached in the Lambda for a few minutes | Read on every browse, changes rarely |
| Search (later) | OpenSearch read model fed by events; hosting decided when search starts | Not needed for R1 |

No filtering or sorting on category pages in R1: products come in the merchandiser's rank order.
Filters and sorting come with search.
Fresh produce is sold in **fixed packs** ("Tomato 500 g"), so quantities are whole numbers everywhere.

## 6. Data model
### 6.1 `catalog-products` (master data)
| Item | pk | sk | Attributes |
|---|---|---|---|
| Product card | `PRODUCT#P-1001` | `META` | sku, name ("Nandini Milk (orange packet) 500 ml"), brand, **netQty + netUnit** (500 + `ml`, shown as "500 ml"), categoryId (`dairy`), subcategoryId (`milk`), status (`ACTIVE`/`INACTIVE`), imageId, **mrpPaise** (packaged goods; empty for fresh produce), version, updatedAt |
| Product detail | `PRODUCT#P-1001` | `DETAIL` | description, **attributes** (map of type-specific extras, e.g. `{fatPercent: 3.0, packColor: "orange"}`; never the pack size), version (read only on the product page, so browse reads stay small) |
| City price | `PRODUCT#P-1001` | `PRICE#BLR` | **sellingPricePaise** (must be ≤ mrpPaise when set), currency `INR`, version, updatedAt |
| Category | `CATEGORY` | `dairy` / `milk` | name, parentId (null for top level), sort, active |

Index **`byCategory`** (admin product list), on product `META` items only:
`categoryKey = dairy#milk`, `nameKey = <name>#<productId>`.

**Category rules** (details in [LLD §2.4](lld.md#24-category-rules)): two levels; every product has
exactly one home subcategory (both ids required); a category without natural subcategories gets one
default subcategory (`eggs-all`, its tabs hidden when it is the only one); products that fit nowhere
go to "Other" (`other` / `other-all`) for the merchandiser to re-home; one home per product in R1
(cross-listing is in the [parking lot](../../parking-lot.md)).

### 6.2 `catalog-store-listings` (per store)
| Item | pk (`storeId`) | sk | Attributes |
|---|---|---|---|
| Listing | `BLR-S-01` | `PRODUCT#P-1001` | listed, sortRank, categoryId, subcategoryId, **maxPerOrder**, **stockStatus** (`IN`/`FEW`/`OUT`, starts `OUT`), **availableQty** (only when `FEW`), stockAt, listedAt; index keys below **only while listed** |
| Category count | `BLR-S-01` | `COUNT#dairy` / `COUNT#dairy#milk` | productCount: listed **and active** products (hides empty categories and subcategories; rebuilt nightly) |
| Store copy | `BLR-S-01` | `STORE` | status (`SETUP`/`OPEN`/`PAUSED`/`CLOSED`), city, name, updatedAt (from Stores events, re-sent nightly) |

Index **`byStoreCategory`** (browse): `storeCategory = BLR-S-01#dairy`,
`subcategoryRank = milk#0005#P-1001` (rank zero-padded so it sorts as a number). Unlisting removes
these attributes, so the row drops out of the index (sparse index) but stays for history.
Index **`byProduct`** (`productId` → stores, keys only) finds every store listing a product, e.g.
when a product moves to another subcategory.

### 6.3 Access patterns
| Pattern | Operation |
|---|---|
| Category menu of a store | Query listings `pk = storeId`, `sk begins_with COUNT#` + cached category tree |
| All products of a store | Query listings `pk = storeId`, `sk begins_with PRODUCT#` (only `listed`) → BatchGet `META` + `PRICE#<city>` |
| Store + category (Dairy) | Query `byStoreCategory` `storeCategory = BLR-S-01#dairy` → BatchGet products + city prices |
| Store + subcategory (Milk) | Same + `begins_with(subcategoryRank, "milk#")` |
| Product page | BatchGet listing + `META` + `PRICE#<city>`; 404 if not listed, inactive, or store not visible |
| Products by ids (cart refresh, max 35) | BatchGet listings + `META` + `PRICE#<city>` |
| Prices at checkout | BatchGet listings + products + city prices (never cached) |
| Badge update | UpdateItem listing (key from the event: storeId + productId) |
| Price change | UpdateItem `PRICE#<city>` (one write) |
| List / unlist | TransactWriteItems: listing row + category counts |
| Admin product list | Query `byCategory` |

**Visibility rule:** a customer sees a product in a store when the store copy is `OPEN` or
`PAUSED`, the product is `ACTIVE`, the listing is `listed`, and a price exists for the store's city.
A product can only be listed in a store whose city has a price for it.

## 7. Interfaces
**Auth:** public routes are open (reached as `/api/catalog/stores/...` through CloudFront, cached,
no cookies; 20 req/s, burst 40 per route in prod). Admin routes use **IAM auth** in every stage, called
only by the operator's scripts, with low throttling (R1 has no admin screens, D10); the staff pool
replaces this with the staff side. Never unauthenticated.

| Method + path | Purpose |
|---|---|
| `GET /stores/{storeId}/categories` | Category tree with counts for this store |
| `GET /stores/{storeId}/products?category=&subcategory=&cursor=&limit=` | Products of the store, optionally by category / subcategory |
| `GET /stores/{storeId}/products/{productId}` | Product page with city price, MRP, stock badge and `maxPerOrder` |
| `GET /stores/{storeId}/products?ids=P-1001,P-1002` | Up to 35 products by id (sorted ids, cached), for the cart page |
| `POST /admin/categories` · `PATCH /admin/categories/{id}` · `GET /admin/categories` | Manage categories (deactivate, no delete) |
| `POST /admin/products` · `PATCH /admin/products/{id}` (`If-Match`) · `GET /admin/products/{id}` · `GET /admin/products?category=&cursor=` | Manage products; `status: INACTIVE` instead of delete |
| `PUT /admin/products/{id}/prices/{city}` | Set the city selling price (422 if above the product's MRP) |
| `POST /admin/products/{id}/image-upload-url` | Presigned S3 upload |
| `PUT /admin/stores/{storeId}/products/{productId}` `{listed, sortRank, maxPerOrder}` | List / unlist / change limit (idempotent) |
| `POST /admin/stores/{storeId}/products:batch` `{list:[...], unlist:[...]}` | Bulk listing (chunked) |
| `GET /admin/stores/{storeId}/products?listed=all` | Store's listings incl. unlisted |
| `POST /internal/prices` `{storeId, productIds}` | Trusted selling price, MRP, listed flag and `maxPerOrder` for Ordering |

Customer product shape:
```json
{ "productId": "P-1001", "name": "Nandini Milk (orange packet) 500 ml", "sellingPricePaise": 2600, "mrpPaise": 2800,
  "stock": { "status": "FEW", "availableQty": 2 }, "maxPerOrder": 3 }
```
Conventions: cursor pagination (encoded `LastEvaluatedKey`), money in paise, `If-Match` optimistic
locking on updates, `Idempotency-Key` on creates, one JSON error format.

**Events published:** `ProductCreated`, `ProductUpdated`, `PriceChanged {productId, city}`,
`AssortmentChanged {storeId, added: [{productId, categoryId, maxPerOrder, listingVersion}], removed}`,
`ListingUpdated {storeId, productId, maxPerOrder, listingVersion}` (Inventory keeps only newer versions).
**Events consumed:** `StockLevelChanged` (Inventory), `StoreCreated` / `StoreUpdated` / `StoreStatusChanged` (Stores).

## 8. Key flows
**8.1 Browse Dairy → Milk**
```
GET /stores/BLR-S-01/products?category=dairy&subcategory=milk
 -> CloudFront hit? return (<= 60 s old)
 -> miss: store copy visible? -> Query byStoreCategory (BLR-S-01#dairy, begins_with milk#)
    -> BatchGet META + PRICE#BLR -> drop INACTIVE -> respond (Cache-Control: max-age=60)
```
**8.2 Stock badge update** ([ADR-0017](../../adr/0017-stock-badge-ownership.md))
```
Inventory -> StockLevelChanged {BLR-S-01, P-1001, status: FEW, availableQty: 2, occurredAt}
 -> UpdateItem listing SET stockStatus, availableQty, stockAt
    CONDITION attribute_exists(pk) AND (attribute_not_exists(stockAt) OR stockAt < :occurredAt)
 -> customers see "Only 2 left" (cart allows max 2) within ~60 s
```
**8.3 Listing a product** (operator script in R1)
```
POST /admin/products -> PUT .../prices/BLR -> image upload
PUT /admin/stores/BLR-S-01/products/P-1001 {listed: true, maxPerOrder: 3}
 -> listing row (stockStatus OUT) + counts -> AssortmentChanged {categoryId, maxPerOrder} -> Inventory creates stock row
```
**8.4 New store being set up**
```
StoreCreated {BLR-S-02, status SETUP, city BLR} -> store copy
 -> the operator lists products (bulk script); public routes return 404 until StoreStatusChanged -> OPEN
```

## 9. Failure handling
| Failure | Handling |
|---|---|
| Duplicate / out-of-order `StockLevelChanged` | Conditional update on `stockAt` |
| Store event missed | Store Network re-sends every store nightly (`StoreUpdated`, `reason: RECONCILE`); the copy takes it if newer |
| A count drifts (missed or raced update) | Nightly count rebuild per store; `CountCorrected` > 0 raises an alarm |
| Two quick `maxPerOrder` changes reach Inventory out of order | `listingVersion` in the event; Inventory keeps the newer one |
| Thumbnail fails | Lambda async retries + DLQ; original image shown |
| Catalog API errors | CloudFront serves cached pages until TTL; 5xx alarm |
| DynamoDB throttling | On-demand; SDK retries; alarm |

## 10. Non-functional design
| Concern | Design |
|---|---|
| Latency | Key-based reads (ms); CloudFront for repeats; browse p99 < 300 ms |
| Consistency | Badge and cached pages eventually consistent (≤ ~60 s); checkout re-checks |
| Scale check | 3,000 stores × ~8K products ≈ 24M listing rows (~5 GB). Item count is not a limit; write volume (badge updates only on status change) and hot keys (popular products, cached) are what matter |
| Security | Admin routes IAM-only (operator scripts, D10) until staff auth; images private behind CloudFront; uploads via short-lived presigned URLs |
| Cost | DynamoDB on-demand + CloudFront: cents at R1 volume. Public routes are throttled (20 req/s, burst 40 in prod), query parameters are validated before any read, and an hourly read-units alarm watches both tables, so a cache-busting flood is capped and noticed within the hour |
| Observability | Browse latency, cache hit ratio, throttles, consumer lag, DLQ depth. **Alarms:** p99 > 500 ms, 5xx > 1%, DLQ > 0, oldest message > 60 s, read units > 1 M/hour, `CountCorrected` > 0 |

## 11. Alternatives considered
| Option | Decision |
|---|---|
| Aurora PostgreSQL (v0.1, with JSONB attributes) | Rejected: key-based access, idle cost, chosen partly "to learn RDS" |
| Single-table DynamoDB | Valid; two tables chosen for clarity |
| A table per store | Rejected: duplicates product data; a table per new store |
| JSON file in S3 as the catalog | Rejected as source of truth; possible later as a generated snapshot |
| Store details (name, address) in Catalog | Rejected: owned by Stores; Catalog keeps only a status/city copy |
| Redis / ElastiCache cache | Rejected: CloudFront already caches; would force a VPC/NAT |
| Few-left threshold computed by Catalog from exact counts | Rejected: Catalog would receive every stock change ([ADR-0017](../../adr/0017-stock-badge-ownership.md)) |

## 12. Risks and open questions
1. Staff auth for admin routes: staff side, after R1 (IAM operator scripts until then, D10).
2. ~~How out-of-stock items look~~: decided, shown in place with a dimmed image and a text label ([UX design §4](../../ux-design.md#4-state-matrix)).
3. Cache TTL 60 s: tune after load tests.

## Change log
Record every design change here with its reason ([scope control](../../scope-control.md)).

| Date | Change | Why (story / requirement) | Approved |
|---|---|---|---|
| 2026-11-14 | v0.1 first draft (Aurora PostgreSQL) | - | - |
| 2026-11-21 | v0.2: DynamoDB two tables; category → subcategory browse index; price per city; `maxPerOrder` + stock badge copy; store status copy; CloudFront cache, no Redis; full API set; no auth for now; R1 one store | [Design review log §3](../../design-review-log.md#3-catalog) | Agreed in design review 2026-11-15..21 |
| 2026-11-21 | v0.3: `mrpPaise` on products (selling price ≤ MRP); `pricePaise` renamed `sellingPricePaise`; `?ids=` batch lookup for the cart page; fresh produce sold in fixed packs | [Design review log §10](../../design-review-log.md#10-ordering-full-review) | Agreed in design review 2026-11-21 |
| 2026-11-21 | v0.4 (from the LLD): product split into `META` + `DETAIL` (≈5× cheaper browse reads); `byProduct` index; three Lambda functions with separate roles; Streams outbox; own images distribution | [LLD](lld.md) | For review |
| 2026-11-21 | v0.5: category rules (one home per product, default subcategory, "Other"); admin routes IAM-only until staff auth; out-of-stock look decided | Your category question; [design review log §12](../../design-review-log.md#12-design-review-fixes) | Agreed 2026-11-21 |
| 2026-11-22 | v0.6 (round-3 fixes): prod throttling and validated cache keys with an hourly read-units alarm; seven functions (count rebuild added); counts = listed and active products, rebuilt nightly; `listingVersion` on listing events; store copy repaired by Store Network's nightly re-send; no in-page filtering in R1; pack size as `netQty` + `netUnit`; admin API for operator scripts in every stage (D10); change log put in date order | [Design review log §14](../../design-review-log.md#14-design-review-fixes-round-3) (H-1, H-2, M-6, M-7, M-8, L-1, L-7, L-8, L-9) | Applied 2026-11-22, for review |
