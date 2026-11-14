# Cart & Checkout - Requirements

**Status:** Draft v0.1 · **Owner:** Commerce team · **Last updated:** 2026-11-14

## Goal
Let customers build a cart and place an order safely: one click creates exactly one order, and every order ends in a clear final state.

## User stories
Each story becomes one Jira story in project `STORE`; start the Jira summary with the story ID (e.g. `INV-01: ...`).

| ID | Story | Acceptance criteria | Priority |
|---|---|---|---|
| ORD-01 | As a customer, I can add/remove items and see my cart on any device | Cart tied to user; prices refreshed at checkout | P0 |
| ORD-02 | As a customer, my cart belongs to the store serving my delivery address | Changing address to another zone moves the cart and flags unavailable items | P0 |
| ORD-03 | As a customer, I can check out with a saved address | Saga: reserve stock -> request payment -> confirm; compensates on failure | P0 |
| ORD-04 | As the system, checkout works out the store from the delivery address | Client-sent storeId is ignored; if the store changed, the customer gets a clear message, never a wrong order | P0 |
| ORD-05 | As a customer, double-clicking Buy never creates two orders | Same Idempotency-Key returns the same order | P0 |
| ORD-06 | As a customer, I can see my order history and status timeline | PENDING -> CONFIRMED -> (R3: PICKING -> DISPATCHED -> DELIVERED), or CANCELLED with a reason | P0 |
| ORD-07 | As a customer, I can cancel before dispatch and get refunded | Triggers stock release + refund | P1 |

## Non-functional requirements
- `POST /checkout` p99 < 1 s (payment completes async)
- No duplicate orders, no orders stuck in PENDING > 15 min (alarm)
- 200 orders/min sustained in load test

## Out of scope
- Coupons and promotions
- Scheduled delivery slots (maybe R3)

## Open questions
- TBD during review
