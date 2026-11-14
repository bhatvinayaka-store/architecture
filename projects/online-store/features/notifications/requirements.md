# Notifications - Requirements

**Status:** Draft v0.1 · **Owner:** Engagement team · **Last updated:** 2026-11-14

## Goal
Tell users and staff what they need to know (order updates, failures, low stock) through the right channel, once, and respect their preferences.

## User stories
Each story becomes one Jira story in project `STORE`; start the Jira summary with the story ID (e.g. `INV-01: ...`).

| ID | Story | Acceptance criteria | Priority |
|---|---|---|---|
| NTF-01 | As a customer, I get an email when my order is confirmed | Sent within 60 s of `OrderConfirmed` | P0 |
| NTF-02 | As a customer, I am told if my payment failed | Email with retry link | P0 |
| NTF-03 | As a store manager, I get low-stock alerts | Batched digest, max one per product per hour | P1 |
| NTF-04 | As a user, I can opt out of non-essential messages | Transactional messages always sent; marketing respects opt-out | P1 |
| NTF-05 | As the system, the same event never sends two messages | Dedup on eventId | P0 |
| NTF-06 | As a customer, I get an email when an item I asked for is back in stock | `StockLevelChanged` from 0 to >0 at my store | P2 |

## Non-functional requirements
- Delivery < 60 s p95 from event
- Fan-out via SNS -> SQS per channel; DLQ per queue

## Out of scope
- SMS and WhatsApp (need paid plan)
- Mobile push (no mobile app yet)

## Open questions
- TBD during review
