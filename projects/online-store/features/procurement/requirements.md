# Supply & Procurement - Requirements

**Status:** Draft v0.1 · **Owner:** Supply team · **Last updated:** 2026-11-14

## Goal
Restock dark stores before items run out: decide what to order, place purchase orders with suppliers, and record what actually arrived. Never edits stock directly; it reports goods received to Inventory.

## User stories
Each story becomes one Jira story in project `STORE`; start the Jira summary with the story ID (e.g. `INV-01: ...`).

| ID | Story | Acceptance criteria | Priority |
|---|---|---|---|
| PRC-01 | As a buyer, a purchase order is suggested when a store's stock is low | Qty = target level - (on hand + already on order) | P0 |
| PRC-02 | As a buyer, I approve purchase orders above a value threshold | Above threshold waits for approval; below auto-approved | P1 |
| PRC-03 | As the system, purchase orders are sent to the supplier and tracked | States: DRAFT -> APPROVED -> SENT -> CONFIRMED -> RECEIVED / CANCELLED | P0 |
| PRC-04 | As store staff, I record what actually arrived | Partial and damaged quantities supported; emits `GoodsReceived` | P0 |
| PRC-05 | As a manager, I can move stock between stores | Transfer out + transfer in, both audited | P2 |
| PRC-06 | As a buyer, I see late and short deliveries per supplier | Supplier performance report | P2 |

## Non-functional requirements
- Never double-orders while a delivery is pending
- Every purchase order and receipt is auditable
- `GoodsReceived` delivered at least once; Inventory dedups

## Out of scope
- Real supplier integrations (EDI)
- Supplier payments and invoicing

## Open questions
- TBD during review
