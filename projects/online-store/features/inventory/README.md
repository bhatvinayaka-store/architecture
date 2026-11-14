# Inventory

> The single source of truth for **how many of each product each dark store has**, and the only
> service that may change those numbers.

| | |
|---|---|
| **Owner team** | Inventory |
| **Status** | HLD draft v0.1 - in review |
| **Release** | R1 (stock, reservations, adjustments) · R2 (low-stock events, goods receipts) |
| **Stack** | Java (Spring Boot 3 on Lambda + SnapStart), DynamoDB (transactions, Streams) |
| **Jira** | [STORE board](https://bhatvinayaka312.atlassian.net/jira/software/projects/STORE/boards/2) · Component `Inventory` · Epic: TBD |

## What it does
- Tracks `onHand` and `reserved` per (store, product); `available = onHand - reserved`.
- **Reserves** stock for an order atomically, so a product can never be oversold.
- Commits reservations when an order is confirmed, releases them when it is cancelled or expires.
- Lets store managers adjust stock (damage, recount) with a reason; every change is audited.
- Publishes stock status for the catalog and (R2) low-stock signals for Procurement.
- (R2) Applies goods received from suppliers.

## Scope by release
| Release | In scope |
|---|---|
| R1 | Stock records, reserve / commit / release, expiry sweeper, manual adjustments, audit log, `StockLevelChanged` |
| R2 | Reorder points + `StockLow`; apply `GoodsReceived` and `StockTransferred` |
| Parking lot | Demand forecasting |

## Owns (data)
| Data | Store |
|---|---|
| Stock, reservations, stock movements (audit) | DynamoDB `inventory-<stage>` (point-in-time recovery on, Streams on) |

## APIs
| Method + path | Called by | Auth | Purpose |
|---|---|---|---|
| `POST /internal/reservations` | Checkout workflow | IAM | Reserve all lines of an order (all or nothing); idempotent on `reservationId` = orderId |
| `DELETE /internal/reservations/{reservationId}` | Checkout workflow | IAM | Release (used on timeouts); idempotent |
| `POST /internal/stock/query` | Procurement, Support | IAM | Current stock for a list of (store, product) |
| `GET /admin/stores/{storeId}/stock?cursor=` | Store manager UI | store_manager | Stock levels for my store |
| `POST /admin/stores/{storeId}/adjustments` | Store manager UI | store_manager | Adjust stock with reason (DAMAGED, RECOUNT, ...) |
| `PUT /internal/stock/{storeId}/{productId}/reorder-point` (R2) | Procurement | IAM | Set the low-stock threshold |

## Events published
| Event | When | Key data | Consumers |
|---|---|---|---|
| `StockLevelChanged` | Availability crosses a bucket: out (0), few left (1-5), in stock (>5) | storeId, productId, inStock, fewLeft | Catalog, Notifications (back in stock), Analytics |
| `StockReserved` / `StockReleased` / `StockCommitted` | Reservation changes | reservationId, storeId, lines | Analytics |
| `StockAdjusted` | Manual adjustment or goods receipt applied | storeId, productId, delta, reason | Analytics |
| `StockLow` (R2) | Available drops to/below reorder point | storeId, productId, available, reorderPoint | Procurement, Notifications (store manager) |

## Events consumed
| Event | From | Effect |
|---|---|---|
| `AssortmentChanged` | Catalog | Create stock records (onHand 0) for newly listed products |
| `OrderConfirmed` | Cart & Checkout | Commit the reservation (onHand -= qty, reserved -= qty) |
| `OrderCancelled` | Cart & Checkout | Release a held reservation, or return committed stock |
| `GoodsReceived`, `StockTransferred` (R2) | Procurement | onHand += received (idempotent on receiptId) |

## Service levels
| Measure | Target |
|---|---|
| Reservation latency | p99 < 200 ms |
| Oversells | **0** with 500 concurrent checkouts on the same product (load test) |
| Stock status to catalog | < 10 s |
| Availability | 99.9% |

## Links
| What | Link |
|---|---|
| Repos | Planned (created when development starts) in [bhatvinayaka-store](https://github.com/bhatvinayaka-store): `inventory-backend`, `inventory-web`, `inventory-infra` · find them with topic `feature-inventory` |
| Pipeline | TBD (Inventory team pipeline) |
| Dashboard section | Prod system dashboard -> "Inventory" |
| Runbook | TBD |

## Local setup
1. `docker compose up` -> DynamoDB Local
2. `scripts/seed-stock` (stock for the 10 stores from `data/seed/`)
3. Run the Spring Boot app; `k6 run load/reserve-same-sku.js` to test contention locally

## Documents
- [Requirements](requirements.md) · [High-level design](hld.md) · [Decisions](adr/)
- Low-level design: written when development of this feature starts (kept in sync with what is built, see [scope control](../../scope-control.md))
