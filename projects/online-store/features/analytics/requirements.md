# Data & Analytics - Requirements

**Status:** Draft v0.1 · **Owner:** Data team · **Last updated:** 2026-11-14

## Goal
Answer business questions: what sold, where, when, how much we bought vs sold, stockout rate and delivery performance.

## User stories
Each story becomes one Jira story in project `STORE`; start the Jira summary with the story ID (e.g. `INV-01: ...`).

| ID | Story | Acceptance criteria | Priority |
|---|---|---|---|
| ANL-01 | As a store manager, I can see sales by product, store and hour | Daily + hourly views | P0 |
| ANL-02 | As the business, I can see where customers asked for delivery but no store serves them | Map of `ServiceabilityMiss {geohash5}` events: where to open the next store. Only a rough area (a ~5 km cell), never exact coordinates; Store Network adds this event when Analytics is built | P2 |
| ANL-03 | As a buyer, I can compare quantity purchased vs sold per product | Shows days of stock remaining | P1 |
| ANL-04 | As ops, I can see stockout rate and on-time delivery rate | Weekly trend | P1 |
| ANL-05 | As a data engineer, I can replay events to rebuild datasets | Idempotent backfill job | P1 |

## Non-functional requirements
- Data freshness < 15 min
- No raw PII in the lake (user IDs pseudonymised)
- Athena query cost per report tracked

## Out of scope
- Real-time dashboards (stream analytics) - maybe later
- ML forecasting

## Open questions
- TBD during review
