# Store Network & Serviceability - High-Level Design

**Status:** Draft v0.6 - agreed in design review; round-3 fixes 2026-11-22 for review · **Owner:** Logistics team · **Last updated:** 2026-11-22
**Requirements:** [requirements.md](requirements.md) · **Builds on:** [system HLD platform defaults](../../system-hld.md#3-platform-defaults) · **Decisions:** [design review log](../../design-review-log.md#4-stores-store-network-minimal-for-r1), [ADR-0009](../../adr/0009-delivery-zones-as-polygons.md)

## 1. Summary
The single source of truth for **which dark stores exist, where they are, and whether they can
take orders**, and the answer to **"which store serves this delivery address?"**, with the other stores in range as backups (one store per order). R1 is minimal:
store details, a status lifecycle, and serviceability by **geohash + radius**. Delivery zone
polygons, the waitlist and automatic pausing come later. R1 builds the API, data and infra; the admin UI comes with the staff side (operator scripts until then).

## 2. Goals and non-goals
**Goals (R1):** STN-01 to STN-05, STN-07, STN-08.
**Later:** delivery zone polygons, waitlist, `ServiceabilityMiss` analytics, automatic pause (STN-06), live ETA.
**Non-goals:** products, stock, orders (Catalog, Inventory, Ordering).

## 3. Context
```
 Web app ── POST /serviceability ────────┐            ┌── Operator scripts (R1; admin UI later): create / update / open / pause / close
 Ordering ─ POST /internal/serviceability┤            │
                                         v            v
                              Store Network API (Lambda) ──> DynamoDB stores-<stage> (+ byGeohash index)
                                         |
                                         └─> EventBridge: StoreCreated, StoreUpdated, StoreStatusChanged
                                               -> Catalog (store copy), later Fulfillment
```

## 4. What drives the design
| Driver | Consequence |
|---|---|
| Lookup on every session and every checkout | Fast, highly available, no full scan |
| Must work for ~3,000 stores | **Geohash** shortlist instead of checking every store |
| A new store needs setup before customers see it | `SETUP` status, invisible to customers |
| Orders, stock and reports refer to stores forever | No delete: `CLOSED` keeps history |
| Prices are per city | Every store has a `city` |
| Stores keep different opening hours | Serviceability returns **every store in range** with its status and hours; one choice rule (§5) picks the serving store for the app and for checkout |

## 5. Architecture
| Component | Choice | Why |
|---|---|---|
| API | Spring Boot 3 on Lambda (SnapStart), public + internal + admin routes, own API URL | [ADR-0016](../../adr/0016-spring-boot-on-lambda.md) |
| Data | DynamoDB `stores-<stage>`, one item per store, index `byGeohash` | Single-item reads; geohash shortlist |
| Geohash | A Java geohash library; precision 5: cells ≈ 4.8 km wide × 4.9 km high in Bengaluru (narrower further north) | Standard, no custom tree |
| Distance | Haversine formula (exact check on candidates) | Cells are squares; delivery areas are circles |
| Store re-send | EventBridge Scheduler nightly (03:15 IST) → Lambda sends `StoreUpdated {…, reason: RECONCILE}` for every store | Repair path for Catalog's store copy if an event was lost ([platform rule](../../system-hld.md#3-platform-defaults)) |

**Serviceability algorithm**
```
pin (lat, lng) -> geohash5 -> the cell + its 8 neighbours (stores near a cell edge)
 -> 9 parallel Queries on byGeohash -> candidate stores (a handful)
 -> keep status OPEN or PAUSED and distance <= store.deliveryRadiusM
 -> stores[]: all of them, nearest first, each with status, openNow, opensAt, distanceM
 -> serving store = choice rule (below) -> SERVICEABLE / TEMPORARILY_UNAVAILABLE / NOT_SERVICEABLE
```
**Choice rule** (one implementation, used for the app and for checkout, so both always agree):
1. The nearest store that is `OPEN` and **open now**.
2. With `keepStoreId` (the store of a cart that has items): that store is kept as long as it is in
   range, `OPEN` and open now. When it stops serving (closes for the day, pauses, shuts down, radius
   changed), the nearest other store open now takes over and the cart moves, with a message.
3. No store open now: the kept store if it is `OPEN` (the customer sees "Opens at 7:00 AM"),
   otherwise the nearest `OPEN` store; no `OPEN` store but a `PAUSED` one →
   `TEMPORARILY_UNAVAILABLE`; nothing in range → `NOT_SERVICEABLE`.

The store never moves back to a nearer one while the cart has items, so nobody is bounced between
stores at opening time (flow 8.4). **One store per order:** combining several stores' products in
one order is in the [parking lot](../../parking-lot.md).

**Delivery radius cap:** the cell + 8 neighbours always contain every store within one cell's
smaller side of the pin (≈ 4.77 km in Bengaluru). So the radius is capped at **95% of that side at
the store's location: 4,500 m in Bengaluru** (≈ 4,100 m in Delhi), computed when the store is saved;
larger values are rejected.

## 6. Data model
**DynamoDB `stores-<stage>`** (pk `storeId`)
| Attribute | Example |
|---|---|
| name | Jayanagar Dark Store |
| address | `{line1, area: "Jayanagar 4th Block", city: "Bengaluru", pincode: "560011"}` |
| city | `BLR` (used for city prices) |
| location | `{lat: 12.9250, lng: 77.5838}` |
| geohash5 | `tdr1v` (computed when the location is saved) |
| deliveryRadiusM | 3000 (default; max 4500 in Bengaluru: radius cap in §5) |
| phone, openingHours | per weekday, e.g. `mon: "06:00-23:00"`; timezone `Asia/Kolkata` |
| status | `SETUP` / `OPEN` / `PAUSED` / `CLOSED`, statusReason, statusChangedAt, statusChangedBy (`system-operator` in R1: no staff accounts yet, D10) |
| openedAt, version, createdAt, updatedAt | |

Index **`byGeohash`**: pk `geohash5`, sk `storeId`.
Extra metadata (GST and FSSAI numbers, manager, capacity, riders) is added when a feature needs it.

**Lifecycle**
```
SETUP ──open──> OPEN ──pause──> PAUSED ──open (resume)──> OPEN
  │               │                │
  └──close──> CLOSED <──close──────┘        (CLOSED is final; reopening = a new store)
```
| Status | Customers see it? | Can order? |
|---|---|---|
| `SETUP` | No | No |
| `OPEN` | Yes | Yes, within opening hours |
| `PAUSED` | Yes, with a banner (if no other store serves them) | No |
| `CLOSED` | No | No |
Invalid transitions (e.g. `CLOSED → OPEN`, `SETUP → PAUSED`) are rejected (conditional writes on status + version).

## 7. Interfaces
**Auth:** public routes open (reached as `/api/stores/...` through CloudFront; throttled at 20 req/s, burst 40 in prod). Admin routes: IAM auth, called by the operator's scripts in R1 (D10); the staff pool replaces this with the staff side.

| Method + path | Caller | Purpose |
|---|---|---|
| `POST /serviceability` `{lat, lng, keepStoreId?}` | Web app | `{result: SERVICEABLE / TEMPORARILY_UNAVAILABLE / NOT_SERVICEABLE, storeId?, stores: [{storeId, storeName, city, cityName, status, openNow, opensAt, distanceM}]}`: `storeId` is the serving store from the choice rule (§5); `stores` lists every store in range, nearest first (max 10). The shell sends its active store as `keepStoreId`, except when the customer chooses a new location or opens the app with an empty cart. `openNow` and `opensAt` are worked out from opening hours in the store's timezone; `opensAt` is a UTC instant and the UI shows it in store time. `city` (`BLR`, for prices and fees) and `cityName` ("Bengaluru", shown on the address form) come from the store. `distanceM` lets the UI confirm the location in words ("Koramangala store, 1.2 km away"). POST so coordinates never appear in access logs; not cached |
| `POST /internal/serviceability` `{lat, lng, keepStoreId}` | Ordering | Same answer for checkout, with the cart's store as `keepStoreId` |
| `GET /stores/{storeId}` | Web app, other teams | Public store info (name, hours, open now) |
| `POST /admin/stores` | Operator script (R1) | Create a store (status `SETUP`) |
| `PATCH /admin/stores/{storeId}` | Operator script (R1) | Update details (name, address, location, hours, radius) |
| `GET /admin/stores` | Operator script (R1) | All stores |
| `POST /admin/stores/{storeId}/open` | Operator script (R1) | `SETUP → OPEN`, or resume `PAUSED → OPEN` |
| `POST /admin/stores/{storeId}/pause` `{reason}` | Operator script (R1) | `OPEN → PAUSED` |
| `POST /admin/stores/{storeId}/close` `{reason}` | Operator script (R1) | Any → `CLOSED` |

**Checkout reasons:** Ordering sends the cart's store as `keepStoreId` and maps the answer
([Ordering HLD §7](../ordering/hld.md#7-interfaces)): `NOT_SERVICEABLE` → `STORE_UNAVAILABLE`
`NOT_SERVED` · `TEMPORARILY_UNAVAILABLE` → `STORE_UNAVAILABLE` `PAUSED` · serving store ≠ cart's
store → `STORE_CHANGED` · same store, `OPEN` but not open now → `STORE_UNAVAILABLE`
`OUTSIDE_HOURS` (with `opensAt`). Store Network itself returns only `result`, `storeId` and `stores`.

**Events published:** `StoreCreated`, `StoreUpdated`, `StoreStatusChanged {storeId, from, to, reason}`;
nightly, `StoreUpdated` with `reason: RECONCILE` for every store (repair path for copies).

## 8. Key flows
**8.1 Customer picks an address**
```
pin -> POST /serviceability {lat, lng} -> {SERVICEABLE, storeId BLR-S-01, stores [BLR-S-01, 1.2 km]}
 -> active location {pin, BLR-S-01, BLR} -> Catalog GET /stores/BLR-S-01/products
```
**8.2 Opening a new store**
```
POST /admin/stores {BLR-S-02, ...} -> SETUP -> StoreCreated
 -> Catalog: products listed (bulk) -> Inventory: stock rows, first delivery received
 -> go-live checklist (manual runbook in R1): products listed, stock received, hours set
 -> POST /admin/stores/BLR-S-02/open -> StoreStatusChanged -> customers can see and order
```
**8.3 A store pauses**
```
POST .../pause {reason: "heavy rain"} -> StoreStatusChanged
 -> next re-check: carts at that store move to the nearest store open now (STORE_CHANGED banner);
    if none is open now, customers see "temporarily unavailable"; checkout applies the same rule
```

**8.4 Closing time with a cart** (two stores in range)
```
22:50  cart at BLR-S-01 (1.2 km, open 06:00-23:00); BLR-S-02 (3.8 km) is open 24 h
23:05  re-check {keepStoreId: BLR-S-01} -> BLR-S-01 not open now -> storeId BLR-S-02
       -> cart moves to BLR-S-02, STORE_CHANGED banner ("Some prices or items may differ")
07:00  BLR-S-01 opens; re-check {keepStoreId: BLR-S-02} -> still open now -> stays (no bounce)
next visit with an empty cart -> no keepStoreId -> nearest store open now: BLR-S-01
```

## 9. Failure handling
| Failure | Handling |
|---|---|
| DynamoDB unreadable | Browsing lookups return 503 with retry; checkout lookups fail closed |
| Two admins change status at once | Conditional write on status + version |
| Store location edited | geohash5 recomputed in the same write; `StoreUpdated` |
| Delivery radius above the cap requested (4.5 km in Bengaluru) | Rejected: the 9-cell lookup could miss customers near the edge of the radius |

## 10. Non-functional design
| Concern | Design |
|---|---|
| Latency | 9 small parallel Queries (~10 ms) + a few distance checks; p99 < 50 ms in the service |
| Scale | Works the same for 1 or 3,000 stores (only candidates are checked) |
| Privacy | Customer coordinates are sent in the request body (POST), used for the lookup, never logged or put in events |
| Cost | Cents per month. Serviceability is throttled at 20 req/s (burst 40) in prod, so a flood of lookups costs at most a dollar or two a day |
| Observability | Lookups, serviceable vs not rate, paused-store skips, latency. **Alarms:** 5xx > 1%, p99 > 100 ms, sudden jump in "not serviceable" |

## 11. Alternatives considered
| Option | Decision |
|---|---|
| Check every store's distance | Fine for 10 stores, wasteful at 3,000; geohash chosen |
| Hand-built quadtree | Same idea as geohash; geohash is standard and has libraries |
| Delivery zone polygons now (JTS, GeoJSON in S3) | Later, when stores overlap (ADR-0009 upgrade path) |
| Road travel time (routing API) | Paid per lookup; overkill |
| `PAUSED` for stores being set up | Rejected: customers would see a half-filled catalog; `SETUP` added |
| Store APIs inside Catalog | Rejected: ownership; data would have to move out later |
| Only the single nearest store, "Opens at …" when it is closed | Rejected: customers near a closed store could not order while another store in range is open |
| Prefer stores open now on every re-check (v0.5) | Replaced by the choice rule: customers were moved to a farther store at night and back at opening time, the cart moving twice |
| Combined catalog of every open store in range (one order from several stores, one rider per store) | Parked: several riders and fees per order, reservations across stores, no per-store cache; R1 has one store ([parking lot](../../parking-lot.md)) |

## 12. Risks and open questions
1. Opening-hours handling across midnight and holidays (LLD).
2. Admin auth: IAM operator scripts in R1 (D10); the staff side replaces them.
3. Go-live checklist is manual in R1; automated checks later.

## Change log
Record every design change here with its reason ([scope control](../../scope-control.md)).

| Date | Change | Why (story / requirement) | Approved |
|---|---|---|---|
| 2026-11-14 | v0.1 first draft (PostGIS write side + S3 snapshot + DynamoDB status) | - | - |
| 2026-11-14 | v0.2: zones as versioned GeoJSON evaluated in memory | Simplification | - |
| 2026-11-21 | Serviceability changed to `POST {lat, lng}` (public and internal) | Coordinates must not appear in access logs ([log §9](../../design-review-log.md#9-identity-customer-side)) | Agreed 2026-11-21 |
| 2026-11-21 | v0.3: R1 minimal store service: details + city, lifecycle `SETUP/OPEN/PAUSED/CLOSED`, serviceability by geohash5 + radius (max 5 km), paused store skipped for the next OPEN store; zones, waitlist and auto-pause moved to later | [Design review log §4](../../design-review-log.md#4-stores-store-network-minimal-for-r1), [ADR-0009](../../adr/0009-delivery-zones-as-polygons.md) | Agreed in design review 2026-11-15..21 |
| 2026-11-21 | v0.4 (design review fixes): serviceability returns `storeName` and `distanceM` (text confirmation for the accessible location picker); `opensAt` as a UTC instant computed in the store's timezone | [Design review log §12](../../design-review-log.md#12-design-review-fixes) | Agreed 2026-11-21 |
| 2026-11-21 | v0.5 (round-2 fixes): how Ordering maps `status` + `openNow` to its `STORE_UNAVAILABLE` reasons (no API change) | [Design review log §13](../../design-review-log.md#13-design-review-fixes-round-2) (BE-12) | Applied 2026-11-21, for review |
| 2026-11-22 | v0.6 (round-3 fixes): serviceability returns every store in range plus the serving store from one choice rule (nearest open now; the cart's store kept while it serves; no bouncing); `keepStoreId`; `city` and `cityName` in the answer; radius capped at 95% of a geohash5 cell (4.5 km in Bengaluru); checkout reasons mapped to `NOT_SERVED` / `PAUSED` / `STORE_CHANGED` / `OUTSIDE_HOURS`; operator scripts instead of an admin UI; `statusChangedBy = system-operator`; prod throttling; event consumers corrected; nightly `StoreUpdated` re-send as the repair path for copies | [Design review log §14](../../design-review-log.md#14-design-review-fixes-round-3) (D10, D11, M-1, M-8, M-18, M-19, H-2, L-17) | Applied 2026-11-22, for review |
