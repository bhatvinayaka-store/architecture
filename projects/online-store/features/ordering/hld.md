# Cart & Checkout - High-Level Design

**Status:** Draft v0.5 - agreed in design review; round-3 fixes 2026-11-22 for review · **Owner:** Commerce team · **Last updated:** 2026-11-22
**Requirements:** [requirements.md](requirements.md) · **Builds on:** [system HLD platform defaults](../../system-hld.md#3-platform-defaults) · **Decisions:** [design review log §6, §10](../../design-review-log.md#10-ordering-full-review)

## 1. Summary
Commerce turns a cart into **exactly one correct order**: right store, right prices, right fees,
stock reserved, and a clear final state. In R1 the cart lives in the browser, payment is **cash on
delivery**, and checkout is **one synchronous call** (no Step Functions until Payments arrives).
The server, never the client, decides the store (Store Network's choice rule), prices and fees.

## 2. Goals and non-goals
**Goals (R1):** ORD-01 to ORD-06, ORD-08 to ORD-10.
**Later:** server cart (after R1), payment step + saga (with Payments), customer cancellation and
delivery statuses (with Fulfillment, ORD-07).
**Non-goals:** coupons, delivery slots, split shipments, guest checkout.

## 3. Context
```
 Browser: cart in localStorage ── GET /api/catalog/stores/{id}/products?ids=... (public, cached)
    │                          └── GET /api/ordering/fees?city=BLR (public, cached 60 s)
    └─ via BFF (session -> token) ──> Commerce API (Lambda) ──> ordering-orders (Streams on)
                                         │  preview / checkout     ordering-idempotency
                                         │                         ordering-config (fees)
                                         ├─ IAM ─> Identity  : address of this user -> lat/lng
                                         ├─ IAM ─> Store Network : does the cart's store serve this address now?
                                         ├─ IAM ─> Catalog   : prices, MRP, listed, maxPerOrder
                                         └─ IAM ─> Inventory : stock query (preview) / reserve (checkout)
 ordering-orders stream ──> publisher ──> OrderConfirmed / OrderAdjusted / OrderCancelled ──> EventBridge
 Inventory: StockCommitFailed ──> SQS ──> Commerce consumer
 Inventory abandoned-reservation job ── IAM GET /internal/orders/{id}/status ──> Commerce API
```

## 4. What drives the design
| Driver | Consequence |
|---|---|
| Exactly one order per click | Idempotency key with a conditional write; orderId fixed before any side effect |
| Client data can be stale or tampered | Server checks the store with Store Network's choice rule (the cart's storeId only as `keepStoreId`) and re-derives prices and fees; the client's prices are only compared |
| No surprises for the customer | Live preview on the checkout page; total must match at checkout |
| Never oversell | Inventory's atomic reservation is the only guarantee |
| Payments will be added later | Inventory's reserve → commit split kept; saga added then |
| Events must match what was saved | Outbox: DynamoDB Streams on the orders table |

## 5. Architecture
| Component | Choice | Why |
|---|---|---|
| Cart (R1) | Browser localStorage `shop.cart.v1` `{storeId, lines: [{productId, qty, sellingPricePaise, mrpPaise, maxPerOrder}]}`, read and written only by Ordering's **cart module** (`get`, `lines`, `setQty(productId, qty, {maxPerOrder, stock})`, `clear`, `subscribe`), which the shell passes to every UI as `ctx.cart`; the quantity cap is applied only there | No backend or login needed; one owner of cart rules ([ADR-0015](../../adr/0015-micro-frontends-with-central-shell.md), [ADR-0017](../../adr/0017-stock-badge-ownership.md)) |
| API | Spring Boot 3 on Lambda (SnapStart), own API URL, reached through the BFF | Platform default |
| Data | DynamoDB `ordering-orders`, `ordering-idempotency`, `ordering-config` | One kind of item per table |
| Event publisher | Streams on `ordering-orders` → Lambda → EventBridge | Outbox pattern, as in Inventory |
| Commit-result consumer | SQS (rule for `StockCommitFailed`) → Lambda | Retries, DLQ |
| Workflow | **None in R1**; Step Functions Standard returns with the payment step | Nothing to wait for with cash on delivery |

**Fees** (config per city, item `FEES#BLR` in `ordering-config`)
```
subtotal      = Σ qty × sellingPrice
you save      = Σ qty × (MRP − sellingPrice)            (display only)
delivery fee  = subtotal >= ₹199 ? 0 : ₹25
platform fee  = ₹5
total (COD)   = subtotal + delivery fee + platform fee   (prices and fees include tax)
```
The order saves a copy of the fees and the config version. Fees are never increased after the order.
The cart page reads the same rules from the public `GET /fees?city=BLR` (cached 60 s), so fees are
visible before checkout.

## 6. Data model
| Table | Keys | Attributes |
|---|---|---|
| `ordering-orders` | pk `orderId`, sk `ORDER` | userId, storeId, **address copy** (recipient, phone, text, lat/lng), **lines** [{productId, name, qty, sellingPricePaise, mrpPaise, lineTotalPaise, status `OK`/`UNAVAILABLE`}], subtotalPaise, deliveryFeePaise, platformFeePaise, totalPaise, feeConfigVersion, paymentMethod `COD`, status, cancelReason, **idempotencyKey**, **adjustments** [{productId, removedQty, amountPaise, reason, at}], createdAt, version |
| `ordering-orders` | pk `orderId`, sk `STATUS#<time>` | status or note ("Milk removed: out of stock") (timeline) |
| `ordering-idempotency` | pk `userId#key` | orderId, requestHash, result (status + body), TTL 24 h |
| `ordering-config` | pk `FEES#<city>` (current), `FEES#<city>#v<n>` (history) | deliveryFeePaise, freeDeliveryFromPaise, platformFeePaise, version, updatedAt, changedBy, reason |

Index `byUser` on `ordering-orders` (`userId`, `createdAt`) for order history. An index by store
comes with the staff design. `orderId` (ULID) is created in the handler for each request, never at
init (SnapStart rule). PITR + deletion protection on `ordering-orders` and `ordering-config` in prod;
the address copy is anonymised after 12 months ([system HLD §3.1](../../system-hld.md#31-personal-data-and-retention)).

**Statuses (R1):** `CONFIRMED`, or `CANCELLED(OUT_OF_STOCK)` when every line fails at commit (a
system cancel). Later: `PICKING → DISPATCHED → DELIVERED`, customer cancellation, `PENDING` with payments.

## 7. Interfaces
All customer routes go through the BFF (`/api/ordering/...`); the customer ID comes only from the token.

| Method + path | Purpose |
|---|---|
| `GET /fees?city=BLR` (public, no auth; CloudFront behaviour `/api/ordering/fees`, cached 60 s) | `{deliveryFeePaise, freeDeliveryFromPaise, platformFeePaise, version}` for the cart page |
| `POST /checkout/preview` `{addressId, storeId, lines}` | Live check: each line `OK` / `ONLY_N_LEFT` / `UNAVAILABLE`, subtotal, savings, fees, total, "add ₹X for free delivery". Reserves nothing |
| `POST /checkout` `{addressId, storeId, lines, expectedTotalPaise}` + `Idempotency-Key` | Place the order → 201 `{order}` (lines with status, `adjustments`) or 409/422/503 with reasons |
| `GET /orders?cursor=` · `GET /orders/{orderId}` | My orders and their timeline (404 if not mine) |
| `GET /internal/orders/{orderId}?userId=` · `GET /internal/users/{userId}/orders` (IAM) | For Support; ownership enforced |
| `GET /internal/orders/{orderId}/status` (IAM) | For Inventory's abandoned-reservation job: `{orderId, storeId, status}` (consistent read, no personal data); 404 if no order |

**Errors** (the body says what changed, so the UI can show it; messages in [UX design §6](../../ux-design.md#6-copy-deck))
| Code | Status | `error.details` | UI action |
|---|---|---|---|
| `TOTAL_CHANGED` | 409 | `{previousTotalPaise, totalPaise, changes: [{productId?, field: price/deliveryFee/platformFee, fromPaise, toPaise}]}` | Show each change; customer confirms the new total |
| `OUT_OF_STOCK` | 409 | `{lines: [{productId, requestedQty, availableQty}]}` | Lower or remove those lines in one tap |
| `ITEM_UNAVAILABLE` | 409 | `{lines: [{productId, reason: NOT_LISTED/INACTIVE/NOT_SOLD_HERE}]}` (covers Inventory's `NOT_SOLD_HERE`) | Remove them |
| `STORE_CHANGED` | 409 | `{expectedStoreId, storeId}`: the cart's store no longer serves this address now, and another store that is open now does | Shell re-runs serviceability and switches to that store; cart moves (ORD-02) |
| `STORE_UNAVAILABLE` | 409 | `{reason: OUTSIDE_HOURS / PAUSED / NOT_SERVED, opensAt?}`: `OUTSIDE_HOURS` = the cart's store is `OPEN` but closed now and no store in range is open now (`opensAt`, UTC instant, only with this reason); `PAUSED` = no store in range is taking orders; `NOT_SERVED` = no store delivers to this address. Mapped from Store Network's answer ([Store Network HLD §7](../store-network/hld.md#7-interfaces)) | `OUTSIDE_HOURS`: "Closed now. Opens at 7:00 AM", cart kept · `PAUSED`: "Try another address" · `NOT_SERVED`: "Change address" |
| `LIMIT_EXCEEDED` | 422 | `{maxLines: 35}` or `{lines: [{productId, maxPerOrder}]}` | The cart module prevents it; shown only if bypassed |
| `IDEMPOTENCY_KEY_REUSED` | 422 | same key, different body | Client bug; new key |
| `BUSY` | 503 + `Retry-After: 2` | Inventory still busy after its own retry | One automatic retry with the same key, then "Try again" |
| `TRY_AGAIN` | 503 | deadline passed or a team is down | Same |

**Idempotency-Key lifecycle:** the UI creates a new key (UUID) each time the customer presses Place
order, and reuses it only for its own automatic retry after a timeout or network error. Only a 201
result is saved; after a 409/422 the same key + body runs the checks again. Keys expire after 24 h.

**Events published:** `OrderConfirmed {orderId, userId, storeId, lines, totals}`,
`OrderAdjusted {orderId, removedLines, newTotal}`, `OrderCancelled {orderId, reason}` (system only in R1).
**Events consumed:** `StockCommitFailed` (Inventory).

## 8. Key flows
**8.1 Three checkpoints**
```
① cart page        Catalog ?ids= lookup (public, ≤ 60 s old): prices, badges, caps quantities
② checkout page    POST /checkout/preview: Identity + Store Network + Catalog + Inventory (live, parallel)
③ place order      POST /checkout: same checks again + Inventory reserve -> CONFIRMED
```
**8.2 Place order (crash-safe)**
```
deadline = now + 8 s, passed to every call (each call's timeout = min(its own, time left))
1. Put ordering-idempotency (userId#key) {orderId: new ULID, requestHash}  CONDITION not exists
     exists + same hash + saved 201 -> return it · same hash, no result -> reuse orderId (retry)
     other hash -> 422 IDEMPOTENCY_KEY_REUSED
2. limits (<= 35 lines, qty >= 1)
3. in parallel: a) Identity: address of THIS user -> Store Network {lat, lng, keepStoreId: cart's store}
                   -> same store, open now? else 409 STORE_CHANGED / STORE_UNAVAILABLE
                b) Catalog: price, MRP, listed, maxPerOrder
4. fees from config -> total; != expectedTotal -> 409 TOTAL_CHANGED {changes}
5. Inventory reserve (reservationId = orderId; idempotent)  -> 409 OUT_OF_STOCK: no order created
6. Put order CONFIRMED {..., idempotencyKey} (CONDITION not exists) + timeline row
     condition fails -> read it: same userId + idempotencyKey -> our own retry, continue
                        otherwise -> 500 + alarm, delete the idempotency row (never expected)
7. save the 201 result on the idempotency row -> 201          (409/422 results are not saved)
8. stream -> OrderConfirmed -> Inventory commits (FEFO, in chunks)
Error after step 5 succeeded (deadline passed, step 6 write failed): before answering, best-effort
   DELETE /internal/reservations/{orderId} (1 s, inside the Lambda's 2 s beyond the deadline).
   Not on the step-6 collision path: that reservation may belong to the other order.
```
Crash after step 5: the retry reuses the orderId, reserve answers "already held", the order is
written. No retry: after the 15-min hold Inventory asks `GET /internal/orders/{id}/status` → 404 →
releases the stock (alarm).

**Error after step 5** (Ordering is still running): it releases the hold at once (best effort), so
the stock is not blocked for 15 minutes; if that call fails too, the 15-min path above applies. A
retry with the same key reuses the orderId and reserves again (a `RELEASED` reservation can be
reserved again, [Inventory HLD §6](../inventory/hld.md#6-data-model)). If the step-6 write did
succeed although it reported an error, `OrderConfirmed` finds the reservation `RELEASED` and
Inventory reserves again before committing; lines it cannot reserve come back as `StockCommitFailed`.

**Timeout budget** (outer limits always longer than inner ones; [platform rule](../../system-hld.md#3-platform-defaults))
| Layer | Timeout |
|---|---|
| CloudFront → BFF | 30 s (origin default) |
| BFF → Ordering (`POST /checkout`) | 12 s |
| Ordering Lambda | 10 s; checkout deadline 8 s |
| Identity, Store Network, Catalog | 2 s each, 1 retry (reads) |
| Inventory reserve | 3 s, 1 retry (idempotent on orderId) |
| DynamoDB | 1 s per attempt (SDK) |
Deadline passed → 503 `TRY_AGAIN`. Written so far: the idempotency row, plus a reservation if step 5
had finished, which Ordering releases at once (best effort; otherwise Inventory after 15 min). The
client's automatic retry with the same key is safe either way.

**8.3 Expiry race at commit**
```
StockCommitFailed {orderId, lines} -> lines UNAVAILABLE, subtotal recalculated (fees unchanged),
timeline note + adjustments entry -> OrderAdjusted; every line failed -> CANCELLED(OUT_OF_STOCK) -> OrderCancelled
```
The customer sees an "Adjusted" label on the order page and in order history, with what was
removed and the new total (ORD-10).

## 9. Failure handling
| Failure | Handling |
|---|---|
| Client retries checkout (timeout) | Same Idempotency-Key → same order / same result |
| Lambda crashes mid-checkout | orderId fixed in step 1; reserve idempotent; Inventory releases the reservation after 15 min once it sees there is no order |
| A downstream team is down or slow | Timeout budget; preview shows "try again"; checkout returns 503 `TRY_AGAIN`; a reservation already made is released at once (best effort) |
| Error after the reservation (deadline passed, order write failed) | Best-effort release before answering; if that fails, Inventory releases after 15 min; a retry with the same key reserves again |
| Price or fee changed in the seconds before the click | 409 TOTAL_CHANGED → preview refreshed |
| Duplicate `StockCommitFailed` | Line status update is conditional (only `OK` → `UNAVAILABLE`) |
| Store paused or past closing time between preview and checkout | Another store open now → 409 `STORE_CHANGED` (the cart moves); none → 409 `STORE_UNAVAILABLE` (`OUTSIDE_HOURS` with the opening time, or `PAUSED`) |

## 10. Non-functional design
| Concern | Design |
|---|---|
| Correctness | Idempotency at API and event level; conditional writes; server-side totals |
| Latency | Checkout: Identity → Store Network in parallel with Catalog, then Inventory; 3 writes. **p99 < 1 s for warm requests.** At R1's low traffic most calls along the chain can be SnapStart restores, so cold starts are measured separately (target p99 < 3 s including them; cold-start share per function). Hard deadline 8 s. No provisioned concurrency in R1 (it is billed every hour); SnapStart priming in the LLD ([parking lot](../../parking-lot.md)) |
| Security | Customer ID from the token; ownership on every read; IAM to other teams |
| Cost | Pay per request; no Step Functions in R1 |
| Observability | Checkout funnel (previews → checkouts → confirmed, failures by reason), latency per downstream call, orders adjusted. **Alarms:** checkout 5xx > 1%, warm p99 > 1.5 s (latency metric emitted only by warm invocations; cold starts counted separately), DLQ > 0, out-of-stock-at-checkout rate spike |

## 11. Alternatives considered
| Option | Decision |
|---|---|
| Step Functions saga in R1 | Deferred: nothing to wait for with cash on delivery |
| Order created as PENDING before reserving | Rejected: failed attempts would fill order history |
| Server cart in R1 | Deferred: browser cart needs no login; server cart after R1 |
| Silently charge a changed price | Rejected: the customer must see what they pay |
| Reserve stock when adding to the cart | Rejected: hoarding |
| Choreography instead of orchestration | Good comparison for when Payments arrives; orchestration kept |

## 12. Risks and open questions
1. Customer cancellation and delivery statuses: with Fulfillment.
2. Fees change without a deploy: an operator script (IAM credentials, like all R1 data set-up) writes
   `FEES#<city>` with `version + 1` (conditional on the old version), `changedBy` (`system-operator`)
   and `reason`, and keeps the old values as `FEES#<city>#v<n>`. Orders keep their own copy.
3. Anonymising address copies after 12 months: a job later ([parking lot](../../parking-lot.md)).

## Change log
Record every design change here with its reason ([scope control](../../scope-control.md)).

| Date | Change | Why (story / requirement) | Approved |
|---|---|---|---|
| 2026-11-14 | v0.1 first draft; status `PAID` dropped (PENDING -> CONFIRMED) | Simpler state model | - |
| 2026-11-21 | Early decisions recorded (browser cart, no payments, 35-product limit, `maxPerOrder`) | [Log §6](../../design-review-log.md#6-ordering-decided-early-full-review-in-10) | Agreed 2026-11-21 |
| 2026-11-21 | v0.2: cash on delivery, synchronous checkout (no Step Functions in R1), no PENDING state, three checkpoints with live preview, total check, fees (delivery free from ₹199, platform fee), MRP on lines, `StockCommitFailed` handling, no customer cancellation in R1, three tables | [Design review log §10](../../design-review-log.md#10-ordering-full-review) | Agreed in design review 2026-11-21 |
| 2026-11-21 | v0.3 (design review fixes): public fees endpoint; 409 bodies say what changed; Idempotency-Key lifecycle (only 201 saved); ownership check on order-write conflicts; timeout budget with an 8 s deadline; Catalog called in parallel; cart module owns the cart; `adjustments` on orders; status endpoint for Inventory | [Design review log §12](../../design-review-log.md#12-design-review-fixes) | Agreed 2026-11-21 |
| 2026-11-21 | v0.4 (round-2 fixes): best-effort release of the reservation on any error after it was made ("nothing written" corrected); `STORE_UNAVAILABLE` reasons `OUTSIDE_HOURS` / `PAUSED` / `CLOSED`, `opensAt` only for `OUTSIDE_HOURS` | [Design review log §13](../../design-review-log.md#13-design-review-fixes-round-2) (BE-9, BE-12) | Applied 2026-11-21, for review |
| 2026-11-22 | v0.5 (round-3 fixes): store check uses Store Network's choice rule with the cart's store as `keepStoreId`; `STORE_UNAVAILABLE` reasons `OUTSIDE_HOURS` / `PAUSED` / `NOT_SERVED` (`CLOSED` could never be returned: a shut store is never in the answer); latency target for warm requests, cold starts measured separately, no provisioned concurrency; fee changes by an operator script with history; `clear` in the cart-module list | [Design review log §14](../../design-review-log.md#14-design-review-fixes-round-3) (D11, M-14, L-15, L-16) | Applied 2026-11-22, for review |
