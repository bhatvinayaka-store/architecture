# Inventory - Requirements

**Status:** Draft v0.3 (round-3 fixes; AWS checks 2026-11-22) · **Owner:** Inventory team · **Last updated:** 2026-11-22

## Goal
Know exactly how much of each product each dark store has, by batch and expiry date, never sell stock that does not exist or has expired, and keep the catalog's stock badges right. Inventory is the **only writer** of stock.

## User stories
Each story becomes one Jira story in project `STORE`; start the Jira summary with the story ID (e.g. `INV-01: ...`).

| ID | Story | Acceptance criteria | Priority |
|---|---|---|---|
| INV-01 | As checkout, I can reserve stock for an order so it cannot be oversold | Reservation succeeds only if available >= qty for every line; atomic; retry-safe on orderId; max 35 lines | P0 |
| INV-02 | As the system, abandoned reservations are released automatically | A 5-min job asks Ordering about each `HELD` reservation past its 15-min hold: no order → released; cancelled → closed; confirmed → committed (never freed); alarm on every action | P0 |
| INV-03 | As a store manager, I can see and adjust stock levels | Every change written to the movement log with a reason and actor; adjustments retry-safe (same id + different body → 422); R1 through operator scripts | P0 |
| INV-04 | As a store manager, I get alerted when stock is low | `StockLow` event | P1 (later, with Procurement) |
| INV-05 | As the system, stock increases when Procurement reports goods received | Applies `GoodsReceived` idempotently | P1 (later) |
| INV-06 | As checkout, a reservation is rejected if the store does not list the product | Clear `NOT_SOLD_HERE` error | P0 |
| INV-07 | As a store manager, I record deliveries with expiry dates | Each delivery creates batches; retry-safe on receiptId (same id + different body → 422); a line already within 1 h of its stop-selling time is refused (422 `EXPIRES_TOO_SOON`); R1 through operator scripts | P0 |
| INV-08 | As the system, expired stock is never sold | Batches stop counting at expiry − minimum shelf life (per product, category defaults); hourly job writes them off; commit takes the earliest-expiring batch first (FEFO) and never a batch past its stop-selling time; raising a minimum shelf life writes off batches past their new stop-selling time at once | P0 |
| INV-09 | As a customer, the catalog shows in stock / only N left / out of stock | `StockLevelChanged` sent only when the status changes (or the count changes while few left), using the `maxPerOrder` copy from Catalog | P0 |

## Non-functional requirements
- **Zero oversell** with 50 concurrent checkouts for the last 30 units of one product (load test in `dev`: 30 confirmed, 20 refused, `BUSY` < 10%). Each checkout holds about three functions at once (BFF, Ordering, Inventory), so the test needs about 150 Lambda concurrency: it waits for the requested quota increase (the account limit was 10 on 2026-11-22, D14), and the BFF cap and route throttles are raised in `dev` for the test. 500 concurrent checkouts would need about 1,500, above the AWS default of 1,000
- Reservation p99 < 200 ms
- Stock movements are auditable and never deleted
- Badge reaches Catalog < 10 s after a status change

## Out of scope
- Suppliers and purchase orders (Procurement team)
- Demand forecasting
- Search (Catalog)

## Open questions
- Who may adjust stock: staff side (after R1); the operator in R1 (D10)
