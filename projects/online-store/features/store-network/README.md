# Store Network & Serviceability

> Knows every dark store and its delivery zone, and answers: **"which store serves this delivery
> address, and is it open?"**

| | |
|---|---|
| **Owner team** | Logistics |
| **Status** | HLD draft v0.2 - in review |
| **Release** | R1 (stores, zones, hours, manual pause) · R3 (automatic pause) |
| **Stack** | Java (Spring Boot 3 on Lambda + SnapStart), JTS geometry library, DynamoDB, S3 |
| **Jira** | [STORE board](https://bhatvinayaka312.atlassian.net/jira/software/projects/STORE/boards/2) · Component `Logistics` · Epic: TBD |

## What it does
- Keeps the list of the 10 Bengaluru South dark stores (BLR-S-01 ... BLR-S-10): location,
  opening hours, status.
- Holds each store's **delivery zone** (a polygon drawn on the map) and publishes versioned zone maps.
- Answers serviceability lookups for the app (every session / address change) and for Checkout
  (before every order).
- Collects a waitlist for addresses no store serves yet.

## Scope by release
| Release | In scope |
|---|---|
| R1 | Store list, zones (GeoJSON upload), opening hours, manual pause/resume, lookup API, waitlist |
| R3 | Automatic pause when Fulfillment reports no free riders; live ETA from Fulfillment |
| Parking lot | Map editor, travel-time zones, multiple cities |

## Owns (data)
| Data | Store |
|---|---|
| Stores, hours, status, zone-set metadata, waitlist | DynamoDB `store-network-<stage>` |
| Zone maps (one GeoJSON file per version) | S3 `store-network-zones-<stage>` (versioned, immutable) |

## APIs
| Method + path | Called by | Auth | Purpose |
|---|---|---|---|
| `GET /serviceability?lat=&lng=` | Web app | Public (rate limited) | Which store serves this point, its status and ETA |
| `GET /internal/serviceability?lat=&lng=` | Cart & Checkout | IAM | Same answer, for server-side checks |
| `GET /stores`, `GET /stores/{storeId}` | Web app, other teams | Public / IAM | Store info |
| `POST /waitlist` | Web app | User JWT | Join the waitlist for an unserved address |
| `POST /admin/stores`, `PUT /admin/stores/{storeId}` | Admin UI | Admin group | Manage stores |
| `PUT /admin/stores/{storeId}/hours` | Admin / store manager | Admin, store_manager | Opening hours |
| `POST /admin/stores/{storeId}/pause` · `/resume` | Store manager | store_manager | Pause/resume a store |
| `POST /admin/zonesets` (upload GeoJSON) · `POST /admin/zonesets/{v}/publish` | Admin | Admin | Draft, validate and publish zones; re-publish an old version to roll back |

## Events published
| Event | When | Key data | Consumers |
|---|---|---|---|
| `StoreCreated` / `StoreUpdated` | Store added or changed | storeId, name, area, location | Catalog, Inventory, Fulfillment |
| `ZoneSetPublished` | New zone version live | version | Catalog (optional), Analytics |
| `StorePaused` / `StoreResumed` | Status change | storeId, reason, until | Catalog (banner), Checkout |
| `ServiceabilityMiss` | Lookup found no store | rough area (~5 km), time | Analytics |

## Depends on
- None in R1. R3: rider availability from Fulfillment.

## Service levels
| Measure | Target |
|---|---|
| Lookup latency | p99 < 50 ms in the service, < 150 ms end to end |
| Availability | 99.9% |
| Zone publish visible everywhere | < 2 minutes |
| Pause visible to customers | < 30 seconds |

## Links
| What | Link |
|---|---|
| Repos | Planned (created when development starts) in [bhatvinayaka-store](https://github.com/bhatvinayaka-store): `store-network-backend`, `store-network-infra` · find them with topic `feature-store-network` |
| Pipeline | TBD (Logistics team pipeline) |
| Dashboard section | Prod system dashboard -> "Store Network" |
| Runbook | TBD |

## Local setup
1. `aws login --profile <your-profile>` (only needed to call real AWS from local)
2. `docker compose up` -> DynamoDB Local + a local S3 (e.g. MinIO); seed with `data/seed/zones-v1.geojson`
3. Run the Spring Boot app locally (`./gradlew bootRun`); same code runs on Lambda

## Documents
- [Requirements](requirements.md) · [High-level design](hld.md) · [Decisions](adr/)
- Low-level design: written when development of this feature starts (kept in sync with what is built, see [scope control](../../scope-control.md))
