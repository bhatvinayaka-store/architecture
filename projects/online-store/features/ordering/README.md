# Cart & Checkout

> Turns a cart into exactly one correct order: right store, right prices, stock reserved, payment
> taken, and a clear final state every time.

| | |
|---|---|
| **Owner team** | Commerce |
| **Status** | HLD draft v0.1 - in review |
| **Release** | R1 (R3 adds delivery statuses) |
| **Stack** | Java (Spring Boot 3 on Lambda + SnapStart), DynamoDB, AWS Step Functions (Standard) |
| **Jira** | [STORE board](https://bhatvinayaka312.atlassian.net/jira/software/projects/STORE/boards/2) · Component `Commerce` · Epic: TBD |

## What it does
- **Cart:** one cart per customer, tied to the store serving their selected delivery address.
- **Checkout:** idempotent order placement that re-checks the store and prices on the server.
- **Checkout workflow (saga):** reserve stock -> take payment -> confirm, with undo steps on failure.
- **Orders:** history, status timeline, cancellation before dispatch.

## Scope by release
| Release | In scope |
|---|---|
| R1 | Cart, store switch on address change, checkout + workflow, order history, cancel (refund + stock return) |
| R3 | Statuses from Fulfillment: PICKING, DISPATCHED, DELIVERED |
| Parking lot | Coupons, scheduled delivery slots |

## Owns (data)
| Data | Store |
|---|---|
| Carts (TTL 7 days), orders + status history, idempotency keys, workflow task tokens | DynamoDB `ordering-<stage>` (PITR on) |
| Checkout workflow executions | Step Functions state machine `checkout-<stage>` |

## APIs
| Method + path | Called by | Auth | Purpose |
|---|---|---|---|
| `GET /cart` | Web app | User JWT | My cart with current prices and availability flags |
| `PUT /cart/items/{productId}` `{qty}` · `DELETE /cart/items/{productId}` | Web app | User JWT | Change cart lines (qty 0 removes) |
| `PUT /cart/address` `{addressId}` | Web app | User JWT | Set delivery address; may move the cart to another store and flag lines |
| `POST /checkout` `{addressId}` + header `Idempotency-Key` | Web app | User JWT | Place the order; returns 202 `{orderId, status: PENDING}` |
| `GET /orders?cursor=` · `GET /orders/{orderId}` | Web app | User JWT | My orders and status timeline |
| `POST /orders/{orderId}/cancel` | Web app | User JWT | Cancel before dispatch |
| `GET /internal/orders/{orderId}?userId=` · `GET /internal/users/{userId}/orders` | Support | IAM | Order lookup for the AI assistant; ownership enforced |

## Events published
| Event | When | Key data | Consumers |
|---|---|---|---|
| `OrderPlaced` | Order created (PENDING) | orderId, userId, storeId, totals | Analytics |
| `OrderConfirmed` | Payment succeeded | orderId, userId, storeId, addressId, lines [{productId, name, qty, pricePaise}], totals | Inventory (commit), Notifications, Analytics, Fulfillment (R3) |
| `OrderCancelled` | Out of stock, payment failed/timed out, or customer cancel | orderId, reason, previousStatus | Inventory (release/return), Payments (refund), Notifications, Analytics |

## Commands sent / APIs called
| To | What |
|---|---|
| Identity | `GET /internal/users/{userId}/addresses/{addressId}` (lat/lng) |
| Store Network | `GET /internal/serviceability` (which store, is it open) |
| Catalog | `POST /internal/prices` (prices + listed flags) |
| Inventory | `POST /internal/reservations`, `DELETE /internal/reservations/{id}` |
| Payments | `ChargeOrder` message on the Payments SQS queue |

## Events consumed
| Event | From | Effect |
|---|---|---|
| `PaymentSucceeded` / `PaymentFailed` | Payments | Resume the waiting checkout workflow |
| `DeliveryStatusChanged` (R3) | Fulfillment | Update order status timeline |

## Service levels
| Measure | Target |
|---|---|
| `POST /checkout` | p99 < 1 s (payment completes asynchronously) |
| Order final state | Every order CONFIRMED or CANCELLED within 15 min (alarm on older PENDING) |
| Duplicates | 0 duplicate orders for the same Idempotency-Key |
| Load test | 200 orders/min sustained |

## Links
| What | Link |
|---|---|
| Repos | Planned (created when development starts) in [bhatvinayaka-store](https://github.com/bhatvinayaka-store): `ordering-backend`, `ordering-web`, `ordering-infra` · find them with topic `feature-ordering` |
| Pipeline | TBD (Commerce team pipeline) |
| Dashboard section | Prod system + business dashboards -> "Checkout funnel" |
| Runbook | TBD |

## Local setup
1. `docker compose up` -> DynamoDB Local + Step Functions Local (or run workflow steps as plain code in tests)
2. Stub other teams' internal APIs with WireMock (contract files from their specs)
3. Run the Spring Boot app; `scripts/demo-checkout` runs a full happy path

## Documents
- [Requirements](requirements.md) · [High-level design](hld.md) · [Decisions](adr/)
- Low-level design: written when development of this feature starts (kept in sync with what is built, see [scope control](../../scope-control.md))
