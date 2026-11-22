# Online Store (working name: ShopLite)

**Status:** Chosen project - **R1 design agreed** (plus Support); round-3 review fixes 2026-11-22 for review; Notifications to review; staff side after R1 · **Last updated:** 2026-11-22

## What is it?
A quick-commerce platform for a fictional startup that runs small neighbourhood warehouses
("dark stores") in one city and delivers groceries and daily essentials in about 30 minutes,
using its own riders.

It is built the way a real company would build it: several teams, each owning a feature end to
end (its own repos, pipeline, data, dashboards and on-call), talking to each other only through
APIs and events.

## Problem statement
Customers want everyday essentials quickly and reliably. A fast-delivery business can only
deliver on that promise if five hard things work together:

1. **Accurate stock.** If the app sells an item the dark store does not have, the order is
   cancelled after payment. Customers lose trust; the business pays for refunds.
2. **Safe checkout under load.** During peaks, many customers buy the same popular items at
   once. Orders must never be duplicated or lost, and payment must never be taken twice.
3. **Efficient delivery.** Riders often carry several orders. A poor route order means late
   deliveries and fewer orders per rider.
4. **Right store, right items.** Each order is served by exactly one dark store, chosen from the
   delivery address the customer picks and the stores' opening hours. Customers must only see what
   that store actually sells.
5. **Support at scale.** Most support contacts are "Where is my order?" and policy questions.
   Answering them by hand does not scale.

The business also needs to **restock on time** and **see what is happening**: what sold,
where, how much was bought versus sold, and how delivery is performing.

## Who uses it
| User | Needs |
|---|---|
| Customer | Browse, search, buy, track, get help |
| Store manager | Stock levels, low-stock alerts, receiving deliveries, sales reports |
| Buyer | Purchase orders, suppliers, approvals |
| Picker | Pick lists for confirmed orders |
| Rider | Assigned deliveries and an optimised route |
| Support agent | Tickets handed off by the AI assistant |
| Merchandiser / admin | Products, prices, roles |

## How we will measure success
Measured in simulation and load tests (there are no real customers):

| Goal | Target |
|---|---|
| Orders cancelled because of missing stock | < 1% |
| Duplicate orders or double charges | 0 |
| Checkout success rate (excluding simulated payment declines) | > 99% |
| Orders delivered within the promised time | > 95% |
| "Where is my order?" questions answered by the AI without a human | > 60% |
| Availability of customer-facing APIs (prod) | 99.5% end to end (each service 99.9%) |

## Features and owning teams
| Feature | Team | Stack | Release |
|---|---|---|---|
| [`common` repo](adr/0014-common-repo-for-shared-infrastructure.md) (shared) | Shared | TypeScript (CDK), React shell | R0 |
| [Catalog & Search](features/catalog/README.md) | Catalog | Java (Spring Boot on Lambda), DynamoDB ×2, S3 + CloudFront; OpenSearch later | R1 (search later) |
| [Store Network & Serviceability](features/store-network/README.md) | Logistics | Java (Spring Boot on Lambda), DynamoDB + geohash | R1 minimal (zones later) |
| [Inventory](features/inventory/README.md) | Inventory | Java (Spring Boot on Lambda), DynamoDB ×5 (transactions, Streams) | R1 |
| [Identity & Accounts](features/identity/README.md) | Identity | Cognito (customer + staff pools, managed login), TypeScript BFF, Java (Spring Boot on Lambda), DynamoDB | R1 (staff side later) |
| [Cart & Checkout](features/ordering/README.md) | Commerce | Java (Spring Boot on Lambda), DynamoDB; browser cart in R1 | R1 (cash on delivery) |
| [Customer Support & AI Assistant](features/support/README.md) | Customer Experience | Java (Spring Boot on Lambda), Bedrock (Converse, Knowledge Base, Guardrails) | R2 |
| [Notifications](features/notifications/README.md) | Engagement | Python (Lambda), SES, DynamoDB, S3 | R3 |
| [Payments](features/payments/README.md) | Payments | Java (Lambda), SQS + DLQ, DynamoDB | Later |
| [Supply & Procurement](features/procurement/README.md) | Supply | Java (Lambda), relational DB, Step Functions | Later |
| [Data & Analytics](features/analytics/README.md) | Data | Python (Lambda), S3, Glue, Athena | Later |
| [Fulfillment & Delivery](features/fulfillment/README.md) | Logistics | Java (Kafka Streams) on EKS, Kafka on EC2, Python optimiser | Later |
| [Platform](platform/README.md) | Platform | TypeScript (AWS CDK), CodePipeline | Not needed for now |

Why this split: each feature is a separate business capability with its own data and its own
reason to change (see [ADR-0002](adr/0002-polyrepo-and-team-ownership.md)). Money (Payments) is
separate from orders because its consistency and audit rules are stricter. Notifications is
separate so no team builds its own email sending. Procurement is separate from Inventory because
restocking is a slow, low-volume workflow while stock reservation is a fast, high-contention hot
path; Inventory stays the only writer of stock ([ADR-0008](adr/0008-procurement-split-inventory-single-writer.md)).
Store Network is separate because every other feature needs "which store serves this address"
([ADR-0009](adr/0009-delivery-zones-as-polygons.md)).

## Build order
Every feature is designed first; development starts once all designs are finalised
([design review log](design-review-log.md)). Then features are built in this order:

1. **Catalog**, with a minimal **Store Network** (stores, status, serviceability), full stack
2. **Inventory**
3. **Identity** (also decides auth for all features)
4. **Ordering** (cart + checkout; no payment step, orders confirmed as cash on delivery)
5. **Support**
6. **Notifications**

R1 runs with **one store** (`BLR-S-01`); the design is sized for ~3,000 stores. Deferred: Payments,
Procurement, Analytics, Fulfillment, Catalog search, delivery zones. Platform is not needed for
now; shared pieces live in the [`common` repo](adr/0014-common-repo-for-shared-infrastructure.md).

## Releases
| Release | Scope | Outcome |
|---|---|---|
| **R0 Foundations** | `common` repo: event buses, budget alert, alarm topics, web shell + hosting, event contracts | Teams can deploy to dev and prod |
| **R1 Core commerce** | Catalog (browse, city prices, MRP, listings), Store Network (minimal), Inventory (batches, reservations, badges), Identity (customer sign-in + BFF), Cart & Checkout (cash on delivery, fees). No staff screens: an operator loads stores, products, prices, listings and stock with IAM-signed scripts ([D10](design-review-log.md#14-design-review-fixes-round-3)) | A customer can browse their store, sign up and place an order. **Resume-ready.** |
| **R2 AI support** | Customer Support & AI Assistant | AI answers policy and order-status questions |
| **R3 Notifications** | Order emails, sent from a project domain with DKIM (a personal mailbox would fail DMARC and land in spam) | Customers are told about their orders |
| **Later** | Staff side (staff pool, roles, admin screens), Payments, Catalog search, Supply & Procurement, Data & Analytics, Fulfillment & Delivery, delivery zones | Staff work in the app, payment step, search, restocking, reports, live delivery |

## Design progress
High-level designs are reviewed one feature at a time, in build order. Decisions are recorded in
the [design review log](design-review-log.md); review fixes are in [§12](design-review-log.md#12-design-review-fixes) (2026-11-21), [§13](design-review-log.md#13-design-review-fixes-round-2) (round 2), [§14](design-review-log.md#14-design-review-fixes-round-3) (round 3, 2026-11-22) and [§15](design-review-log.md#15-aws-checks) (AWS checks, 2026-11-22).

| # | Feature | HLD status |
|---|---|---|
| 1 | Catalog & Search | **HLD v0.6 - agreed** (round-3 fixes for review) · LLD v0.4 for review |
| 1 | Store Network & Serviceability | **Draft v0.6 - agreed** (round-3 fixes for review: one store per order with backups, 4.5 km cap) |
| 2 | Inventory | **Draft v0.5 - agreed** (round-3 fixes for review) |
| 3 | Identity & Accounts | **Draft v0.5 - customer side agreed** (round-3 fixes for review); staff side after R1 |
| 4 | Cart & Checkout | **Draft v0.5 - agreed** (round-3 fixes for review) |
| 5 | Customer Support & AI Assistant | **Draft v0.4 - agreed** (round-3 fixes for review; Bedrock checked: Claude through the `au.` profile, D15) |
| 6 | Notifications | Draft v0.2 - in review (sender domain decided) |
| - | Customer UX rules (URLs, states, location picker, copy, accessibility) | [UX design](ux-design.md) v0.3 for review; wireframes still to do |
| - | Staff side (staff pool + roles, admin screens, agent console) | **After R1** ([D10](design-review-log.md#14-design-review-fixes-round-3)); R1 uses IAM-signed operator scripts and the `system-operator` actor |
| - | Payments, Procurement, Fulfillment, Analytics | Draft v0.2 - deferred (release labels updated) |
| - | Platform | Draft v0.1 - not needed for now (unchanged) |

## Documents
- [Requirements](requirements.md) - product-wide goals, rules and non-functional requirements
- [Design review log](design-review-log.md) - every design decision, with the reason
- [System HLD](system-hld.md) - how all features fit together (draft for review)
- [UX design](ux-design.md) - customer screen rules: URLs, states, location picker, error messages, accessibility
- [Decisions (ADRs)](adr/)
- [Scope control](scope-control.md) - the main goal, and how we change designs as we build
- [Parking lot](parking-lot.md) - good ideas deferred to later
- [Operational readiness checklist](operational-readiness.md)
- [Data sources](data/sources.md)
- [Glossary](glossary.md)

## Links
| What | Link |
|---|---|
| Jira board | [STORE Kanban board](https://bhatvinayaka312.atlassian.net/jira/software/projects/STORE/boards/2) (project key `STORE`, grouped by epic) |
| GitHub organisation | [bhatvinayaka-store](https://github.com/bhatvinayaka-store): one repo per feature part, named `<feature>-<part>` ([ADR-0013](adr/0013-github-organisation-and-repo-conventions.md)) |
| AWS project / Region | ap-southeast-2 (fixed by the AWS project) |
