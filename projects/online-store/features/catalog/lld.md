# Catalog & Search - Low-Level Design

**Status:** Draft v0.5 - for review (walkthrough fixes 2026-11-22) · **Owner:** Catalog team · **Last updated:** 2026-11-22
**Builds on:** [HLD v0.6](hld.md) · **Scope:** R1 (everything except search) · Kept in sync with the code ([scope control](../../scope-control.md))

## 0. Conventions
| Topic | Rule |
|---|---|
| JSON | camelCase; unknown **request** fields rejected (400); unknown fields in **events and responses** we read are ignored (tolerant reader, [system HLD §4](../../system-hld.md#4-event-conventions)) |
| IDs | Product `P-<number>` (from an atomic counter, e.g. `P-1001`); category/subcategory: lowercase slug, unique across both levels (`dairy`, `milk`, `curd`); store `BLR-S-01` (from Stores) |
| Money | Integer paise (`sellingPricePaise: 2600`), currency `INR` |
| Time | ISO-8601 UTC (`2026-11-21T10:15:00Z`) |
| Pagination | `limit` is **20 (default) or 50**, nothing else (400: every value is a separate cache entry) + opaque `cursor` = base64url of `LastEvaluatedKey` **plus an HMAC-SHA256 signature** (per-stage key: an SSM SecureString created once by an operator script, since CloudFormation cannot create SecureStrings; cached in the Lambda). A cursor with a bad signature, or keys that don't belong to the requested store/category, → 400 before any DynamoDB read. Rotating the key only sends open lists back to page 1 |
| Optimistic locking | Every mutable item has `version`; responses return `ETag: "<version>"`; updates need `If-Match` (412 on mismatch). For a product the ETag is the **`META` version**: a change to `DETAIL` also bumps `META.version` in the same transaction, so one `If-Match` covers both |
| Idempotency | `Idempotency-Key` header required on admin `POST` creates; same key + same body → same response for 24 h; same key + different body → 422 |
| Correlation | `X-Correlation-Id` accepted or generated; returned and logged; passed in events |
| Errors | `{"error": {"code": "PRICE_ABOVE_MRP", "message": "...", "details": {...}, "correlationId": "..."}}` |
| Versioning | No version prefix in R1; breaking changes follow expand → migrate → contract |

## 1. Code and repository structure
| Repo | Contents |
|---|---|
| `catalog-backend` | Spring Boot 3 app (Java 21), one jar, several Lambda handlers; `openapi.yaml` |
| `catalog-web` | Micro-frontends (React + TypeScript). R1 builds the **`customer`** bundle (browse; listed in `/mfe/catalog/manifest.json`, loaded by the customer shell). The **`staff`** bundle (admin screens; a separate entry point, so customers never download admin code) comes with the staff side. Standalone dev mode |
| `catalog-infra` | CDK (TypeScript): data stack, service stack, pipeline stack |
| `catalog-data` | Seed files (categories, sample products, BLR prices, BLR-S-01 listings) and the **operator scripts** that load and change them through the admin API with IAM-signed requests, in every stage (R1 has no admin screens, D10) |

**`catalog-backend` packages**
```
com.shoplite.catalog
├── api/            PublicCatalogController, AdminCategoryController, AdminProductController,
│                   AdminListingController, InternalPriceController, dto/, ErrorHandler, validation/
├── domain/         Product, ProductDetail, CityPrice, Category, Listing, StockStatus,
│                   PriceRules (≤ MRP), VisibilityRule, SortKeys (zero-padded rank)
├── service/        BrowseService, ProductService, CategoryService, ListingService,
│                   PriceLookupService, ImageUploadService, IdempotencyService
├── persistence/    ProductTable, ListingTable (DynamoDB Enhanced Client), CursorCodec
├── events/         StreamEventMapper (outbox), EventBridgePublisher,
│                   StockLevelChangedHandler, StoreEventHandler, CategoryMoveHandler
├── images/         ThumbnailHandler (S3 event)
└── config/         Spring profiles: public | admin | internal | worker
```
**Lambda functions** (same jar, different Spring profile and IAM role, for least privilege)
| Function | Trigger | Profile | Memory / timeout |
|---|---|---|---|
| `catalog-public-api` | HTTP API (public routes) | `public` (read-only role) | 1024 MB / 10 s, SnapStart |
| `catalog-admin-api` | HTTP API (`/admin/*`) | `admin` | 1024 MB / 29 s, SnapStart |
| `catalog-internal-api` | HTTP API (`/internal/*`, IAM) | `internal` (read-only role) | 1024 MB / 10 s, SnapStart |
| `catalog-events-consumer` | SQS `catalog-inbound` (batch 10): stock and store events, and Catalog's own `ProductUpdated` when `subcategoryId` or `status` changed | `worker` | 512 MB / 30 s |
| `catalog-stream-publisher` | DynamoDB Streams (both tables) | `worker` | 512 MB / 30 s |
| `catalog-thumbnail` | S3 `ObjectCreated` on `originals/` | `worker` | 1536 MB / 60 s |
| `catalog-count-rebuild` | EventBridge Scheduler, nightly 03:30 IST | `worker` | 512 MB / 300 s |

## 2. Data model
### 2.1 Table `catalog-products-<stage>`
| Setting | Value |
|---|---|
| Keys | `pk` (S), `sk` (S) |
| Billing | On-demand |
| Streams | `NEW_AND_OLD_IMAGES` (outbox) |
| Protection | PITR on; deletion protection in prod; AWS-owned encryption |
| GSI `byCategory` | pk `categoryKey` (S), sk `nameKey` (S); projection INCLUDE `sku, name, brand, netQty, netUnit, status, mrpPaise, imageId` |

| Item | pk | sk | Attributes (type) |
|---|---|---|---|
| Product card | `PRODUCT#P-1001` | `META` | sku (S), name (S), brand (S), **netQty (N, e.g. 500) + netUnit (S `g`/`kg`/`ml`/`l`/`pcs`)** (the API also returns the display text `unit: "500 ml"`), categoryId (S), subcategoryId (S), status (S `ACTIVE`/`INACTIVE`), mrpPaise (N, optional), imageId (S, optional), categoryKey (S `dairy#milk`), nameKey (S `nandini milk orange packet 500 ml#P-1001`), version (N), createdAt, updatedAt (S) |
| Product detail | `PRODUCT#P-1001` | `DETAIL` | description (S, ≤ 2,000 chars), attributes (M, ≤ 30 keys; values S/N/BOOL; type-specific extras such as `fatPercent`, never the pack size), version (N), updatedAt |
| City price | `PRODUCT#P-1001` | `PRICE#BLR` | sellingPricePaise (N), currency (S), version (N), updatedAt |
| SKU guard | `SKU#NDN-MILK-500` | `SKU` | productId (S) — guarantees unique SKUs |
| Category | `CATEGORY` | `dairy` / `milk` | name (S), parentId (S, absent for top level), sort (N), active (BOOL), version (N) |
| Product counter | `COUNTER` | `PRODUCT` | seq (N) — `UpdateItem ADD seq :1`, returns the new id |
| Idempotency | `IDEMP#<key>` | `IDEMP` | requestHash (S), statusCode (N), body (S), ttl (N, 24 h) |

**Why `META` and `DETAIL` are split:** DynamoDB charges reads by item size, even with a projection.
Browse pages read 20 product cards; keeping description and attributes in `DETAIL` keeps each card
~300 bytes instead of ~2 KB (≈5× cheaper browse reads). `DETAIL` is read only on the product page.

Example items:
```json
{ "pk": "PRODUCT#P-1001", "sk": "META", "sku": "NDN-MILK-500", "name": "Nandini Milk (orange packet) 500 ml",
  "brand": "Nandini", "netQty": 500, "netUnit": "ml", "categoryId": "dairy", "subcategoryId": "milk", "status": "ACTIVE",
  "mrpPaise": 2800, "imageId": "01JD3K...", "categoryKey": "dairy#milk",
  "nameKey": "nandini milk orange packet 500 ml#P-1001", "version": 3 }
{ "pk": "PRODUCT#P-1001", "sk": "DETAIL", "description": "Toned milk...", "attributes": {"fatPercent": 3.0, "packColor": "orange"}, "version": 1 }
{ "pk": "PRODUCT#P-1001", "sk": "PRICE#BLR", "sellingPricePaise": 2600, "currency": "INR", "version": 2 }
```

### 2.2 Table `catalog-store-listings-<stage>`
| Setting | Value |
|---|---|
| Keys | `pk` (S = storeId), `sk` (S) |
| Billing / Streams / Protection | On-demand / `NEW_AND_OLD_IMAGES` / PITR, deletion protection in prod |
| GSI `byStoreCategory` (sparse) | pk `storeCategory` (S `BLR-S-01#dairy`), sk `subcategoryRank` (S `milk#0005#P-1001`); projection INCLUDE `productId, sortRank, maxPerOrder, stockStatus, availableQty` |
| GSI `byProduct` | pk `productId` (S), sk `pk` (storeId); projection KEYS_ONLY (badge updates never write to it) |

| Item | pk | sk | Attributes (type) |
|---|---|---|---|
| Listing | `BLR-S-01` | `PRODUCT#P-1001` | productId (S), listed (BOOL), sortRank (N 1-9999), categoryId (S), subcategoryId (S), maxPerOrder (N 1-50), stockStatus (S `IN`/`FEW`/`OUT`, starts `OUT`), availableQty (N, only when `FEW`), stockAt (S), productActive (BOOL, copy of the product's status, so a repeated status event never changes the counts twice), listedAt, updatedAt, version (N); `storeCategory` + `subcategoryRank` **only while listed** |
| Category count | `BLR-S-01` | `COUNT#dairy` / `COUNT#dairy#milk` | productCount (N) |
| Store copy | `BLR-S-01` | `STORE` | status (S), city (S), name (S), eventAt (S) |

Counts include listed **and active** products, whatever their stock. They are used only to hide
empty categories, never shown as exact numbers. A product's status change adjusts the counts of every
store listing it (the events consumer, on Catalog's own `ProductUpdated`; Query `byProduct`, like a subcategory move in 5.3), and a **nightly
count rebuild** per store (`catalog-count-rebuild`) recomputes every `COUNT#` item from the listings
and fixes drift (metric `CountCorrected`).

### 2.3 Access patterns
| # | Pattern | Operation | Reads (approx.) |
|---|---|---|---|
| A1 | Category menu | Query listings `pk = :store AND begins_with(sk, "COUNT#")` + cached category tree | 1 small query |
| A2 | Browse a category / subcategory | Query `byStoreCategory` `storeCategory = :sc [AND begins_with(subcategoryRank, :sub#)]`, `Limit 20` + GetItem `STORE` (visibility, §3.1) → BatchGet 20 `META` + 20 `PRICE#<city>` | ~1.5 + 20 RRU |
| A3 | All products of a store | Query listings `begins_with(sk, "PRODUCT#")`, filter `listed = true` → BatchGet | ~ A2 |
| A4 | Products by ids (≤ 35) | BatchGet `STORE` + listings + `META` + `PRICE#<city>` (≤ 106 keys, split into 100-key batches) | ~ 1 per item |
| A5 | Product page | BatchGet listing + `STORE` + `META` + `DETAIL` + `PRICE#<city>` | ~5 RRU |
| A6 | Internal prices | Same as A4 with `ConsistentRead = true` | ~2 per item |
| A7 | Admin product list | Query `byCategory` `categoryKey = :ck` | small |
| A8 | Stores listing a product | Query `byProduct` `productId = :p` | small |
| A9 | Badge update | UpdateItem listing (condition on `stockAt`) | 1 WRU |

### 2.4 Category rules
Every product has a place in the browse index; no product is ever left without a category.

| Rule | Detail |
|---|---|
| Two levels only | Category (`dairy`) → subcategory (`milk`). A subcategory's parent must be a top-level category (422 `PARENT_NOT_TOP_LEVEL`) |
| Every product has exactly one home | `categoryId` and `subcategoryId` are both required; the subcategory must be **active** and its parent must be `categoryId` (422 `SUBCATEGORY_MISMATCH`, `CATEGORY_INACTIVE`). A product is never attached to a top-level category alone |
| Category with no natural subcategories (e.g. Eggs) | Gets one default subcategory: slug `<category>-all` (`eggs-all`), same name as the category ("Eggs"). Every product's data and index keys keep the same shape (`subcategoryRank = eggs-all#0005#P-2101`) |
| Only one subcategory to show | UIs skip the subcategory tabs and list the products straight away (default subcategories, or a category whose other subcategories are empty) |
| Product fits nowhere | Category `other` "Other" with subcategory `other-all`, sorted last, hidden when empty like any category. The merchandiser checks it weekly (`GET /admin/products?category=other`) and moves products to a better home, or creates a new category when several similar products collect there |
| Empty categories | Hidden by the `COUNT#` items (§2.2); categories are deactivated, never deleted |
| Deactivating | 409 `CATEGORY_IN_USE` while active products (or, for a top-level category, active subcategories) still use it; move them first (§5.3). Products never vanish from browse by accident |
| One product in several categories (cross-listing) | Not in R1: one home per product; search (later) finds products across categories. [Parking lot](../../parking-lot.md) |

## 3. API specification
Full schemas live in `catalog-backend/openapi.yaml`; this section is the contract summary.

### 3.1 Public (no auth; through CloudFront as `/api/catalog/...`, cached 60 s)
**`GET /stores/{storeId}/categories`** → 200
```json
{ "storeId": "BLR-S-01",
  "categories": [ { "categoryId": "dairy", "name": "Dairy", "subcategories": [ { "categoryId": "milk", "name": "Milk" } ] } ] }
```
Only active categories with `productCount > 0`. A category with one visible subcategory still
returns it; the UI skips the subcategory tabs ([§2.4](#24-category-rules)). `404 STORE_NOT_FOUND` if the store copy is missing,
`SETUP` or `CLOSED`.

**`GET /stores/{storeId}/products?category=&subcategory=&limit=&cursor=`** → 200
```json
{ "items": [ { "productId": "P-1001", "name": "Nandini Milk (orange packet) 500 ml", "brand": "Nandini",
               "unit": "500 ml", "imageUrl": "https://<images>/thumbs/P-1001/01JD3K_320.webp",
               "sellingPricePaise": 2600, "mrpPaise": 2800,
               "stock": { "status": "FEW", "availableQty": 2 }, "maxPerOrder": 3 } ],
  "nextCursor": "eyJwayI6..." }
```
`subcategory` requires `category` (400). Inactive products and products without a city price are
dropped, so a page can hold fewer than `limit` items.

Every products route (by category or by `ids`) also reads the store copy: `404 STORE_NOT_FOUND`
if it is missing, `SETUP` or `CLOSED`. The store ID comes from the browser (a saved location or a
shared link), so it can point to a store that has shut or not launched. Catalog only refuses those;
choosing the serving store, opening hours included, stays with Store Network.

**`GET /stores/{storeId}/products?ids=P-1001,P-1002`** → 200 `{ "items": [...], "unavailable": ["P-1002"] }`
Max 35 ids, **sorted ascending and without duplicates**, each matching `^P-\d{4,10}$` (400 otherwise, before any read); not combinable with `category` (400). Sorted ids let identical carts share cache entries, and rejecting other orders stops junk from filling the cache.

**`GET /stores/{storeId}/products/{productId}`** → 200: card fields + `description`, `attributes`,
`imageUrl` (800 px), `categoryId`, `subcategoryId`. `404 PRODUCT_NOT_FOUND` if not listed, inactive,
no city price, or the store is not visible. When the product exists in the master, `details` says why
and where similar products are: `{reason: NOT_LISTED | INACTIVE | NO_PRICE | STORE_NOT_VISIBLE,
categoryId, subcategoryId}`, so the UI can offer "Browse similar" ([UX design §2](../../ux-design.md#2-urls-and-owners)); unknown ids get no details.

Headers on 200: `Cache-Control: public, max-age=60`. On 404: `Cache-Control: public, max-age=10`.

### 3.2 Admin (`/admin/*`; IAM auth for the operator's scripts in R1, staff pool later)
| Method + path | Body | Success | Errors |
|---|---|---|---|
| `POST /admin/categories` | `{categoryId, name, parentId?, sort}` | 201 + category | 409 `CATEGORY_EXISTS`; 422 `PARENT_NOT_TOP_LEVEL` (max two levels) |
| `PATCH /admin/categories/{id}` + `If-Match` | `{name?, sort?, active?}` | 200 | 404, 412; 409 `CATEGORY_IN_USE` (deactivating while in use) |
| `GET /admin/categories` | - | 200 full tree incl. inactive | - |
| `POST /admin/products` + `Idempotency-Key` | `{sku, name, brand, netQty, netUnit, categoryId, subcategoryId, mrpPaise?, description?, attributes?}` | 201 `{productId, version}` | 409 `SKU_EXISTS`; 422 `SUBCATEGORY_MISMATCH`, `CATEGORY_INACTIVE`, `INVALID_ATTRIBUTES` |
| `PATCH /admin/products/{id}` + `If-Match` | any of the above + `status` | 200 | 404, 412, 422 `PRICE_ABOVE_MRP` (lowering MRP below a city price) |
| `GET /admin/products/{id}` | - | 200 card + detail + all city prices | 404 |
| `GET /admin/products?category=&subcategory=&cursor=` | - | 200 page | - |
| `PUT /admin/products/{id}/prices/{city}` | `{sellingPricePaise}` | 200 | 404; 422 `PRICE_ABOVE_MRP` |
| `POST /admin/products/{id}/image-upload-url` | `{contentType: image/jpeg\|image/png\|image/webp}` | 200 `{url, fields, imageId, expiresIn: 300}` (presigned POST, max 5 MB) | 404 |
| `PUT /admin/stores/{storeId}/products/{productId}` | `{listed, sortRank, maxPerOrder}` | 200 listing | 404 `STORE_NOT_FOUND`/`PRODUCT_NOT_FOUND`; 422 `NO_CITY_PRICE`, `PRODUCT_INACTIVE` |
| `POST /admin/stores/{storeId}/products:batch` | `{list: [{productId, sortRank, maxPerOrder}], unlist: [productId]}` (≤ 500) | 200 `{succeeded, failed: [{productId, code}]}` (partial success) | 400 if > 500 |
| `GET /admin/stores/{storeId}/products?listed=all\|true\|false&cursor=` | - | 200 page | - |

Validation: `sku` `^[A-Z0-9-]{3,40}$`; `name` 3-120 chars; `netQty` > 0 (up to 3 decimals), `netUnit` one of `g`, `kg`, `ml`, `l`, `pcs`; `attributes` ≤ 30 keys,
key `^[a-zA-Z][a-zA-Z0-9]{0,29}$`, values string (≤ 200) / number / boolean; `sortRank` 1-9999;
`maxPerOrder` 1-50; request body ≤ 64 KB.

### 3.3 Internal (`/internal/*`, IAM SigV4; callers: Ordering)
**`POST /internal/prices`** `{storeId, productIds: [≤ 35]}` → 200
```json
{ "storeId": "BLR-S-01", "city": "BLR",
  "items": [ { "productId": "P-1001", "name": "Nandini Milk (orange packet) 500 ml", "listed": true, "active": true,
               "sellingPricePaise": 2600, "mrpPaise": 2800, "maxPerOrder": 3 } ] }
```
Strongly consistent reads; never cached. Unknown or unlisted products return `listed: false`. No store
status here: Ordering takes it from Store Network.

## 4. Event schemas
All events use the [system envelope](../../system-hld.md#4-event-conventions); JSON Schemas in
`common/contracts/catalog/`. `source = "catalog"`.

| Event (`detail-type`) | Emitted when (stream mapper) | `data` |
|---|---|---|
| `ProductCreated` v1 | `META` inserted | `{productId, sku, name, brand, categoryId, subcategoryId, status, mrpPaise}` |
| `ProductUpdated` v1 | `META` modified (a `DETAIL` change always bumps `META.version` in the same transaction, so one edit gives one event; when only `version`/`updatedAt` changed, `changedFields: ["detail"]`) | `{productId, changedFields: [...], ...current card fields}` |
| `PriceChanged` v1 | `PRICE#<city>` inserted/modified | `{productId, city, oldPricePaise, newPricePaise}` |
| `AssortmentChanged` v1 | Listing `listed` false→true / true→false (grouped per store per stream batch; a product changed twice in one batch appears once, in its final state) | `{storeId, added: [{productId, categoryId, subcategoryId, maxPerOrder, listingVersion}], removed: [productId]}` |
| `ListingUpdated` v1 | `maxPerOrder` changed on a listed row | `{storeId, productId, maxPerOrder, listingVersion}`: the listing's `version`, so Inventory keeps only a newer value (SQS can deliver two quick changes out of order) |

The mapper **ignores** changes to `stockStatus`/`availableQty` (badge updates must not echo back),
`COUNT#`, `STORE`, `SKU#`, `COUNTER`, `IDEMP#` items.

**Consumed** (EventBridge rules → SQS `catalog-inbound`, DLQ after 4 receives):
| Event | Handler effect |
|---|---|
| `StockLevelChanged {storeId, productId, status, availableQty?, occurredAt, reason?}` | `UpdateItem` listing `SET stockStatus, availableQty (or REMOVE), stockAt = :occurredAt` `CONDITION attribute_exists(pk) AND (attribute_not_exists(stockAt) OR stockAt < :occurredAt)`; condition failure = stale, counted and dropped. `reason: RECONCILE` (Inventory's nightly job) uses `ReturnValues: UPDATED_OLD`; if `stockStatus` changed, it counts `BadgeCorrected` (an earlier event was lost) |
| `StoreCreated` / `StoreUpdated` / `StoreStatusChanged` | `PutItem` store copy `CONDITION attribute_not_exists(eventAt) OR eventAt < :occurredAt`. Store Network re-sends every store nightly (`StoreUpdated`, `reason: RECONCILE`), which repairs a missed event |
| `ProductUpdated` (Catalog's own; rule: `source = catalog` and `changedFields` contains `subcategoryId` or `status`) | `CategoryMoveHandler`: a move as in §5.3; a status change → per listing of the product (Query `byProduct`), one transaction: `SET productActive = :new` `CONDITION productActive <> :new` + `ADD ±1` on both `COUNT#` items, only for listed rows; duplicates fail the condition and are skipped |

## 5. Detailed flows
**5.1 Create a product**
```
POST /admin/products (Idempotency-Key k)
 1. IDEMP#k exists? same hash -> stored response · other hash -> 422
 2. validate; category tree: subcategoryId is an active subcategory whose parent == categoryId (§2.4)
 3. COUNTER ADD 1 -> P-1001
 4. TransactWriteItems: Put SKU#sku (attribute_not_exists) · Put META · Put DETAIL
      · Put IDEMP#k {requestHash, 201 response, ttl} CONDITION attribute_not_exists(pk)
      IDEMP condition fails (a parallel request with the same key won) -> read IDEMP#k:
          same hash -> its stored response · other hash -> 422
      SKU condition fails -> 409 SKU_EXISTS
 5. stream -> ProductCreated
```
A counter value used by a failed transaction leaves a gap in product numbers (harmless).
**5.2 List a product in a store**
```
PUT /admin/stores/BLR-S-01/products/P-1001 {listed: true, sortRank: 5, maxPerOrder: 3}
 1. BatchGet STORE copy (city BLR), META (ACTIVE?), PRICE#BLR (exists?)
 2. TransactWriteItems:
      ConditionCheck META CONDITION version = :readVersion AND #status = ACTIVE
          (a parallel subcategory move or deactivation cancels the write; retried from step 1)
      Update listing SET listed = true, sortRank, maxPerOrder, categoryId, subcategoryId,
             storeCategory = "BLR-S-01#dairy", subcategoryRank = "milk#0005#P-1001", productActive = true,
             stockStatus = if_not_exists(OUT)
             CONDITION attribute_not_exists(listed) OR listed = false
      Update COUNT#dairy ADD productCount 1 · Update COUNT#dairy#milk ADD productCount 1
    already listed (condition fails) -> plain update of sortRank / maxPerOrder (no count change)
 3. stream -> AssortmentChanged (or ListingUpdated) -> Inventory
```
Unlisting mirrors this: `REMOVE storeCategory, subcategoryRank`, counts `ADD -1`.
Transaction conflicts on the count items are retried with jitter (max 5). The bulk endpoint groups
items by subcategory and processes groups in parallel (concurrency 8), items within a group in order.

**5.3 Move a product to another subcategory** (rare)
```
PATCH META {subcategoryId: "flavoured-milk"} -> stream -> ProductUpdated (changedFields has subcategoryId)
 -> EventBridge rule -> catalog-inbound -> CategoryMoveHandler (events consumer; retries and DLQ as for any event): Query byProduct (all stores) -> per listed row, one transaction:
    update GSI keys CONDITION subcategoryId = :old (rows already moved are skipped) + both count pairs
 -> the nightly count rebuild (§2.2) fixes any count the handler missed
```
**5.4 Image upload**
```
admin -> POST .../image-upload-url -> presigned POST to s3://catalog-images/originals/P-1001/<imageId>
browser uploads (≤ 5 MB) -> S3 event -> catalog-thumbnail:
  read width and height from the image header (no decoding) -> reject > 4000 px per side or > 40 MP
  (decompression bombs) -> decode with ImageIO (rejects non-images; SVG not allowed)
  -> write thumbs/P-1001/<imageId>_320.webp and _800.webp
  -> UpdateItem META SET imageId = :id
       CONDITION attribute_exists(pk) AND (attribute_not_exists(imageId) OR imageId < :id)
       ReturnValues UPDATED_OLD
  -> old imageId returned -> tag originals/P-1001/<old> and thumbs/P-1001/<old>_* replaced=true;
     an S3 lifecycle rule deletes tagged objects after 1 day (browse pages cached 60 s still use them)
     condition fails (an older upload processed late) -> delete this upload's objects instead
admin UI polls GET /admin/products/{id} until imageId changes
```
`imageId` is a ULID, so it sorts by upload time and the newest image always wins. Replaced images are
deleted a day later, so the bucket holds only current images (plus a day of replaced ones).
**5.5 Browse** (see HLD 8.1) and **5.6 badge update** (see section 4).

## 6. Caching, concurrency and consistency
| Topic | Design |
|---|---|
| CloudFront cache policy (public paths) | Default TTL 60 s, max 60 s; cache key = path + query strings `category, subcategory, limit, cursor, ids`; **no cookies, no headers**; compression on. Every key part is validated before any read (fixed `limit`, signed `cursor`, sorted `ids`), so junk gets a cheap 400 instead of a new cache entry |
| Error caching | 404 cached 10 s; 5xx not cached |
| In-memory | Category tree in the Lambda for 5 min (stale ≤ 5 min after a category change) |
| Consistency | GSI reads are eventually consistent (a just-listed product can be missing for a moment); internal prices use consistent reads |
| Concurrency | `If-Match`/`version` on admin updates; conditional transactions for list/unlist; `stockAt` / `eventAt` ordering for events |
| Event duplicates | All consumers are idempotent through conditions; the publisher may emit a duplicate after a retry (consumers handle it) |

## 7. Security
| Area | Design |
|---|---|
| Public routes | No auth; CloudFront in front; API Gateway route throttling **20 req/s (burst 40) in prod**; `dev` the same, raised to 300 req/s (burst 600) only during a load test (CDK context value) |
| Admin routes | **R1: IAM authorizer in every stage.** Only the operator calls them, with their own AWS credentials (`aws login`) through the `catalog-data` scripts; throttled at 10 req/s (burst 20); never unauthenticated (D10). Later: JWT authorizer on the staff pool + role check |
| Internal routes | IAM authorizer; only Ordering's Lambda role is granted `execute-api:Invoke` on `POST /internal/prices` |
| IAM (per function) | public & internal: `dynamodb:GetItem, Query, BatchGetItem` on both tables + indexes · admin: + `PutItem, UpdateItem, ConditionCheckItem` (transactions), `s3:PutObject` on `originals/*` (for presigning) · consumer: `UpdateItem, PutItem, ConditionCheckItem` on listings (also inside transactions), `Query` on the `byProduct` index, SQS receive/delete · publisher: stream read, `events:PutEvents` on `shop-<stage>` only · thumbnail: `s3:GetObject originals/*`, `s3:PutObject thumbs/*`, `s3:PutObjectTagging` and `s3:DeleteObject` on `originals/*, thumbs/*`, `UpdateItem` products · count rebuild: `Query` + `UpdateItem` on listings, `BatchGetItem` on products (counts need each product's status; it also corrects `productActive`) · images bucket: lifecycle rule deletes objects tagged `replaced=true` after 1 day |
| Input validation | Bean Validation on every DTO; ID patterns (`^P-\d{4,10}$`, `^[A-Z]{3}-[A-Z]-\d{2,3}$`: up to 999 stores per city zone); body ≤ 64 KB; unknown fields rejected; cursors checked against the request |
| Images bucket | Block public access, bucket-owner-enforced, SSE-S3, TLS-only policy; Catalog's own CloudFront distribution reads **only `thumbs/*`** through origin access control; `originals/` never public; presigned POST limits size and content type |
| Data | No personal data in Catalog |
| Supply chain | Dependabot + `gitleaks`; image decoding only through the JDK (no native libraries) |

## 8. Observability
| Type | Details |
|---|---|
| Logs | Powertools JSON: `correlationId, function, route, storeId, statusCode, latencyMs, coldStart`; no request bodies |
| Metrics | Built-in Lambda, API Gateway, DynamoDB and CloudFront metrics for latency, errors, throttles, read units and cache hits (free). **Custom metrics** (namespace `ShopLite/Catalog`, prod only, no `storeId`/`productId` dimensions; [metrics budget](../../system-hld.md#7-cost-budget)): `BadgeCorrected`, `CountCorrected`, `BadgeUpdatesStale`, `ThumbnailFailures`, `PublisherBatchFailures`. Everything else (products returned, listing changes, category moves, badge updates applied) comes from the JSON logs with Logs Insights |
| Traces | X-Ray on all functions |
| Alarms | public p99 > 500 ms (5 min) · 5xx > 1% · DLQ > 0 · oldest SQS message > 60 s · stream iterator age > 60 s · thumbnail errors > 0 · DynamoDB throttles > 0 · `BadgeCorrected` > 0 · `CountCorrected` > 0 · **consumed read units > 1 M in an hour** on either table (≈ $0.14 at the Sydney price; runbook: lower the public throttle to 1 req/s) |
| Dashboard | "Catalog" section on the system dashboard: traffic, latency, errors, cache hit ratio (CloudFront), consumer lag |

## 9. Capacity estimates
| Item | R1 (1 store) | At scale (3,000 stores) |
|---|---|---|
| Products | ~5,000 × (~300 B META + ~1.5 KB DETAIL) ≈ 9 MB | 80,000 ≈ 150 MB |
| Listings | ~2,000 × ~350 B ≈ 0.7 MB | ~24 M ≈ 8 GB |
| Browse load (dev load test) | 300 req/s, ~80% CloudFront hits → ~60 origin req/s × ~21 RRU ≈ 1,300 RRU/s | per store traffic similar; hot products cached |
| Prod worst case (20 req/s per route, every request a cache miss) | ≈ 20 × 21 RRU (category page) to 20 × 52 RRU (35-id cart lookup) ≈ 400-1,000 RRU/s ≈ $5-13 a day; the hourly read-units alarm fires within the hour | same per route (throttles are per route, not per store) |
| Writes | Badge updates ~4 per product per day; admin edits | ~100 M listing updates/day only if every product changes status 4×/day: still within on-demand limits |
| Lambda | ~60 concurrent at the load-test peak | The account limit was **10** on 2026-11-22 (new-account default); the requested increase to 1,000 (D14) must be granted before the load test |

Cost of a 10-minute load test: ~800 K read units ≈ $0.11 at $0.1425 per million in Sydney (checked 2026-11-22).

## 10. Testing strategy
| Level | What |
|---|---|
| Unit | Price ≤ MRP, visibility rule, sort-key padding, cursor validation, stream event mapping (incl. ignored badge changes) |
| Integration | Testcontainers + DynamoDB Local: repositories, list/unlist transactions and counts, GSIs, idempotency, optimistic locking |
| Contract | `openapi.yaml` validated in the build; emitted events validated against `common/contracts` schemas; Ordering's expectations of `/internal/prices` as a contract test |
| Security | Admin routes reject unsigned requests (IAM) now, and missing/invalid tokens once staff auth exists; oversized bodies; bad IDs; SVG/fake images and oversized image headers rejected; forged cursors, other `limit` values and unsorted `ids` → 400 without a DynamoDB read |
| Load | k6: 300 req/s browse mix for 10 min in dev (throttle raised for the test only); p99 and error targets |
| Smoke (pre-traffic hook) | **dev:** create category → product → price → list in the test store `BLR-S-99` (dev seed, always `SETUP`, so never visible) → admin and internal reads return it → unlist. **prod: read-only:** categories and a seed product page in BLR-S-01, internal prices for a seed product, `GET /admin/products/{seed}` (IAM). A test never writes prod data: categories and products are never deleted, and a listing in an open store is seen by customers |

## 11. Rollout and migration
- Deploy order ([ADR-0014](../../adr/0014-common-repo-for-shared-infrastructure.md)): `common`
  foundation (event bus) → Store Network (store events) → `catalog-infra` data stack → service stack
  (publishes its SSM outputs) → seed data from `catalog-data` → `common` edge (adds `/api/catalog/*`
  and `/mfe/catalog/*` now that the SSM parameters exist).
- Lambda aliases with CodeDeploy: a **pre-traffic hook runs the smoke test** (read-only in prod, §10) against the new version
  before traffic moves, then all traffic shifts at once (at R1 traffic a 10% canary would see almost no
  requests and prove nothing); rollback on hook failure or on alarms in the next 10 minutes.
- Schema changes are additive (new attributes, new GSIs); removals follow expand → migrate → contract.
- R1 seed, loaded by the operator script from `catalog-data` through the admin API (IAM): top-level categories + subcategories (incl. default `<category>-all` ones and `other` / `other-all`), ~200 sample products, BLR prices, all listed in BLR-S-01.

## 12. Infrastructure (CDK, `catalog-infra`)
| Stack | Resources |
|---|---|
| `CatalogData-<stage>` (stateful, termination protection in prod) | Two tables + GSIs, images bucket |
| `CatalogService-<stage>` | Seven Lambda functions, HTTP API (routes; IAM authorizer on internal and admin routes, the staff JWT authorizer later; throttling), nightly count-rebuild schedule, SQS `catalog-inbound` + DLQ, EventBridge rules, stream event source mappings, images CloudFront distribution (OAC), alarms, dashboard widgets |
| `CatalogPipeline` | CodePipeline: GitHub source (CodeConnections) → build + unit/integration tests → deploy dev → smoke + contract tests → manual approval → deploy prod |

Outputs published to SSM Parameter Store for other teams: `/shop/<stage>/catalog/api-url`,
`/shop/<stage>/catalog/images-url`, `/shop/<stage>/catalog/ui-bucket` (read by the `common` edge
stack and the BFF route map).

## Change log
| Date | Change | Why | Approved |
|---|---|---|---|
| 2026-11-21 | v0.1 first LLD | Detailed design requested before development | For review |
| 2026-11-21 | v0.2: category rules (§2.4: one home per product, default `<category>-all` subcategory, "Other", `CATEGORY_IN_USE`); admin routes IAM-only until staff auth; thumbnail worker deletes replaced images (ULID order) | Your category question; [design review log §12](../../design-review-log.md#12-design-review-fixes) | For review |
| 2026-11-21 | v0.3 (round-2 fixes): customer and staff UI as separate bundles (admin code never shipped to customers; scripts until the staff pool); deploy order with the `common` foundation and edge stacks; UI bucket in SSM; `BadgeCorrected` metric and alarm for Inventory's reconciliation | [Design review log §13](../../design-review-log.md#13-design-review-fixes-round-2) (FE-12, BE-11, BE-7) | For review |
| 2026-11-22 | v0.4 (round-3 fixes): prod throttling 20 req/s per public route; fixed `limit` values, HMAC-signed cursors and sorted `ids` validated before any read; hourly read-units alarm; create-product idempotency race closed (`IDEMP#` condition in the transaction); list transaction checks `META`; move handler conditioned; counts = listed and active products, nightly rebuild (`CountCorrected`); `ListingUpdated`/`AssortmentChanged` carry `listingVersion`; 404 details for "Browse similar"; store copy repaired by Store Network's nightly re-send; product ETag = `META` version; replaced images deleted after a day; image size checked from the header; pack size as `netQty` + `netUnit`; no `storeStatus` in internal prices; store ID pattern; metrics budget; pre-traffic smoke hook; admin API for operator scripts in every stage (D10); tolerant reader | [Design review log §14](../../design-review-log.md#14-design-review-fixes-round-3) (H-1, H-2, M-3, M-5, M-6, M-7, M-8, M-10, M-16, M-17, L-1 to L-9) | For review |
| 2026-11-22 | v0.4 AWS checks: the account's Lambda limit was 10, so the load test waits for the requested increase (D14); load-test read cost $0.11 at the Sydney price; prod worst case confirmed | [Design review log §15](../../design-review-log.md#15-aws-checks) | Applied 2026-11-22, for review |
| 2026-11-22 | v0.5 (walkthrough fixes): products routes refuse `SETUP`/`CLOSED` stores (store copy read); prod smoke test read-only, full write test in `dev` in the hidden store `BLR-S-99`; subcategory moves and status-change counts run in the events consumer on Catalog's own `ProductUpdated` (publisher stays publish-only), made idempotent with `productActive`; count rebuild may read products; one `ProductUpdated` per edit; header points to HLD v0.6 | [log §16](../../design-review-log.md#16-catalog-lld-walkthrough-and-customer-store-decisions) | Applied 2026-11-22, for review |
