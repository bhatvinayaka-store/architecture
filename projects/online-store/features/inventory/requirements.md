# Inventory - Requirements

**Status:** Draft v0.1 · **Owner:** Inventory team · **Last updated:** 2026-11-14

## Goal
Know exactly how much of each product each dark store has, and never sell stock that does not exist. Inventory is the **only writer** of stock counts.

## User stories
Each story becomes one Jira story in project `STORE`; start the Jira summary with the story ID (e.g. `INV-01: ...`).

| ID | Story | Acceptance criteria | Priority |
|---|---|---|---|
| INV-01 | As checkout, I can reserve stock for an order so it cannot be oversold | Reservation succeeds only if available >= qty; atomic | P0 |
| INV-02 | As the system, expired reservations are released automatically | Held stock returns after 10 min if unpaid | P0 |
| INV-03 | As a store manager, I can see and adjust stock levels | Every change written to an audit log with reason | P0 |
| INV-04 | As a store manager, I get alerted when stock is low | `StockLow` when below reorder point | P1 (R2) |
| INV-05 | As the system, stock increases when Procurement reports goods received | Applies `GoodsReceived` idempotently (same receipt twice = counted once) | P1 (R2) |
| INV-06 | As checkout, a reservation is rejected if the store does not list the product | Clear 'not sold at this store' error | P0 |

## Non-functional requirements
- **Zero oversell** with 500 concurrent checkouts on the same product (load test)
- Reservation p99 < 200 ms
- Stock movements are auditable and never deleted

## Out of scope
- Suppliers and purchase orders (Procurement team)
- Demand forecasting (possible later with ML)

## Open questions
- TBD during review
