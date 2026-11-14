# Inventory - High-Level Design

**Status:** Draft v0.1 - in review · **Owner:** Inventory team · **Last updated:** 2026-11-14
**Requirements:** [requirements.md](requirements.md) · **Builds on:** [system HLD platform defaults](../../system-hld.md#3-platform-defaults)

## 1. Summary
Inventory keeps exact stock per (store, product) and is the **only writer** of those numbers
(ADR-0008). The core problem is **never overselling** when many customers buy the same item at
the same moment. It is solved with DynamoDB **conditional writes inside transactions**: a
reservation succeeds only if enough stock is available at the instant it is written.

## 2. Goals and non-goals
**Goals (R1):** INV-01 to INV-03, INV-06. **(R2):** INV-04, INV-05.
**Non-goals:** suppliers and purchase orders (Procurement), forecasting.

## 3. Context
```
 Checkout workflow ── reserve / release (IAM) ──> Inventory API (Lambda) ──> DynamoDB inventory-<stage>
 Store manager UI ─── stock view / adjustments ─>        |                        |
                                                         |                   DynamoDB Streams
 Catalog: AssortmentChanged ─┐                           |                        v
 Commerce: OrderConfirmed ───┼─> SQS ──> event consumer ─┘           stream publisher Lambda
 Commerce: OrderCancelled ───┤                                         -> StockLevelChanged, StockLow,
 Procurement: GoodsReceived ─┘ (R2)                                       StockReserved/... -> EventBridge
```

## 4. What drives the design
| Driver | Consequence |
|---|---|
| Zero oversell under contention | Atomic check-and-reserve in the database, not in application memory |
| An order has several lines; all or nothing | Multi-item transaction (one order = one transaction) |
| Events must match what was written | Publish from **DynamoDB Streams** (the outbox pattern), never "write then publish" in code |
| Every change must be explainable | Movement records written in the same transaction as the stock change |

## 5. Architecture
| Component | Choice | Why |
|---|---|---|
| API | Spring Boot on Lambda (SnapStart), internal + admin routes | Platform default |
| Data | DynamoDB single table, on-demand, PITR | Conditional writes + transactions give atomic reservations with no idle cost |
| Event consumer | SQS (one queue, EventBridge rules for the 4 consumed events) -> Lambda | Retries, DLQ, buffering |
| Event publisher | DynamoDB Streams -> Lambda -> EventBridge | Events only for changes that really happened |
| Expiry sweeper | EventBridge Scheduler every 5 min -> Lambda releases `HELD` reservations past `expiresAt` | Safety net if the checkout workflow fails to release |

**The reservation transaction** (one `TransactWriteItems` per order, up to 100 lines; carts are
limited to 50 lines):
```
for each line:
  Update STOCK#store#product
     SET reserved = reserved + :qty
     CONDITION attribute_exists(PK) AND (onHand - reserved) >= :qty      -- listed and enough stock
Put RESERVATION#orderId {status: HELD, lines, expiresAt: now + 10 min}
     CONDITION attribute_not_exists(PK)                                  -- idempotent
Put MOVEMENT items (one per line, type RESERVE)
```
If any condition fails, nothing is written and the response says which line failed
(`OUT_OF_STOCK` or `NOT_SOLD_HERE`). If the reservation already exists, the original result is
returned (safe retry).

**Commit / release** are transactions with `CONDITION status = HELD`, so applying the same event
twice changes nothing the second time.

## 6. Data model
**DynamoDB `inventory-<stage>`**
| PK | SK | Attributes |
|---|---|---|
| `STOCK#<storeId>#<productId>` | `STOCK` | onHand, reserved, reorderPoint (R2), bucket (`OUT`/`FEW`/`IN`), updatedAt |
| `RESERVATION#<orderId>` | `RESERVATION` | storeId, lines[{productId, qty}], status (`HELD`/`COMMITTED`/`RELEASED`), expiresAt, createdAt |
| `MOVEMENT#<storeId>#<productId>` | `<timestamp>#<movementId>` | type (RESERVE/COMMIT/RELEASE/RETURN/ADJUST/RECEIPT), qty, ref (orderId/receiptId), actor, reason |
| `PROCESSED#<eventId>` | `EVENT` | processedAt, TTL 7 days (de-duplication of consumed events) |

GSI `byStore`: PK `storeId`, SK `productId` on stock items (store manager stock view).
GSI `byStatusExpiry`: sparse, only `HELD` reservations, SK `expiresAt` (sweeper).

## 7. Interfaces
See the [README](README.md). Design rules:
- Reservations are keyed by `orderId`, so retries never double-reserve.
- `StockLevelChanged` is sent only when the **bucket** changes (out / few / in), keeping event
  volume low; consumers that need exact numbers call `POST /internal/stock/query`.
- Stock records exist only for products the store lists (created from `AssortmentChanged`).

## 8. Key flows
**8.1 Reserve (checkout)**
```
workflow -> POST /internal/reservations {reservationId=orderId, storeId, lines}
  -> transaction OK -> 201 HELD (expiresAt)
  -> condition failed -> 409 {line, reason: OUT_OF_STOCK | NOT_SOLD_HERE}
  -> conflict with a concurrent transaction -> retry with jittered backoff (max 3), then 409 BUSY
```
**8.2 Confirm / cancel**
```
OrderConfirmed -> commit: onHand -= qty, reserved -= qty, status COMMITTED
OrderCancelled -> HELD: release (reserved -= qty) · COMMITTED: return (onHand += qty) · RELEASED: no-op
```
**8.3 Stream to events**
```
stock item changes -> Stream record (old + new image) -> bucket changed? -> StockLevelChanged
(R2) available crossed reorderPoint downwards -> StockLow
```
**8.4 Expiry safety net**
```
every 5 min: query byStatusExpiry where expiresAt < now -> release each (conditional on HELD)
```

## 9. Failure handling
| Failure | Handling |
|---|---|
| Two checkouts race for the last unit | One transaction succeeds; the other's condition fails -> 409 OUT_OF_STOCK |
| Transaction conflict (same items in flight) | Retry with jitter; measured in load tests |
| Checkout workflow dies after reserving | Reservation expires; sweeper releases it |
| Duplicate / out-of-order events | Conditional state transitions + `PROCESSED#` records |
| Stream publisher fails | Lambda retries the stream batch; bisect on error; DLQ for poison records |

## 10. Non-functional design
| Concern | Design |
|---|---|
| Correctness | All stock changes are conditional transactions; movement log written atomically with them |
| Hot items | DynamoDB limits writes per item (about 1,000/s); far above our target, but the load test will show transaction conflicts on a single hot item: that measurement is a deliverable |
| Consistency | Reservations strongly consistent; catalog copy eventually consistent (< 10 s) |
| Security | Only Checkout's role may call reservations; only store managers of that store may adjust (storeId claim checked) |
| Cost | On-demand DynamoDB; pennies at our volume |
| Observability | Metrics: reservations ok / out-of-stock / conflict, retries, sweeper releases, stream publisher lag. **Alarms:** any sweeper release (signals a workflow bug), conflict rate > 5%, DLQ > 0, reservation p99 > 300 ms, stream iterator age > 60 s |

## 11. Alternatives considered
| Option | Decision |
|---|---|
| PostgreSQL with row locks (`SELECT ... FOR UPDATE`) | Classic and valid; rejected to keep the hot path serverless with no idle cost. Good interview comparison: conditional writes vs row locks |
| Reserve in Redis, write to DB later | Rejected: two sources of truth, harder to recover |
| DynamoDB TTL for reservation expiry | Rejected as the main mechanism: TTL deletion can be delayed by hours; used only for cleaning old records |

## 12. Risks and open questions
1. Who sets initial stock for the 10 stores in R1 (before Procurement exists)? Proposed: a seed
   script + manual adjustments.
2. Store manager to store mapping: a `storeId` attribute on the user (Identity) or a group per
   store? To decide with Identity.

## Change log
Record every design change here with its reason ([scope control](../../scope-control.md)).

| Date | Change | Why (story / requirement) | Approved |
|---|---|---|---|
| 2026-11-14 | v0.1 first draft (commit on `OrderConfirmed` instead of `PaymentSucceeded`) | Checkout workflow is the single decision point for an order | Pending review |
