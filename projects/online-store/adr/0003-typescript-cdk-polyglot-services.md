# ADR-0003: TypeScript CDK for infrastructure, polyglot services

**Status:** Accepted (revised 2026-11-22) · **Date:** 2026-11-14

## Context
Teams should pick the right language per feature, but infrastructure must stay consistent.

## Decision
All infrastructure is AWS CDK in TypeScript. For now each team's CDK package holds its own
constructs, and the `common` repo holds the shared stacks (event bus, web distribution;
[ADR-0014](0014-common-repo-for-shared-infrastructure.md)); there is no Platform team or shared
construct library yet. Services use a paved road of Java (Spring Boot) for business services,
including Support's AI assistant (Bedrock Converse API), and Python for analytics and small event
handlers (e.g. Notifications); React + TypeScript for web.

## Consequences
Consistent infra (shared stacks in `common`, defaults in the system HLD); engineers need TypeScript
for infra even in Java/Python teams. If the same constructs end up copied across teams, a shared
construct library becomes worth its upkeep.

**Revised 2026-11-22** ([design review log §14](../design-review-log.md#14-design-review-fixes-round-3), M-23): no Platform construct library for now; Support's AI is Java (Converse API), not Python.
