# Online Store (working name: ShopLite)

**Status:** Candidate (under evaluation) - requirements draft · **Last updated:** 2026-11-14

## What is it?
A quick-commerce platform for a fictional startup that runs small neighbourhood warehouses
("dark stores") in one city and delivers groceries and daily essentials in about 30 minutes,
using its own riders.

It is built the way a real company would build it: several teams, each owning a feature end to
end (its own repos, pipeline, data, dashboards and on-call), talking to each other only through
APIs and events.

## Problem statement
Customers want everyday essentials quickly and reliably. A fast-delivery business can only
deliver on that promise if four hard things work together:

1. **Accurate stock.** If the app sells an item the dark store does not have, the order is
   cancelled after payment. Customers lose trust; the business pays for refunds.
2. **Safe checkout under load.** During peaks, many customers buy the same popular items at
   once. Orders must never be duplicated or lost, and payment must never be taken twice.
3. **Efficient delivery.** Riders often carry several orders. A poor route order means late
   deliveries and fewer orders per rider.
4. **Right store, right items.** Each customer is served by exactly one dark store, decided by
   the delivery address they choose. They must only see what that store actually sells.
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
| Availability of customer-facing APIs (prod) | 99.5% |

## Features and owning teams
| Feature | Team | Stack | Release |
|---|---|---|---|
| [Store Network & Serviceability](features/store-network/README.md) | Logistics | Java (Lambda), DynamoDB, S3 (GeoJSON zones) | R1 (R3 auto-pause) |
| [Identity & Accounts](features/identity/README.md) | Identity | Cognito, Java (Lambda), DynamoDB | R1 |
| [Catalog & Search](features/catalog/README.md) | Catalog | Java (Lambda), Aurora PostgreSQL, S3; R2 OpenSearch + ElastiCache | R1 / R2 |
| [Inventory](features/inventory/README.md) | Inventory | Java (Lambda), DynamoDB transactions + Streams | R1 / R2 |
| [Cart & Checkout](features/ordering/README.md) | Commerce | Java (Lambda), DynamoDB, Step Functions | R1 |
| [Payments](features/payments/README.md) | Payments | Java (Lambda), SQS + DLQ, DynamoDB | R1 |
| [Notifications](features/notifications/README.md) | Engagement | Python (Lambda), SES, DynamoDB, S3 | R1 |
| [Supply & Procurement](features/procurement/README.md) | Supply | Java (Lambda), Aurora PostgreSQL, Step Functions | R2 |
| [Data & Analytics](features/analytics/README.md) | Data | Python (Lambda), S3, Glue, Athena | R2 |
| [Fulfillment & Delivery](features/fulfillment/README.md) | Logistics | Java (Kafka Streams) on EKS, Kafka on EC2, Python optimiser | R3 |
| [Customer Support & AI Assistant](features/support/README.md) | Customer Experience | Python (Lambda), Bedrock | R4 |
| [Platform](platform/README.md) | Platform | TypeScript (AWS CDK), CodePipeline | R0 + ongoing |

Why this split: each feature is a separate business capability with its own data and its own
reason to change (see [ADR-0002](adr/0002-polyrepo-and-team-ownership.md)). Money (Payments) is
separate from orders because its consistency and audit rules are stricter. Notifications is
separate so no team builds its own email sending. Procurement is separate from Inventory because
restocking is a slow, low-volume workflow while stock reservation is a fast, high-contention hot
path; Inventory stays the only writer of stock ([ADR-0008](adr/0008-procurement-split-inventory-single-writer.md)).
Store Network is separate because every other feature needs "which store serves this address"
([ADR-0009](adr/0009-delivery-zones-as-polygons.md)).

## Releases
| Release | Scope | Outcome |
|---|---|---|
| **R0 Foundations** | Platform: network, event bus, constructs, pipeline template, budget alarms | Teams can ship a "hello" service to dev and prod |
| **R1 Core commerce** | Store Network (stores + zones), Identity, Catalog (browse), Inventory (stock + reservations), Cart & Checkout, Payments, Notifications, web shell | A customer can sign up, buy, pay and get an email. **Resume-ready.** |
| **R2 Search, supply, insights** | Catalog search + cache, Supply & Procurement, Data & Analytics | Fast search, automatic restocking, sales reports |
| **R3 Delivery** | Fulfillment & Delivery | Live rider tracking, dispatch, route optimisation |
| **R4 AI support** | Customer Support & AI Assistant | AI answers policy and order-status questions |

## Design progress
High-level designs are written and reviewed one feature at a time, in this order. Platform comes
last because its design is driven by what the features need (it is still **built** first).

| # | Feature | HLD status |
|---|---|---|
| 1 | Store Network & Serviceability | Draft v0.2 - in review |
| 2 | Identity & Accounts | Draft v0.1 - in review |
| 3 | Catalog & Search | Draft v0.1 - in review |
| 4 | Inventory | Draft v0.1 - in review |
| 5 | Cart & Checkout | Draft v0.1 - in review |
| 6 | Payments | Draft v0.1 - in review |
| 7 | Notifications | Draft v0.1 - in review |
| 8 | Supply & Procurement | Draft v0.1 - in review |
| 9 | Fulfillment & Delivery | Draft v0.1 - in review |
| 10 | Customer Support & AI Assistant | Draft v0.1 - in review |
| 11 | Data & Analytics | Draft v0.1 - in review |
| 12 | Platform | Draft v0.1 - in review |

## Documents
- [Requirements](requirements.md) - product-wide goals, rules and non-functional requirements
- [System HLD](system-hld.md) - how all features fit together (draft for review)
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
