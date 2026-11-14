# Store Network & Serviceability - High-Level Design

**Status:** Draft v0.2 - in review · **Owner:** Logistics team · **Last updated:** 2026-11-14
**Reviewers:** Architecture, Catalog and Commerce teams (main consumers)
**Requirements:** [requirements.md](requirements.md) · **Builds on:** [system HLD platform defaults](../../system-hld.md#3-platform-defaults)

## 1. Summary
Answers one question for the whole product: **"Which dark store serves this delivery address, and
is it open right now?"** Called when a customer opens the app or changes address, and again by
Checkout before every order. Also lets admins manage stores, delivery zones and opening hours.

## 2. Goals and non-goals
**Goals (R1):** STN-01 to STN-05.
**Non-goals:** automatic pausing (R3), map editor, travel-time zones, multiple cities
([parking lot](../../parking-lot.md)).

## 3. Context
```
 Web app ── GET /serviceability ──┐                 ┌── Admin UI: stores, zones, hours, pause
 Checkout ─ GET /internal/... ────┤                 │
                                  v                 v
                         +--------------------------------+
                         |  Store Network (one Lambda app) |
                         +--------------------------------+
                           |          |              |
                       DynamoDB      S3        EventBridge: StorePaused, ZoneSetPublished,
                    (stores, status) (zone maps)  ServiceabilityMiss -> Catalog, Checkout, Analytics
```

## 4. What drives the design
| Driver | Consequence |
|---|---|
| Called on every session and every checkout | Must be fast and highly available |
| Only 10 stores; the zone map is a few KB | Keep the whole map **in memory**; no database query per lookup |
| Same address must give the same store in the app and in Checkout | Deterministic tie-breaks + a zone **version** in every answer |
| Zones change rarely; status can change any time | Zones as immutable versioned files; status as a small, quickly-read record |

## 5. Architecture
```
Lookup (hot path)
  request -> API Gateway -> Lambda
     1. zone map in memory (JTS spatial index), loaded from S3 for the CURRENT version
     2. point-in-polygon -> matching zones -> pick highest priority, then lowest storeId
     3. store status from DynamoDB (cached in memory ~15 s)
     4. reply {serviceable, storeId, status, opensAt, etaMinutes, zoneVersion}
  every ~60 s (and right after a SnapStart restore): read the CURRENT pointer; reload if changed

Admin (rare)
  upload GeoJSON -> validate (valid polygons, every store has one zone, overlaps have distinct
  priorities) -> saved as DRAFT version -> preview (which test addresses change store)
  -> publish: file to S3 (immutable) -> CURRENT pointer in DynamoDB -> ZoneSetPublished
  rollback = publish an older version again
```

| Component | Choice | Why |
|---|---|---|
| Compute | One Spring Boot app on Lambda (SnapStart), separate routes for public, internal and admin | Platform default; tiny, spiky workload |
| Geometry | JTS (Java Topology Suite) | Mature, in-process point-in-polygon and polygon validation |
| Zones | GeoJSON per version in S3 | Immutable, easy rollback, human-readable |
| Status, stores, pointer | DynamoDB | Fast single-item reads, no idle cost |

## 6. Data model
**DynamoDB `store-network-<stage>`** (single table)
| PK | SK | Attributes |
|---|---|---|
| `STORE#BLR-S-04` | `PROFILE` | name, area, lat, lng, address, zonePriority, timezone `Asia/Kolkata` |
| `STORE#BLR-S-04` | `HOURS` | per weekday opens/closes |
| `STORE#BLR-S-04` | `STATUS` | `OPEN` / `PAUSED` / `CLOSED`, reason, until, updatedAt, version (conditional updates) |
| `ZONESET` | `V#0007` | s3Key, checksum, state `DRAFT`/`PUBLISHED`, createdBy, publishedAt |
| `ZONESET` | `CURRENT` | version 7 |
| `WAITLIST#<rough area>` | `<timestamp>#<id>` | email (personal data), rough location only |

**S3:** `zones/v0007.geojson`: a FeatureCollection, one Feature per store
(`properties: {storeId, priority}`).

**Status rule:** effective status = `PAUSED` if paused, else `CLOSED` outside opening hours, else `OPEN`.

## 7. Interfaces
See the [README](README.md) for the full API and event tables. Design rules:
- Lookups need only `lat`/`lng`; nothing the client sends about stores is trusted.
- Internal lookups (Checkout) use IAM; public lookups are rate-limited at API Gateway.
- Every answer includes `zoneVersion` so callers can detect disagreements during a publish.

## 8. Key flows
**8.1 Customer picks a delivery address**
```
App -> GET /serviceability(address lat/lng) -> BLR-S-04, OPEN, ETA 25, zoneVersion 7
App -> Catalog GET /stores/BLR-S-04/products
Not served -> "We don't deliver here yet" -> optional POST /waitlist; ServiceabilityMiss
```
**8.2 Checkout re-check**
```
Checkout -> Identity: lat/lng for addressId -> GET /internal/serviceability
  same store + OPEN -> continue · other store -> 409 STORE_CHANGED · PAUSED/CLOSED -> 409 STORE_UNAVAILABLE
```
**8.3 Publish zones**
```
upload v8 -> validate -> preview -> publish -> S3 v8 + CURRENT=8 -> ZoneSetPublished
-> Lambdas reload within ~60 s -> answers carry zoneVersion 8 · rollback: publish v7
```
**8.4 Pause**
```
store manager pauses -> STATUS=PAUSED -> StorePaused -> lookups show PAUSED within ~15 s,
Checkout blocks orders, Catalog shows a banner
```

## 9. Failure handling
| Failure | Effect | Handling |
|---|---|---|
| S3 unreadable at cold start | No zone map | Use the last-known-good zone file packaged with the deployment; alarm |
| DynamoDB status unreadable | Status unknown | **Browsing fails open** (assume OPEN, flag `statusUnknown`); **internal/checkout lookups fail closed** (503, customer retries) |
| Bad zone published (e.g. wrong store gets an area) | Wrong store shown | "Not served" rate alarm + preview step; roll back by re-publishing the previous version |
| Two admins publish at once | Race | Conditional write on `CURRENT` (expected version) |

## 10. Non-functional design
| Concern | Design |
|---|---|
| Latency | In-memory check (microseconds) + cached status: p99 < 50 ms in the service |
| Availability | Depends only on Lambda, DynamoDB and S3 (all multi-AZ regional services); 99.9% target |
| Consistency | Zone changes reach all instances within ~60 s; status within ~15 s; Checkout handles mismatches |
| Borders | A point on a boundary counts as inside; overlaps go to higher priority, then lower storeId |
| Security | Admin routes need admin/store_manager groups; publishes record who and when; coordinates rounded in logs (~110 m) and events (~5 km); waitlist emails encrypted and deletable |
| Cost | Cents per month (per-request services + S3) |
| Observability | Metrics: lookups, served vs not-served rate, latency, zone version + age per instance, status cache hit rate. **Alarms:** not-served rate jumps > 3x baseline (bad publish), zone file older than CURRENT for > 10 min, 5xx > 1%, p99 > 100 ms |

## 11. Alternatives considered
| Option | Decision |
|---|---|
| Postgres + PostGIS query per lookup | v0.1 design. Rejected for R1: adds a database to the customer path for 10 polygons. Upgrade path if zones become large |
| Nearest store within a radius | Rejected: ignores roads; overlapping claims |
| H3 hexagon grid | Rejected: built for large scale |
| Amazon Location Service geofences | Rejected: built for tracking moving devices with events, not request/response lookups (verify) |

## 12. Risks and open questions
1. SnapStart restores a snapshot that may contain an old zone map: reload check must run right
   after restore (verify the restore hook in the AWS docs).
2. Zone editing in R1 = upload a GeoJSON file drawn in a free map tool; is that acceptable?
3. ETA is a fixed number per store in R1 (e.g. 25 min); live ETA in R3.

## Change log
Record every design change here with its reason ([scope control](../../scope-control.md)).

| Date | Change | Why (story / requirement) | Approved |
|---|---|---|---|
| 2026-11-14 | v0.1 first draft (PostGIS write side + S3 snapshot + DynamoDB status) | - | - |
| 2026-11-14 | v0.2: removed Postgres/PostGIS; zones as versioned GeoJSON evaluated in memory; stores + status in DynamoDB | Simplification: 10 tiny polygons; one less database on the customer path; budget | Pending review |
