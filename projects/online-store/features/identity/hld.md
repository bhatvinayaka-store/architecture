# Identity & Accounts - High-Level Design

**Status:** Draft v0.5 - customer side agreed in design review; round-3 fixes and AWS checks 2026-11-22 for review; staff side after R1 · **Owner:** Identity team · **Last updated:** 2026-11-22
**Requirements:** [requirements.md](requirements.md) · **Builds on:** [system HLD platform defaults](../../system-hld.md#3-platform-defaults) · **Decisions:** [design review log](../../design-review-log.md#9-identity-customer-side), [ADR-0018](../../adr/0018-customer-sign-in-with-managed-login-and-bff.md), [ADR-0019](../../adr/0019-separate-user-pools-for-customers-and-staff.md)

## 1. Summary
Cognito handles credentials (sign-up, verification, passwords, tokens) through **managed login**.
The Identity team owns three pieces of our own: the **BFF**, which keeps each customer's session on
the server and forwards signed-in calls to team APIs; the **profile and address service**; and the
post-confirmation trigger. Customers and staff live in **separate user pools**; this document covers
the customer side, the staff side is designed later.

## 2. Goals and non-goals
**Goals (R1):** IDN-01 to IDN-04, IDN-06, IDN-08 to IDN-10.
**Later:** staff side (IDN-05, IDN-07), passkeys / email codes, social login.
**Non-goals:** SMS/phone login (not on the Free plan), self-service account deletion (manual in R1).

## 3. Context
```
 Browser ── https://<shop> (one CloudFront distribution, common repo) ─────────────────────────┐
   /                         -> S3 web shell                                                    │
   /mfe/<team>/*             -> each team's UI bundle (team S3 bucket, OAC; ADR-0015)           │
   /api/ordering/fees        -> Ordering API (public, cached 60 s)                              │
   /api/catalog/stores/*     -> Catalog API (public, cached)                                    │
   /api/stores/serviceability-> Store Network API (public, POST, not cached)                    │
   /api/auth/*               -> BFF: login / callback / logout / me ── Cognito managed login     │
   /api/*                    -> BFF ── cookie -> session -> Bearer token ──> team APIs (JWT check)
                                         │                                   e.g. /me -> Identity profile service
                                         └── identity-bff-sessions (DynamoDB)
 Cognito customer pool ── post-confirmation trigger ──> profile row, UserRegistered
 Ordering, Support, Notifications ── IAM /internal ──> Identity profile service
```

## 4. What drives the design
| Driver | Consequence |
|---|---|
| Never store passwords ourselves | Cognito owns credentials; managed login pages |
| Tokens must not be readable by browser scripts | BFF keeps tokens server-side; browser holds an HttpOnly cookie |
| Every team needs "who is calling" | Access token forwarded by the BFF; each API checks it (JWT authorizer) and uses `sub` |
| Public browsing must stay fast and cached | Public routes bypass the BFF; cookies stripped |
| Addresses decide the store | Saved addresses with a location (current location or a map pin); the store is re-derived, never stored |
| Personal data | Kept in Identity only; not in events or logs |

## 5. Architecture
| Component | Choice | Why |
|---|---|---|
| Customer user pool | Cognito `shop-customers-<stage>`: email as username, self sign-up, email verification, MFA optional, managed login on the Cognito prefix domain, **Essentials** feature plan (managed login and its branding editor need Essentials or Plus; checked in AWS docs 2026-11-21) | [ADR-0019](../../adr/0019-separate-user-pools-for-customers-and-staff.md) |
| App client | Confidential client used by the BFF (secret in SSM SecureString), authorization code + PKCE, scopes `openid email profile`, refresh rotation + revocation on | The BFF is a server, so it can keep a secret |
| Tokens | Access 60 min, refresh 30 days | Agreed |
| BFF | **TypeScript** Lambda function URL behind CloudFront (origin access control, verified 2026-11-21). Every browser POST/PUT, including `/api/auth/logout` (hash of the empty body), carries `x-amz-content-sha256`, added by the shell's `ctx.api`; the BFF never needs it itself and does not forward it | Thin, fast cold start; [ADR-0018](../../adr/0018-customer-sign-in-with-managed-login-and-bff.md) |
| Sessions | DynamoDB `identity-bff-sessions-<stage>`: key = SHA-256 of the session ID; `expiresAt` checked in code (TTL only cleans up, days late); only the BFF's role can read it | Tokens never leave the server; a copy of the table gives no usable cookie |
| Profile & address service | Spring Boot 3 on Lambda (SnapStart), own API URL, JWT authorizer (customer pool) + IAM on `/internal` | Platform default |
| Post-confirmation trigger | Small Lambda: create profile (if absent), emit `UserRegistered` | Keeps Cognito and our data in step |
| Email | Cognito default email for verification/reset: **50 emails a day per account** (checked 2026-11-22); SES later with Notifications | Enough for testing |
| Staff pool | `shop-staff-<stage>`: after R1 (operator scripts until then, D10) | [ADR-0019](../../adr/0019-separate-user-pools-for-customers-and-staff.md) |

**BFF behaviour**
| Route | What it does |
|---|---|
| `GET /api/auth/login?returnTo=` | `returnTo` checked (rule below); new `state` + PKCE verifier saved as a login row (TTL 10 min) → 302 to Cognito managed login. This route is public, so anyone can create login rows: the BFF's concurrency cap limits the rate and TTL removes them. **Option for the LLD:** keep `state` + verifier in a short-lived encrypted HttpOnly cookie (`__Host-login`, 10 min) instead, so starting a login writes nothing |
| `GET /api/auth/callback?code&state` | Check `state` → exchange code + verifier + client secret for tokens → create session → `Set-Cookie: __Host-sid=<random 256-bit>; HttpOnly; Secure; SameSite=Lax; Path=/` → 302 to `returnTo` (checked again) |
| `GET /api/auth/me` | `{signedIn, userId, name, email}` for the shell; never tokens |
| `POST /api/auth/logout` | Revoke the refresh token, delete the session, clear the cookie → Cognito logout |
| `* /api/<team>/...` | Cookie → session → refresh if the access token expires within 5 min (single-flight, below) → forward to the team's API URL (route map) with `Authorization: Bearer` → return the response |
| `POST /api/telemetry/errors` | Browser error reports from the shell ([ADR-0015](../../adr/0015-micro-frontends-with-central-shell.md)): no session needed; body ≤ 8 KB with known fields only (team, version, route path, message, stack, correlation ID), anything else dropped → one structured log line → 204. Never forwarded to a team |
| Every write (POST/PUT/PATCH/DELETE) | Rejected unless `Origin` is our site (CSRF) |

**`returnTo` rule:** a path that starts with exactly one `/` (not `//` or `/\`), with no scheme, host
or control characters, at most 512 characters, and not under `/api/`; anything else becomes `/`.

**Token refresh (single-flight).** The shell loads several sections at once, so several requests can
find the same session due for refresh; with refresh-token rotation on, only the first refresh with a
given refresh token succeeds. So:
1. A request that sees fewer than 5 min left **claims** the refresh: `UpdateItem SET
   refreshClaimUntil = :now + 10 s CONDITION refreshVersion = :seen AND
   (attribute_not_exists(refreshClaimUntil) OR refreshClaimUntil < :now)`.
2. The winner calls Cognito's token endpoint (`grant_type=refresh_token` with the client secret;
   rotation rules out the `REFRESH_TOKEN_AUTH` flow), writes the new tokens with `refreshVersion + 1`
   and removes the claim.
3. The others never refresh: if the current access token is still valid they forward with it; if it
   has already expired they re-read the row (strongly consistent, up to 3 × 300 ms) and use the new
   token, else 503 `TRY_AGAIN` (never a sign-out).
4. Cognito rejects the refresh token (`invalid_grant`: revoked or expired) → the session is deleted
   **only if it still holds that refresh token** (`CONDITION refreshToken = :used`), then 401.
   Cognito slow or down → 503 `TRY_AGAIN`, session kept.
5. Cognito's rotation grace period (`RetryGracePeriodSeconds`, up to 60 s allowed) is set to 10 s as
   a second line of defence. Rotation never extends a session: it still ends 30 days after sign-in
   (both checked 2026-11-22).

**BFF proxy rules** (the BFF forwards only what it must)
| Rule | Detail |
|---|---|
| Route allow-list | Route map from config: `/api/<team>/<path>` → that team's API URL; unknown team → 404. `/admin/*` and `/internal/*` paths are never forwarded (404) |
| Paths | Decoded and normalised once; `..`, `//`, encoded slashes and backslashes rejected (400) |
| Headers | Forwards only `Content-Type`, `Accept`, `Idempotency-Key`, `If-Match`, `X-Correlation-Id` and the `Authorization: Bearer` it adds. Never forwards `Cookie` or a client-sent `Authorization` |
| Body | ≤ 64 KB (413); JSON only on writes |
| Timeouts | Upstream 12 s for `POST /api/ordering/checkout`, 20 s for `POST /api/support/conversations/*/messages`, 5 s otherwise; BFF Lambda timeout 25 s (below CloudFront's 30 s origin timeout); one retry for `GET` only |
| Upstream down | 502 / 504 `{"error": {"code": "UPSTREAM_UNAVAILABLE"}}`; the UI shows "Something went wrong. Try again" |
| Rate limits | Team APIs keep their own API Gateway throttling, but **the BFF is not behind API Gateway**, so that does not protect the BFF itself, `/api/auth/*` or the telemetry route. R1: **reserved concurrency of 40** on the BFF caps load and cost (sizing below); Lambda keeps 100 of the account's concurrency unreserved, so 40 needs an account limit of at least 140. This account's limit was **10** on 2026-11-22 (the new-account default; the AWS default is 1,000), so an increase to 1,000 was requested that day (D14; the load tests need it too). If AWS grants less than 140, an API Gateway HTTP API with stage throttling goes between CloudFront and the BFF ([ADR-0018](../../adr/0018-customer-sign-in-with-managed-login-and-bff.md), D6). In `dev` the cap is raised for a load test (CDK context value), like the public route throttles. A throttled function URL returns **429**: `ctx.api` shows "Busy right now. Try again in a moment" and retries a GET once after 1 s. WAF rate rules later ([parking lot](../../parking-lot.md)) |

**Concurrency sizing** (concurrent requests = requests per second × seconds each one holds a slot).
Every BFF call holds a slot for its whole upstream time. At the load-test target, 200 orders/min ≈
3.3 checkouts/s: about 4 slots at ~1 s each, but up to ~27 when a team is slow and checkouts run to
the 8 s deadline; signed-in reads (~10/s × 0.2 s) add about 2. **40** covers the slow case and still
caps a flood. Revisit for R2 chat (up to 20 s per message).

## 6. Data model
**`identity-users-<stage>`** (pk `userId` = Cognito `sub`)
| sk | Attributes |
|---|---|
| `PROFILE` | name, phone (optional, unverified), defaultAddressId, addressCount, createdAt, updatedAt |
| `ADDR#<addressId>` | label (Home/Work/Other), **line1** (flat / house no., building), **line2** (street, optional), **area** (locality), landmark (optional), pincode, city (code of the serving store's city, e.g. `BLR`; never typed), lat, lng (current location or map pin), recipientName, recipientPhone (10 digits, stored without +91), createdAt, updatedAt |

Max 10 addresses: `PROFILE.addressCount` is updated in the same transaction as the address
(`CONDITION addressCount < 10`), so two parallel adds cannot pass the limit. The location must be
inside the service area. Deleting an address **really deletes** it (orders keep their own copy);
deleting the default address also clears `defaultAddressId` in the same transaction. Setting the
default updates `defaultAddressId`. Table has PITR and deletion protection in prod.

**`identity-bff-sessions-<stage>`** (pk `id`)
| Item | Attributes |
|---|---|
| `SESSION#<SHA-256 of sessionId>` | userId, name, email (from the ID token at sign-in and at every refresh, for `/me`; the ID token itself is not kept), accessToken, refreshToken, accessExpiresAt, **refreshVersion**, refreshClaimUntil (single-flight refresh, §5), **expiresAt** (30 days, checked on every request), createdAt, TTL (= expiresAt) |
| `LOGIN#<state>` | codeVerifier, returnTo, expiresAt + TTL (10 min) |

The cookie holds the random session ID; the table holds only its hash. A stolen refresh token is
useless on its own: the app client is confidential, so refreshing needs the client secret, which only
the BFF's role can read (SSM SecureString). No PITR on sessions: losing them only signs people out.
`PATCH /me` also updates the Cognito `name` attribute, so every session shows a new name after its
next refresh (within an hour); the session that made the change copies it at once from the response.

**In the browser** (owned by the shell): the **active delivery location**
`{addressId | null, lat, lng, storeId, storeName, city, cityName, checkedAt}` in localStorage, all
from the serviceability answer. The serving store is **not** saved on the address: it is looked up
when an address is chosen, on app open and when an API reports the store unavailable; checkout checks
the cart's store on the server with the same choice rule ([Store Network HLD §5](../store-network/hld.md#5-architecture)).
The shell sends its active store as `keepStoreId`, except when the customer chooses a new location or
opens the app with an empty cart. It re-checks when the result is older than 15 min, on tab focus and
on any 409 `STORE_*`, syncs tabs through the `storage` event, and clears `addressId` on sign-out
([ADR-0015](../../adr/0015-micro-frontends-with-central-shell.md)).

## 7. Interfaces
**Who may call what** (applies to every team)
| Route type | Examples | Who | How it is checked |
|---|---|---|---|
| Public | Catalog browse, store info, serviceability | Anyone | No token; CloudFront cache + throttling |
| Customer | `/me`, addresses, checkout, orders, support chat | Signed-in customer | BFF session → access token → JWT authorizer (customer pool); customer ID **only from `sub`** |
| Staff | `/admin/*` | R1: the operator's scripts; staff once the staff side exists | R1: IAM authorizer (D10); later JWT authorizer (staff pool) + role/store check |
| Internal | `/internal/*` | Other services | IAM SigV4 (ADR-0012) |

**Profile & address service** (customer routes reached through the BFF as `/api/identity/...`)
| Method + path | Purpose |
|---|---|
| `GET /me` · `PATCH /me` | Own profile |
| `GET /me/addresses` · `POST /me/addresses` | List / add (max 10) |
| `PUT /me/addresses/{addressId}` · `DELETE /me/addresses/{addressId}` | Update / delete |
| `PUT /me/addresses/{addressId}/default` | Set the default |
| `GET /internal/users/{userId}` (IAM) | Contact details (name, email) for Notifications, Support |
| `GET /internal/users/{userId}/addresses/{addressId}` (IAM) | Address with lat/lng for Ordering; **404 if not that user's** |

**Events:** `UserRegistered {userId}`, `AddressAdded` / `AddressUpdated` / `AddressRemoved
{userId, addressId, area}`. No email, phone or exact coordinates.

## 8. Key flows
**8.1 Sign-up:** managed login sign-up → email code → verified → trigger creates the profile and
sends `UserRegistered` → callback → session cookie → back to the app.

**8.2 Signed-in request**
```
Browser GET /api/identity/me/addresses (cookie) -> BFF: session -> token valid for > 5 min
 -> GET <identity API>/me/addresses  Authorization: Bearer ... -> JWT authorizer -> sub
 -> Query userId = sub -> only this customer's addresses
```
**8.3 Guest becomes a customer at checkout**
```
guest: current location (browser permission) or a map pin placed by tap or keyboard
 -> serviceability -> store + distanceM ("Delivering from Koramangala store, 1.2 km")
 -> browse -> cart (browser) -> "Checkout" -> 401 from the BFF
 -> /api/auth/login?returnTo=/checkout -> sign in / sign up -> back to /checkout
 -> the current location is saved as an address (flat/house and building, area, landmark, recipient) -> checkout preview
```
**8.4 Sign-out:** refresh token revoked, session deleted, cookie cleared. The old access token is
never in the browser, so nothing usable remains on the device. The shell clears `addressId` from the
active location (lat/lng stay, so browsing continues) so the next person on the device never sees
the saved address. **The shell also clears the cart** (`cart.clear()`): the R1 cart lives only in
this browser and is not tied to an account, so on a shared device it would show the previous
person's shopping. The sign-out button says so ("Sign out. Your cart on this device will be
cleared"). A server cart that comes back after sign-in is in the [parking lot](../../parking-lot.md).
A session that merely expires keeps the cart ([UX design §4](../../ux-design.md#4-state-matrix)).

## 9. Failure handling
| Failure | Handling |
|---|---|
| Cognito unavailable | Sign-in fails with a clear message; browsing still works (public routes) |
| Session table unavailable | Signed-in routes return 503; public routes unaffected |
| Refresh token revoked or expired | Session deleted only if it still holds that refresh token (a parallel request may have refreshed it) → 401 → shell sends the user to sign in |
| Several requests need a refresh at once | Single-flight claim on the session row: one Cognito call; the others use the still-valid or newly written token (§5) |
| BFF at its concurrency cap | 429 → "Busy right now. Try again in a moment" (one automatic retry for GET) |
| Post-confirmation trigger fails | Sign-up fails visibly; trigger is create-if-absent; `/me` creates a missing profile lazily |
| Callback with an unknown or expired `state` | Rejected; user restarts sign-in |
| Session past `expiresAt` but not yet removed by TTL | Treated as missing → 401 (TTL deletion can lag by days) |
| A team API is slow or down | BFF timeout → 504 `UPSTREAM_UNAVAILABLE`; other teams' routes unaffected |

## 10. Non-functional design
| Concern | Design |
|---|---|
| Security | Passwords only in Cognito; tokens only in the BFF; HttpOnly + Secure + SameSite cookie; Origin check on writes; proxy rules above; strict Content-Security-Policy on the shell; JWT checked by every API; IAM on internal routes; WAF later |
| Privacy | Events carry IDs only; logs never contain email, phone, address text or coordinates |
| Latency | BFF adds ~10-30 ms (warm) to signed-in calls; public browse unaffected |
| Cost | Cognito Essentials: $0.015 per monthly active user in Sydney (price list, 2026-11-22), so under $1 a month for demo users even without a free tier; Lambda + DynamoDB pay per request |
| Observability | Sign-ups, sign-in failures, BFF latency and errors, refresh failures, address writes. **Alarms:** BFF 5xx > 1%, BFF overhead p99 > 100 ms (time spent in the BFF itself, excluding the upstream call), any 429, refresh failures > 5%, trigger errors > 0, internal lookup 5xx > 1%. Upstream latency is alarmed by each team |

## 11. Alternatives considered
| Option | Decision |
|---|---|
| Tokens in the browser (Amplify) | Rejected for the BFF: an injected script could read them |
| Tokens inside an encrypted cookie | Rejected: the three tokens approach the 4 KB cookie limit |
| One user pool with groups | Rejected: MFA is per pool; customer tokens must never reach admin routes |
| Our own login forms | Rejected: more code, passwords pass through our UI |
| Passing the customer ID from the front end | Rejected: anyone could change it (IDOR) |
| Saving the serving store on the address | Rejected: stores pause and open |
| API keys in the front end / Origin checks as authentication | Rejected: anyone can read or fake them |
| Profiles in Cognito custom attributes | Rejected: addresses are a list |

## 12. Risks and open questions
1. Staff side (pool details, roles, store scoping), after R1. Until then admin routes are IAM-only
   and called by operator scripts (D10), so they are never open.
2. Map: Leaflet + OpenStreetMap tiles, loaded only when the picker opens ([UX design §3](../../ux-design.md#3-location-picker)). OSM's tile policy allows light use only: fine for a demo, change provider if traffic grows.
3. Verify: BFF cold start (early in development). Checked 2026-11-21: managed login needs
   Essentials or Plus; a function URL behind CloudFront OAC works with the body-hash header.
   Checked 2026-11-22 ([log §15](../../design-review-log.md#15-aws-checks)): default email 50 a day; rotation
   grace period up to 60 s, refreshes through the token endpoint; Essentials $0.015 per active user;
   this account's Lambda limit was 10, so an increase to 1,000 was requested (D14).
4. Address search (geocoding) is not in R1; [parking lot](../../parking-lot.md).

## Change log
Record every design change here with its reason ([scope control](../../scope-control.md)).

| Date | Change | Why (story / requirement) | Approved |
|---|---|---|---|
| 2026-11-14 | v0.1 first draft | - | - |
| 2026-11-21 | v0.2 (customer side): two user pools; managed login; BFF in TypeScript with server-side sessions; one CloudFront origin; public routes bypass the BFF; route-access rules; addresses (server) vs active location (browser); store never saved on addresses; real address deletes | [Design review log §9](../../design-review-log.md#9-identity-customer-side) | Agreed in design review 2026-11-21 |
| 2026-11-21 | v0.3 (design review fixes): sessions keyed by hash, `expiresAt` checked in code, ID token not stored; BFF proxy rules (allow-list, headers, body limit, timeouts); `addressCount` limit in a transaction; deleting the default clears it; location by current location or tap/keyboard pin; sign-out clears the active address; Essentials plan; PITR on users | [Design review log §12](../../design-review-log.md#12-design-review-fixes) | Agreed 2026-11-21 |
| 2026-11-21 | v0.4 (round-2 fixes): OAC verified with the body-hash header; the BFF is not behind API Gateway, so reserved concurrency (or an HTTP API in front) protects it; login rows created by a public route noted, cookie option for the LLD; telemetry route for browser errors; sign-out clears the cart on the device | [Design review log §13](../../design-review-log.md#13-design-review-fixes-round-2) (BE-8, BE-10, FE-13, UX-11) | Applied 2026-11-21, for review |
| 2026-11-22 | v0.5 (round-3 fixes): single-flight token refresh (claim on `refreshVersion`; a session is deleted only if it still holds the failed refresh token; rotation grace period); BFF reserved concurrency sized at 40, 429 handled; BFF alarm on its own overhead, not upstream time; exact `returnTo` rule; session name kept current; address fields aligned with the UX form (`line1`, `line2`, `area`, city from the store); active location carries `city`/`cityName` and sends `keepStoreId`; admin routes IAM-only for operator scripts | [Design review log §14](../../design-review-log.md#14-design-review-fixes-round-3) (H-4, M-1, M-2, M-12, M-15, L-13, L-14, L-15, D10, D11) | Applied 2026-11-22, for review |
| 2026-11-22 | v0.5 AWS checks: the account's Lambda limit was 10, so an increase to 1,000 was requested before the BFF cap can be set (D14), with the D6 fallback if less is granted; the cap is raised in `dev` for load tests; refreshes go through the token endpoint (rotation rules out `REFRESH_TOKEN_AUTH`); default email 50 a day; Essentials price | [Design review log §15](../../design-review-log.md#15-aws-checks) (D6, D14) | Applied 2026-11-22, for review |
