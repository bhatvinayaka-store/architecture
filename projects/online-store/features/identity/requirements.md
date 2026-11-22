# Identity & Accounts - Requirements

**Status:** Draft v0.4 (customer side; round-3 fixes) · **Owner:** Identity team · **Last updated:** 2026-11-22

## Goal
Let customers sign up, sign in and manage their profile and delivery addresses safely; keep their session on the server; and let services call each other securely. Staff accounts are designed separately.

## User stories
Each story becomes one Jira story in project `STORE`; start the Jira summary with the story ID (e.g. `IDN-01: ...`).

| ID | Story | Acceptance criteria | Priority |
|---|---|---|---|
| IDN-01 | As a customer, I can sign up with email and verify it | Cognito managed login; verification code; unverified users cannot sign in or order | P0 |
| IDN-02 | As a customer, I can sign in, sign out and reset my password | Session kept by the BFF (HttpOnly cookie); signed in for up to 30 days; sign-out revokes the session | P0 |
| IDN-03 | As a customer, I can save multiple delivery addresses | Text address + location (lat/lng) from my current location or a map pin I can place by tap, drag or keyboard, confirmed in text ("Koramangala store, 1.2 km away"); max 10; one default; delete really deletes (deleting the default clears it) | P0 |
| IDN-04 | As a customer, I can add an address for someone else (e.g. parents' home) | Address has recipient name + phone; served by that area's store | P1 |
| IDN-05 | As an admin, I can manage staff accounts and roles | Staff pool, roles (staff, manager, admin, regional manager) | Later (staff side) |
| IDN-06 | As a service, I can call another team's API securely | IAM-signed request (SigV4), no shared secrets (ADR-0012) | P1 |
| IDN-07 | As staff, I must use MFA | MFA required in the staff pool | Later (staff side) |
| IDN-08 | As a guest, I can browse and fill a cart without an account, and sign in at checkout | Public routes need no session; after sign-in I return to checkout with my cart | P0 |
| IDN-09 | As a customer, nobody can see my data by changing an ID in a request | Every service takes my ID only from the verified token | P0 |
| IDN-10 | As a customer, my delivery location decides my store | Active location kept in the browser; store looked up again when it may have changed | P0 |

## Non-functional requirements
- Sign-in p99 < 500 ms; BFF adds < 30 ms (warm) to signed-in calls
- Passwords never stored by us; tokens never readable by browser scripts
- PII (phone, address) encrypted at rest; never written to logs or events
- Location picker and sign-in usable with keyboard and screen reader (WCAG 2.2 AA)

## Out of scope
- Social login, passkeys, email codes (parking lot)
- Phone/SMS OTP login (needs paid-plan SMS)

## Open questions
- Staff side: after R1; until then the operator uses IAM-signed scripts (D10)
- ~~Map tiles~~: decided, Leaflet + OpenStreetMap, lazy-loaded ([UX design §3](../../ux-design.md#3-location-picker))
