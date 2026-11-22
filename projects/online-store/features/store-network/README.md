# Store Network & Serviceability

> Knows every dark store (details, location, city, status) and answers: **"which store serves
> this delivery address, and can it take orders now?"**

| | |
|---|---|
| **Owner team** | Logistics |
| **Status** | HLD draft v0.7 - agreed in design review; round-3 fixes and D16-D17 2026-11-22 for review |
| **Release** | R1 (store details, lifecycle, geohash serviceability; built with Catalog) · Later (admin UI with the staff side, delivery zones, waitlist, automatic pause) |
| **Stack** | Java (Spring Boot 3 on Lambda + SnapStart), DynamoDB (+ geohash index), geohash library |
| **Jira** | [STORE board](https://bhatvinayaka312.atlassian.net/jira/software/projects/STORE/boards/2) · Component `Logistics` · Epic: TBD |

## What it does
- Keeps every dark store: name, address, **city**, location (lat/lng + **geohash5**), phone,
  opening hours, delivery radius (default 3 km, max 4.5 km in Bengaluru). R1 has one store: `BLR-S-01`.
- Runs the store **lifecycle**: `SETUP` (hidden while being set up) → `OPEN` ⇄ `PAUSED` → `CLOSED`
  (final, kept for history; no delete).
- Answers **serviceability**: every store whose radius covers the address pin (geohash shortlist),
  nearest first, and the serving store: the nearest one open now, with a cart's store kept while it
  serves. One store per order.
- Tells other teams about stores through events.

## Scope by release
| Release | In scope |
|---|---|
| R1 | Store details, lifecycle with action endpoints, serviceability (geohash + radius, backup stores), store events; data entered by operator scripts (IAM) |
| Later | Admin UI (staff side), delivery zone polygons (when stores overlap), waitlist + `ServiceabilityMiss`, automatic pause from Fulfillment, live ETA, extra metadata (GST, FSSAI, capacity) |

## Owns (data)
| Data | Store |
|---|---|
| Stores (details, location, geohash, status) | DynamoDB `stores-<stage>` with index `byGeohash` |

## APIs
Auth: public routes open (throttled); admin routes IAM-only, called by the operator's scripts in R1 (staff pool later).

| Method + path | Called by | Purpose |
|---|---|---|
| `POST /serviceability` `{lat, lng, keepStoreId?}` | Web app | The serving store (used in API calls, never shown), city, opening status and a delivery estimate (POST: coordinates never in logs) |
| `POST /internal/serviceability` `{lat, lng, keepStoreId}` | Ordering | Same answer for checkout (the cart's store as `keepStoreId`) |
| `GET /stores/{storeId}` | Web app, other teams | Store info (name, hours, open now) |
| `POST /admin/stores` · `PATCH /admin/stores/{storeId}` · `GET /admin/stores` | Operator script (R1) | Create (status `SETUP`), update, list |
| `POST /admin/stores/{storeId}/open` · `/pause` · `/close` | Operator script (R1) | Lifecycle actions (validated transitions) |

## Events published
| Event | When | Key data | Consumers |
|---|---|---|---|
| `StoreCreated` / `StoreUpdated` | Store added or changed; `StoreUpdated` also nightly for every store (`reason: RECONCILE`) | storeId, name, city, status, location | Catalog (store copy), later Fulfillment |
| `StoreStatusChanged` | Open / pause / close | storeId, from, to, reason | Catalog (visibility, banner), later Fulfillment |

## Depends on
- Nothing in R1. Later: rider availability from Fulfillment.

## Service levels
| Measure | Target |
|---|---|
| Lookup latency | p99 < 50 ms in the service |
| Availability | 99.9% |
| Status change visible to customers | < 60 s |

## Links
| What | Link |
|---|---|
| Repos | Planned (created after the design is finalised) in [bhatvinayaka-store](https://github.com/bhatvinayaka-store): `store-network-backend`, `store-network-web`, `store-network-infra` · find them with topic `feature-store-network` |
| Pipeline | TBD (defined in the team's CDK package) |
| Decisions | [ADR-0009](../../adr/0009-delivery-zones-as-polygons.md), [design review log](../../design-review-log.md#4-stores-store-network-minimal-for-r1) |
| Runbook | TBD (incl. the go-live checklist for a new store) |

## Local setup
1. `docker compose up` -> DynamoDB Local
2. `scripts/create-tables` then `scripts/seed-stores` (`BLR-S-01` from `data/seed/`)
3. Run the Spring Boot app locally; UI in standalone mode with `npm run dev`

## Documents
- [Requirements](requirements.md) · [High-level design](hld.md) · [Decisions](adr/)
- Low-level design: written when development of this feature starts (kept in sync with what is built, see [scope control](../../scope-control.md))
