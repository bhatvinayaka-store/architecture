# Inventory

> The single source of truth for **how many of each product each dark store has, by batch and
> expiry date**, and the only service that may change those numbers.

| | |
|---|---|
| **Owner team** | Inventory |
| **Status** | HLD draft v0.5 - agreed in design review; round-3 fixes 2026-11-22 for review |
| **Release** | R1 (stock, batches + expiry, reservations, receipts, adjustments, badges) · Later (low-stock events, goods receipts from Procurement) |
| **Stack** | Java (Spring Boot 3 on Lambda + SnapStart), DynamoDB (5 tables, transactions, Streams), EventBridge Scheduler |
| **Jira** | [STORE board](https://bhatvinayaka312.atlassian.net/jira/software/projects/STORE/boards/2) · Component `Inventory` · Epic: TBD |

## What it does
- Tracks `onHand` (sellable) and `reserved` per (store, product); `available = onHand - reserved`.
- Holds stock as **batches with expiry dates**; stops counting a batch at expiry − minimum shelf
  life; refuses deliveries that are already short-dated; an hourly job writes off expired batches.
- **Reserves** stock for an order atomically (all lines or none), so nothing is ever oversold.
- Commits reservations when an order is confirmed, taking stock **first-expired-first-out**, in
  chunks so a 35-line order fits DynamoDB's 100-item transaction limit; releases them when
  cancelled, or after a **15-minute hold** once Ordering confirms there is no order.
- Records deliveries (batches) and stock adjustments with a reason; every change is audited. In R1 the
  operator does this with scripts; store managers get screens with the staff side.
- Tells Catalog the stock badge (`IN` / `FEW` + count / `OUT`) **only when it changes**, using its
  copy of each listing's `maxPerOrder`.

## Scope by release
| Release | In scope |
|---|---|
| R1 | Stock rows, batches + expiry, reserve / commit / release, abandoned-reservation job, expiry job, nightly badge reconciliation, receipts, adjustments, movement log, `StockLevelChanged` |
| Later | `StockLow` + low-stock alerts, `GoodsReceived` and transfers from Procurement |
| Parking lot | Demand forecasting, sharded stock rows for extreme hot items, near-expiry discounts |

## Owns (data)
| Data | Store |
|---|---|
| Stock summary per (store, product) | DynamoDB `inventory-stock-<stage>` (Streams on) |
| Batches with expiry | DynamoDB `inventory-batches-<stage>` |
| Reservations | DynamoDB `inventory-reservations-<stage>` |
| Movement log (audit) | DynamoDB `inventory-movements-<stage>` |
| Idempotency records for receipts and adjustments | DynamoDB `inventory-idempotency-<stage>` (TTL 30 days) |

## APIs
Auth: internal routes IAM; admin routes IAM too, called by the operator's scripts in R1 (staff pool later, D10).

| Method + path | Called by | Purpose |
|---|---|---|
| `POST /internal/reservations` | Ordering | Reserve all lines of an order (all or nothing); idempotent on orderId |
| `DELETE /internal/reservations/{orderId}` | Ordering | Release a `HELD` reservation after a failed checkout (best effort); any other status unchanged; idempotent |
| `POST /internal/stock/query` | Ordering, Support | Current available stock for a list of products |
| `GET /admin/stores/{storeId}/stock?cursor=` | Operator script (R1) | Stock levels for the store |
| `GET /admin/stores/{storeId}/stock/{productId}` | Operator script (R1) | Batches and recent movements of one product |
| `POST /admin/stores/{storeId}/receipts` | Operator script (R1) | Record a delivery (batches with expiry) |
| `POST /admin/stores/{storeId}/adjustments` | Operator script (R1) | Adjust stock with a reason (DAMAGED, RECOUNT, ...) |
| `PUT /admin/stores/{storeId}/stock/{productId}/settings` | Operator script (R1) | Minimum shelf life |

## Events published
| Event | When | Key data | Consumers |
|---|---|---|---|
| `StockLevelChanged` | Badge status changes, or count changes while few left; nightly for every product (`reason: RECONCILE`) | storeId, productId, status, availableQty (when FEW), reason? | Catalog, Analytics |
| `StockReserved` / `StockReleased` / `StockCommitted` | Reservation changes | orderId, storeId, lines | Analytics |
| `StockCommitFailed` | A line had no sellable batch at commit (expiry race) | orderId, storeId, lines | **Ordering** (corrects the order), Analytics |
| `StockReceived` / `StockAdjusted` / `StockExpired` | Delivery, adjustment, write-off | storeId, productId, batchId, qty, reason | Analytics |

## Events consumed
| Event | From | Effect |
|---|---|---|
| `AssortmentChanged` | Catalog | Create stock rows (onHand 0) with `maxPerOrder` and `categoryId` |
| `ListingUpdated` | Catalog | Update the `maxPerOrder` copy if its `listingVersion` is newer |
| `OrderConfirmed` | Ordering | Commit the reservation (FEFO) |
| `OrderCancelled` | Ordering | Per line: release held lines, return committed lines, skip failed ones; reservation ends `CLOSED` |

## Service levels
| Measure | Target |
|---|---|
| Reservation latency | p99 < 200 ms |
| Oversells | **0** with 50 concurrent checkouts for the last 30 units of one product (load test: 30 confirmed, 20 refused, `BUSY` < 10%) |
| Badge to Catalog | < 10 s after a status change |
| Availability | 99.9% |

## Links
| What | Link |
|---|---|
| Repos | Planned (created after the design is finalised) in [bhatvinayaka-store](https://github.com/bhatvinayaka-store): `inventory-backend`, `inventory-web`, `inventory-infra` · find them with topic `feature-inventory` |
| Pipeline | TBD (defined in the team's CDK package) |
| Decisions | [Inventory ADR-0001](adr/0001-batches-expiry-fefo.md), [ADR-0017](../../adr/0017-stock-badge-ownership.md), [design review log](../../design-review-log.md#5-inventory) |
| Sample data / test scenarios | [inventory-sample.md](../../data/seed/inventory-sample.md) |
| Runbook | TBD |

## Local setup
1. `docker compose up` -> DynamoDB Local
2. `scripts/create-tables` then `scripts/seed-stock` (batches from `data/seed/`)
3. Run the Spring Boot app; `k6 run load/reserve-same-sku.js` tests contention locally

## Documents
- [Requirements](requirements.md) · [High-level design](hld.md) · [Decisions](adr/)
- Low-level design: written when development of this feature starts (kept in sync with what is built, see [scope control](../../scope-control.md))
