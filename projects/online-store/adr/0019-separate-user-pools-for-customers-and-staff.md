# ADR-0019: Separate Cognito user pools for customers and staff

**Status:** Accepted (staff details to be designed) · **Date:** 2026-11-21

## Context
v0.1 put every user in one pool with roles as groups. Customers and staff need different rules:
customers sign themselves up and MFA is optional; staff are created by an admin and must use MFA.
Cognito sets MFA per pool.

## Decision
- **Customer pool** `shop-customers-<stage>`: self sign-up, email verification, MFA optional.
  Its tokens are accepted only on customer routes.
- **Staff pool** `shop-staff-<stage>`: no self sign-up (admins create accounts), MFA required.
  Its tokens are accepted only on `/admin/*` routes (a separate JWT authorizer per pool).
- Staff roles agreed in principle, designed later: **staff** (lists items, a manager approves),
  **manager** (all permissions for their own store, can list and approve directly), **admin** and
  **regional manager** (permissions across stores).

## Consequences
MFA and sign-up rules fit each group cleanly, and a bug in a role check cannot let a customer token
reach an admin route. Costs: two pools to configure, and a separate staff sign-in entry in the UI.
