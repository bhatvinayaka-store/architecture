# Payments

> Takes payment for an order **exactly once**, refunds correctly, and can prove every amount.
> Uses a simulated payment gateway: no real money.

| | |
|---|---|
| **Owner team** | Payments |
| **Status** | HLD draft v0.1 - in review |
| **Release** | R1 (reconciliation report P2) |
| **Stack** | Java (Spring Boot 3 on Lambda + SnapStart), SQS + DLQ, DynamoDB |
| **Jira** | [STORE board](https://bhatvinayaka312.atlassian.net/jira/software/projects/STORE/boards/2) · Component `Payments` · Epic: TBD |

## What it does
- Processes `ChargeOrder` requests from the checkout workflow through a work queue.
- Calls a **simulated payment gateway** (owned by this team) that can approve, decline, fail
  temporarily or be slow, controlled by configuration, so failure handling can be tested.
- Guarantees no double charge: idempotent by orderId at every step.
- Refunds when an order is cancelled after payment (including late successes).
- (P2) Daily reconciliation between our records and the gateway's.

## Scope by release
| Release | In scope |
|---|---|
| R1 | Charge, retries + DLQ, decline handling, refunds, payment status API, gateway simulator |
| R1 (P2) | Daily reconciliation report |
| Never | Real payment providers, wallets, EMI (learning project) |

## Owns (data)
| Data | Store |
|---|---|
| Payments, attempts, refunds | DynamoDB `payments-<stage>` (PITR on) |
| Charge requests | SQS `payments-charge-<stage>` + DLQ |
| Gateway simulator ledger | DynamoDB `payments-gateway-sim-<stage>` (the "bank's" records) |

## APIs and commands
| Interface | Called by | Auth | Purpose |
|---|---|---|---|
| SQS message `ChargeOrder` {orderId, userId, amountPaise, currency} | Checkout workflow | IAM (queue policy) | Request a charge |
| `GET /payments/{orderId}` | Web app | User JWT (own orders only) | Payment status and refunds |
| `GET /internal/payments/{orderId}` | Support | IAM | Payment status for the assistant |
| `PUT /admin/simulator` {declineRate, errorRate, latencyMs} | Admin / tests | admin | Configure the gateway simulator |

## Events published
| Event | When | Key data | Consumers |
|---|---|---|---|
| `PaymentSucceeded` | Gateway approved | orderId, paymentId, amountPaise | Cart & Checkout (resume workflow), Analytics |
| `PaymentFailed` | Declined, or retries exhausted | orderId, reason (`DECLINED` / `GATEWAY_ERROR`) | Cart & Checkout, Notifications, Analytics |
| `RefundIssued` | Refund completed | orderId, refundId, amountPaise | Notifications, Analytics |

## Events consumed
| Event | From | Effect |
|---|---|---|
| `OrderCancelled` | Cart & Checkout | Refund if a payment succeeded (also covers payments that succeed after a timeout) |

## Service levels
| Measure | Target |
|---|---|
| Double charges | **0** (verified by chaos test: kill the worker mid-charge) |
| Charge processed | p95 < 5 s from message to event (simulator latency excluded) |
| DLQ | Any message in the DLQ pages on-call |

## Links
| What | Link |
|---|---|
| Repos | Planned (created when development starts) in [bhatvinayaka-store](https://github.com/bhatvinayaka-store): `payments-backend`, `payments-infra` · find them with topic `feature-payments` |
| Pipeline | TBD (Payments team pipeline) |
| Dashboard section | Prod system + business dashboards -> "Payments" |
| Runbook | TBD (incl. "how to redrive the DLQ") |

## Local setup
1. `docker compose up` -> DynamoDB Local + ElasticMQ (SQS-compatible)
2. Run the Spring Boot app; the simulator runs in the same process locally
3. `scripts/charge-test` sends charges with different simulator settings

## Documents
- [Requirements](requirements.md) · [High-level design](hld.md) · [Decisions](adr/)
- Low-level design: written when development of this feature starts (kept in sync with what is built, see [scope control](../../scope-control.md))
