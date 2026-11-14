# Payments - Requirements

**Status:** Draft v0.1 · **Owner:** Payments team · **Last updated:** 2026-11-14

## Goal
Take payment for orders exactly once, refund correctly, and be able to prove every amount. Uses a simulated payment gateway; no real money.

## User stories
Each story becomes one Jira story in project `STORE`; start the Jira summary with the story ID (e.g. `INV-01: ...`).

| ID | Story | Acceptance criteria | Priority |
|---|---|---|---|
| PAY-01 | As checkout, I can request a charge and get a result event | Simulated gateway with configurable failure rate and latency | P0 |
| PAY-02 | As the business, a customer is never charged twice for one order | Idempotent on orderId; retries safe | P0 |
| PAY-03 | As the system, transient gateway failures are retried with backoff | Max 3 retries, then DLQ + alarm | P0 |
| PAY-04 | As a customer, cancelled orders are refunded | `RefundIssued` emitted; amounts reconcile | P1 |
| PAY-05 | As finance, a daily reconciliation report shows mismatches | Report in S3; mismatch count metric | P2 |

## Non-functional requirements
- Exactly-once effect per order (verified by chaos test: kill worker mid-charge)
- DLQ depth > 0 pages on-call
- All amounts in minor units (paise/cents), never floats

## Out of scope
- Real payment providers
- Wallets, EMI, split payments

## Open questions
- TBD during review
