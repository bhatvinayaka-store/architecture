# Online Store - System High-Level Design

**Status:** Draft v0.7 - R1 (Catalog, Stores, Inventory, Identity customer side, Ordering) and Support agreed in design review; round-3 fixes and AWS checks 2026-11-22 for review; Notifications to review; staff side after R1 · **Last updated:** 2026-11-22

How all features fit together, and the **defaults** every feature HLD builds on. Feature HLDs only
describe where they differ. Decisions and their reasons: [design review log](design-review-log.md).

## 1. Context
```
 Customer / staff (browser)
        |
  https://<shop>: one CloudFront distribution (common repo)
    /                -> web shell; loads each team's micro-frontend from /mfe/<team>/* (team's S3 bucket)
    /c/*, /p/*, /cart, ... (app routes) -> CloudFront Function rewrites to the shell's /index.html (deep links)
    /api/<public>    -> team APIs directly (Catalog browse, store info: cached; serviceability: POST)
    /api/auth/*, /api/* -> BFF (Identity, TypeScript): session cookie -> access token -> team API
        |
  One API per team, each on its own URL (API Gateway HTTP API, JWT check; /internal = IAM)
        |
 +-------------+-----------+------------+-----------+-----------+------------------+
 |             |           |            |           |           |                  |
 Store Network Catalog     Inventory    Identity    Ordering    Support (R2)       Notifications (R3)
 (stores)      (+CloudFront)                        (cart+checkout)
 |             |           |            |           |           |                  |
 +-------------+-----------+---- EventBridge bus "shop-<stage>" (common repo) ----+
 Later: Payments, Procurement, Data & Analytics, Fulfillment & Delivery (Kafka on EC2 + EKS stint)
```

## 2. Teams, features and data ownership
| Team | Feature | Build order / release | Owns (data) | Compute |
|---|---|---|---|---|
| (shared) | `common` repo ([ADR-0014](adr/0014-common-repo-for-shared-infrastructure.md)) | R0 | Event buses, budget alert, alarm topics, web shell + hosting, event contracts | CDK, React |
| Catalog | Catalog & Search | 1 · R1 (search later) | Products, city prices, categories, listings + badge copy (DynamoDB ×2), images (S3) | Lambda (Java) |
| Logistics | Store Network (minimal) | 1 · R1, built with Catalog | Stores, location + geohash, status (DynamoDB) | Lambda (Java) |
| Inventory | Inventory | 2 · R1 | Stock, batches, reservations, movements, idempotency records (DynamoDB ×5) | Lambda (Java) |
| Identity | Identity & Accounts | 3 · R1 | Cognito user pools (customers, staff), profiles + addresses, BFF sessions | Lambda (Java) + BFF (TypeScript) |
| Commerce | Cart & Checkout (Ordering) | 4 · R1 | Orders, idempotency keys, fee config (DynamoDB); cart in the browser in R1 | Lambda (Java) |
| Customer Experience | Support & AI Assistant | 5 · R2 | Conversations, tickets, help docs (Knowledge Base) | Lambda (Java) + Bedrock |
| Engagement | Notifications | 6 · R3 | Preferences, sent log, templates | Lambda (Python) |
| Payments | Payments | Later | Payments, refunds | Lambda (Java) |
| Supply | Supply & Procurement | Later | Suppliers, POs, receipts (relational, ADR-0011) | Lambda (Java) + Step Functions |
| Data | Data & Analytics | Later | Data lake (S3), Glue catalog | Lambda (Python) + Athena |
| Logistics | Fulfillment & Delivery | Later | Deliveries, rider state, GPS stream (Kafka) | Containers on EKS + Kafka on EC2 |

Platform (construct library, pipeline templates) is **not needed for now**; its documents are kept
unchanged in [platform/](platform/).

**Rules**
- No team reads another team's database. Only APIs, events and published datasets.
- Each team owns its repos, pipeline(s), infrastructure and API URL ([ADR-0002](adr/0002-polyrepo-and-team-ownership.md)).
- Shared pieces live only in the `common` repo and change by PR.

## 3. Platform defaults
| Area | Default | Why |
|---|---|---|
| **Compute** | Lambda. Java: **Spring Boot 3 on Lambda** + SnapStart ([ADR-0016](adr/0016-spring-boot-on-lambda.md)); Python 3.13. Servers/containers only for long-running or stateful work (Fulfillment) ([ADR-0010](adr/0010-serverless-first.md)) | Choose compute by workload shape; no idle cost |
| **APIs** | One API Gateway HTTP API per team per stage, on its own URL; public, customer, admin and `/internal` routes. Browsers reach them through one CloudFront origin; signed-in calls pass through the thin BFF ([ADR-0018](adr/0018-customer-sign-in-with-managed-login-and-bff.md)) | Teams deploy independently; BFF holds no business logic |
| **Auth** | Customers: Cognito customer pool, managed login, session held by the BFF (HttpOnly cookie), access token checked by each API's JWT authorizer; customer ID **only from `sub`**. Staff: separate staff pool on `/admin/*` once the staff side is built (after R1). **R1: operator scripts.** Admin routes use IAM auth in every stage and are called only with the operator's own AWS credentials (`aws login`; human access is managed by AWS in this project, so no extra IAM role), with low throttling; admin writes record the actor `system-operator`; never unauthenticated (decision D10). Public routes open + throttled ([ADR-0018](adr/0018-customer-sign-in-with-managed-login-and-bff.md), [ADR-0019](adr/0019-separate-user-pools-for-customers-and-staff.md)) | Tokens never in the browser; customers can never reach admin routes |
| **Service-to-service** | IAM SigV4 on `/internal` routes (ADR-0012) | No shared secrets |
| **Default database** | **DynamoDB** on-demand, tables per feature per stage; PITR + deletion protection on every prod table, except short-lived tables listed under Data protection | Key-based access, no idle cost |
| **Relational database** | Only where data is truly relational (Procurement, later; ADR-0011, proposed and deferred) | Never chosen just to learn it |
| **Caching** | **CloudFront** for public, identical responses (Catalog browse, 60 s). No Redis unless a feature needs it (rider geo, rate limits, server cart) | Cheapest effective cache; ElastiCache forces VPC/NAT |
| **Search** | OpenSearch as a read model for Catalog search, later; hosting decided then | Not needed for R1 |
| **Events** | One EventBridge bus per stage (`shop-dev`, `shop-prod`) from the `common` repo, archive on (a replay always names its target rules, [§4](#4-event-conventions)); schemas in `common/contracts/` | Decoupled pub/sub, replay |
| **Work queues** | SQS per consumer with DLQ (`maxReceiveCount` 4) + alarm | Reliable retries |
| **Workflows** | Step Functions Standard where waits/compensation are needed (Ordering's payment step when Payments arrives, Procurement); none in R1 | Retries, timeouts, history |
| **Streams** | Kafka only for rider GPS (Fulfillment), self-managed (ADR-0006) | High-volume ordered data |
| **Observability** | Powertools (Java/Python/TypeScript): JSON logs, EMF metrics, X-Ray; `correlationId` everywhere | One way to log and trace |
| **Metrics** | Built-in AWS metrics first (Lambda, API Gateway, DynamoDB, SQS, CloudFront: free). **Custom metrics** only for a signal that has an alarm or a dashboard tile, sent in prod only, never with high-cardinality dimensions (`storeId`, `productId`, `route`, `reason`); detail comes from the JSON logs with Logs Insights. Each LLD lists its custom metrics: about 5 per service, ~30 in total ([§7](#7-cost-budget)) | Each custom metric is billed for every hour it is sent, and every dimension value is a separate metric |
| **Networking** | Lambdas outside a VPC; no NAT gateway | NAT costs more than the budget |
| **Web** | Central shell (`common`) + team micro-frontends: each team's own S3 bucket and pipeline, served same-origin by the one web distribution at `/mfe/<team>/*`; `config.json` per stage lists the bundle URLs. **Each team bundles its own React in R1** (no shared import map: [parking lot](parking-lot.md)). **Deep links** (`/p/P-1001`, refresh on any page) reach the shell through a CloudFront Function that rewrites app routes to `/index.html`, not through custom error responses, which apply to the whole distribution and would turn API 404s into the shell page (CloudFront Functions are allowed in the new AWS experience, checked 2026-11-22; fallback in ADR-0015). Team UIs call same-origin `/api/<team>` and never handle tokens; shared primitives in `common/ui` ([ADR-0015](adr/0015-micro-frontends-with-central-shell.md), [UX design](ux-design.md)) | Teams ship UI independently; strict CSP |
| **Edge protection** | API Gateway throttling on every public route: **20 req/s, burst 40 in prod**, raised only in `dev` for a load test. Public query parameters are validated so junk cannot create cache entries (fixed `limit` values, signed cursors, sorted `ids`). Hourly read-cost alarm on each public table. AWS WAF on CloudFront later | Budget: a flood that bypasses the cache costs at most ~$10-15 a day and the alarm fires within the hour |
| **Time** | Instants stored as ISO-8601 UTC with `Z` (`2026-11-21T10:15:00Z`); keys, indexes and scheduled jobs use UTC instants, never local dates. Store-local values (opening hours, expiry printed on packs) are read in the store's timezone (`Asia/Kolkata`) and converted once, where they enter the system. UIs show store-local time | Lambda clocks run in UTC, stores in IST: one rule prevents 5½-hour mistakes |
| **Timeouts and retries** | Every network call has an explicit timeout; every Lambda sets its timeout (never the 3 s default); retries only for idempotent calls (max 1-2, jittered); each synchronous flow has a timeout budget with one deadline passed down (outer > inner), written in its LLD | No hung requests; predictable failures |
| **Event consumers** | SQS: partial batch responses, DLQ (`maxReceiveCount` 4) + alarm. **Streams (outbox publishers):** bisect on error + partial batch responses; **retry until success, with no retry cap and no maximum record age**, so an outage downstream pauses the shard (records are kept for the stream's 24 h) instead of dropping events; a record with bad data is written whole to the publisher's own DLQ by the handler and skipped; the SQS on-failure destination is the last resort and receives **only shard and sequence numbers, not the records**. Alarm on iterator age > 5 min; [replay runbook](operational-readiness.md). Every copy of another team's data has a repair path (e.g. Inventory's nightly badge reconciliation). Every handler idempotent | No event is lost while the stream still holds it; a bad record never blocks a shard |
| **Data protection** | Prod tables: PITR on, deletion protection on, CDK `RemovalPolicy.RETAIN`; dev: `DESTROY` so teardown works. **No PITR (deletion protection kept)** on short-lived tables that are safe to lose: `identity-bff-sessions` (customers sign in again) and `ordering-idempotency` (24 h keys; a retry across a restore could repeat a checkout: accepted). Table names come from config (SSM), so a PITR restore (always a new table) can be swapped in. **A restored table comes back without Streams, TTL and auto scaling** (verified), so the [restore runbook](operational-readiness.md) also turns on Streams and re-creates the stream's event source mapping (new stream ARN), TTL, PITR, deletion protection, tags and alarms, checks IAM policies that name the table ARN, then runs the feature's reconciliation (events written during the gap). One restore drill before each release. One Region by project rule: no cross-Region copies (accepted risk) | Recoverable, and teardown can't delete prod data |
| **Personal data** | Listed with retention in [§3.1](#31-personal-data-and-retention); never in logs or events (tokens, email, phone, address text, coordinates) | Privacy by default |
| **IDs and randomness** | IDs (ULIDs, session IDs) and other random values are created per request from a secure random source, never during init: SnapStart copies init state to every restored instance; Java builds run AWS's SnapStart scanning rules ([ADR-0016](adr/0016-spring-boot-on-lambda.md)) | Unique IDs under SnapStart |
| **Accessibility** | WCAG 2.2 AA on every UI; `common/ui` primitives carry it; axe checks in each UI pipeline ([UX design](ux-design.md)) | Everyone can order |
| **AI** | Amazon Bedrock (Converse API, Knowledge Base, Guardrails). Claude is offered in Sydney only through inference profiles, so Support uses the Australia (`au.`) profile: requests run in Sydney or Melbourne, never outside Australia, and the project's SCP allows Bedrock calls across Regions (D15). Data, the Knowledge Base and embeddings stay in Sydney | Support |

### 3.1 Personal data and retention
Synthetic data only in this project; the rules mirror what a real shop would need (e.g. India's DPDP Act).

| Data | Where | Kept |
|---|---|---|
| Email, name, password (Cognito stores only a hash) | Cognito customer pool | Until the account is deleted |
| Profile and addresses (phone, address text, coordinates) | `identity-users` | Until the customer deletes them, or the account |
| Address copy on each order (recipient, phone, text, coordinates) | `ordering-orders` | Anonymised 12 months after the order (job later, [parking lot](parking-lot.md)) |
| Session: tokens, plus name and email for the header | `identity-bff-sessions` (no PITR) | 30 days (expiry checked in code; TTL removes rows within a few days) |
| Login state (PKCE verifier, return path) | `identity-bff-sessions` `LOGIN#` rows | 10 minutes (TTL) |
| Chat messages | `support-conversations` | 30 days (TTL); a conversation copied into a ticket is kept with the ticket (12 months) |
| Tickets | `support-tickets` | 12 months |
| Logs | CloudWatch Logs | 30 days; personal data is never logged |
| Backups | DynamoDB PITR | Rolling 35-day window |

**Deletion request (manual in R1):** Cognito user, profile and addresses, sessions, address copies on
orders (anonymised, orders kept), tickets; conversations expire by themselves. Runbook checked in
[operational readiness](operational-readiness.md).

## 4. Event conventions
Every event uses the same envelope (`detail-type` = event name); JSON Schemas live in `common/contracts/`:
```json
{
  "eventId": "uuid",            // consumers de-duplicate on this or on a natural key
  "eventType": "StockLevelChanged",
  "version": 1,                 // bump only for breaking changes; adding fields is safe (tolerant readers)
  "occurredAt": "2026-11-21T10:15:00Z",
  "producer": "inventory",
  "correlationId": "uuid",
  "data": { }
}
```
- Delivery is **at least once**: every consumer is idempotent.
- **Requests strict, events and responses tolerant:** an API rejects unknown request fields (400),
  but every reader of an event or an API response ignores fields it does not know (the shared
  Jackson config turns `FAIL_ON_UNKNOWN_PROPERTIES` off; Python and TypeScript readers do the same),
  so adding a field never breaks a consumer. Contract tests in `common/contracts/` check both rules.
- **Replays name their targets:** an archive replay always lists the rules it re-delivers to
  (`FilterArns`), never the whole bus, so only the team that asked sees old events again
  (Analytics' backfill must not re-send order emails). Consumers that send messages or move money
  (Notifications, Payments) also skip replayed events, which carry a `replay-name` field.
- Events carry the data consumers need (e.g. `AssortmentChanged` includes `categoryId` and `maxPerOrder`).
- No personal data in events beyond IDs (no emails, phones, exact coordinates).

## 5. Key cross-team flows
**5.1 Which store serves the customer**
```
App: delivery location (current location, saved address or map pin: lat/lng)
  -> Store Network: POST /serviceability {lat, lng, keepStoreId?} -> geohash5 cell + 8 neighbours
     -> every store in range (radius <= 4.5 km in Bengaluru), nearest first, with status and opening hours
     -> serving store: the nearest store open now; keepStoreId (the cart's store) is kept while it is open now
        (else "Opens at 7:00 AM" / "temporarily unavailable" / "not served"); one store per order
  -> Catalog: GET /stores/{storeId}/products  (city price, badge, maxPerOrder)
  -> active location {pin, storeId, city} + cart kept in the browser; checkout re-checks the cart's store with the same rule
```
**5.2 Checkout (R1, cash on delivery)**
```
① cart page      Catalog GET /stores/{id}/products?ids=... (public, cached): prices, MRP, badges
② checkout page  (signed in) BFF -> Ordering POST /checkout/preview: Identity address -> Store Network store
                 -> Catalog prices -> Inventory exact stock -> fees (₹25 delivery, free from ₹199; ₹5 platform)
③ place order    BFF -> Ordering POST /checkout (Idempotency-Key, expected total, <= 35 lines)
                 same checks -> Inventory reserve (all or nothing) -> order CONFIRMED (COD) -> 201
  stream -> OrderConfirmed -> Inventory commits (FEFO); a line without stock -> StockCommitFailed
         -> Ordering removes it, lowers the total -> OrderAdjusted
  Reservation fails -> 409 with the failing lines; no order is created
Later with Payments: reserve -> payment (Step Functions, 10 min hold) -> confirm
```
**5.3 Stock badge reaches the catalog** ([ADR-0017](adr/0017-stock-badge-ownership.md))
```
Catalog listing: maxPerOrder ──AssortmentChanged / ListingUpdated──> Inventory (copy)
Inventory stock change -> Streams -> status(available, maxPerOrder) changed? -> StockLevelChanged {status, availableQty if FEW}
  -> Catalog listing badge -> CloudFront (60 s) -> "In stock / Only 2 left / Out of stock"; cart caps at min(maxPerOrder, availableQty)
Checkout's reservation is the final answer.
```
**5.4 Opening a new store**
```
Store Network: create (SETUP) -> StoreCreated -> Catalog: list products (bulk) -> AssortmentChanged
  -> Inventory: stock rows, first delivery (receipts) -> go-live checklist -> open -> StoreStatusChanged -> visible
```
**5.5 Customer signs in and calls an API** ([ADR-0018](adr/0018-customer-sign-in-with-managed-login-and-bff.md))
```
"Sign in" -> /api/auth/login -> Cognito managed login -> /api/auth/callback -> BFF stores tokens
  -> HttpOnly session cookie -> later: browser /api/ordering/... (cookie) -> BFF adds Bearer token
  -> Ordering API: JWT check -> sub = customer ID
```
**5.6 Restocking (later, with Procurement)**
```
Inventory -> StockLow -> Procurement PO -> GoodsReceived -> Inventory batches (Inventory is the only writer, ADR-0008)
```

## 6. Environments and delivery
- Stages `dev` and `prod` as separate stacks in one AWS account (ADR-0004); names
  `<feature>-<resource>-<stage>`, tags `Project=shop`, `Team`, `Stage`.
- Each team's CDK package defines its own pipeline: build → dev → tests → approval → prod (ADR-0002).
  Repos and pipelines are created after the design of all features is finalised.
- Deploy order ([ADR-0014](adr/0014-common-repo-for-shared-infrastructure.md)): **`common` foundation**
  stack (event bus, budget, alarm topics) → **team services** (each writes its API URL and UI bucket
  to SSM) → **`common` edge** stack (web distribution, CloudFront Function, security headers), which
  adds a team's paths only once that team's SSM parameters exist. Re-run the edge stack when a team
  adds an origin. No circular dependency between `common` and the teams.
- Lambda deployments (CodeDeploy) run a **pre-traffic hook** with the feature's smoke test against the
  new version before any traffic moves, then shift all traffic at once and roll back on a hook
  failure or an alarm in the next 10 minutes. A 10% canary would get almost no requests at R1
  traffic and prove nothing; canaries come back when traffic is high enough to judge.

## 7. Cost budget
**Budget:** $120 of credits until 2027-05-13, about **$20 per month**. The Free plan ends on that
date or when the credits run out, whichever comes first; the account then **closes** unless it is
upgraded to the Paid plan within 90 days (AWS keeps the content for 90 days). Sydney prices checked
2026-11-22 (AWS Price List): custom metric $0.30 a month, standard alarm $0.10 a month, log
ingestion $0.67/GB, DynamoDB on-demand $0.1425 per million read units and $0.71 per million write
units. The Always-free offers apply on the Free plan. Other figures are rough estimates; check
them again before each release.

| Item | Idle cost | Notes |
|---|---|---|
| Lambda (incl. BFF), API Gateway, DynamoDB, SQS, EventBridge | ~$0 | Pay per request |
| Cognito | ~$0-1 | Essentials $0.015 per monthly active user in Sydney; demo users cost under $1 |
| Bedrock + Knowledge Base (R2) | per token / per query | Capped by limits and a daily alarm; Knowledge Base storage cost to verify |
| CloudFront (browse cache, images, web) | ~$0-1 | Low traffic |
| CloudWatch alarms | ~$4-6 | Mostly in prod |
| CloudWatch dashboards | $0 | Only 3 dashboards |
| CloudWatch custom metrics | ~$3-6 | About 30 in prod (none in dev) at $0.30 per metric-month after 10 free (Sydney price, checked 2026-11-22), billed per hour sent; rule in [§3](#3-platform-defaults) |
| CloudWatch Logs, X-Ray | ~$0-1 | Under the Always-free allowances at demo traffic (they apply on the Free plan; ingestion beyond them is $0.67/GB); 30-day log retention; X-Ray sampling |
| CodePipeline / CodeBuild | ~$2-5 | Depends on pushes |
| **R1 total (estimate)** | **~$10-18/month** | No database servers in R1. Over $15 a month: cut dev alarms and custom metrics first |

**Learning stints** (created for the stint, destroyed afterwards): OpenSearch (~$1/day), EKS + nodes
(~$3-4/day), Kafka on EC2 (~$0.5/day), ElastiCache/Redis (~$0.5/day), Bedrock (per token, capped).
Guardrails: budget alerts at 50 / 80 / 100% of $20/month (from `common`); every dev stack has a teardown; prod data stacks are retained (see Data protection).

## 8. Decisions
ADR-0001..0019 in [adr/](adr/), plus feature ADRs (e.g. [catalog](features/catalog/adr/),
[inventory](features/inventory/adr/)). New since v0.2: ADR-0014 `common` repo, ADR-0015
micro-frontends, ADR-0016 Spring Boot on Lambda, ADR-0017 stock badge ownership, ADR-0018
customer sign-in with managed login + BFF, ADR-0019 separate user pools; ADR-0002, 0003, 0005, 0009, 0010,
0011, 0012 (now Accepted), 0013, 0014, 0015, 0016, 0017, 0018 revised.

## 9. Open questions for review
1. **Staff side** (after R1): staff pool, roles (staff/manager approval, admin, regional manager), store scoping, admin screens. It replaces the R1 operator scripts and the `system-operator` actor (D10).
2. **Budget:** ~$20/month (credits only), or will you add your own money later?
3. **Region:** ap-southeast-2 with India-based customers in the story: accepted for a learning project?
4. Screen designs (customer + admin): customer rules are in [UX design](ux-design.md); wireframes still to do (UI design pass).
5. Verify AWS details: SnapStart with Spring Boot 3 (priming, early in development) and WAF pricing
   (when WAF is added). Verified 2026-11-22 ([design review log §15](design-review-log.md#15-aws-checks), account and
   AWS docs): this account's **Lambda concurrency limit was 10**, so an increase to 1,000 was
   requested (D14; the BFF cap and the load tests wait for it); CloudFront Functions are allowed
   (only Lambda@Edge is excluded); Bedrock is on the Free plan, with Claude only through inference
   profiles in Sydney (D15); the Always-free offers apply on the Free plan; Route 53 cannot register
   domains on the Free plan; DynamoDB transactions take up to 100 items and 4 MB; CloudFront honours
   `stale-while-revalidate`. Verified 2026-11-21 (AWS docs): TTL deletes within a few days; SnapStart uniqueness rules;
   managed login needs the Cognito Essentials or Plus plan; a Lambda function URL behind OAC needs
   the `x-amz-content-sha256` header (SHA-256 of the body) on POST/PUT; a Streams on-failure
   destination gets metadata only; a PITR restore does not bring back Streams, TTL or auto scaling;
   CloudFront custom error responses apply to the whole distribution.
6. Notifications review (R3).

Resolved: Spring Boot on Lambda (ADR-0016); Cart and Checkout are one feature; customer auth
(ADR-0018, ADR-0019); checkout without Step Functions in R1; Support in Java with a Knowledge Base.

## Change log
| Date | Change | Why | Approved |
|---|---|---|---|
| 2026-11-14 | v0.1 first draft | - | - |
| 2026-11-14 | v0.2: platform defaults, serverless-first, event conventions, cost budget, onboarding flow; Kafka limited to GPS stream | ~$20/month budget; simplification | - |
| 2026-11-21 | v0.3: build order + R1 scope (one store, no payments); Catalog on DynamoDB; Store Network minimal (geohash); stock badge flow; `common` repo; micro-frontends; separate API URL per team; no auth yet; caching/search defaults; Platform not needed for now; costs without Aurora | [Design review log](design-review-log.md) | Agreed in design review 2026-11-15..21 |
| 2026-11-21 | v0.4: customer auth (managed login, BFF, two pools, one CloudFront origin); serviceability POST; checkout flow with preview, fees and `StockCommitFailed`; Support in Java with a Knowledge Base; open questions updated | [Design review log §9-11](design-review-log.md#9-identity-customer-side) | Agreed in design review 2026-11-21 |
| 2026-11-21 | v0.5 (design review fixes): platform rules for time, timeouts, event consumers, data protection, personal data (§3.1), IDs, accessibility; UI bundles served by the one web distribution; admin routes IAM-only until the staff pool exists | [Design review log §12](design-review-log.md#12-design-review-fixes) | Agreed 2026-11-21 (hosting chosen by you) |
| 2026-11-21 | v0.6 (round-2 fixes): outbox publishers retry until success and keep records 24 h, with a replay runbook and repair paths; restore runbook (Streams, mappings, TTL, PITR, IAM, alarms, reconciliation); short-lived tables exempt from PITR; sessions hold name and email; React per team; deep links through a CloudFront Function; `common` split into foundation and edge stacks; verify list updated | [Design review log §13](design-review-log.md#13-design-review-fixes-round-2) (BE-7, DB-7, DB-9, FE-8, FE-9, BE-11, BE-8) | Applied 2026-11-21, for review |
| 2026-11-22 | v0.7 (round-3 fixes): R1 operator scripts with IAM admin routes in every stage and the `system-operator` actor (D10); one store per order with backups and one choice rule (D11); prod throttling of 20 req/s with validated cache keys and a read-cost alarm; metrics rule and cost lines (R1 ~$10-18/month); tolerant readers; replays name their target rules; pre-traffic smoke hook instead of a canary; chat copied into a ticket follows ticket retention; Inventory has five tables; staff side after R1 | [Design review log §14](design-review-log.md#14-design-review-fixes-round-3) (D10, D11, H-1, H-2, M-1, M-10, M-11, M-16, M-17, L-18) | Applied 2026-11-22, for review |
| 2026-11-22 | v0.7 AWS checks: the AI row now says Claude goes through the `au.` inference profile (D15); replay targets and `replay-name` confirmed; Free plan end and Sydney prices in §7 (Cognito ~$0-1); §9 item 5 updated with this account's Lambda limit of 10 and the requested increase (D14) | [Design review log §15](design-review-log.md#15-aws-checks) (D14, D15) | Applied 2026-11-22, for review |
