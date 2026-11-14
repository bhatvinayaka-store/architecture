# Supply & Procurement - High-Level Design

**Status:** Draft v0.1 - in review · **Owner:** Supply team · **Last updated:** 2026-11-14
**Requirements:** [requirements.md](requirements.md) · **Builds on:** [system HLD platform defaults](../../system-hld.md#3-platform-defaults)

## 1. Summary
A back-office workflow system. Relational data (suppliers, POs with lines, receipts) lives in
PostgreSQL; each purchase order is a long-running Step Functions workflow that can wait hours or
days for approvals, suppliers and deliveries. It never writes stock: it reports `GoodsReceived`
and Inventory applies it (ADR-0008).

## 2. Goals and non-goals
**Goals (R2):** PRC-01 to PRC-04. **(P2):** PRC-05, PRC-06.
**Non-goals:** supplier invoices and payments, EDI, forecasting.

## 3. Context
```
 Inventory: StockLow ──> SQS ──> planner Lambda ─┐         nightly EventBridge Scheduler ─┐
                                                 v                                        v
                                    PostgreSQL "procurement" <──── Procurement API (Lambda) <── Buyer / store staff UI
                                                 |
                                   start ──> Step Functions "purchase-order" (one execution per PO)
                                                 |  approval wait (task token, 48 h)
                                                 |  send to supplier simulator
                                                 |  wait for supplier confirmation (callback)
                                                 |  wait for goods receipt (callback, lead time + 1 day)
                                                 v
                          GoodsReceived, PurchaseOrder* events ──> EventBridge ──> Inventory, Analytics, Notifications
```

## 4. What drives the design
| Driver | Consequence |
|---|---|
| Relational data and reports (supplier -> PO -> lines -> receipts) | PostgreSQL |
| Processes that wait for people and suppliers for days | Step Functions Standard with callbacks and timeouts |
| Must not order twice while a delivery is pending | "On order" quantity counted in planning + one open line per (store, product) enforced by a unique index |
| Low volume, not on the customer path | Aurora auto-pause is fine (a resume delay is acceptable for back-office users) |

## 5. Architecture
| Component | Choice | Why |
|---|---|---|
| API | Spring Boot on Lambda (SnapStart) | Platform default |
| Database | Aurora PostgreSQL database `procurement` via Data API | ADR-0011 |
| PO lifecycle | Step Functions Standard, one execution per PO (name = poId) | Long waits, visible state per PO |
| Planner | Lambda triggered by `StockLow` (via SQS) and nightly schedule | Event-driven + catch-up safety net |
| Supplier simulator | Lambda + DynamoDB + EventBridge Scheduler (delayed callbacks); configurable delay, short-ship %, late % | Realistic supplier behaviour for testing |

**Purchase order workflow**
```
Draft -> value > threshold? -> WaitForApproval (task token, timeout 48 h -> Expired)
      -> Approved -> SendToSupplier -> WaitForConfirmation (timeout 24 h -> alert buyer)
      -> Confirmed (expectedAt) -> WaitForReceipt (timeout expectedAt + 1 day -> PurchaseOrderLate, keep waiting up to 7 days)
      -> Received (full or partial; partial may stay open for the rest) -> Closed
   any step -> Cancelled by buyer
```

## 6. Data model
**PostgreSQL `procurement`**
| Table | Key columns |
|---|---|
| `suppliers` | id, name, contact, active |
| `supplier_products` | (supplier_id, product_id), cost_paise, lead_time_days, min_order_qty, preferred |
| `reorder_rules` | (store_id, product_id), reorder_point, target_level, active |
| `purchase_orders` | id, supplier_id, store_id, status, total_paise, created_by, approved_by, expected_at, created_at |
| `purchase_order_lines` | (po_id, product_id), qty_ordered, qty_received, cost_paise |
| `goods_receipts` / `goods_receipt_lines` | receipt id, po_id, store_id, received_by, received_at / (receipt_id, product_id), qty_received, qty_damaged |
| `audit_log` | entity, entity_id, action, actor, at, details (JSON) |
| `processed_events` | event_id |

Unique partial index: one open PO line per (store_id, product_id).

## 7. Interfaces
See the [README](README.md). Design rules:
- Only `GoodsReceived` / `StockTransferred` affect stock, and only through Inventory.
- `GoodsReceived` carries `receiptId`; Inventory de-duplicates on it.
- Reorder points are owned here and pushed to Inventory (Inventory only uses them to raise `StockLow`).

## 8. Key flows
**8.1 Low stock to purchase order**
```
StockLow{BLR-S-04, milk, available 8, reorderPoint 10}
 -> planner: rule target 60; on order 0 -> qty 52 -> round up to supplier min order (60)
 -> PO draft (preferred supplier) -> workflow -> value under threshold -> auto-approved -> sent
```
**8.2 Supplier and receipt**
```
simulator confirms (expectedAt tomorrow 10:00) -> callback -> Confirmed
delivery arrives -> staff POST receipt {milk: received 58, damaged 2}
 -> receipt stored -> GoodsReceived{milk +58} -> Inventory on hand += 58 -> PO line partially received
```

## 9. Failure handling
| Failure | Handling |
|---|---|
| `StockLow` and the nightly run both suggest the same order | Unique open-line index -> second suggestion skipped |
| Supplier never confirms | Timeout -> buyer alerted -> choose another supplier |
| Receipt submitted twice | Same receipt id (client-generated) -> idempotent insert |
| Inventory down when `GoodsReceived` is published | Event waits in Inventory's queue; applied later |

## 10. Non-functional design
| Concern | Design |
|---|---|
| Correctness | Constraints in SQL (unique open line, non-negative quantities); idempotent receipts |
| Security | Buyer actions need `buyer`; receipts only by store managers of that store |
| Cost | Aurora auto-paused when idle; Step Functions per state transition (cheap at PO volume) |
| Observability | Metrics: suggested vs approved POs, time to approve, supplier on-time %, short-ship %. **Alarms:** workflow failures > 0, POs late > 3, DLQ > 0 |

## 11. Alternatives considered
| Option | Decision |
|---|---|
| PO status as a column updated by cron jobs (no workflow engine) | Simpler, but timeouts and waits become hand-written polling; Step Functions chosen as the place to learn long-running workflows |
| DynamoDB for POs | Possible; reports and joins fit SQL better |

## 12. Risks and open questions
1. Approval threshold value (proposed ₹10,000 per PO).
2. One preferred supplier per product in R2 (proposed), choosing between suppliers later.

## Change log
Record every design change here with its reason ([scope control](../../scope-control.md)).

| Date | Change | Why (story / requirement) | Approved |
|---|---|---|---|
| 2026-11-14 | v0.1 first draft | - | Pending review |
