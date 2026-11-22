# Cart & Checkout - Requirements

**Status:** Draft v0.4 (round-3 fixes) · **Owner:** Commerce team · **Last updated:** 2026-11-22

## Goal
Let customers build a cart and place an order safely: they see exactly what they will pay, one click creates exactly one order, and every order ends in a clear state.

## User stories
Each story becomes one Jira story in project `STORE`; start the Jira summary with the story ID (e.g. `ORD-01: ...`).

| ID | Story | Acceptance criteria | Priority |
|---|---|---|---|
| ORD-01 | As a customer, I can add/remove items in my cart | R1: cart kept in the browser; prices and badges refreshed from Catalog when the cart opens; fees (delivery fee, free-delivery threshold, platform fee) shown in the cart. Later: server cart on any device | P0 |
| ORD-02 | As a customer, my cart belongs to the store serving my delivery address | Changing address to another store, or my store closing for the day or pausing while another store in range is open, moves the cart and flags items the new store does not sell; it never moves back at opening time | P0 |
| ORD-03 | As a customer, I can check out with a saved address and pay cash on delivery | Reserve stock → order CONFIRMED in one call; later a payment step | P0 |
| ORD-04 | As the system, checkout works out the store from the delivery address | Store Network's choice rule, with the client-sent storeId only as a preference (`keepStoreId`); if the store changed, a clear message, never a wrong order | P0 |
| ORD-05 | As a customer, double-clicking "Place order" never creates two orders | Same Idempotency-Key returns the same result | P0 |
| ORD-06 | As a customer, I can see my order history and status timeline | CONFIRMED (+ notes such as removed items); later PICKING → DISPATCHED → DELIVERED | P0 |
| ORD-07 | As a customer, I can cancel before dispatch | Later (with Fulfillment). Not allowed in R1, and the checkout page says so next to Place order ("Orders can't be cancelled once placed") | Later |
| ORD-08 | As a customer, I cannot exceed order limits | Max 35 different products; per product the store's `maxPerOrder`; enforced in the UI and again by Ordering | P0 |
| ORD-09 | As a customer, the checkout page shows exactly what I will pay | Live preview: line availability, subtotal, savings vs MRP, delivery fee (free from ₹199), platform fee, total; if anything changes before I click, I see the new total and **what changed** (item, old → new price or fee) before confirming | P0 |
| ORD-10 | As a customer, if an item turns out to be unavailable after ordering, my bill is corrected | Line removed, total reduced, fees never increased; timeline note; shown as "Adjusted" on the order page and in order history | P1 |

## Non-functional requirements
- `POST /checkout` p99 < 1 s for warm requests (< 3 s including cold starts); fails within 8 s at worst (timeout budget), never hangs
- No duplicate orders; zero oversells (Inventory)
- 200 orders/min sustained in load test

## Out of scope
- Coupons and promotions
- Scheduled delivery slots
- Guest checkout (sign-in required at checkout)

## Open questions
- None for R1
