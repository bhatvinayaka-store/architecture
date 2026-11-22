# Store Network & Serviceability - Requirements

**Status:** Draft v0.3 (round-3 fixes) · **Owner:** Logistics team · **Last updated:** 2026-11-22

## Goal
Own the list of dark stores (details, location, city, status) and answer one question fast: which store serves this delivery address, and can it take orders now?

## User stories
Each story becomes one Jira story in project `STORE`; start the Jira summary with the story ID (e.g. `STN-01: ...`).

| ID | Story | Acceptance criteria | Priority |
|---|---|---|---|
| STN-01 | As a customer, the app shows the store that serves my chosen delivery address | Store decided by the delivery location I choose (current location, saved address or map pin), never silently by GPS movement; the nearest store open now whose delivery radius covers it (max 4.5 km in Bengaluru); while my cart has items the store is kept unless it stops serving | P0 |
| STN-02 | As a customer, I am told clearly if my address is not served | "We don't deliver here yet" (waitlist later) | P0 |
| STN-03 | As checkout, I can confirm which store serves an address | Same answer as the app for the same address and cart store (one choice rule) | P0 |
| STN-04 | As an admin, I can create stores and edit their details | Name, address, city, location (lat/lng → geohash), phone, hours, delivery radius | P0 |
| STN-05 | As an admin, I can pause and resume a store | Paused store takes no orders; customers see the reason / reopening | P1 |
| STN-06 | As the system, a store pauses automatically when no riders are free | Driven by Fulfillment data | P2 (later) |
| STN-07 | As an admin, a new store stays hidden until it is ready | New stores start in `SETUP`; invisible to customers until opened; `CLOSED` instead of delete | P0 |
| STN-08 | As a customer, if my store is paused or closed for the day I am served by another nearby store | The nearest other store open now that covers my address takes over, with a message, and stays until it stops serving (no switching back at opening time); none open → "Opens at …" or "temporarily unavailable" | P1 |

## Non-functional requirements
- Lookup p99 < 50 ms inside the service; works the same for 1 or 3,000 stores
- Availability 99.9%
- Precise customer coordinates never logged or put in events

## Out of scope
- Delivery zone polygons and the waitlist (later); overlapping radius circles are handled by the choice rule
- One order combining products from several stores ([parking lot](../../parking-lot.md))
- Travel-time-based zones

## Open questions
- ~~Admin auth~~: R1 operator scripts with IAM (D10); staff screens with the staff side
