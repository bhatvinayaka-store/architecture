# Catalog & Search

> What we sell, at what price in your city, and what **your** store has: browsing, product pages,
> images, purchase limits and stock badges. Search comes later.

| | |
|---|---|
| **Owner team** | Catalog |
| **Status** | HLD v0.6 agreed, round-3 fixes 2026-11-22 for review · LLD v0.4 for review |
| **Release** | R1 (browse, product pages, admin API for operator scripts, images, city prices, listings) · Later (search, staff screens) |
| **Stack** | Java (Spring Boot 3 on Lambda + SnapStart), DynamoDB (2 tables), S3 + CloudFront (images + 60 s browse cache) |
| **Jira** | [STORE board](https://bhatvinayaka312.atlassian.net/jira/software/projects/STORE/boards/2) · Component `Catalog` · Epic: TBD |

## What it does
- City-wide **product master**: name, brand, pack size (`netQty` + `netUnit`, e.g. 500 ml), description,
  category → subcategory, images, and attributes that differ per product type (e.g. fat %).
- **Selling prices per city** (paise), never above the product's **MRP** (packaged goods).
- **Category tree** (e.g. Dairy → Milk, Curd, Paneer).
- Per-store **listings**: which products each store sells, sort order, and **`maxPerOrder`**
  (the purchase limit, which also triggers "only N left").
- A copy of each listing's **stock badge** (`IN` / `FEW` + count / `OUT`) received from Inventory,
  and of each store's status and city received from Stores.
- Store-scoped browsing: a customer only ever sees what their store lists; stores in `SETUP` or
  `CLOSED` are invisible.
- Admin API for products, categories, city prices, images and listings (single and bulk), used by the
  operator's scripts in R1 (staff screens later). Soft delete only.

## Scope by release
| Release | In scope |
|---|---|
| R1 | Categories, products, city prices, images + thumbnails, listings incl. bulk and `maxPerOrder`, store-scoped browse and product pages, stock badges from Inventory, internal price lookup, CloudFront cache. One store (`BLR-S-01`) |
| Later | Search (keyword, filters, autocomplete) with OpenSearch; hosting decided then |
| Parking lot | Recommendations, reviews, product variants grouped on one card |

## Owns (data)
| Data | Store |
|---|---|
| Products, city prices, categories | DynamoDB `catalog-products-<stage>` |
| Listings (+ `maxPerOrder`, stock badge copy), category counts, store status copy | DynamoDB `catalog-store-listings-<stage>` |
| Product images + thumbnails | S3 `catalog-images-<stage>` behind CloudFront |
| Search index (later) | OpenSearch (read model, rebuildable) |

## APIs
Auth: public routes open (cached, through CloudFront; throttled at 20 req/s in prod); admin routes IAM-only, called by the operator's scripts in every stage until the staff side (D10); never unauthenticated.

| Method + path | Called by | Purpose |
|---|---|---|
| `GET /stores/{storeId}/categories` | Web app | Categories (with counts) that have products in this store |
| `GET /stores/{storeId}/products?category=&subcategory=&cursor=` | Web app | Products of the store, optionally by category / subcategory |
| `GET /stores/{storeId}/products/{productId}` | Web app | Product page (selling price, MRP, stock badge, `maxPerOrder`); **404 if the store does not list it**, with the reason and the product's category for "Browse similar" |
| `GET /stores/{storeId}/products?ids=` | Web app (cart page) | Up to 35 products by id |
| `POST/PATCH/GET /admin/categories` | Operator script (R1) | Manage categories (deactivate, no delete) |
| `POST/PATCH/GET /admin/products` · `GET /admin/products?category=` | Operator script (R1) | Manage products (`status: INACTIVE`, no delete) |
| `PUT /admin/products/{id}/prices/{city}` | Operator script (R1) | Set the city price |
| `POST /admin/products/{id}/image-upload-url` | Operator script (R1) | Presigned S3 upload |
| `PUT /admin/stores/{storeId}/products/{productId}` | Operator script (R1) | List / unlist, sort rank, `maxPerOrder` |
| `POST /admin/stores/{storeId}/products:batch` | Operator script (R1) | Bulk list / unlist (opening a store) |
| `GET /admin/stores/{storeId}/products?listed=all` | Operator script (R1) | All listings of a store |
| `POST /internal/prices` | Ordering | Trusted selling prices, MRP, listed flags and `maxPerOrder` (preview and checkout) |

## Events published
| Event | When | Key data | Consumers |
|---|---|---|---|
| `ProductCreated` / `ProductUpdated` | Product change | productId, name, categoryId, status | Search indexer (later), Analytics |
| `PriceChanged` | City price change | productId, city, old/new price | Analytics |
| `AssortmentChanged` | Store lists / unlists products | storeId, added [{productId, categoryId, maxPerOrder, listingVersion}], removed | **Inventory** (creates stock rows), Analytics |
| `ListingUpdated` | `maxPerOrder` changed | storeId, productId, maxPerOrder, listingVersion | **Inventory** (updates its copy if newer) |

## Events consumed
| Event | From | Effect |
|---|---|---|
| `StockLevelChanged` | Inventory | Update the listing's stock badge (status, count when few left) |
| `StoreCreated` / `StoreUpdated` / `StoreStatusChanged` | Stores | Update the store copy (status, city, name); a nightly re-send repairs missed events |

## Service levels
| Measure | Target |
|---|---|
| Browse latency | p99 < 300 ms (Lambda, warm); CloudFront hits < 100 ms |
| Stock badge freshness | ≤ ~60 s after a status change (event + cache) |
| Load test | 300 browse requests/s (in dev; prod is throttled at 20 req/s per route) |

## Links
| What | Link |
|---|---|
| Repos | Planned (created after the design is finalised) in [bhatvinayaka-store](https://github.com/bhatvinayaka-store): `catalog-backend`, `catalog-web`, `catalog-infra`, `catalog-data` · find them with topic `feature-catalog` |
| Pipeline | TBD (defined in the team's CDK package) |
| Decisions | [Catalog ADR-0001](adr/0001-dynamodb-two-tables.md), [ADR-0017](../../adr/0017-stock-badge-ownership.md), [design review log](../../design-review-log.md#3-catalog) |
| Runbook | TBD |

## Local setup
1. `docker compose up` -> DynamoDB Local + MinIO (S3)
2. `scripts/create-tables` then `scripts/seed-catalog` (sample products from `data/seed/`)
3. Run the Spring Boot app locally (AWS SDK pointed at DynamoDB Local); UI in standalone mode with `npm run dev`

## Documents
- [Requirements](requirements.md) · [High-level design](hld.md) · [Low-level design](lld.md) · [Decisions](adr/)
- The LLD is kept in sync with what is built (see [scope control](../../scope-control.md))
