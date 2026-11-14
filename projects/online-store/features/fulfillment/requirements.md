# Fulfillment & Delivery - Requirements

**Status:** Draft v0.1 · **Owner:** Logistics team · **Last updated:** 2026-11-14

## Goal
Get confirmed orders picked in the dark store and delivered by riders on time, with live tracking, and plan the best route when a rider carries several orders.

## User stories
Each story becomes one Jira story in project `STORE`; start the Jira summary with the story ID (e.g. `INV-01: ...`).

| ID | Story | Acceptance criteria | Priority |
|---|---|---|---|
| FUL-01 | As a picker, I get a pick list for each confirmed order | Ordered by aisle | P1 |
| FUL-02 | As a rider, my app sends my location every 5 s | Simulated riders for load testing | P0 |
| FUL-03 | As the system, the nearest available rider is assigned | Assignment < 5 s after order picked | P0 |
| FUL-04 | As the system, a rider can carry up to 3 orders with an optimised route | Respects promised times; compare nearest-first vs 2-opt | P1 |
| FUL-05 | As a customer, I can track my rider live with an ETA | Map updates < 3 s behind | P0 |

## Non-functional requirements
- Ingest 2,000 location updates/s (simulated)
- 95% of orders delivered within promised time in simulation

## Out of scope
- Rider payroll
- Real mobile rider app (a web simulator is enough)

## Open questions
- TBD during review
