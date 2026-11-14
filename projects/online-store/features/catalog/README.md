# Catalog & Search

> What we sell, at what price, and what **your** store has: browsing, product pages, images,
> and (R2) fast search.

| | |
|---|---|
| **Owner team** | Catalog |
| **Status** | HLD draft v0.1 - in review |
| **Release** | R1 (browse, product pages, admin, images) · R2 (search, caching) |
| **Stack** | Java (Spring Boot 3 on Lambda + SnapStart), Aurora PostgreSQL (Data API), S3 + CloudFront; R2: OpenSearch, ElastiCache |
| **Jira** | [STORE board](https://bhatvinayaka312.atlassian.net/jira/software/projects/STORE/boards/2) · Component `Catalog` · Epic: TBD |

## What it does
- City-wide **product master**: name, brand, unit, description, category, price (in paise),
  images.
- Per-store **assortment**: which products each of the 10 stores lists.
- Per-store **availability copy** (in stock / few left / out), kept up to date from Inventory events.
- Store-scoped browsing: a customer only ever sees what their serving store lists.
- Merchandiser admin: create/edit products, upload images, manage assortment.

## Scope by release
| Release | In scope |
|---|---|
| R1 | Categories, product list/detail per store, availability flags, admin, image upload + thumbnails, internal price lookup |
| R2 | Search (keyword, filters, autocomplete) with OpenSearch; Redis cache for hot pages (both as learning stints) |
| Parking lot | Per-store pricing, recommendations, reviews |

## Owns (data)
| Data | Store |
|---|---|
| Products, categories, prices, assortment, availability copy | Aurora PostgreSQL database `catalog` (shared cluster, ADR-0011) |
| Product images + thumbnails | S3 `catalog-images-<stage>` behind CloudFront |
| Search index (R2) | OpenSearch (read model, rebuildable) |

## APIs
| Method + path | Called by | Auth | Purpose |
|---|---|---|---|
| `GET /stores/{storeId}/categories` | Web app | Public | Categories that have products in this store |
| `GET /stores/{storeId}/products?category=&cursor=` | Web app | Public | Product list for the store (paginated) |
| `GET /stores/{storeId}/products/{productId}` | Web app | Public | Product page; **404 if the store does not list it** |
| `GET /stores/{storeId}/search?q=&filters=` (R2) | Web app | Public | Search within the store |
| `POST /internal/prices` (batch of productIds + storeId) | Cart & Checkout | IAM | Current prices + listed flag, used at checkout |
| `GET /internal/products/{productId}` | Procurement, Support | IAM | Product master data |
| `POST/PUT /admin/products` · `POST /admin/products/{id}/image-upload-url` | Admin UI | merchandiser | Manage products, presigned S3 upload |
| `PUT /admin/stores/{storeId}/assortment` | Admin UI | merchandiser | List / unlist products in a store |

## Events published
| Event | When | Key data | Consumers |
|---|---|---|---|
| `ProductCreated` / `ProductUpdated` | Product change | productId, name, category, price | Search indexer (R2), Procurement, Analytics |
| `PriceChanged` | Price change | productId, oldPrice, newPrice | Analytics |
| `AssortmentChanged` | Store lists/unlists products | storeId, added[], removed[] | **Inventory** (creates stock records), Analytics |

## Events consumed
| Event | From | Effect |
|---|---|---|
| `StockLevelChanged` | Inventory | Update availability copy for (store, product) |
| `StoreCreated` | Store Network | Create an empty assortment for the store |
| `StorePaused` / `StoreResumed` | Store Network | Store banner flag |

## Service levels
| Measure | Target |
|---|---|
| Browse latency | p99 < 300 ms (warm), R2 with cache < 100 ms |
| Search latency (R2) | p99 < 500 ms |
| Availability flag freshness | < 10 s after a stock change |
| Load test | 300 browse requests/s |

## Links
| What | Link |
|---|---|
| Repos | Planned (created when development starts) in [bhatvinayaka-store](https://github.com/bhatvinayaka-store): `catalog-backend`, `catalog-web`, `catalog-infra`, `catalog-data` · find them with topic `feature-catalog` |
| Pipeline | TBD (Catalog team pipeline) |
| Dashboard section | Prod system dashboard -> "Catalog" |
| Runbook | TBD |

## Local setup
1. `docker compose up` -> PostgreSQL 16 + LocalStack-style S3 (or MinIO)
2. Run migrations, then `scripts/seed-catalog` (sample products from `data/seed/`)
3. Run the Spring Boot app locally (JDBC locally, Data API in AWS behind one repository interface)

## Documents
- [Requirements](requirements.md) · [High-level design](hld.md) · [Decisions](adr/)
- Low-level design: written when development of this feature starts (kept in sync with what is built, see [scope control](../../scope-control.md))
