# Supply & Procurement

> Restocks the dark stores before they run out: decides what to order, places purchase orders
> with suppliers, and records what actually arrived. Never changes stock itself.

| | |
|---|---|
| **Owner team** | Supply |
| **Status** | HLD draft v0.1 - in review |
| **Release** | R2 |
| **Stack** | Java (Spring Boot 3 on Lambda + SnapStart), Aurora PostgreSQL (Data API), AWS Step Functions (Standard) |
| **Jira** | [STORE board](https://bhatvinayaka312.atlassian.net/jira/software/projects/STORE/boards/2) · Component `Supply` · Epic: TBD |

## What it does
- **Suppliers** and the products they supply (cost price, lead time, minimum order quantity).
- **Reorder rules** per (store, product): reorder point and target level.
- **Replenishment planning:** on `StockLow` and nightly, suggests quantities
  `target - (available + already on order)`.
- **Purchase orders (POs):** draft -> approval (above a value threshold) -> sent -> confirmed -> received.
- **Goods receipt:** store staff record what arrived (partial, damaged) -> `GoodsReceived` -> Inventory.
- **Supplier simulator:** a fake supplier that confirms, delays or short-ships.

## Scope by release
| Release | In scope |
|---|---|
| R2 | Suppliers, reorder rules, planning, PO lifecycle with approval, supplier simulator, goods receipt |
| R2 (P2) | Stock transfers between stores, supplier performance report |
| Parking lot | Real supplier integrations (EDI), supplier invoicing and payments, forecasting |

## Owns (data)
| Data | Store |
|---|---|
| Suppliers, supplier products, reorder rules, POs + lines, receipts + lines, transfers | Aurora PostgreSQL database `procurement` (shared cluster, ADR-0011) |
| PO lifecycle executions | Step Functions `purchase-order-<stage>` |
| Supplier simulator state | DynamoDB `supply-supplier-sim-<stage>` |

## APIs
| Method + path | Called by | Auth | Purpose |
|---|---|---|---|
| `GET/POST/PUT /admin/suppliers` · `/admin/suppliers/{id}/products` | Buyer UI | buyer | Manage suppliers and what they supply |
| `GET/PUT /admin/reorder-rules?storeId=` | Buyer UI | buyer | Reorder point + target level |
| `GET /admin/purchase-orders?status=` · `GET /admin/purchase-orders/{poId}` | Buyer UI | buyer, store_manager | Track POs |
| `POST /admin/purchase-orders/{poId}/approve` · `/reject` | Buyer UI | buyer | Approve high-value POs |
| `POST /admin/stores/{storeId}/receipts` {poId, lines[{productId, received, damaged}]} | Store staff UI | store_manager | Record goods received |
| `POST /internal/supplier-callbacks` | Supplier simulator | IAM | Supplier confirms / ships |

## Events published
| Event | When | Key data | Consumers |
|---|---|---|---|
| `PurchaseOrderCreated` / `PurchaseOrderApproved` / `PurchaseOrderSent` | Lifecycle steps | poId, supplierId, storeId, lines, totalPaise | Analytics |
| `PurchaseOrderLate` | Not received by expected date | poId, expectedAt | Notifications (buyer), Analytics |
| `GoodsReceived` | Receipt recorded | receiptId, poId, storeId, lines [{productId, qty}] | **Inventory** (on hand += qty), Analytics |
| `StockTransferred` (P2) | Transfer completed | transferId, fromStore, toStore, lines | Inventory, Analytics |

## Events / APIs consumed
| From | What | Why |
|---|---|---|
| Inventory | `StockLow` event, `POST /internal/stock/query`, `PUT /internal/stock/.../reorder-point` | Trigger planning, current availability, push reorder points |
| Catalog | `ProductCreated`, `GET /internal/products/{id}` | Product details for POs |
| Store Network | `StoreCreated`, `GET /stores` | Store list |

## Service levels
| Measure | Target |
|---|---|
| Duplicate orders | Never two open PO lines for the same (store, product) |
| `StockLow` to suggested PO | < 5 min |
| Audit | Every PO and receipt change recorded with who and when |

## Links
| What | Link |
|---|---|
| Repos | Planned (created when development starts) in [bhatvinayaka-store](https://github.com/bhatvinayaka-store): `procurement-backend`, `procurement-web`, `procurement-infra` · find them with topic `feature-procurement` |
| Pipeline | TBD (Supply team pipeline) |
| Dashboard section | Prod system dashboard -> "Procurement" |
| Runbook | TBD |

## Local setup
1. `docker compose up` -> PostgreSQL 16 + DynamoDB Local
2. Migrations + `scripts/seed-suppliers`
3. Run the Spring Boot app; the supplier simulator runs as a separate local process

## Documents
- [Requirements](requirements.md) · [High-level design](hld.md) · [Decisions](adr/)
- Low-level design: written when development of this feature starts (kept in sync with what is built, see [scope control](../../scope-control.md))
