# Design Review Log

A running record of design decisions made in review sessions: **what** was decided, **why**, and
**where** it is written down. Newest entries at the bottom of each section. When a decision changes
a document, the document's change log points back here.

**Sessions covered:** 2026-11-15 to 2026-11-22: Catalog, Stores, Inventory, cross-cutting, then
Identity (customer side), Ordering and Support, followed by three rounds of review fixes (§12-§14) and AWS checks (§15).
**R1 design is complete** (Notifications still to review; the staff side comes after R1, D10).

## 1. Process and scope
| Date | Decision | Why | Recorded in |
|---|---|---|---|
| 2026-11-15 | Design every feature first, then finalise all docs, **then** start development | Avoid rework; keep the main goal in view | This log, [README](README.md) |
| 2026-11-15 | Build order: **Catalog → Inventory → Identity → Ordering → Support → Notifications**. Store Network (minimal) is built with Catalog | Catalog is what customers see first; each step builds on the previous one | [README](README.md#build-order), [system HLD](system-hld.md) |
| 2026-11-15 | R1 starts with **one store (BLR-S-01)**; the design must scale to ~3,000 stores and 45-80K products | Small first release, no redesign later | [requirements](requirements.md), feature HLDs |
| 2026-11-15 | **No Payments feature for now**: checkout reserves stock and confirms the order immediately (cash on delivery) | Simplify R1; Payments slots in later without changing Inventory | [Ordering README](features/ordering/README.md), [Payments README](features/payments/README.md) |
| 2026-11-15 | **Platform is not needed for now**; its documents are left untouched | Each team owns its repo, pipeline and infra (like Amazon teams did); a central tooling team is not needed at this size | This log; shared parts move to the `common` repo ([ADR-0014](adr/0014-common-repo-for-shared-infrastructure.md)) |
| 2026-11-20 | Repos and pipelines per team are created **only after the design is finalised** | Design first | [ADR-0002](adr/0002-polyrepo-and-team-ownership.md) |
| 2026-11-20 | **No auth for now**; auth guardrails are decided with the Identity feature | Identity is designed after Catalog/Inventory | [system HLD](system-hld.md#9-open-questions-for-review) (open item) |

## 2. Cross-cutting architecture
| Date | Decision | Why | Recorded in |
|---|---|---|---|
| 2026-11-15 | **Serverless for every feature except Fulfillment's streaming parts** (Kafka broker, stream processing, rider tracking) | Choose compute by workload shape: low/spiky traffic and short requests → Lambda; long-running/stateful → servers or containers | [ADR-0010](adr/0010-serverless-first.md) |
| 2026-11-15 | **Never choose a technology just to learn it**; RDS is used only where data is truly relational | Design quality first; learning follows the right fit | [ADR-0010](adr/0010-serverless-first.md), [catalog ADR-0001](features/catalog/adr/0001-dynamodb-two-tables.md) |
| 2026-11-15 | **No central routing server**; each team owns its own API | A central server is a single point of failure and a bottleneck; API Gateway already routes | [system HLD](system-hld.md) |
| 2026-11-20 | **Spring Boot 3 on Lambda** (+ SnapStart) for all Java services | Portable, employer-relevant skills; same app runs locally | [ADR-0016](adr/0016-spring-boot-on-lambda.md) |
| 2026-11-20 | **Separate API URL per feature/team**; the feature's routes live inside it | Mimics independent teams | [ADR-0002](adr/0002-polyrepo-and-team-ownership.md) |
| 2026-11-20 | **Central UI shell with a placeholder per team** (micro-frontends); each team develops and tests its UI alone | Teams cannot see or depend on each other's UI code | [ADR-0015](adr/0015-micro-frontends-with-central-shell.md) |
| 2026-11-20 | **`common` repo** for everything shared: event buses, budget alert, alarm topics, web shell + hosting, event contracts | One place for shared pieces, in code (not console clicks); no full Platform team | [ADR-0014](adr/0014-common-repo-for-shared-infrastructure.md) |
| 2026-11-15 | **No Redis** for Catalog (CloudFront already caches); Redis later where it fits (rider locations with Redis GEO, rate limiting, server cart) | Don't add a cache that isn't needed; ElastiCache also forces a VPC/NAT | [parking lot](parking-lot.md), [catalog HLD](features/catalog/hld.md) |
| 2026-11-21 | **No read replicas** for Inventory: DynamoDB + CQRS (customers read Catalog's copy behind CloudFront) | DynamoDB already keeps 3 copies; heavy reads never reach Inventory | [ADR-0017](adr/0017-stock-badge-ownership.md) |
| 2026-11-21 | **Search (OpenSearch) is a Catalog feature for later**; hosting (managed stint vs Oracle Always Free) decided when it starts | Not a fit for Inventory (no atomic writes, ~1 s refresh); not needed for R1 | [parking lot](parking-lot.md) |

## 3. Catalog
| Date | Decision | Why |
|---|---|---|
| 2026-11-15 | **DynamoDB, not Aurora** | Each product type has different attributes; all reads are key-based; no idle cost |
| 2026-11-20 | **Two tables**: `catalog-products` (products, city prices, categories) and `catalog-store-listings` (per-store listings, category counts, store status copy) | Clearer than a single table while learning |
| 2026-11-15 | Products stored **once**; one small **listing row per store per product** | No duplication of product data; a new store only adds listing rows |
| 2026-11-15 | **Category → subcategory** (e.g. Dairy → Milk → "Nandini Milk (orange packet) 500 ml"); browse index `byStoreCategory` = `storeId#category` + `subcategory#rank#productId` | One index serves both "all Dairy" and "only Milk" (hierarchical sort key) |
| 2026-11-15 | **Soft delete only**: product `status` (global), listing `listed` (per store; unlisted rows leave the browse index) | Keep history; allow re-listing |
| 2026-11-15 | Listing rows do **not** copy name/price | A price change is one write, not one per store |
| 2026-11-15 | **Price per city** (`PRICE#<city>` item per product) | Multi-city pricing; stores carry a city |
| 2026-11-21 | **`maxPerOrder` per store + product**, fixed, set by the merchandiser: the purchase limit **and** the "few left" trigger (few left = available < maxPerOrder) | Customers see the limit while adding to the cart, never as a surprise at checkout |
| 2026-11-15 | **CloudFront** caches public browse responses (60 s); no Redis | Cheap, handles read-heavy traffic; checkout re-checks prices and stock |
| 2026-11-15 | Full API set: public store-scoped reads; admin categories, products, images, city prices, listings (single + bulk); internal prices | Agreed in review |
| 2026-11-15 | Scale check: 3,000 stores × ~8K products ≈ 24M listings (~5 GB) is fine; write volume and hot keys are the real limits | Design holds without changes |
| 2026-11-21 | LLD refinements: product split into `META` (card) + `DETAIL` (description, attributes); `byProduct` index; one jar as three Lambda functions with separate IAM roles; Streams outbox; Catalog's own images CloudFront | Browse reads ≈5× cheaper; least privilege; events always match saved data ([LLD](features/catalog/lld.md)) |

## 4. Stores (Store Network, minimal for R1)
| Date | Decision | Why |
|---|---|---|
| 2026-11-15 | Stores are their **own service** (Store Network), built full stack | Store data belongs to one owner; Catalog only uses `storeId` |
| 2026-11-15 | Store data: name, address, **city**, lat/lng, **geohash5**, phone, opening hours, delivery radius, opened date | City needed for pricing; extra metadata (GST, FSSAI, capacity) added when a feature needs it |
| 2026-11-15 | Lifecycle **`SETUP → OPEN ⇄ PAUSED → CLOSED`** with action endpoints; no delete | A new store is invisible while being set up; history kept |
| 2026-11-15 | **Serviceability by geohash**: user's geohash5 cell + 8 neighbours → candidate stores → exact distance check → nearest. Max delivery radius 5 km (default 3 km) | Avoids checking every store; standard proximity technique |
| 2026-11-15 | A **paused store is skipped**: the customer gets the next nearby OPEN store within 5 km, else "temporarily unavailable" | Keep serving customers when one store pauses |
| 2026-11-15 | R1 uses a **radius**; hand-drawn delivery zone polygons come later when stores overlap | One store needs no polygons |

## 5. Inventory
| Date | Decision | Why |
|---|---|---|
| 2026-11-21 | **Four tables**: `inventory-stock`, `inventory-batches`, `inventory-reservations`, `inventory-movements` | One kind of item per table; transactions can span tables |
| 2026-11-21 | **Batches with expiry**, sold **FEFO** (first expired, first out); **minimum shelf life** per product (category defaults: milk 12 h, curd/bread 24 h, chips 7 d, rice 30 d) | Groceries expire; validated with the [sample dataset](data/seed/inventory-sample.md) |
| 2026-11-21 | **Reserve → commit / release** kept even without payments | No change needed when Payments arrives |
| 2026-11-21 | Badge = **available (onHand − reserved)**, i.e. reservation-aware | The badge matches what checkout will allow |
| 2026-11-21 | Inventory keeps a **copy of `maxPerOrder`** (from Catalog events) and sends `StockLevelChanged` **only when the status changes**, or when the count changes while "few left" | Few events (e.g. ~4 per product per day instead of one per checkout); stock logic stays in Inventory |
| 2026-11-21 | Expiry collides with a reservation → commit takes the next batch, else that line fails with `LINE_UNAVAILABLE`; expiry job runs 1 h before stop-selling time | Found in the sample walkthrough |
| 2026-11-21 | `AssortmentChanged` carries `categoryId` and `maxPerOrder` | Inventory needs them when a product is first listed |
| 2026-11-21 | Idempotency via natural keys (`orderId`, `receiptId`, `adjustmentId`); no "processed events" table | Simpler |

## 6. Ordering (decided early; full review in §10)
| Date | Decision | Why |
|---|---|---|
| 2026-11-21 | **Cart lives in the browser (localStorage) in R1**; a server cart table (`ordering-carts`, TTL) comes after Identity, with guest-cart merge at login | No backend or login needed for R1; checkout re-checks everything |
| 2026-11-21 | **No separate cart service**: cart and checkout stay one feature | They change together |
| 2026-11-21 | Limits: **max 35 different products per order**; per product the store's `maxPerOrder` | Fits DynamoDB's 100-item transaction (35 × 2 + 1 = 71) |
| 2026-11-21 | Adding to the cart does **not** reserve stock; reservation happens at checkout | Prevents hoarding |

## 6b. Other features: compute shape (agreed 2026-11-15, details reviewed per feature later)
| Feature | Choice | Notes to carry into its review |
|---|---|---|
| Identity | Cognito + a small Lambda | Cognito does most of the work |
| Payments (later) | SQS worker Lambda + a Lambda endpoint for payment-gateway webhooks | Never charge twice: idempotent on orderId |
| Notifications | EventBridge → SQS → Lambda → SES | Dedup log so no email is sent twice |
| Support | Lambda + Bedrock (+ Knowledge Base), conversations in DynamoDB | Start with request/response; streaming answers (WebSocket API or Lambda response streaming) later; cap tokens per conversation |
| Procurement (later) | Lambda + Step Functions Standard (POs wait days) | Relational database by fit |
| Analytics (later) | Lambda → S3 data lake, Glue catalog, Athena | Partition data so Athena scans less |
| Fulfillment (later) | **The exception**: Kafka broker on EC2, Kafka Streams in containers (EKS stint), Redis GEO for live rider positions; route optimiser as Lambda or container | Long-running, stateful work |
| Web | S3 + CloudFront | Shell + team micro-frontends |

## 7. Repository and workflow
| Date | Decision | Why |
|---|---|---|
| 2026-11-14 | Architecture repo published: `main` started with an empty commit; changes go through PRs; branches and PR titles use the **Jira task key** (e.g. `STORE-2`), never the epic key (`STORE-1`) | PR-based history linked to Jira |
| 2026-11-14 | Jira automation comments on the task when a PR is created / merged / declined | Traceability without manual comments |
| 2026-11-14 | Claude Code review workflow runs on every PR and **comments**; a human merges | AI reviews, humans approve |
| 2026-11-14 | Repo names stay lowercase kebab-case (`analytics-infra`); no `STORE-` prefix | Org name already scopes them; lowercase-only tools (ECR, S3, npm) |

## 8. Open items carried forward
| Item | Decide when |
|---|---|
| **Staff side**: staff pool details, roles (staff lists → manager approves; manager = all permissions for their store; admin and regional manager across stores), store scoping, admin screens, support agent console | Staff-side design (next) |
| Create the **staff user pool + token check before Catalog's first deploy**, so admin routes are never open (security). Until then admin routes use **IAM auth, `dev` only** (§12) | Staff-side design |
| Customer and admin screen designs: customer rules, states and the out-of-stock look are now in [UX design](ux-design.md); wireframes and admin screens still to do | UI design pass |
| ~~Map tiles for the address pin~~: **decided** 2026-11-21, Leaflet + OpenStreetMap, lazy-loaded; current location first ([UX design §3](ux-design.md#3-location-picker)) | Done |
| Search hosting (managed OpenSearch stint vs Oracle Always Free) | Catalog search |
| Seed data source (Open Food Facts licence/attribution) | Before development |
| **Language** for Notifications and Analytics (Support decided: Java) | Those features' reviews |
| **Run services locally as containers too** (same Spring Boot app: Docker + Kubernetes with `kind`, Spring Cloud Gateway, Resilience4j; a short EKS stint) to learn how microservices are *run*, while AWS stays on Lambda | When those features are reached (2026-11-21) |
| **Verify Bedrock for Support**: available on the Free plan? Claude models on-demand in ap-southeast-2 without cross-Region inference? Managed Knowledge Base + embedding model in-Region? (fallback: self-managed KB on S3 Vectors; never OpenSearch Serverless) | Before Support development |
| Verify AWS details: SnapStart with Spring Boot 3 (priming), CloudFront `stale-while-revalidate`, Cognito Essentials free tier and default email limit, WAF on CloudFront (flat-rate plan), Lambda function URL with CloudFront OAC, Lambda concurrency quota, free-tier costs. **Checked 2026-11-21 (AWS docs):** TTL deletes within a few days; SnapStart uniqueness rules; managed login needs Cognito Essentials or Plus | Start of development |

## 9. Identity (customer side)
| Date | Decision | Why |
|---|---|---|
| 2026-11-21 | **Two Cognito user pools: customers and staff**; staff side designed later | Staff need MFA and no self sign-up; customer tokens can never reach admin routes ([ADR-0019](adr/0019-separate-user-pools-for-customers-and-staff.md)) |
| 2026-11-21 | **Cognito managed login** (hosted sign-up, sign-in, verification, reset); email + password; authorization code + PKCE | Passwords never touch our code; least code |
| 2026-11-21 | **BFF (Backend for Frontend)** holds the session: tokens stay on the server, the browser gets an HttpOnly cookie; **owned by Identity, written in TypeScript** | Tokens never reachable by browser scripts ([ADR-0018](adr/0018-customer-sign-in-with-managed-login-and-bff.md)) |
| 2026-11-21 | One CloudFront distribution serves the shell and `/api/*` on **one origin**; the BFF forwards `/api/<team>/...` to each team's own API with the access token; teams keep their own URLs and token checks | First-party cookies, no CORS; BFF holds no business logic |
| 2026-11-21 | **Public browse and store info bypass the BFF** (cached, cookies stripped); serviceability bypasses it, not cached | Caching works; no session needed for public data |
| 2026-11-21 | Access token **60 min**, session **30 days**, refresh rotation + revocation; CSRF defence = SameSite=Lax + Origin check | Agreed |
| 2026-11-21 | **Customer ID only from the verified token** (`sub`), never from the URL/body | Prevents reading other customers' data (IDOR) |
| 2026-11-21 | Protection layers: token check at API Gateway → ownership check in the service → IAM on `/internal` → throttling → CORS; **WAF later** | "Only our UI can call the backend" can't be guaranteed; the backend never trusts the UI |
| 2026-11-21 | **Saved addresses on the server** (default on the profile); **active delivery location in the browser**; the serving store is **not saved** on the address; checkout re-derives it | Stores pause/open; client storeId is never trusted |
| 2026-11-21 | Addresses are **really deleted** (orders keep their own copy) | Privacy; exception to "no hard deletes", which covers business records |
| 2026-11-21 | **`POST /serviceability {lat, lng}`** instead of GET | Coordinates must never appear in access logs |

## 10. Ordering (full review)
| Date | Decision | Why |
|---|---|---|
| 2026-11-21 | **Cash on delivery; no Step Functions in R1**: checkout is one synchronous call returning 201 CONFIRMED or 409 with failing lines | Nothing to wait for without payments; saga returns with Payments |
| 2026-11-21 | Crash-safe without a PENDING state: orderId fixed in the idempotency row, Inventory reserve idempotent on it, order written after a successful reserve; **failed attempts create no order** | Clean order history; retries are safe |
| 2026-11-21 | **Three checkpoints**: cart page (Catalog `?ids=` lookup, cached) → checkout page (`POST /checkout/preview`, live across Identity, Store Network, Catalog, Inventory, nothing reserved) → place order (checks again + reserve) | No surprises for the customer; only the reservation guarantees stock |
| 2026-11-21 | Total seen in the preview is sent with checkout; mismatch → 409, page refreshes the preview | Customer never pays an amount they did not see |
| 2026-11-21 | **No customer cancellation in R1** (later, with Fulfillment) | No picking/delivery yet |
| 2026-11-21 | **Fees**: delivery ₹25, **free from ₹199** subtotal; **platform fee ₹5**; config per city in Ordering; fee copy saved on the order; fees never increased after the order | Agreed; changeable without deploy |
| 2026-11-21 | Prices are set by the merchandiser (packaged goods ≤ MRP; fresh produce daily, sold in fixed packs); purchase cost belongs to Procurement | Explains when prices change |
| 2026-11-21 | **`StockCommitFailed`** from Inventory → line marked unavailable, total recalculated (fees not increased), `OrderAdjusted`; all lines failed → system `CANCELLED(OUT_OF_STOCK)` | Rare expiry race handled cleanly |
| 2026-11-21 | Tables `ordering-orders` (+ `byUser`), `ordering-idempotency` (TTL), `ordering-config` (fees); events via DynamoDB Streams | Same outbox pattern as Inventory |
| 2026-11-21 | Catalog adds the **`?ids=` batch lookup** and **`mrpPaise`** (selling price never above MRP) | Cart refresh for guests; legal MRP rule; "you save" display |

## 11. Support (R2)
| Date | Decision | Why |
|---|---|---|
| 2026-11-21 | **Java** (Spring Boot on Lambda + AWS SDK Converse API), our own tool-use loop; no Bedrock Agents (maintenance mode), no AgentCore | One backend language; few tools |
| 2026-11-21 | **Bedrock Knowledge Base** for policies (Managed KB; fallback self-managed on S3 Vectors); docs in git → S3 → ingestion → evals | Chosen in review (prompt-only was the simpler alternative) |
| 2026-11-21 | Retrieval is a **tool** (`search_policies`); other tools `list_my_orders`, `get_order`, `create_ticket`; userId always from the token | Order questions skip retrieval; model cannot fetch other users' data |
| 2026-11-21 | **Request/response** chat through the BFF ("typing…"); streaming later | Simple; fits the BFF |
| 2026-11-21 | **Signed-in customers only** | Order tools need a user; cost and abuse control |
| 2026-11-21 | **Bedrock Guardrails**: prompt-attack filter + denied topics | Agreed |
| 2026-11-21 | Limits: 20 turns, 3 tool calls/turn, 512 output tokens, 30 messages/hour/user, daily cost alarm; message text never logged; conversations TTL 30 days | Cost and privacy |
| 2026-11-21 | Scope in R2: policies, order details/status, tickets; no live ETA (Fulfillment), no agent console (staff side) | Honest scope for R2 |

## 12. Design review fixes
Combined UI/UX, front-end, back-end and database review of the R1 docs (2026-11-21): **24 findings**
(2 critical, 8 high, 14 medium), all fixed in the docs on 2026-11-21. Each changed document has a
change-log row pointing here.

**Decisions**
| # | Question | Decision | Why | Approved |
|---|---|---|---|---|
| D1 | Checkout: live calls or local copies of other teams' data | Keep the **live synchronous calls** in R1, with a timeout budget (8 s deadline) | Simplest; local copies add events and staleness | Recommendation applied 2026-11-21 (open to change) |
| D2 | Cart size vs the 100-item transaction limit | Keep **35 lines**; **commit in chunks** | Keeps the agreed limit; line status makes chunks safe to retry | Recommendation applied 2026-11-21 |
| D3 | Where team UI bundles are hosted | **One web CloudFront**: `/mfe/<team>/*` from each team's own S3 bucket and pipeline | Same origin: strict CSP, no CORS | **Your choice** 2026-11-21 |
| D4 | Admin UIs inside the customer shell or a separate staff shell | Decided in the staff-side design (recommendation: separate shell on its own domain); `/admin` removed from the customer shell | A script-injection bug on the customer side can't reach staff sessions | Deferred to staff-side design |
| D5 | Address search (geocoding) | **None in R1**: current location, saved addresses or a pin (tap or keyboard) | Not needed for one store; Amazon Location on the Free plan unverified | Recommendation applied ([parking lot](parking-lot.md)) |

**Findings → fixes**
| Finding | Fix | Where |
|---|---|---|
| DB-1 [Critical] Inventory commit exceeds 100 items for 34+ lines | Commit in chunks of ≤ 100 items; line status skips committed lines on retry | [Inventory HLD §5](features/inventory/hld.md#5-architecture), [sample S9](data/seed/inventory-sample.md) |
| UX-1 [Critical] Location only by map pin | Current location first, saved addresses, tap/keyboard pin, result in words (`storeName`, `distanceM`) | [UX design §3](ux-design.md#3-location-picker), Identity HLD + requirements, Store Network HLD |
| UX-2 [High] No accessibility target | WCAG 2.2 AA in requirements and platform rules; axe + manual pass | [requirements](requirements.md), [system HLD §3](system-hld.md#3-platform-defaults), [UX design §8](ux-design.md#8-accessibility-rules) |
| UX-3 [High] 409s don't say what changed | 409 bodies carry the details; copy deck | [Ordering HLD §7](features/ordering/hld.md#7-interfaces), [UX design §5-6](ux-design.md#6-copy-deck) |
| FE-1 [High] Nobody owns the cart across UIs | Ordering's cart module passed as `ctx.cart`; cap rule applied only there | [ADR-0015](adr/0015-micro-frontends-with-central-shell.md), ADR-0017, Ordering HLD |
| FE-2 [High] No failure isolation in the shell | Error boundaries, import timeout, `ctx.api` / `notify` / `setTitle`, manifest + hashed files | ADR-0015 |
| BE-1 [High] Admin routes planned without auth in dev | IAM auth until the staff pool exists; `dev` only; never unauthenticated | [Catalog HLD](features/catalog/hld.md#7-interfaces) + [LLD §7](features/catalog/lld.md#7-security), system HLD |
| BE-2 [High] Release job can free a confirmed order's stock | 15-min hold; the job asks Ordering (`/internal/orders/{id}/status`): no order → release, confirmed → commit, unavailable → wait; commit re-reserves a released reservation | [Inventory HLD §8.6](features/inventory/hld.md#8-key-flows), Ordering HLD, [sample S10](data/seed/inventory-sample.md) |
| BE-3 [High] No timeout budget | Platform rule; checkout budget (8 s deadline); BFF and Support budgets | system HLD, Ordering HLD §8.2, Identity HLD §5, Support HLD §5 |
| DB-2 [High] Expiry times have no time zone | UTC instants everywhere; store-local input converted once | system HLD (Time), [Inventory HLD §6](features/inventory/hld.md#6-data-model), [sample S11](data/seed/inventory-sample.md) |
| UX-4 [Medium] Fees only at checkout | Public `GET /fees`; fees shown in the cart | Ordering HLD, README, requirements |
| UX-5 [Medium] No notice of "no cancellation" or of adjusted orders | Text next to Place order; "Adjusted" label + one-time banner | Ordering requirements (ORD-07, ORD-10), UX design §5, §7 |
| UX-6 [Medium] Key screen states not designed | State matrix (out of stock greyed in place; closed store: browse yes, checkout no) | [UX design §4](ux-design.md#4-state-matrix) |
| UX-7 [Medium] No URL scheme | URLs and owners, deep links through the location step, "not available at your store" page | [UX design §2](ux-design.md#2-urls-and-owners) |
| FE-3 [Medium] No shared UI building blocks | `common/ui` package (tokens, primitives, messages) | ADR-0014, ADR-0015 |
| FE-4 [Medium] Bundle hosting open | D3 | ADR-0015, ADR-0018, system HLD |
| FE-5 [Medium] Stale data after a location change | Remount on change, data keyed by storeId, abort on unmount, re-check rules, tab sync, `addressId` cleared on sign-out | ADR-0015, Identity HLD §6 |
| FE-6 [Medium] AI answers rendered as HTML | Plain text with allow-listed formatting; same component in the agent console | Support HLD §5 |
| BE-4 [Medium] Idempotency-Key lifecycle undefined | New key per press; reused only for automatic retries; only 201 saved | Ordering HLD §7 |
| BE-5 [Medium] Order-write clash doesn't check whose order it is | Compare `userId` + `idempotencyKey`; otherwise alarm | Ordering HLD §8.2 |
| BE-6 [Medium] BFF proxy rules unspecified | Allow-list, path normalising, header list, 64 KB body, timeouts, `UPSTREAM_UNAVAILABLE` | [Identity HLD §5](features/identity/hld.md#5-architecture) |
| DB-3 [Medium] Raw session IDs and tokens in the session table | Key = SHA-256 of the session ID; ID token not stored; `expiresAt` checked in code; KMS field encryption parked | Identity HLD §6, parking lot |
| DB-4 [Medium] Backups and delete protection inconsistent | PITR + deletion protection + `RETAIN` on every prod table; restore drill | system HLD (Data protection), requirements, [operational readiness](operational-readiness.md) |
| DB-5 [Medium] No retention policy for personal data | Personal data table with retention; deletion runbook | [system HLD §3.1](system-hld.md#31-personal-data-and-retention) |

**Also added while fixing** (not review findings)
| Change | Why | Where |
|---|---|---|
| Category rules: one home subcategory per product; default `<category>-all` subcategory; "Other" category; `CATEGORY_IN_USE` | Your question about products and categories | [Catalog LLD §2.4](features/catalog/lld.md#24-category-rules), Catalog HLD §6 |
| Inventory calls a status-only endpoint `GET /internal/orders/{id}/status` | Least privilege: Inventory never sees addresses | Ordering HLD §7, Inventory HLD §7 |
| Support chat gets a 20 s BFF budget (Lambda 18 s, deadline 15 s) | The general 5 s BFF timeout would cut off chat answers | Identity HLD §5, Support HLD §5 |
| Platform rules for event consumers and IDs under SnapStart | Consistent DLQ/retry settings; unique IDs after snapshot restore | system HLD §3, ADR-0016 |
| Thumbnail worker deletes replaced images (newest ULID wins) | No orphaned images in the bucket | Catalog LLD §5.4 |
| Verified in AWS docs: TTL deletes "within a few days"; SnapStart uniqueness; managed login needs Essentials or Plus | Replaces three *verify* notes | system HLD §9, Identity HLD |

## 13. Design review fixes (round 2)
Second combined UI/UX, front-end, back-end and database review of the R1 docs (2026-11-21), run after
the §12 fixes: **23 findings** (1 critical, 5 high, 12 medium, 5 low), all fixed in the docs on
2026-11-21. Three were bugs in the §12 fixes themselves (DB-6, BE-9, BE-12). Each changed document
has a change-log row pointing here.

**Decisions** (recommendations applied while you asked for the fixes; each can still be changed)
| # | Question | Decision | Why | Approved |
|---|---|---|---|---|
| D6 | How the BFF is protected from floods and runaway cost | Keep the **Lambda function URL behind CloudFront + OAC** and cap it with **reserved concurrency (about 20)**. If this account's Lambda concurrency limit is 100 or lower (Lambda keeps 100 unreserved), put an **API Gateway HTTP API** with stage throttling in front instead | No extra hop or cost if the quota allows; API Gateway is the fallback | Recommendation applied 2026-11-21; **final after the quota check** (read-only `GetAccountSettings`, needs your OK) |
| D7 | Shared React through an import map, or React in each team bundle | **Each team bundles its own React in R1** | An import map must be inline (strict CSP needs a hash per change) and React has no official ES-module build | Recommendation applied 2026-11-21 |
| D8 | Help for customers in R1 (Support starts in R2) | **Static help page** (FAQ + contact email), "Need help?" on order pages | Orders can't be cancelled, so customers need a way to reach us from day one | Recommendation applied 2026-11-21 |
| D9 | `common` as one stack, or split | **Two stacks:** `foundation` (bus, budget, topics) first, `edge` (web distribution) after the teams | One stack needed team origins before teams could deploy, and teams need the bus first | Recommendation applied 2026-11-21 |

**Findings → fixes**
| Finding | Fix | Where |
|---|---|---|
| DB-6 [Critical] Cancelling an order whose commit took nothing "returned" stock that never left the shelf (phantom stock, then oversell). It is R1's only cancel path | Cancel works per line and returns only committed lines; a commit that took nothing ends `CLOSED` (final); status table; commit records the batches it used | [Inventory HLD §5, §6, 8.5](features/inventory/hld.md#8-key-flows), [sample S12](data/seed/inventory-sample.md) |
| BE-7 [High] Outbox could lose events (1 h max record age; the on-failure destination gets metadata only); no way to repair a wrong badge | Publishers retry until success with no max record age (records kept 24 h); bad records parked whole by the handler; replay runbook; nightly badge reconciliation + `BadgeCorrected` alarm | [system HLD §3](system-hld.md#3-platform-defaults), [Inventory HLD 8.8, §9](features/inventory/hld.md#8-key-flows), [Catalog LLD](features/catalog/lld.md) |
| BE-8 [High] OAC on the BFF's function URL needs `x-amz-content-sha256` on POST/PUT; nothing sent it | `ctx.api` adds the body hash on every POST/PUT | [ADR-0018](adr/0018-customer-sign-in-with-managed-login-and-bff.md), [ADR-0015](adr/0015-micro-frontends-with-central-shell.md), [Identity HLD §5](features/identity/hld.md#5-architecture) |
| FE-7 [High] The shell contract had no navigation: team UIs would each run a router and fight over history | `ctx.route`, `onRouteChange`, `navigate`; `Link` in `common/ui`; only the shell owns history | ADR-0015 |
| FE-8 [High] No deep-link fallback; distribution-wide custom error responses would turn API 404s into the shell | CloudFront Function rewrites app routes to `/index.html`; API and bundle paths never rewritten; fallback: hash routing | ADR-0015, ADR-0014, system HLD, [UX design §2](ux-design.md#2-urls-and-owners) |
| FE-9 [High] An import map from runtime `config.json` conflicts with the strict CSP, and React has no ES-module build | D7: each team bundles React; `ctx` holds plain objects only | ADR-0015, system HLD, ADR-0014 |
| BE-9 [Medium] A checkout that failed after reserving left a 15-min hold, and the doc said "nothing written" | Best-effort release before answering (not on the orderId-collision path); text corrected | [Ordering HLD 8.2, §9](features/ordering/hld.md#8-key-flows), Inventory HLD §7 |
| BE-10 [Medium] The BFF is not behind API Gateway, so "API Gateway throttling" did not protect it | D6; public login rows noted, cookie option for the LLD | ADR-0018, Identity HLD §5 |
| BE-11 [Medium] Deploy-order loop between `common` and the teams | D9: foundation → teams (SSM outputs) → edge | ADR-0014, system HLD §6, Catalog LLD §11-12 |
| BE-12 [Medium] `STORE_UNAVAILABLE` mixed "closed now" with "closed for good" | Reasons `OUTSIDE_HOURS` / `PAUSED` / `CLOSED`; `opensAt` only with `OUTSIDE_HOURS`; copy per reason | Ordering HLD §7, [Store Network HLD §7](features/store-network/hld.md#7-interfaces), UX design §4, §6 |
| DB-7 [Medium] Restore steps incomplete: a restored table has no Streams, TTL or auto scaling | Restore runbook: Streams + new event source mapping, TTL, PITR, deletion protection, tags, alarms, IAM by ARN, then reconciliation | system HLD §3, [operational readiness](operational-readiness.md) |
| DB-8 [Medium] The abandoned-reservation job could miss holds in older UTC-date partitions | Queries the last 7 UTC dates every run; alarm on any reservation `HELD` > 1 h | Inventory HLD §6, 8.6, §10 |
| FE-10 [Medium] Cart module was a single point of failure with no versioning | Own manifest, semver, stand-in when it fails ("Cart unavailable", Add disabled, cart kept), consumer contract test, `clear()` | ADR-0015, UX design §4 |
| FE-11 [Medium] No CSS isolation rules between team bundles | CSS Modules, no global selectors, shell owns reset/tokens/top layers, CSS as `<link>` files, stylelint | ADR-0015 |
| FE-12 [Medium] Admin screens shipped inside the customer bundle | Separate customer and staff bundles; scripts until the staff pool exists | [Catalog LLD §1](features/catalog/lld.md#1-code-and-repository-structure) |
| FE-13 [Medium] Browser errors reported nowhere | Shell posts errors to `POST /api/telemetry/errors` (BFF → logs → alarm); no personal data; RUM parked | ADR-0015, Identity HLD §5 |
| UX-8 [Medium] No way to get help in R1 | D8: static help page, "Need help?", "What happens next" on the order page | [UX design §7, §11](ux-design.md#11-help-and-support-chat) |
| UX-9 [Medium] Checkout address step undefined | Fields, order, autocomplete, validation, error summary, saved-address choice, someone else, limit | [UX design §5.1](ux-design.md#51-delivery-address-step) |
| UX-10 [Low] PRD-05 said "not their current location", contradicting the location picker | Reworded: current location is one way to choose; the store never changes silently with GPS | [requirements](requirements.md) |
| UX-11 [Low] On a shared device the next person saw the previous person's cart | Sign-out clears the device cart, confirmed in a dialog when it has items | Identity HLD 8.4, UX design §6, §10, ADR-0015 |
| DB-9 [Low] "PITR on every prod table" contradicted the session table; §3.1 missed name/email in sessions | Named exemptions (`identity-bff-sessions`, `ordering-idempotency`, deletion protection kept); §3.1 rows updated | system HLD §3, §3.1 |
| BE-13 [Low] Support diagram showed `POST /api/support/messages` | Corrected to `POST /api/support/conversations/{id}/messages` | [Support HLD §3](features/support/hld.md#3-context) |
| FE-14 [Low] No client-side timeouts, so the browser could give up before the BFF answered | `ctx.api`: 8 s default, 15 s checkout, 22 s chat (just above the BFF's 5 / 12 / 20 s) | ADR-0015, UX design §5, §11 |

**Changed from the review's own recommendation while fixing**
| Change | Why |
|---|---|
| DB-6: a commit that took nothing ends **`CLOSED`** (new, final status), not `RELEASED` as the review suggested | `RELEASED` means "can be reserved again", so a duplicate `OrderConfirmed` after the cancel would have reserved and committed stock for a cancelled order |
| BE-7: publishers **retry until success** instead of a retry cap | With a cap, an EventBridge outage sends every batch to the on-failure queue within seconds (sequence numbers only); without one the shard pauses and resumes in order |

**Also fixed while editing** (not review findings): PRD-06/PRD-07 order in requirements; system HLD
change-log rows put in date order.

**Verified in AWS docs (2026-11-21):** a function URL behind OAC needs `x-amz-content-sha256` on
POST/PUT; a Streams on-failure destination gets metadata only (records re-readable within the 24 h
retention); a PITR restore does not bring back Streams, TTL or auto scaling; CloudFront custom error
responses apply to the whole distribution. **Still to verify:** CloudFront Functions in the new AWS
experience; this account's Lambda concurrency limit (D6).

## 14. Design review fixes (round 3)
Third strict review of the whole architecture folder (2026-11-22; `platform/` excluded) through API,
back-end, database, UI/UX and front-end lenses: **61 findings** (4 high, 26 medium, 31 low), all
fixed in the docs on 2026-11-22, with decisions D10-D13 below. Each changed document has a
change-log row or revision line pointing here. The two items left open then are settled: the Jira
site name stays as it is for now (your decision 2026-11-22), and the D6 concurrency check ran the
same day ([§15](#15-aws-checks)).

**Decisions**
| # | Question | Decision | Why | Approved |
|---|---|---|---|---|
| D10 | How does R1 data get in without a staff side? (H-1) | **No staff side in R1.** Tables first; an operator loads stores, products, prices, listings and stock with scripts that send IAM-signed requests to the admin APIs, in every stage (low throttling, no admin UIs), using their own `aws login` credentials (human access is managed by AWS in this project, so no new IAM role). Records that need a person get the default actor `system-operator` (Store Network `statusChangedBy`, Inventory movement `actor`, Ordering fee `changedBy`); the staff side replaces this after R1 | Every admin route was dev-only or waiting for the staff pool, so R1 could not be set up in prod | Your decision 2026-11-22 |
| D11 | Which store serves an order when stores keep different hours? (M-19, and your question about using every store within 5 km) | **One store per order, with backups.** Serviceability returns every store in range (nearest first, max 10, each with status, open now, opening time, distance and city) and the serving store from one choice rule used by the app and by checkout: the nearest store open now; the cart's store (`keepStoreId`) is kept while it is open now; when it stops serving, the nearest other store open now takes over and the cart moves with a message; never back to a nearer store while the cart has items. No store open now → "Opens at …" (`OPEN`), "temporarily unavailable" (only `PAUSED`), else "not served". One order from several stores is parked | Customers near a closed store can still order from another store in range; nobody bounces between stores at opening time; one rider and one reservation per order keep R1 simple | Your decision 2026-11-22 (one store + backup list) |
| D12 | Checkout latency target with cold starts (M-14) | **p99 < 1 s for warm requests; p99 < 3 s including cold starts**, measured separately. No provisioned concurrency in R1; SnapStart priming in the LLD; provisioned concurrency parked | At R1 traffic most calls along the 4-5 function chain can be SnapStart restores; provisioned concurrency is billed every hour | You agreed 2026-11-22 |
| D13 | Delivery radius vs the geohash search (M-18) | **Radius cap = 95% of a geohash5 cell's smaller side at the store: 4,500 m in Bengaluru** (cell ≈ 4.77 × 4.86 km; ≈ 4,100 m in Delhi), computed when a store is saved; larger values are rejected. "Within 5 km" becomes "within 4.5 km" in Bengaluru | The cell + 8 neighbours only guarantee one cell side around a pin near an edge, so 5 km could miss customers 4.77-5 km away. Exactly 5 km would need a precision-4 shortlist (more candidate stores per lookup) | You agreed 2026-11-22 |

**Findings → fixes**
| Finding | Fix | Where |
|---|---|---|
| H-1 [High] R1 could not be set up or opened in prod: every admin route was dev-only or waiting for the staff pool | D10: IAM admin routes in every stage, operator scripts, `system-operator` actor; staff side after R1 | [system HLD §3](system-hld.md#3-platform-defaults), [requirements](requirements.md) PRD-01, [README](README.md) releases, Catalog HLD and LLD, Inventory, Store Network and Identity HLDs, Ordering HLD §12, [operational readiness](operational-readiness.md) |
| H-2 [High] Public browse could use up the credit in about a day (300 req/s in prod, cache-busting `cursor`/`limit`/`ids`, no WAF) | 20 req/s (burst 40) per public route in prod, 300 only for a dev load test; `limit` 20 or 50 only; HMAC-signed cursors; sorted, de-duplicated `ids`; all checked before any read; hourly read-units alarm; serviceability throttled too | [Catalog LLD §0, §3, §7-§9](features/catalog/lld.md#0-conventions), [Catalog HLD §5](features/catalog/hld.md#5-architecture), system HLD §3, [Store Network HLD §7](features/store-network/hld.md#7-interfaces) |
| H-3 [High] Expired goods could stay on sale (short-dated receipts, shelf-life changes, a "since last run" job window) | A receipt line within 1 h of its stop-selling time → 422 `EXPIRES_TOO_SOON`; a raised minimum shelf life writes off affected batches in the same transaction; the job queries the last 7 UTC dates up to the date of now + 1 h, with a heartbeat alarm; commit skips batches past `sellUntil`; samples S13, S14 | [Inventory HLD §6-§9](features/inventory/hld.md#6-data-model), [Inventory ADR-0001](features/inventory/adr/0001-batches-expiry-fefo.md), [sample data](data/seed/inventory-sample.md) |
| H-4 [High] Parallel token refreshes signed customers out | Single-flight refresh (claim on `refreshVersion`); the others use the valid or new token; a session is deleted only if it still holds the refresh token that failed; rotation grace period 10 s (checked 2026-11-22: up to 60 s allowed) | [Identity HLD §5, §9](features/identity/hld.md#5-architecture), [ADR-0018](adr/0018-customer-sign-in-with-managed-login-and-bff.md), operational readiness |
| M-1 [Medium] `ctx.city` had no source | Serviceability returns `city` and `cityName`; the active location stores them; `ctx.cityName` added | Store Network HLD §7, Identity HLD §5, [ADR-0015](adr/0015-micro-frontends-with-central-shell.md), system HLD §5.1 |
| M-2 [Medium] UX and Identity disagreed on address fields | One model: `line1`, `line2` (optional), `area` (required), landmark, pincode, city code from the store; phone stored as 10 digits | [UX design §5.1](ux-design.md#51-delivery-address-step), Identity HLD §6 |
| M-3 [Medium] Catalog create was not safe under concurrent retries | `Put IDEMP#k` with `attribute_not_exists` inside the transaction; on that failure, the stored response (same hash) or 422 | [Catalog LLD §5](features/catalog/lld.md#5-detailed-flows) |
| M-4 [Medium] Inventory idempotency did not compare the request | `requestHash` on reservations, receipts and adjustments (new `inventory-idempotency` table); same key with a different body → 422 `IDEMPOTENCY_KEY_REUSED`, as in Ordering | Inventory HLD §5-§6, [Inventory requirements](features/inventory/requirements.md) |
| M-5 [Medium] `PRODUCT_NOT_FOUND` gave the UI nothing to recover with | 404 `details {reason, categoryId, subcategoryId}` when the product exists in the master | Catalog LLD §3, Catalog README |
| M-6 [Medium] `ListingUpdated` could apply out of order | `listingVersion` in `ListingUpdated` and `AssortmentChanged`; Inventory keeps only a newer value | Catalog LLD §4, Catalog HLD §7, Inventory HLD §6-§7 |
| M-7 [Medium] The listing transaction did not guard the subcategory, and counts were never rebuilt | ConditionCheck on `META` (version, `ACTIVE`); the move handler is conditioned on the old subcategory; nightly count rebuild with a `CountCorrected` alarm | Catalog LLD §1, §2.2, §5 |
| M-8 [Medium] Catalog's store copy had no repair path | Store Network re-sends every store nightly (`StoreUpdated`, `reason: RECONCILE`) | Store Network HLD §5, §7, Catalog LLD §4, Catalog HLD §9 |
| M-9 [Medium] Scheduled jobs had no stored state or heartbeat | Fixed windows (no job state); alarms when a job has no successful run (expiry 2 h, abandoned reservations 15 min, reconciliation 26 h) | Inventory HLD §6, §10, operational readiness |
| M-10 [Medium] Adding event fields would break strict readers | Requests strict; events and responses tolerant (shared Jackson config, contract tests) | [system HLD §4](system-hld.md#4-event-conventions), [scope control](scope-control.md), Catalog LLD §0 |
| M-11 [Medium] An archive replay re-triggered every consumer | Replays name their target rules (`FilterArns`, checked 2026-11-22); message and money consumers skip replayed events; Analytics' backfill targets only its own rule | system HLD §3-§4, [Analytics HLD](features/analytics/hld.md) |
| M-12 [Medium] The BFF cap of about 20 was not sized, and 429 had no UI | Reserved concurrency 40, sized as rate × time per call; `ctx.api` shows "Busy right now" and retries a GET once | Identity HLD §5, ADR-0018, ADR-0015, UX design §6 |
| M-13 [Medium] Two load targets (500 vs 50 concurrent) | One target: 50 concurrent checkouts for the last 30 units (30 confirmed, 20 refused, `BUSY` < 10%) | Inventory README and requirements |
| M-14 [Medium] Checkout p99 < 1 s ignored cold starts | D12 | [Ordering HLD §10](features/ordering/hld.md#10-non-functional-design), Ordering requirements and README, [requirements](requirements.md), [parking lot](parking-lot.md) |
| M-15 [Medium] The BFF p99 alarm included upstream time | Alarm on BFF overhead p99 > 100 ms, plus any 429 and refresh failures > 5% | Identity HLD §10 |
| M-16 [Medium] Custom metrics, logs and traces were not in the budget | Metrics rule (alarmed or dashboarded signals only, prod only, no high-cardinality dimensions; ~30 in total) and cost lines; R1 estimate now ~$10-18 a month | [system HLD §3, §7](system-hld.md#7-cost-budget), Catalog LLD §8, operational readiness |
| M-17 [Medium] Gradual deployment could not catch anything at R1 traffic | CodeDeploy pre-traffic hook runs the smoke test on the new version, then all traffic shifts; rollback on hook failure or alarm | [system HLD §6](system-hld.md#6-environments-and-delivery), Catalog LLD §11, operational readiness |
| M-18 [Medium] The 5 km radius was not covered by the geohash search | D13 | Store Network HLD §5, §6, §9, [ADR-0009](adr/0009-delivery-zones-as-polygons.md), Store Network README and requirements |
| M-19 [Medium] "Prefer open now" bounced customers between stores | D11; flow 8.4 "Closing time with a cart" | Store Network HLD §5, §7, §8, Ordering HLD §7, UX design §3, §4, §6, ADR-0009, requirements PRD-05 |
| M-20 [Medium] Chat cost was an alarm, not a cap | A global daily cap (starts at 100 messages, SSM value) and the per-user hourly counter, one conditional transaction before each model call (`support-limits`) | [Support HLD §5-§7](features/support/hld.md#5-architecture), Support README |
| M-21 [Medium] Greyed out-of-stock text would fail contrast (WCAG 1.4.3) | Only the image is dimmed; text keeps ≥ 4.5:1 | [UX design §4](ux-design.md#4-state-matrix), Catalog requirements and HLD |
| M-22 [Medium] The cart module loaded before any team UI | Loaded in parallel with the team bundle | ADR-0015 |
| M-23 [Medium] ADRs were stale or had the wrong status | ADR-0003 (no Platform library; Support's AI in Java), ADR-0011 (Proposed; hosted by Procurement), ADR-0012 (Accepted), ADR-0009 (R1 rules; file name kept so links stay valid) | [ADR-0003](adr/0003-typescript-cdk-polyglot-services.md), [ADR-0011](adr/0011-shared-aurora-data-api.md), [ADR-0012](adr/0012-iam-service-to-service-auth.md), ADR-0009 |
| M-24 [Medium] The Notifications sender would fail DMARC | Project domain with Easy DKIM, SPF and DMARC, stated in the R3 outcome; SES checked on the Free plan 2026-11-22 (sandbox), domain from another registrar ([§15](#15-aws-checks)) | [Notifications HLD](features/notifications/hld.md), README releases |
| M-25 [Medium] The Claude workflows used moving tags and had no limits | Actions pinned to commit SHAs; review workflow: one run per PR (`cancel-in-progress`), drafts skipped; 15-minute timeouts | *(root)* `.github/workflows/`, [ADR-0013](adr/0013-github-organisation-and-repo-conventions.md) |
| M-26 [Medium] Secret scanning and the Jira-key check were not enforced | New `Docs checks` workflow as a required check: Jira key in the PR title, gitleaks 8.30.1 pinned by checksum, link check (`scripts/check-links.py`); PR template | *(root)* `.github/workflows/docs-checks.yml`, `scripts/check-links.py`, [ADR-0005](adr/0005-jira-tracking-conventions.md), ADR-0013 |
| L-1 [Low] Counts included inactive products | Counts = listed and active products; status changes adjust them; nightly rebuild | Catalog LLD §2.2, Catalog HLD §6 |
| L-2 [Low] `AssortmentChanged` could list a product as both added and removed | Final state per product in each batch | Catalog LLD §4 |
| L-3 [Low] The ETag's meaning was unclear (two versions) | Product ETag = `META` version; a `DETAIL` change bumps it | Catalog LLD §0 |
| L-4 [Low] A replaced image was deleted while still cached | Tagged `replaced=true`, deleted by a lifecycle rule after 1 day | Catalog LLD §5, §7 |
| L-5 [Low] Images were decoded before their size was checked | Width and height read from the header first (≤ 4000 px a side, ≤ 40 MP) | Catalog LLD §5 |
| L-6 [Low] The store ID pattern allowed only 99 stores per zone | `\d{2,3}` | Catalog LLD §7 |
| L-7 [Low] In-page filtering gave wrong results across pages; `storeStatus` in internal prices | No filtering in R1 (it comes with search); `storeStatus` removed | Catalog HLD §5, Catalog LLD §3 |
| L-8 [Low] Catalog docs out of order or stale | Change log in date order; CAT-10 before CAT-11; stale open questions closed; seven functions | Catalog HLD, [Catalog requirements](features/catalog/requirements.md) |
| L-9 [Low] Pack size was stored twice | `netQty` + `netUnit` on `META`; the display `unit` is derived; attributes keep type-specific extras only | Catalog LLD §2-§3, Catalog HLD §6, Catalog README, UX design §9 |
| L-10 [Low] The commit race was read as a batch conflict | A reservation-condition failure re-reads the reservation and skips committed lines | Inventory HLD §5 |
| L-11 [Low] Alarms were looser than the SLOs | Reservation p99 > 200 ms; iterator age > 10 s | Inventory HLD §10 |
| L-12 [Low] Inventory doc gaps | INV-02 asks Ordering first; interim admin auth (D10); reservations kept 90 days after they end, movements kept as the audit log; `9999-12-31` documented | Inventory requirements, HLD §6, sample data |
| L-13 [Low] The `returnTo` rule was not exact | One leading `/` (not `//` or `/\`), no scheme or control characters, ≤ 512 characters, not under `/api/`; checked at login and at callback | Identity HLD §5 |
| L-14 [Low] The session name stayed stale for 30 days | `PATCH /me` updates Cognito; sessions copy the name at every refresh | Identity HLD §6 |
| L-15 [Low] Lines left stale by round 2 | Identity risk 3 updated; `clear` in Ordering's cart-module list; STN-01 matches PRD-05 | Identity HLD §12, Ordering HLD §5, [Store Network requirements](features/store-network/requirements.md) |
| L-16 [Low] No path or audit for fee changes | An operator script writes `FEES#<city>` (`version + 1`, `changedBy`, `reason`) and keeps history items | Ordering HLD §6, §12 |
| L-17 [Low] Store Network listed consumers that don't consume its events | Consumers: Catalog, later Fulfillment | Store Network HLD §3, README |
| L-18 [Low] Chat text copied into a ticket: 30 days or 12 months? | It follows ticket retention (12 months) | [system HLD §3.1](system-hld.md#31-personal-data-and-retention), Support HLD §6, §10 |
| L-19 [Low] Durability, availability and roles disagreed | Durability names the exemptions; 99.5% end to end vs 99.9% per service explained; PRD-02 roles match ADR-0019 | requirements, README |
| L-20 [Low] "Four hard things" listed five; the review-fixes link pointed only to §12 | "Five"; links to §12, §13 and §14 | README |
| L-21 [Low] The CSP directives were not written down | Full policy in ADR-0015; ADR-0014 points to it | ADR-0015, [ADR-0014](adr/0014-common-repo-for-shared-infrastructure.md) |
| L-22 [Low] The cart did not sync across tabs | `subscribe` also fires on `storage` events | ADR-0015 |
| L-23 [Low] "Still loading…" fired together with the 10 s timeout | "Still loading…" at 5 s, failure at 10 s | UX design §4 |
| L-24 [Low] Phone normalisation and toast timing | Spaces, dashes and a leading `+91`, `91` or `0` removed before checking; info toasts 6 s, error toasts never disappear on their own | UX design §5.1, §8 |
| L-25 [Low] Arrow-key map panning clashed with screen-reader browse keys | The map is one focusable `role="application"` element with instructions; the other options need no map | [UX design §3](ux-design.md#3-location-picker) |
| L-26 [Low] `/help` owner, `web-shell/help/`, placeholder mailbox | The shell owns `/help` in R1; `help/` in ADR-0014's tree; `help@shoplite.example` marked as a placeholder | ADR-0015, ADR-0014, [UX design §11](ux-design.md#11-help-and-support-chat) |
| L-27 [Low] `GoodsReceived` had no per-line expiry | `productId`, `qty` and `expiry` per line | [Procurement HLD](features/procurement/hld.md) |
| L-28 [Low] Stale release labels and the "Commerce" team name | Labels match the release plan (Later; phases A and B for Fulfillment; order emails in R3, payment emails with Payments); Commerce → Ordering | Payments, Notifications, Procurement, Analytics and Fulfillment HLDs and READMEs |
| L-29 [Low] Analytics said "hash userId"; `ServiceabilityMiss` was undefined | HMAC everywhere; `ServiceabilityMiss {geohash5}` (a rough area only), added by Store Network when Analytics is built | Analytics HLD, [Analytics requirements](features/analytics/requirements.md) |
| L-30 [Low] Templates had drifted from the docs actually written | HLD (12 sections), LLD (Catalog's structure), feature README (the real sections), ADR (revision line), PR checklist (all documents) | *(root)* `templates/`, `.github/pull_request_template.md` |
| L-31 [Low] The root README was stale | Project status, LLD rule and document statuses updated; Docs checks mentioned | *(root)* `README.md` |

**Changed from the review's own recommendation while fixing**
| Change | Why |
|---|---|
| H-1: **no `operator-<stage>` IAM role**; the operator signs with their own `aws login` credentials | Human access is managed by AWS in this project, and roles are not assigned to people unless absolutely necessary |
| H-1: the audit trail is the `actor` field on every write plus API access logs, **not CloudTrail** | CloudTrail records API Gateway management calls, not invocations of a deployed API (checked 2026-11-22: API Gateway is not a CloudTrail data-event source) |
| D11/M-19: **`NOT_SERVED` replaces `CLOSED`** as a `STORE_UNAVAILABLE` reason | A shut store is never in the serviceability answer, so `CLOSED` could never be returned |
| H-3: the expiry window ends at the **date of now + 1 h**, not today | Just before midnight UTC the job writes off batches due after midnight, which sit in the next date's partition |
| D13/M-18: the cap **depends on latitude** (95% of the cell's smaller side at the store), not a flat 4.5 km | Cells get narrower further north (≈ 4,100 m in Delhi) |
| H-2: **no separate throttle for `?ids=`**; the products route stays at 20/40 and the hourly read-units alarm covers the cost | HTTP API routes don't include query strings |
| M-13: the load target is **50 concurrent checkouts** now, not after the D6 check | 500 concurrent would need about 1,500 Lambda concurrency (three functions per checkout), above the AWS default of 1,000; 50 matches the existing scenario. The D6 check then found a limit of 10, so the test waits for the requested increase ([§15](#15-aws-checks)) |
| M-25: `claude.yml` got pins and a timeout but **no concurrency group** | Comment-triggered runs on one PR would share a group, and GitHub keeps only one pending run per group, so a later comment could cancel a waiting `@claude` run |

**Also fixed while editing** (not review findings): release labels in the later features' READMEs
(payment and refund emails wait for Payments; `TicketUpdated` "R4" → Later); the
`inventory-idempotency` table counted in the system HLD and READMEs (five Inventory tables); Store
Network flow 8.4 "Closing time with a cart"; Inventory ADR-0001 revised; the system HLD §8 list of
revised ADRs; the link checker used for these reviews is now `scripts/check-links.py` in the repo.

**Verified 2026-11-22:** the action commit SHAs (`actions/checkout` v4.4.0, `claude-code-action`
v1.0.286) and the gitleaks 8.30.1 Linux checksum, read from GitHub. The AWS items still open then
(refresh-token rotation, replay targets, CloudTrail, Sydney prices, Free plan allowances, SES, the D6
concurrency limit, pinning the plugin marketplace) were checked the same day: [§15](#15-aws-checks).

## 15. AWS checks

Checked on 2026-11-22, after the round-3 fixes, with read-only AWS CLI calls in ap-southeast-2
(`vinayaka` profile), the AWS Price List API (served from us-east-1, which the project's SCP allows
for pricing) and the AWS documentation, read directly because the AWS docs server was still
disconnected. No resources were created. One request was sent to AWS: the Lambda quota increase
(D14).

**Decisions**
| # | Question | Decision | Why | Approved |
|---|---|---|---|---|
| D14 | This account's Lambda limit is 10 concurrent executions (the new-account default; the AWS default is 1,000). What now? | **Raise it to 1,000 now:** a Service Quotas request for `Concurrent executions` (`L-B99A9384`) in ap-southeast-2, sent 2026-11-22 (pending). The BFF cap (40) needs at least 140; the browse and checkout load tests need about 60 and 150. If AWS grants less than 140, the D6 fallback applies: an API Gateway HTTP API with stage throttling in front of the BFF | A limit of 10 allows no reserved concurrency at all and cannot run the load tests; the request is free and approval can take days | Your decision 2026-11-22 |
| D15 | Claude is not offered on-demand in Sydney, only through inference profiles. Which model does Support use? | **Claude through the Australia (`au.`) cross-Region inference profile:** requests run in Sydney or Melbourne, never outside Australia. Conversations, tickets, the Knowledge Base, its documents and embeddings stay in Sydney. A small, fast model (e.g. `au.anthropic.claude-haiku-5-5`) is chosen in the Support LLD; the fallback is an Amazon Nova model on-demand in Sydney through the same Converse API | The project's SCP exempts Bedrock inference from the Region limit, which is what lets geographic profiles work; the one-Region rule still holds for stored data | Your decision 2026-11-22 |

**Results**
| Item | Result | Effect on the design |
|---|---|---|
| Account plan | Free plan, active, $119.99 of the $120 credits left. It ends 2027-05-13 or when the credits run out, whichever comes first; the account then closes unless upgraded to the Paid plan within 90 days (content kept 90 days) | Budget note in [system HLD §7](system-hld.md#7-cost-budget) |
| Lambda concurrency (D6) | Limit **10** (unreserved 10), adjustable; AWS default 1,000. Reserved concurrency can use at most the unreserved amount minus 100. Throttled calls get 429 | D14; Identity HLD §5, ADR-0018, Catalog LLD capacity, Inventory requirements, operational readiness |
| Cognito refresh-token rotation | Grace period up to 60 s (10 s is valid). With rotation on, refreshes go through the token endpoint or `GetTokensFromRefreshToken`; `REFRESH_TOKEN_AUTH` is refused. Rotation does not extend the session past the refresh-token validity counted from sign-in | Identity HLD §5 refresh steps, ADR-0018 |
| Cognito email and price | Default email: 50 messages a day per account. Essentials: $0.015 per monthly active user in Sydney (the price list does not show whether a free tier applies) | Identity HLD; system HLD §7 |
| EventBridge replay | A replay's `FilterArns` lists the rules it delivers to; replayed events carry `replay-name` | M-11 design holds |
| CloudTrail | API Gateway API calls are logged as management events; API Gateway is not a CloudTrail data-event source, so calls to a deployed API are not recorded | H-1 audit design (actor field + access logs) holds |
| CloudFront Functions | Allowed: the project's SCP allows `cloudfront:*` in us-east-1, and only Lambda@Edge is excluded | ADR-0015 deep links need no fallback |
| CodePipeline V2 triggers | Push triggers filter on file paths (include and exclude globs) | ADR-0014 holds |
| DynamoDB, CloudFront caching | Transactions take up to 100 items and 4 MB; CloudFront honours `stale-while-revalidate` | Both hold |
| Sydney prices | Custom metric $0.30 a month (first 10,000), standard alarm $0.10 a month, log ingestion $0.67/GB, log storage $0.033/GB-month, DynamoDB on-demand $0.1425 per million read units and $0.71 per million write units (first 25 GB stored free), Route 53 hosted zone $0.50 a month | System HLD §7 holds; Catalog load test ≈ $0.11 (was $0.25); the prod worst case of $5-13 a day holds |
| Free plan allowances | The Free plan includes the Always-free offers; the Free Tier usage API lists none yet (no usage) | System HLD §7 |
| SES | On the Free plan (no deliverability dashboard). This account is in the sandbox: verified recipients only, 200 emails a day, 1 a second | Matches the Notifications design |
| Route 53 domains | Registration refused on the Free plan ("Free Tier accounts are not supported for this service") | Notifications: domain from another registrar (or after upgrading), DNS in a Route 53 hosted zone |
| Bedrock models | On the Free plan. In Sydney, Claude is offered only through inference profiles (`au.`: Sydney and Melbourne; `global.`: worldwide). On-demand in Sydney: Amazon Nova, Titan Text Embeddings V2, Cohere Embed and others. Claude Haiku 4.5 is authorized in this account; Bedrock creates the Marketplace subscription on the first call (the Free plan allows Marketplace for Bedrock) | D15; Support HLD |
| Knowledge Bases | The Knowledge Bases and S3 Vectors APIs answer in Sydney for this account; Managed Knowledge Bases list Sydney among their Regions (10 concurrent ingestion jobs there); Titan Text Embeddings V2 and Cohere Embed work with Knowledge Bases in Sydney | Support HLD: Managed Knowledge Base in Sydney holds |
| `claude-code-action` plugin marketplace | Cannot be pinned to a commit: the action accepts only URLs ending in `.git` and runs `claude plugin marketplace add`. Left unpinned (official Anthropic repository; the action itself is pinned); the alternative is to copy the plugin into this repo as a local marketplace | Comment in `claude-code-review.yml` |

**Not checked yet:** SnapStart with Spring Boot 3 priming and the BFF cold start (early in
development); the first Claude call and the Knowledge Base storage price (Support LLD); SES
production access on the Free plan (before R3); WAF pricing (when WAF is added).
