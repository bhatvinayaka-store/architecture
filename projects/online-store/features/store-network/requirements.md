# Store Network & Serviceability - Requirements

**Status:** Draft v0.1 · **Owner:** Logistics team · **Last updated:** 2026-11-14

## Goal
Own the list of dark stores and their delivery zones, and answer one question fast: which store serves this delivery address, and is it open?

## User stories
Each story becomes one Jira story in project `STORE`; start the Jira summary with the story ID (e.g. `INV-01: ...`).

| ID | Story | Acceptance criteria | Priority |
|---|---|---|---|
| STN-01 | As a customer, the app shows the store that serves my chosen delivery address | Store decided by the delivery address, not my current location; phone location only a default | P0 |
| STN-02 | As a customer, I am told clearly if my address is not served | 'We don't deliver here yet' + join waitlist | P0 |
| STN-03 | As checkout, I can confirm which store serves an address | Same answer as the app for the same address and zone version | P0 |
| STN-04 | As an admin, I can create stores and draw their delivery zones | Overlaps resolved by zone priority; gaps reported | P0 |
| STN-05 | As a store manager, I can set opening hours and pause the store | Paused store blocks checkout; customers see when it reopens | P1 |
| STN-06 | As the system, a store pauses automatically when no riders are free | Driven by Fulfillment data | P2 (R3) |

## Non-functional requirements
- Lookup p99 < 50 ms inside the service
- Availability 99.9% (on every session and every checkout)
- Zone changes live everywhere within 2 minutes
- Precise customer coordinates never logged

## Out of scope
- Multiple cities
- Travel-time-based zones (polygons are hand drawn in R1)

## Open questions
- TBD during review
