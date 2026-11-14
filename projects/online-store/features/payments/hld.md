# Payments - High-Level Design

**Status:** Draft v0.1 - in review · **Owner:** Payments team · **Last updated:** 2026-11-14
**Requirements:** [requirements.md](requirements.md) · **Builds on:** [system HLD platform defaults](../../system-hld.md#3-platform-defaults)

## 1. Summary
Payments is a queue-driven worker that turns `ChargeOrder` messages into exactly one charge per
order at a simulated gateway, and turns `OrderCancelled` into refunds. Every step is idempotent
by `orderId`, so retries, duplicates and crashes can never charge twice.

## 2. Goals and non-goals
**Goals (R1):** PAY-01 to PAY-04. **(P2):** PAY-05 reconciliation.
**Non-goals:** real providers, saved cards, partial refunds, multiple currencies.

## 3. Context
```
 Checkout workflow ── ChargeOrder ──> SQS payments-charge ──> charge worker (Lambda) ──> gateway simulator
                                           |  (DLQ after 4 receives)          |              (Lambda + its ledger)
                                           v                                  v
                                       DLQ + alarm                   DynamoDB payments-<stage>
                                                                              |
                                  PaymentSucceeded / PaymentFailed / RefundIssued ──> EventBridge
 Commerce: OrderCancelled ──> SQS payments-refunds ──> refund worker (Lambda) ──> gateway simulator
```

## 4. What drives the design
| Driver | Consequence |
|---|---|
| Never charge twice | Idempotency key = orderId at our table **and** at the gateway |
| Gateways fail and time out | Queue-based retries with backoff; distinguish *decline* (final) from *error* (retry) |
| Late results after the order gave up | Refund on `OrderCancelled` whenever a payment succeeded |
| Money must be exact | Integer paise, currency code, no floating point anywhere |

## 5. Architecture
| Component | Choice | Why |
|---|---|---|
| Charge worker | Lambda (Spring Boot + SnapStart) on SQS, batch size up to 10, **partial batch failure** reporting | One bad message does not block the others |
| Retries | Transient error -> message returned with increasing visibility timeout (backoff); `maxReceiveCount` 4 -> DLQ | Standard SQS retry pattern |
| Gateway simulator | Separate Lambda + its own table; behaviour from configuration (decline %, error %, latency) | Lets tests and chaos drills create realistic failures |
| Data | DynamoDB | Conditional state transitions |
| Refund worker | SQS subscribed to `OrderCancelled` -> Lambda | Same retry model |

**Payment state machine** (each arrow is a conditional update)
```
(none) -> PROCESSING -> SUCCEEDED -> REFUND_PENDING -> REFUNDED
                     -> FAILED
```

## 6. Data model
**DynamoDB `payments-<stage>`**
| PK | SK | Attributes |
|---|---|---|
| `PAYMENT#<orderId>` | `PAYMENT` | paymentId, userId, amountPaise, currency, status, gatewayRef, attempts, createdAt, updatedAt, version |
| `PAYMENT#<orderId>` | `ATTEMPT#<n>` | startedAt, outcome (APPROVED / DECLINED / ERROR / TIMEOUT), latencyMs |
| `PAYMENT#<orderId>` | `REFUND#<refundId>` | amountPaise, status, gatewayRef, createdAt |

**Simulator ledger `payments-gateway-sim-<stage>`:** `CHARGE#<idempotencyKey>` -> result. Retrying
the same key returns the original result, like a real gateway.

## 7. Interfaces
See the [README](README.md). Design rules:
- `ChargeOrder` is a **command** (one consumer, a queue); `PaymentSucceeded` is an **event** (bus).
- Customers can read only their own payment (userId from the token must match).
- Events contain no card or personal data (there is none: simulated payments).

## 8. Key flows
**8.1 Charge**
```
receive ChargeOrder(orderId)
 -> Put PAYMENT (condition: not exists) or load existing
      SUCCEEDED/FAILED already -> re-publish the same event (safe) and delete message
 -> call simulator(idempotencyKey = orderId)
      APPROVED -> SUCCEEDED -> PaymentSucceeded
      DECLINED -> FAILED(DECLINED) -> PaymentFailed            (no retry)
      ERROR/TIMEOUT -> attempt recorded -> message back to queue with backoff
 -> 4th failure -> DLQ -> alarm; the checkout workflow times out and cancels the order
```
**8.2 Refund**
```
OrderCancelled(orderId) -> PAYMENT status?
   SUCCEEDED -> REFUND_PENDING -> simulator refund(key = orderId:refund) -> REFUNDED -> RefundIssued
   PROCESSING -> retry later (wait for the charge outcome)
   none / FAILED -> nothing to do
```
**8.3 Chaos test: worker killed mid-charge**
```
simulator charged, worker crashed before writing SUCCEEDED -> message redelivered
 -> simulator returns the original APPROVED for the same key -> SUCCEEDED once, one charge
```

## 9. Failure handling
| Failure | Handling |
|---|---|
| Duplicate `ChargeOrder` | Conditional put + simulator idempotency |
| Gateway down | Backoff retries -> DLQ -> order times out -> cancelled; DLQ redrive after the incident |
| Payment succeeds after the order timed out | `OrderCancelled` already happened or arrives -> refund |
| Event publish fails after state write | Worker retries publishing (message not deleted until published); consumers de-duplicate |

## 10. Non-functional design
| Concern | Design |
|---|---|
| Correctness | Idempotency at every layer; integer money; conditional transitions |
| Security | Queue accepts messages only from the checkout workflow role; simulator config admin-only |
| Cost | Pay-per-use; negligible |
| Observability | Metrics: charges by outcome, attempts per payment, gateway latency, refunds, DLQ depth. **Alarms:** DLQ > 0, error outcome rate > 10% for 5 min, oldest message age > 2 min, refund pending > 10 min |

## 11. Alternatives considered
| Option | Decision |
|---|---|
| Call the gateway synchronously from checkout | Rejected: couples customer latency to the gateway; no buffering |
| Step Functions for each payment | Rejected: a queue worker with idempotency is simpler for a single step |
| Double-entry ledger | Valuable for a fintech project; parking lot here |

## 12. Risks and open questions
1. Reconciliation (P2) output format: CSV report in S3 + mismatch metric (proposed).

## Change log
Record every design change here with its reason ([scope control](../../scope-control.md)).

| Date | Change | Why (story / requirement) | Approved |
|---|---|---|---|
| 2026-11-14 | v0.1 first draft | - | Pending review |
