# ADR-0009: Delivery zones as polygons; store decided by delivery address

**Status:** Accepted (revised 2026-11-14) · **Date:** 2026-11-14

## Context
Customers must only see and buy from the one store that serves the address they deliver to.
Radius-based "nearest store" ignores roads and lakes and causes overlapping claims. There are
only 10 stores, so the complete zone map is a few kilobytes.

## Decision
- Each store has a hand-drawn delivery zone polygon (GeoJSON). Overlaps are resolved by zone
  priority, then store id.
- The serving store is derived from the **delivery address the customer chooses**, never from a
  client-sent storeId and never from the phone's current location.
- Zones are published as **versioned GeoJSON snapshots in S3** and evaluated **in memory** with a
  geometry library (JTS). No database query on the lookup path.

**Revision:** the first version stored zones in Postgres + PostGIS. Replaced because the data is
tiny, in-memory lookup is simpler, faster and cheaper, and it removes a database from the customer
path. PostGIS stays the upgrade path if zones ever become large or numerous.

## Consequences
Zones can be redrawn without code changes and rolled back by re-publishing an older version.
Lookup instances can briefly hold an older version (up to ~1 minute) after a publish; responses
carry `zoneVersion` so Checkout can detect it.
