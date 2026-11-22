# Cart & Checkout

> Turns a cart into exactly one correct order: right store, right prices and fees, stock reserved,
> and a clear final state every time.

| | |
|---|---|
| **Owner team** | Commerce |
| **Status** | HLD draft v0.6 - agreed in design review; round-3 fixes and checkout decisions (D18) 2026-11-22 for review |
| **Release** | R1 (browser cart, cash on delivery; built after Identity) · Later (server cart, payment step, cancellation, delivery statuses) |
| **Stack** | Java (Spring Boot 3 on Lambda + SnapStart), DynamoDB (Streams); Step Functions only when Payments arrives |
| **Jira** | [STORE board](https://bhatvinayaka312.atlassian.net/jira/software/projects/STORE/boards/2) · Component `Commerce` · Epic: TBD |

## What it does
- **Cart (R1):** kept in the browser, tied to the store serving the active delivery location;
  max 35 products, per product the store's `maxPerOrder`. Ordering owns the **cart module**
  (`ctx.cart`, storage key `shop.cart.v1`) that every team UI uses, so cart rules live in one place.
- **Checkout preview:** a live check on the checkout page (address, store, prices, stock, fees).
- **Checkout:** one idempotent call that re-checks everything, reserves stock and creates a
  CONFIRMED cash-on-delivery order.
- **Fees:** delivery ₹25 (free from ₹199), platform fee ₹5, configurable per city; public
  `GET /fees?city=` so the cart shows them.
- **Orders:** history, timeline, automatic correction if an item turns out to be unavailable.

## Scope by release
| Release | In scope |
|---|---|
| R1 | Browser cart, preview, checkout (COD), fees, order history + timeline, `StockCommitFailed` handling |
| Later | Server cart + guest merge, payment step (Step Functions saga), customer cancellation, PICKING / DISPATCHED / DELIVERED |
| Parking lot | Coupons, scheduled delivery slots |

## Owns (data)
| Data | Store |
|---|---|
| Orders + status timeline | DynamoDB `ordering-orders-<stage>` (Streams on, PITR on), index `byUser` |
| Idempotency keys | DynamoDB `ordering-idempotency-<stage>` (TTL 24 h) |
| Fee configuration per city | DynamoDB `ordering-config-<stage>` |

## APIs
Customer routes go through the BFF (`/api/ordering/...`); the customer ID comes only from the token.

| Method + path | Called by | Auth | Purpose |
|---|---|---|---|
| `GET /fees?city=BLR` | Web app (cart) | Public (cached 60 s) | Fee rules for the cart page |
| `POST /checkout/preview` | Web app | Customer (BFF) | Live check of the cart: lines, fees, total |
| `POST /checkout` + header `Idempotency-Key` | Web app | Customer (BFF) | Place the order → 201 CONFIRMED or 409/422 with reasons |
| `GET /orders?cursor=` · `GET /orders/{orderId}` | Web app | Customer (BFF) | My orders and timeline |
| `GET /internal/orders/{orderId}?userId=` · `GET /internal/users/{userId}/orders` | Support | IAM | Order lookup for the AI assistant; ownership enforced |
| `GET /internal/orders/{orderId}/status` | Inventory | IAM | Status only, for the abandoned-reservation job |

## Events published
| Event | When | Key data | Consumers |
|---|---|---|---|
| `OrderConfirmed` | Order created | orderId, userId, storeId, lines [{productId, name, qty, sellingPricePaise}], totals | Inventory (commit), Notifications, Analytics, Fulfillment (later) |
| `OrderAdjusted` | Lines removed after `StockCommitFailed` | orderId, removedLines, newTotal | Notifications, Analytics |
| `OrderCancelled` | Every line failed (system cancel; customers cannot cancel in R1) | orderId, reason | Inventory, Notifications, Analytics |

## Events consumed
| Event | From | Effect |
|---|---|---|
| `StockCommitFailed` | Inventory | Mark lines unavailable, recalculate the total, add a timeline note |

## Commands sent / APIs called
| To | What |
|---|---|
| Identity | `GET /internal/users/{userId}/addresses/{addressId}` (lat/lng, ownership) |
| Store Network | `POST /internal/serviceability` with the cart's store as `keepStoreId` (does it serve this address now) |
| Catalog | `POST /internal/prices` (selling price, MRP, listed, `maxPerOrder`) |
| Inventory | `POST /internal/stock/query` (preview), `POST /internal/reservations` (checkout) |

## Service levels
| Measure | Target |
|---|---|
| Checkout latency | p99 < 1 s warm (< 3 s including cold starts) |
| Duplicate orders | 0 |
| Load test | 200 orders/min |

## Links
| What | Link |
|---|---|
| Repos | Planned (created after the design is finalised) in [bhatvinayaka-store](https://github.com/bhatvinayaka-store): `ordering-backend`, `ordering-web`, `ordering-infra` · find them with topic `feature-ordering` |
| Pipeline | TBD (defined in the team's CDK package) |
| Decisions | [Design review log §10](../../design-review-log.md#10-ordering-full-review) |
| Runbook | TBD |

## Local setup
1. `docker compose up` -> DynamoDB Local
2. `scripts/create-tables` then `scripts/seed-fees`
3. Run the Spring Boot app with stubbed Identity / Store Network / Catalog / Inventory clients (WireMock)

## Documents
- [Requirements](requirements.md) · [High-level design](hld.md) · [Decisions](adr/)
- Low-level design: written when development of this feature starts (kept in sync with what is built, see [scope control](../../scope-control.md))
