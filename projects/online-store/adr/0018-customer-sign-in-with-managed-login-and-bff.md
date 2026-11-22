# ADR-0018: Customer sign-in with Cognito managed login and a BFF

**Status:** Accepted · **Date:** 2026-11-21

## Context
Customers browse anonymously and sign in to check out. Every team has its own API on its own URL
(ADR-0002), and the web app is a shell with team micro-frontends (ADR-0015). Tokens kept in browser
storage can be read by any script injected into the page (XSS).

## Decision
- **Sign-in:** Cognito **managed login** (Cognito-hosted pages) on the customer user pool
  (ADR-0019): email + password, email verification, password reset. OAuth 2.0 authorization code
  with PKCE and `state`.
- **Session: a BFF (Backend for Frontend)**, owned by the **Identity team**, written in **TypeScript**,
  running as a Lambda function URL that only CloudFront may call (origin access control, verified
  2026-11-21). OAC signs each request with SigV4, so **on POST and PUT the browser must send
  `x-amz-content-sha256` with the SHA-256 of the body**; the shell's `ctx.api` adds it for every
  team ([ADR-0015](0015-micro-frontends-with-central-shell.md)). A missing or wrong hash fails the
  signature (403).
  - It runs the login, keeps the tokens in DynamoDB (`identity-bff-sessions`, TTL 30 days), and gives
    the browser only a cookie: `__Host-sid` (HttpOnly, Secure, SameSite=Lax).
  - It forwards `/api/<team>/...` to that team's API with `Authorization: Bearer <access token>`,
    refreshing the token when it is about to expire (single-flight per session, so parallel requests
    never sign the customer out; [Identity HLD §5](../features/identity/hld.md#5-architecture)). It holds **no business logic**.
  - CSRF defence: SameSite=Lax + rejecting writes whose `Origin` is not our site.
- **One CloudFront distribution, one origin:** `/` → web shell; `/mfe/<team>/*` → each team's UI
  bucket ([ADR-0015](0015-micro-frontends-with-central-shell.md)); `/api/catalog/stores/*`,
  `/api/stores/stores/*` and `/api/ordering/fees` → team APIs directly (public, cached, cookies
  stripped); `/api/stores/serviceability` → Store Network (public, not cached); `/api/auth/*` and
  every other `/api/*` → BFF (proxy rules in the [Identity HLD](../features/identity/hld.md#5-architecture)).
- Team APIs keep their own URLs and **JWT check at API Gateway**; services take the customer ID only
  from the token's `sub`.
- Access token 60 min, refresh token / session 30 days, refresh rotation and revocation on (rotation
  grace period 10 s, up to 60 s allowed; refreshes use the token endpoint because rotation rules out
  `REFRESH_TOKEN_AUTH`; rotation never extends the 30 days; checked 2026-11-22).
- **Flood and cost protection:** a function URL has no throttling of its own (it is not behind API
  Gateway). R1 caps the BFF with **reserved concurrency** (40, sized in the Identity HLD; a throttled call
  gets 429 and the UI says "Busy right now"), which limits both cost and the load passed to team APIs. Lambda always keeps 100 of the account's concurrency unreserved, so this
  needs an account limit of at least 140. The quota check on 2026-11-22 found 10 (the new-account
  default), so an increase to 1,000 was requested ([log §15](../design-review-log.md#15-aws-checks), D14). If AWS
  grants less than 140, an API Gateway HTTP API with stage throttling goes between CloudFront and
  the BFF instead ([log §13](../design-review-log.md#13-design-review-fixes-round-2), decision D6).
- WAF in front of CloudFront later.

## Consequences
Tokens are never readable by browser scripts; no CORS; team APIs are unchanged. Costs: one more
hop (~10-30 ms warm) for signed-in calls, a session table, the BFF route map to update when a team
is added, and a browser-to-API entry point that must stay thin so it never becomes a central router.

**Revised 2026-11-21** (design review fixes, [log §12](../design-review-log.md#12-design-review-fixes)): `/mfe/<team>/*` and `/api/ordering/fees` behaviours added; BFF proxy rules and session hashing in the Identity HLD.

**Revised 2026-11-21 (round 2)** ([log §13](../design-review-log.md#13-design-review-fixes-round-2), BE-8, BE-10): OAC verified, with the body-hash header on POST/PUT; flood and cost protection for the BFF (reserved concurrency, or API Gateway in front if the account quota is too low).

**Revised 2026-11-22 (round 3)** ([log §14](../design-review-log.md#14-design-review-fixes-round-3), H-4, M-12): single-flight token refresh; reserved concurrency sized at 40, with 429 handling. AWS checks the same day ([log §15](../design-review-log.md#15-aws-checks)): the cap waits for the requested quota increase (the limit was 10); refreshes use the token endpoint.
