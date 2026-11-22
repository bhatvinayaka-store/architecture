# ADR-0009: Store chosen from the delivery address: geohash + radius now, zone polygons later

**Status:** Accepted (revised 2026-11-22) · **Date:** 2026-11-14

## Context
Customers must only see and buy from the store that serves the address they deliver to. R1 has
**one store**; the design must work for ~3,000 stores in several cities. Checking every store's
distance on every lookup wastes work at that scale.

## Decision
- The serving store is derived from the **delivery location the customer chooses** (current
  location, saved address or map pin: lat/lng). A client-sent storeId is never trusted: it is only a
  preference to keep (`keepStoreId`), checked against the same rule. The store never changes because
  the phone's GPS moved.
- **R1: radius + geohash.** Each store has a delivery radius (default 3 km, **max 95% of a
  geohash5 cell's smaller side: 4.5 km in Bengaluru**) and a stored **5-character geohash** (cells
  ≈ 4.8 × 4.9 km in Bengaluru) indexed in DynamoDB. Lookup: user's geohash5 cell + its 8
  neighbours → candidate stores → exact (haversine) distance check → **every store in range**,
  nearest first.
- **One store per order, chosen by one rule** (app and checkout): the nearest store open now. The
  store of a cart with items is kept while it is open now; when it stops serving, the nearest other
  store open now takes over (never back to a nearer store while the cart has items). No store open
  now → "Opens at …" (an `OPEN` store), "temporarily unavailable" (only `PAUSED` stores) or "not
  served". `SETUP` and `CLOSED` stores are never chosen.
- **Later (when stores overlap):** hand-drawn **delivery zone polygons** (GeoJSON, versioned in
  S3, evaluated in memory with JTS), replacing the radius check; the geohash shortlist stays.

**Revisions:** v1 stored polygons in PostGIS; v2 (2026-11-14) moved them to versioned GeoJSON in
memory; v3 (2026-11-15) uses radius + geohash for R1 and keeps polygons as the upgrade path; v4
(2026-11-22) returns every store in range with one choice rule (no bouncing between stores) and caps
the radius from the cell size (5 km could miss customers). The file name is kept from v1 so links stay valid.

## Consequences
Lookups touch only a few candidate stores at any scale. Radius ignores roads and lakes, which is
acceptable with one store and fixed later by polygons. A larger delivery radius would need a
coarser geohash or more neighbour rings.
