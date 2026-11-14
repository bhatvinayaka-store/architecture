# Identity & Accounts - Requirements

**Status:** Draft v0.1 · **Owner:** Identity team · **Last updated:** 2026-11-14

## Goal
Let every type of user (customer, store staff, rider, support agent, admin) sign up, sign in, and manage their profile and delivery addresses, and let services call each other securely.

## User stories
Each story becomes one Jira story in project `STORE`; start the Jira summary with the story ID (e.g. `INV-01: ...`).

| ID | Story | Acceptance criteria | Priority |
|---|---|---|---|
| IDN-01 | As a customer, I can sign up with email and verify it | Verification code sent; unverified users cannot place orders | P0 |
| IDN-02 | As a user, I can sign in, sign out and reset my password | JWT issued; access token expires in 1h; refresh works | P0 |
| IDN-03 | As a customer, I can save multiple delivery addresses | Address stored with lat/lng; one marked default | P0 |
| IDN-04 | As a customer, I can add an address for someone else (e.g. parents' home) | Address has recipient name + phone; served by that area's store | P1 |
| IDN-05 | As an admin, I can assign roles (customer, staff, rider, support, admin) | Role appears in token `cognito:groups`; APIs enforce it | P0 |
| IDN-06 | As a service, I can call another team's API securely | IAM-signed request (SigV4), no shared secrets (ADR-0012) | P1 |
| IDN-07 | As a user, I can enable MFA | TOTP MFA optional for customers, required for admins | P2 |

## Non-functional requirements
- Sign-in p99 < 500 ms
- Passwords never stored by us (Cognito owns credentials)
- PII (phone, address) encrypted at rest; never written to logs

## Out of scope
- Social login (Google) - maybe R2
- Phone/SMS OTP login (needs paid-plan SMS)

## Open questions
- TBD during review
