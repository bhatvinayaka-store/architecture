# Parking Lot

Good ideas that are **not** needed for the current goal. Reviewed at release planning, or as soon as a parked idea becomes needed
(see [scope control](scope-control.md)). Add the date and where the idea came from.

| Idea | Feature | Came from | Earliest release | Notes |
|---|---|---|---|---|
| Delivery zone polygons (+ map editor) | Store Network | Design review 2026-11-15 | When stores overlap | R1 uses geohash + radius (ADR-0009) |
| Travel-time-based delivery zones | Store Network | Store Network requirements | Later | |
| Waitlist for unserved addresses + `ServiceabilityMiss` | Store Network | Design review 2026-11-15 | Later | |
| Extra store metadata (GST, FSSAI, manager, capacity) | Store Network | Design review 2026-11-15 | When a feature needs it | |
| Automated go-live checks for a new store | Store Network | Design review 2026-11-15 | Later | Manual checklist in R1 |
| Dynamic store pausing when no riders are free | Store Network | Store Network requirements | R3 | Needs Fulfillment |
| Per-store pricing | Catalog | Catalog requirements | Later | Prices are per **city** (decided 2026-11-15) |
| Catalog search (OpenSearch; managed stint or Oracle Always Free) | Catalog | Design review 2026-11-21 | After R1 | |
| Product variants on one card (`variantGroupId`) | Catalog | Design review 2026-11-15 | Later | |
| Generated catalog snapshot in S3 | Catalog | Design review 2026-11-15 | Later | Not a source of truth |
| Hosting Catalog on EC2 (learning exercise) | Catalog | Design review 2026-11-15 | Optional | Serverless chosen |
| Near-expiry discounts, best-before date on product page, waste reports | Inventory / Catalog | Design review 2026-11-21 | Later | |
| Sharded stock rows for extreme hot items | Inventory | Design review 2026-11-21 | If load tests need it | |
| Server cart (`ordering-carts`) with guest-cart merge | Cart & Checkout | Design review 2026-11-21 | After Identity | R1 cart is in the browser and sign-out clears it; a server cart brings it back after sign-in |
| Backend-for-frontend (BFF) | Web | Design review 2026-11-20 | **Adopted in R1** | Moved into R1 on 2026-11-21 ([ADR-0018](adr/0018-customer-sign-in-with-managed-login-and-bff.md)) |
| Redis GEO for rider locations | Fulfillment | Design review 2026-11-15 | With Fulfillment | |
| Org-wide Claude review workflow (reusable workflow) | Repos | Design review 2026-11-14 | When more repos exist | |
| Personalised recommendations, reviews and ratings | Catalog | Catalog requirements | Later | |
| Social login (Google) | Identity | Identity requirements | R2+ | |
| Phone / SMS OTP login, SMS and WhatsApp notifications | Identity, Notifications | Requirements | Later | Needs the paid AWS plan |
| Coupons and promotions | Cart & Checkout | Ordering requirements | Later | |
| Scheduled delivery slots | Cart & Checkout | Ordering requirements | R3+ | |
| Stock transfers between stores | Procurement | Procurement requirements | R2 (P2) | |
| Demand forecasting (ML) | Inventory / Procurement | Requirements | Later | |
| Real payment providers, wallets, EMI | Payments | Payments requirements | Never (learning project) | |
| Real-time analytics dashboards | Analytics | Analytics requirements | Later | |
| Multiple cities / Regions | All | Product requirements | Never (AWS project is one Region) | |
| Native mobile apps | All | Product requirements | Never | Web only |
| Open-source SQS <-> Kafka bridge | Platform | Planning discussion | After R3 | Resume extra, not core |
| Customer cancellation before dispatch | Cart & Checkout | Design review 2026-11-21 | With Fulfillment | Not allowed in R1 |
| Passkeys / email one-time codes | Identity | Design review 2026-11-21 | Later | R1: email + password |
| Custom login domain (`login.<shop>`) | Identity | Design review 2026-11-21 | Later | Needs a certificate; R1 uses the Cognito prefix domain |
| AWS WAF on CloudFront | Web / all | Design review 2026-11-21 | Later | Check CloudFront flat-rate plans; include rate-based rules for `/api/auth/*`, the BFF and the telemetry route (round 2) |
| "Buy again" / personalised content (through the BFF) | Catalog / Ordering | Design review 2026-11-21 | Later | |
| Streaming chat answers (WebSocket / response streaming) | Support | Design review 2026-11-21 | Later | R2: request/response |
| Support for guests (policy questions only) | Support | Design review 2026-11-21 | Later | R2: signed-in only |
| Delivery-status and payment tools for the assistant | Support | Design review 2026-11-21 | With Fulfillment / Payments | |
| Address search / geocoding (Amazon Location; check the Free plan) | Identity / web shell | Design review 2026-11-21 | Later | R1: current location, saved addresses or a pin |
| KMS field encryption for session tokens | Identity | Design review 2026-11-21 | Later | R1: hashed session key; table readable only by the BFF role |
| Job that anonymises order address copies after 12 months | Cart & Checkout | Design review 2026-11-21 | Before real users | Rule in [system HLD §3.1](system-hld.md#31-personal-data-and-retention) |
| Self-service account deletion | Identity | Design review 2026-11-21 | Later | Manual runbook in R1 |
| One product in several categories (cross-listing) | Catalog | Category question 2026-11-21 | With Catalog search | R1: one home subcategory per product ([Catalog LLD §2.4](features/catalog/lld.md#24-category-rules)) |
| "Notify me when back in stock" | Catalog / Notifications | Design review 2026-11-21 | Later | Out-of-stock items are shown in place with a dimmed image |
| Shared React runtime (import map with a CSP hash + a self-built ES-module React) | Web | Design review round 2, 2026-11-21 | When bundle size matters | R1: each team bundles its own React (decision D7) |
| CloudWatch RUM (browser errors, Web Vitals) | Web | Design review round 2, 2026-11-21 | Later | R1: the shell posts errors to the BFF telemetry route |
| Delivery time promise and order tracking on the order page | Cart & Checkout / Fulfillment | Design review round 2, 2026-11-21 | With Fulfillment | R1 promises no delivery time |
| One order from several stores (combined catalog of every open store in range, one rider per store) | Cart & Checkout / Store Network / Fulfillment | Your question 2026-11-22 | Later, if ever | R1: one store per order, with the other stores in range as backups (D11) |
| Provisioned concurrency or more priming for the checkout chain | Cart & Checkout | Round-3 review 2026-11-22 | If measured cold starts hurt | R1: p99 target for warm requests; cold starts measured separately |
