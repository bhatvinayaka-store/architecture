# ADR-0002: Polyrepo with team ownership

**Status:** Accepted (revised 2026-11-20) · **Date:** 2026-11-14

## Context
We want to simulate multiple teams that own features end to end and cannot change each other's code.

## Decision
- Each team owns its own repos (service code, CDK infrastructure, web UI, data) and its own
  pipeline(s). Teams interact only through APIs, events and published schemas (in the `common`
  repo's `contracts/`, ADR-0014). The architecture repo is readable by everyone.
- **Each team exposes its own API on its own URL**; the feature's routes live inside it. There is
  no central routing server. Browsers reach team APIs through one CloudFront origin: public reads
  go straight to the team API, signed-in calls pass through the thin BFF that only adds the token
  ([ADR-0018](0018-customer-sign-in-with-managed-login-and-bff.md)).
- Each service's CDK package defines its own pipeline (build → dev → tests → approval → prod),
  the way Amazon teams own a CDK package per service.
- Repos and pipelines are created **only after the design of all features is finalised**.

**Revision (2026-11-20):** "one team pipeline with multiple repo sources" replaced by a pipeline
defined in each service's own CDK package; added the separate-URL rule and "create repos after design".

**Revision (2026-11-21):** browser access via one CloudFront origin and the BFF (ADR-0018).

## Consequences
Realistic boundaries and independent releases; more repos and pipelines to maintain; cross-team
changes need contract tests and versioning; the BFF's route map lists each team's API.
