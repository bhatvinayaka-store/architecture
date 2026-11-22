# Inventory - High-Level Design

**Status:** Draft v0.5 - agreed in design review; round-3 fixes 2026-11-22 for review · **Owner:** Inventory team · **Last updated:** 2026-11-22
**Requirements:** [requirements.md](requirements.md) · **Builds on:** [system HLD platform defaults](../../system-hld.md#3-platform-defaults) · **Decisions:** [design review log](../../design-review-log.md#5-inventory)

## 1. Summary
Inventory keeps exact stock per (store, product), **by batch with expiry**, and is the **only
writer** of stock (ADR-0008). Its core problems are **never overselling** when many customers buy
the same item at once (DynamoDB conditional writes inside transactions) and **never selling expired
goods** (batches, minimum shelf life, FEFO). It tells Catalog the stock badge, but **only when the
badge changes** ([ADR-0017](../../adr/0017-stock-badge-ownership.md)).

## 2. Goals and non-goals
**Goals (R1):** INV-01 to INV-03, INV-06 to INV-09. **Later:** INV-04, INV-05 (with Procurement).
**Non-goals:** suppliers and purchase orders (Procurement), forecasting, search.

## 3. Context
```
 Ordering ── reserve / release / stock query ──> Inventory API (Lambda) ──> inventory-stock (Streams on)
 Operator scripts ── stock, receipts, adjustments ─>        |                 inventory-batches
                                                            |                 inventory-reservations
 Catalog: AssortmentChanged, ListingUpdated ─┐              |                 inventory-movements
 Ordering: OrderConfirmed, OrderCancelled ───┴─> SQS ──> event consumer
 Scheduler: hourly expiry job · 5-min abandoned-reservation job ── GET /internal/orders/{id}/status ──> Ordering
 inventory-stock stream ──> publisher Lambda ──> StockLevelChanged (only on badge change) ──> EventBridge
 Scheduler: nightly badge reconciliation ──> StockLevelChanged (every product, reason RECONCILE) ──> EventBridge
```

## 4. What drives the design
| Driver | Consequence |
|---|---|
| Zero oversell under contention | Atomic check-and-reserve inside the write (`CONDITION onHand - reserved >= qty`); no read first |
| An order has several lines; all or nothing | Reserve: one `TransactWriteItems` per order (max 35 lines → 71 items, under the 100-item limit). Commit needs up to 4 items per line, so it runs in chunks |
| Groceries expire | Batches with expiry; minimum shelf life per product; FEFO on commit ([Inventory ADR-0001](adr/0001-batches-expiry-fefo.md)) |
| Badge must match what checkout allows, with few events | Status from `available`; events only on status change ([ADR-0017](../../adr/0017-stock-badge-ownership.md)) |
| Events must match what was written | Publish from DynamoDB Streams (outbox pattern) |
| Every change explainable | Movement rows written in the same transaction |

## 5. Architecture
| Component | Choice | Why |
|---|---|---|
| API | Spring Boot 3 on Lambda (SnapStart), internal + admin routes, own API URL | [ADR-0016](../../adr/0016-spring-boot-on-lambda.md) |
| Data | Five DynamoDB tables (stock, batches, reservations, movements, idempotency), on-demand, PITR on | One kind of item per table; transactions span tables |
| Event consumer | SQS (EventBridge rules for consumed events) -> Lambda | Retries, DLQ |
| Badge publisher | `inventory-stock` Streams -> Lambda compares old vs new status -> EventBridge | Few events; stock logic stays here |
| Expiry job | EventBridge Scheduler hourly -> Lambda; queries a fixed window (no stored state); success heartbeat | Writes off batches 1 h before stop-selling time; a missed run is caught up by the next one |
| Abandoned-reservation job | EventBridge Scheduler every 5 min -> Lambda; asks Ordering about the order before acting | Safety net that never frees a confirmed order's stock; alarm on every action |
| Badge reconciliation job | EventBridge Scheduler nightly (03:00 IST) -> Lambda; re-sends the current badge of every product | Repairs a badge whose event was lost (8.8); Catalog ignores anything older than what it has |

**Reservation transaction** (no read beforehand):
```
for each line (max 35):
  Update inventory-stock (storeId, productId)
     SET reserved = reserved + :qty
     CONDITION attribute_exists(storeId) AND (onHand - reserved) >= :qty
  Put inventory-movements (RESERVE)
Put inventory-reservations (orderId) {HELD, storeId, requestHash, lines [{productId, qty, status: HELD}],
                                     createdAt, expiresAt = createdAt + 15 min}
     CONDITION attribute_not_exists(orderId) OR #status = RELEASED
```
Any failed condition → nothing written. A stock condition → `409 {lines: [{productId, reason:
OUT_OF_STOCK | NOT_SOLD_HERE, availableQty}]}`. The reservation condition (it already exists, `HELD`
or `COMMITTED`) → the existing reservation is returned if its `requestHash` matches (a retry never
reserves twice); other lines under the same orderId → 422 `IDEMPOTENCY_KEY_REUSED`. A `RELEASED`
reservation (it expired, or Ordering released it) can be reserved again; a `CLOSED` one never can
(see the status rules in §6).

**Commit with FEFO, in chunks** (on `OrderConfirmed`). One line needs up to 4 items (1-2 batch
updates, the stock update, a COMMIT movement), so a 35-line order (up to ~140 items) does not fit one
100-item transaction. Lines still `HELD` are packed into chunks of ≤ 100 items (about 20 lines):
```
read the reservation; skip lines already COMMITTED / FAILED
for each chunk:
  read sellable batches of its lines (ACTIVE and sellUntil > now, oldest expiry first)
  TransactWriteItems:
    per line: batch qty -= n (CONDITION qty >= n; may span two batches)
              stock onHand -= n, reserved -= n
              Put COMMIT movement
    one Update reservation SET lines[i].status = COMMITTED, lines[i].batches = [{batchId, n}]
              CONDITION #status = HELD AND lines[i].status = HELD    -- a repeat writes nothing
  batch condition fails -> re-read batches, retry the chunk (max 3)
  reservation condition fails (the event consumer and the job commit at once) -> re-read the
      reservation, drop lines already COMMITTED from the chunk, retry the rest
after the last chunk:
  at least one line COMMITTED -> Update reservation SET #status = COMMITTED
  every line FAILED           -> Update reservation SET #status = CLOSED    -- nothing was taken
```
A line with no sellable batch left → its reservation is released (line `FAILED`, RELEASE movement)
and, after all chunks, **`StockCommitFailed {orderId, storeId, lines}`** is published for Ordering.
**If every line failed, the reservation ends `CLOSED`, not `COMMITTED`:** no stock left the shelf,
so the `OrderCancelled` that Ordering sends next has nothing to return ([sample S12](../../data/seed/inventory-sample.md)).
A crash between chunks is safe: SQS redelivers and committed lines are skipped. The reservation
stays `HELD` until every line is done, so the abandoned-reservation job also finishes it (8.6).
`OrderConfirmed` for a `RELEASED` reservation → reserve again first; lines that cannot be reserved
→ `StockCommitFailed`. `OrderConfirmed` for a `CLOSED` reservation → nothing (a duplicate or late event).

**Badge rule** (stream publisher): `status(available, maxPerOrder)` = `OUT` if 0 · `FEW` if
available < maxPerOrder · else `IN`. Send `StockLevelChanged` if old status ≠ new status, or status
is `FEW` and the count changed. Reserve and release change `available`; commit does not.

## 6. Data model
| Table | pk / sk | Attributes |
|---|---|---|
| `inventory-stock` | `storeId` / `productId` | onHand (sellable units), reserved, **maxPerOrder** (copy from Catalog) + listingVersion (only a newer one is applied), categoryId, minShelfLifeHours, version, updatedAt |
| `inventory-batches` | `storeId#productId` / `expiresAt#batchId` (UTC instant) | qty, receivedAt, receiptId, expiresAt (`9999-12-31T23:59:59Z` for goods that never expire: no `bySellUntil` key, so the expiry job never sees them), **sellUntil** (= expiresAt − minShelfLife, UTC), status (`ACTIVE`/`EXPIRED`/`EMPTY`) |
| `inventory-reservations` | `orderId` | storeId, lines [{productId, qty, status `HELD`/`COMMITTED`/`FAILED`/`RELEASED`/`RETURNED`, batches [{batchId, qty}] (set at commit)}], status (`HELD`/`COMMITTED`/`RELEASED`/`CLOSED`), createdAt, expiresAt (createdAt + 15 min), requestHash, ttl (90 days after the reservation reaches `COMMITTED`, `RELEASED` or `CLOSED`; cleanup only, never while `HELD`) |
| `inventory-movements` | `storeId#productId` / `timestamp#movementId` | type (`RESERVE`/`COMMIT`/`RELEASE`/`RETURN`/`RECEIVE`/`ADJUST`/`EXPIRE`), qty, batchId, ref (orderId / receiptId / adjustmentId), reason, actor (`system-operator` for admin calls in R1, D10; `ordering` for reservations; `inventory` for jobs and events); kept as the audit log |
| `inventory-idempotency` | `key` (`RECEIPT#<receiptId>` / `ADJUST#<adjustmentId>`) | requestHash, response, ttl (30 days); written in the receipt or adjustment transaction with `attribute_not_exists(key)` |

**Reservation status:**
| From → to | When | Can be reserved again? |
|---|---|---|
| `HELD` → `COMMITTED` | Commit finished and took at least one line | - |
| `HELD` → `RELEASED` | Hold freed before any order decision: no order exists (job), or Ordering released it after a failed checkout | Yes (same `orderId`) |
| `HELD` / `COMMITTED` / `RELEASED` → `CLOSED` | Order cancelled (8.5), or the commit took nothing (every line `FAILED`) | No: final; later events for this order do nothing |

**Indexes (sparse):**
- `inventory-batches.bySellUntil`: pk = sell-until **UTC date** (one partition per day), sk =
  `sellUntil#storeId#productId#batchId`; only `ACTIVE` batches that expire. The expiry job queries a
  **fixed window: the last 7 UTC dates up to the date of now + 1 h** (sparse index, so empty days cost
  almost nothing). No job state to keep: a missed run is caught up by the next one, and a batch whose
  `sellUntil` moves into the past (shelf-life change) is still found.
- `inventory-reservations.byHeldExpiry`: pk = UTC date of `expiresAt`, sk = `expiresAt#orderId`; only `HELD`.
  The abandoned-reservation job queries the **last 7 UTC dates** every run (the index is sparse, so
  empty days cost almost nothing): a hold that expires just after 00:00 UTC, or one left `HELD`
  through an outage, is never stranded in an older partition. Anything older still is caught by the
  "`HELD` > 1 h" alarm (§10).

**Time** ([platform rule](../../system-hld.md#3-platform-defaults)): receipts give the printed expiry
in the **store's timezone** (`Asia/Kolkata`), as a date (`2026-11-23`, meaning the end of that day)
or a date-time (`2026-11-23T06:00`). Inventory converts it once to a UTC instant `expiresAt`; keys,
indexes and jobs use UTC only (a batch stopping at 02:00 IST lands in the previous UTC day's
partition, which the job still finds). Store screens show IST.

"All stock in my store" is a plain Query on `inventory-stock` (pk = storeId).
**Idempotency** uses natural keys: `orderId` (on the reservation), `receiptId` and `adjustmentId` (in
`inventory-idempotency`), each with a `requestHash`: the same key with a different body → 422
`IDEMPOTENCY_KEY_REUSED` (as in Ordering), never a silent success with the old data. No processed-events table.
**Category defaults** for minimum shelf life (config, seeded): milk 12 h, curd/bread 24 h, chips 7 days,
rice 30 days, non-perishables none. Changing a product's value recomputes `sellUntil` for its active batches
in the same transaction; a batch whose new `sellUntil` ≤ now + 1 h is written off there and then
(`EXPIRED`, `onHand −= qty`, EXPIRE movement), so a raised minimum never leaves unsellable stock counted.

## 7. Interfaces
**Auth:** internal routes IAM. Admin routes: IAM too, called by the operator's scripts in R1 (initial
stock and deliveries from seed files, D10); store managers get screens with the staff side.

| Method + path | Caller | Purpose |
|---|---|---|
| `POST /internal/reservations` `{reservationId=orderId, storeId, lines}` | Ordering | Reserve all lines (idempotent) |
| `DELETE /internal/reservations/{orderId}` | Ordering | Release a `HELD` reservation after a failed checkout (best effort): `HELD` → `RELEASED`; any other status → no change. Always 204 |
| `POST /internal/stock/query` `{storeId, productIds}` | Ordering, Support | Exact available counts |
| `GET /admin/stores/{storeId}/stock?cursor=` | Operator script (R1) | Stock list |
| `GET /admin/stores/{storeId}/stock/{productId}` | Operator script (R1) | One product: batches + recent movements |
| `POST /admin/stores/{storeId}/receipts` `{receiptId, lines: [{productId, qty, expiry}]}` (`expiry` = local date or date-time, store timezone) | Operator script (R1) | Receive a delivery (new batches). Rejected whole with 422 `EXPIRES_TOO_SOON {lines}` if any line would stop selling within 1 h (`expiry − minShelfLife ≤ now + 1 h`) |
| `POST /admin/stores/{storeId}/adjustments` `{adjustmentId, productId, batchId, delta, reason}` | Operator script (R1) | DAMAGED, RECOUNT, LOST, RETURNED |
| `PUT /admin/stores/{storeId}/stock/{productId}/settings` `{minShelfLifeHours}` | Operator script (R1) | Shelf-life rule |

**Calls:** Ordering `GET /internal/orders/{orderId}/status` (IAM, consistent read; returns status
only, no personal data), only from the abandoned-reservation job.

**Events published:** `StockLevelChanged {storeId, productId, status, availableQty?, occurredAt}`
(only on badge change), `StockReserved` / `StockReleased` / `StockCommitted`, **`StockCommitFailed`**, `StockReceived`,
`StockAdjusted`, `StockExpired`.
**Events consumed:** `AssortmentChanged` (create stock rows at 0 with `maxPerOrder`, `categoryId`),
`ListingUpdated` (update the `maxPerOrder` copy only if its `listingVersion` is newer, since SQS can
reorder two quick changes; may change the badge), `OrderConfirmed` (commit),
`OrderCancelled` (per line, see 8.5). Later: `GoodsReceived` (Procurement).

## 8. Key flows
Worked through with real numbers in the [sample dataset](../../data/seed/inventory-sample.md).

**8.1 Checkout (R1, no payments)**
```
Ordering -> POST /internal/reservations -> HELD -> Ordering confirms at once (cash on delivery)
 -> OrderConfirmed -> commit with FEFO
```
**8.2 Two customers, last unit**
```
both: CONDITION 1 - 0 >= 1 -> DynamoDB applies them one at a time -> first OK, second 409 OUT_OF_STOCK
available 1 -> 0 -> status FEW -> OUT -> StockLevelChanged -> Catalog shows "Out of stock"
```
**8.3 Receive stock**
```
receipt {40 milk, expiry 23 Nov} -> sellUntil (expiry − 12 h) > now + 1 h? yes
 -> transaction: batch + onHand += 40 + RECEIVE movement + idempotency row
 -> status OUT -> IN -> StockLevelChanged
receipt with a line already within 1 h of its stop-selling time -> 422 EXPIRES_TOO_SOON, nothing written
```
**8.4 Expiry**
```
hourly: Query bySellUntil (last 7 UTC dates up to the date of now + 1 h; sellUntil <= now + 1 h)
 -> per batch: EXPIRED, onHand -= qty, EXPIRE movement -> badge change? -> StockLevelChanged
 -> success heartbeat (alarm if there is no successful run for 2 h)
```
**8.5 Cancel** (`OrderCancelled`), **per line**, never per reservation:
```
reservation HELD or COMMITTED:
  line HELD      -> release (reserved -= qty, RELEASE movement), line RELEASED
  line COMMITTED -> return to the batches in lines[i].batches (onHand += n, RETURN movement), line RETURNED;
                    a batch already past its sellUntil is written off instead (EXPIRE movement)
  line FAILED    -> nothing (its hold was released at commit)
  then reservation -> CLOSED          (chunks of <= 100 items like commit; line status makes a repeat safe)
reservation RELEASED -> CLOSED, nothing else (the hold is already gone)
reservation CLOSED   -> nothing (duplicate event, or the commit took nothing: sample S12)
```
In R1 the only cancel is Ordering's `CANCELLED(OUT_OF_STOCK)` after every line failed, which lands on
a `CLOSED` reservation. Returning committed lines is needed once staff can cancel (staff-side design).

**8.6 Abandoned reservation (every 5 min)**
```
Query byHeldExpiry (last 7 UTC dates, expiresAt < now) -> per reservation: GET /internal/orders/{orderId}/status (Ordering)
  404 (no order: checkout died after reserving)  -> release -> RELEASED + alarm
  order CANCELLED                               -> release -> CLOSED
  order CONFIRMED or later                      -> commit (FEFO, chunks) + alarm (OrderConfirmed lost or late)
  Ordering times out / 5xx                      -> leave it; next run (alarm if > 3 runs)
```
**8.7 Big order:** 35 lines → reserve in one transaction (71 items) → commit in 2 chunks (≈ 20 + 15
lines), see the [sample dataset S9](../../data/seed/inventory-sample.md).

**8.8 Nightly badge reconciliation** (03:00 IST)
```
per store: Query inventory-stock (strongly consistent, paged) -> badge per product (same rule as §5)
  -> StockLevelChanged {storeId, productId, status, availableQty?, occurredAt = read time, reason: RECONCILE}
Catalog: applies it only if occurredAt is newer than what it has (as for every StockLevelChanged);
         counts the ones that changed a badge -> metric BadgeCorrected (each one = an event that was lost)
```
R1 has one store with a few hundred products, so this is a few hundred events a night (well under
a cent). It repairs what the stream publisher could not deliver (§9) without a second source of truth.

## 9. Failure handling
| Failure | Handling |
|---|---|
| Two checkouts race for the last unit | One transaction succeeds; the other's condition fails → 409 |
| Transaction conflict on a hot item | Retry with jitter (max 3), then 409 BUSY; measured in load test |
| Ordering crashes after reserving | Reservation expires after 15 min; the job asks Ordering: no order → release + alarm |
| `OrderConfirmed` lost or late (consumer down) | The job finds the order `CONFIRMED` → commits it + alarm; the late event is a no-op. Stock is never freed for a confirmed order |
| Commit crashes between chunks | SQS redelivers; committed lines skipped (line status); the job finishes it if the event is gone |
| Ordering unavailable to the job | Reservation left `HELD`; retried next run; alarm after 3 runs |
| Expiry vs reservation | Commit uses the next batch, else `StockCommitFailed` for that line (Ordering corrects the order) |
| Expiry job fails or runs late | Fixed window: the next run writes off everything due; commit never takes a batch past its `sellUntil`; alarm after 2 h without a successful run |
| A delivery that is already short-dated | 422 `EXPIRES_TOO_SOON` for the whole receipt; nothing counted |
| Same orderId, receiptId or adjustmentId with a different body | 422 `IDEMPOTENCY_KEY_REUSED`; the first request's data stays |
| Duplicate / out-of-order events | Conditional state transitions on natural keys |
| Stream publisher fails | [Platform rule](../../system-hld.md#3-platform-defaults): retries until success with bisect on error, **no retry cap and no maximum record age**, so an EventBridge outage pauses the shard (records kept for the stream's 24 h) instead of dropping badge events. A record with bad data is written whole to the publisher's DLQ by the handler and skipped. The SQS on-failure destination (last resort) gets **only shard and sequence numbers, not the records**: the [replay runbook](../../operational-readiness.md) re-reads them while the stream still holds them. Alarm on iterator age |
| A badge event is lost anyway (more than 24 h, or a bug) | The nightly reconciliation (8.8) re-sends the current badge; `BadgeCorrected` > 0 raises an alarm |
| Cancel after a commit that took nothing | Reservation is already `CLOSED` → nothing returned; no phantom stock (sample S12) |
| Duplicate `OrderConfirmed` after the order was cancelled | Reservation `CLOSED` → ignored (a `RELEASED` one would have been reserved again) |

## 10. Non-functional design
| Concern | Design |
|---|---|
| Correctness | All stock changes are conditional transactions with movement rows |
| Read scaling | **No read replicas**: DynamoDB keeps 3 copies; customer reads go to Catalog's copy behind CloudFront (CQRS). Own reads eventually consistent except where the write condition guarantees correctness |
| Hot items | ~1,000 writes/s per item; far above our load; conflicts measured in the "50 customers, 30 milk" load test. Beyond that: sharded stock rows (parking lot) |
| Partition key | `storeId` on `inventory-stock`: a store's rows share a partition (~1,000 writes/s); far above a store's peak |
| Cost | On-demand DynamoDB; few events (status changes only) |
| Observability | Reservations OK / out-of-stock / conflict, retries, expiry write-offs, abandoned releases, job commits, stream lag. **Alarms:** any abandoned release or job commit, any reservation `HELD` > 1 h (oldest age reported by the job), conflict rate > 5%, DLQ or on-failure queue > 0, reservation p99 > 200 ms (the SLO), iterator age > 10 s (the badge SLO), `BadgeCorrected` > 0, a job without a successful run (expiry 2 h, abandoned-reservation 15 min, reconciliation 26 h) |

## 11. Alternatives considered
| Option | Decision |
|---|---|
| PostgreSQL with row locks / read replicas | Valid; rejected: single write primary, replica lag, idle cost |
| Redis holds counts, DB later | Rejected: two sources of truth |
| OpenSearch / Elasticsearch | Rejected: no atomic conditional writes, ~1 s refresh; search belongs to Catalog |
| Single table | Valid; separate tables chosen for clarity |
| Badge on purchase (onHand) only | Rejected: badge would promise stock that checkout refuses |
| Send every stock change, Catalog decides | Rejected: many more events; Catalog would hold exact stock |
| Fixed "1-5 = few left" | Rejected by the sample data; replaced by `maxPerOrder` |
| DynamoDB TTL for reservation expiry | Rejected as the main mechanism (deletes can be late); used only for cleanup |

## 12. Risks and open questions
1. Initial stock for R1: entered by the operator's script through the receipts API from seed files (D10).
2. Who may adjust stock (staff vs manager of that store): staff side, after R1; the operator in R1.
3. Stream read pricing: check in the first cost review (the 100-item transaction limit is known and designed for).

## Change log
Record every design change here with its reason ([scope control](../../scope-control.md)).

| Date | Change | Why (story / requirement) | Approved |
|---|---|---|---|
| 2026-11-14 | v0.1 first draft (single table; commit on `OrderConfirmed`) | Checkout is the single decision point for an order | - |
| 2026-11-21 | `StockCommitFailed` event replaces the `LINE_UNAVAILABLE` reply | Ordering corrects the order ([log §10](../../design-review-log.md#10-ordering-full-review)) | Agreed 2026-11-21 |
| 2026-11-21 | v0.2: four tables; batches + expiry + FEFO; min shelf life per product; badge from `available` with `maxPerOrder` copy, events only on change; expiry fallback; natural-key idempotency; 35-line limit; no read replicas | [Design review log §5](../../design-review-log.md#5-inventory), [sample dataset](../../data/seed/inventory-sample.md) | Agreed in design review 2026-11-21 |
| 2026-11-21 | v0.3 (design review fixes): chunked commit (35 lines exceed 100 items); 15-min hold; abandoned job asks Ordering before releasing (commits confirmed orders); re-reserve on a late confirm; line status; UTC expiry from store-local input; 409 lists every line | [Design review log §12](../../design-review-log.md#12-design-review-fixes) | Agreed 2026-11-21 |
| 2026-11-21 | v0.4 (round-2 fixes): cancel works per line and returns only committed lines; a commit that took nothing ends `CLOSED` (final) instead of `COMMITTED`, so cancelling it cannot create phantom stock; status table; commit records the batches used; abandoned job scans the last 7 UTC dates + "`HELD` > 1 h" alarm; stream publisher keeps records 24 h with a replay runbook; nightly badge reconciliation | [Design review log §13](../../design-review-log.md#13-design-review-fixes-round-2) (DB-6, DB-8, BE-7) | Applied 2026-11-21, for review |
| 2026-11-22 | v0.5 (round-3 fixes): short-dated deliveries refused (422 `EXPIRES_TOO_SOON`); a raised minimum shelf life writes off affected batches in the same transaction; expiry job uses a fixed window (last 7 UTC dates up to now + 1 h) with a heartbeat alarm; commit skips batches past `sellUntil`; request hashes on reservations, receipts and adjustments (`inventory-idempotency` table); commit race with the job handled; `listingVersion` guard on the `maxPerOrder` copy; alarms at the SLOs; reservation retention; non-expiring batches documented; admin routes for operator scripts, actor `system-operator` (D10) | [Design review log §14](../../design-review-log.md#14-design-review-fixes-round-3) (H-1, H-3, M-4, M-6, M-9, M-13, L-10, L-11, L-12) | Applied 2026-11-22, for review |
