# ADR-0012: IAM (SigV4) for service-to-service calls

**Status:** Accepted (2026-11-22) · **Date:** 2026-11-14

## Context
Teams call each other's APIs (e.g. Checkout -> Inventory reservations). Calls need
authentication and least-privilege authorization without secrets to store and rotate.

## Decision
- Each team's HTTP API exposes internal routes under `/internal/...` with **IAM authorization**.
- The calling Lambda's role is granted `execute-api:Invoke` on exactly the routes it needs.
- When a call is made on behalf of a customer, the caller passes the verified `userId`, and the
  called team enforces ownership (e.g. an order belongs to that user).
- Cognito JWTs are used only for calls from the browser.

## Consequences
No shared secrets; permissions are visible in CDK code and reviewed in PRs. Cross-team grants
require knowing the other team's API ARN (published via SSM by the owning team).

**Accepted 2026-11-22** ([design review log §14](../design-review-log.md#14-design-review-fixes-round-3), M-23): every HLD already relies on it (`/internal` routes with IAM).
