# Cart & Checkout - High-Level Design

**Status:** Draft v0.1 - in review · **Owner:** Commerce team · **Last updated:** 2026-11-14
**Requirements:** [requirements.md](requirements.md) · **Builds on:** [system HLD platform defaults](../../system-hld.md#3-platform-defaults)

## 1. Summary
Commerce owns carts and orders and **orchestrates** checkout across four other teams. Checkout is
a **saga** run by Step Functions: each step talks to one team, and each step that changes
something has an undo step. Placing an order is idempotent, and the server, not the client,
decides the store and the prices.

## 2. Goals and non-goals
**Goals (R1):** ORD-01 to ORD-07.
**Non-goals:** coupons, delivery slots, split shipments, guest checkout.

## 3. Context
```
 Web app ── cart / checkout / orders ──> Commerce API (Lambda) ──> DynamoDB ordering-<stage>
                                              |
                                              └─ start execution ──> Step Functions "checkout"
                                                                       |  reserve  -> Inventory (IAM)
                                                                       |  charge   -> Payments SQS (ChargeOrder)
                                                                       |  wait     <- PaymentSucceeded/Failed
 Payments ── PaymentSucceeded/Failed ──> EventBridge ──> SQS ──> resume Lambda (sends task token)
                                              |
                       OrderPlaced / OrderConfirmed / OrderCancelled ──> EventBridge
```

## 4. What drives the design
| Driver | Consequence |
|---|---|
| Exactly one order per click | Idempotency key stored with a conditional write; workflow execution name = orderId |
| Many teams involved, any step can fail | Orchestrated saga with explicit compensations and timeouts |
| Payment is asynchronous and may be slow | Workflow waits for a payment event (callback with task token), max 10 min |
| Client data can be stale or tampered | Server re-derives store (from the address) and prices (from Catalog) |
| Teams must stay decoupled | Payments never calls Commerce's workflow directly; it publishes events, and Commerce resumes its own workflow |

## 5. Architecture
| Component | Choice | Why |
|---|---|---|
| API | Spring Boot on Lambda (SnapStart) | Platform default |
| Data | DynamoDB single table | Key access per user/order; TTL for carts |
| Saga | Step Functions **Standard** | Long waits, built-in retries/timeouts, visual history of every order; execution names are unique, which protects against duplicate starts |
| Resume handler | SQS (subscribed to payment events) -> Lambda: looks up the task token by orderId -> `SendTaskSuccess` / `SendTaskFailure` | Keeps Payments unaware of Commerce's workflow |

**Checkout workflow (states)**
```
ReserveStock (Lambda -> Inventory)          retry 2x on 5xx/BUSY
   ├─ 409 OUT_OF_STOCK / NOT_SOLD_HERE ─> MarkCancelled(OUT_OF_STOCK) ─> PublishOrderCancelled ─> End
   v
RequestPayment (Lambda: save task token, send ChargeOrder)  .waitForTaskToken, timeout 10 min
   ├─ PaymentFailed ──────────────> ReleaseStock -> MarkCancelled(PAYMENT_FAILED) -> PublishOrderCancelled
   ├─ timeout ────────────────────> ReleaseStock -> MarkCancelled(PAYMENT_TIMEOUT) -> PublishOrderCancelled
   v
MarkConfirmed (conditional: status = PENDING) -> PublishOrderConfirmed -> End
```
Compensation `ReleaseStock` = `DELETE /internal/reservations/{orderId}` (idempotent). A late
`PaymentSucceeded` after a timeout is handled by Payments refunding on `OrderCancelled`.

## 6. Data model
**DynamoDB `ordering-<stage>`**
| PK | SK | Attributes |
|---|---|---|
| `CART#<userId>` | `CART` | storeId, addressId, lines [{productId, qty}], updatedAt, TTL (7 days) |
| `ORDER#<orderId>` | `ORDER` | userId, storeId, addressId, lines with price snapshot, subtotal/deliveryFee/total (paise), status, cancelReason, createdAt, version |
| `ORDER#<orderId>` | `STATUS#<timestamp>` | status, note (timeline) |
| `IDEMP#<userId>#<key>` | `IDEMP` | orderId, requestHash, TTL 24 h |
| `TOKEN#<orderId>` | `PAYMENT_WAIT` | taskToken, TTL 1 day |

GSI `byUser`: PK `userId`, SK `createdAt` (order history).

**Order statuses (R1):** `PENDING -> CONFIRMED`, or `CANCELLED` (with reason). R3 adds
`PICKING -> DISPATCHED -> DELIVERED`. Every transition is a conditional update on the current status.

## 7. Interfaces
See the [README](README.md). Design rules:
- `Idempotency-Key` is required on `POST /checkout`; the same key with a different cart -> 422.
- Prices, store and totals in the order come only from server-side lookups at checkout time.
- `OrderConfirmed` carries the line details consumers need (event-carried state).

## 8. Key flows
**8.1 Place order**
```
POST /checkout {addressId} Idempotency-Key: k1
 1. Put IDEMP#user#k1 (condition: not exists) — if exists: return its order (same response)
 2. Identity: address -> lat/lng · Store Network: serviceability
      store != cart.storeId -> 409 STORE_CHANGED · not OPEN -> 409 STORE_UNAVAILABLE
 3. Catalog: prices for cart lines; unlisted line -> 409 ITEM_UNAVAILABLE
 4. Put ORDER (PENDING) + OrderPlaced · StartExecution(name = orderId) -> 202 {orderId}
 5. App polls GET /orders/{orderId} until CONFIRMED / CANCELLED
```
**8.2 Address change with a full cart**
```
PUT /cart/address {addressId} -> serviceability -> new storeId?
 -> move cart to the new store -> Catalog prices/listed for lines -> mark unavailable lines
```
**8.3 Customer cancels a confirmed order (R1, before dispatch)**
```
POST /orders/{id}/cancel -> conditional status CONFIRMED -> CANCELLED(CUSTOMER)
 -> OrderCancelled -> Inventory returns stock · Payments refunds · Notifications emails
```

## 9. Failure handling
| Failure | Handling |
|---|---|
| Client retries `POST /checkout` (network timeout) | Same Idempotency-Key -> same order |
| Lambda crashes after creating the order, before starting the workflow | Start uses execution name = orderId (duplicate start rejected); a sweeper restarts PENDING orders with no execution after 2 min |
| Inventory or Catalog temporarily failing | Workflow retries with backoff; API returns 503 for synchronous steps |
| Payment never answers | 10-minute timeout -> release stock -> CANCELLED(PAYMENT_TIMEOUT) |
| Resume event arrives twice | Task token already used -> ignored |

## 10. Non-functional design
| Concern | Design |
|---|---|
| Correctness | Conditional status transitions; idempotency at API, workflow and event levels |
| Latency | Checkout API does 3 internal calls + 2 writes; payment is async |
| Security | User id from token only; internal order lookups check ownership; IAM per downstream route |
| Cost | Step Functions Standard is billed per state transition (~10 per order): fractions of a cent per order |
| Observability | Business metrics: checkouts started, confirmed, cancelled by reason (the **checkout funnel**). Technical: workflow failures, step latency, PENDING age. **Alarms:** any order PENDING > 15 min, workflow execution failures > 0, checkout 5xx > 1%, cancel rate for PAYMENT_TIMEOUT > 2% |

## 11. Alternatives considered
| Option | Decision |
|---|---|
| Choreography (each team reacts to the previous team's event, no orchestrator) | Rejected for checkout: harder to see where an order is stuck and to add timeouts. Good interview comparison |
| Synchronous payment call inside `POST /checkout` | Rejected: slow and fragile; payments are naturally async |
| Carts in Redis | Rejected for R1: DynamoDB with TTL is simpler and has no idle cost |

## 12. Risks and open questions
1. Delivery fee: fixed (e.g. ₹25) or free above a threshold in R1? Proposed: fixed fee.
2. Maximum cart size: 50 lines (fits Inventory's transaction limit).
3. Is polling `GET /orders/{id}` acceptable for the "waiting for payment" screen in R1 (no WebSockets)?

## Change log
Record every design change here with its reason ([scope control](../../scope-control.md)).

| Date | Change | Why (story / requirement) | Approved |
|---|---|---|---|
| 2026-11-14 | v0.1 first draft; status `PAID` dropped (PENDING -> CONFIRMED) | Simpler state model; payment result is captured by Payments | Pending review |
