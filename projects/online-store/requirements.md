# Online Store - Product Requirements

**Status:** Draft v0.1 · **Last updated:** 2026-11-14

Feature-level user stories live in each feature's `requirements.md`. This file holds what applies
to the **whole product**.

## 1. Goals
1. Customers can buy essentials and receive them within the promised time.
2. Stock shown in the app matches reality; nothing is sold that does not exist.
3. Every order and payment is correct even under load and partial failures.
4. The business can see sales, stock and delivery performance.
5. Built and operated like a production system: pipelines, stages, monitoring, alarms, runbooks.

## 2. Product-wide functional requirements
| ID | Requirement |
|---|---|
| PRD-01 | All customer and staff actions require sign-in, except browsing the catalog |
| PRD-02 | Role-based access: customer, picker, rider, store manager, support agent, admin |
| PRD-03 | Every important state change is published as an event other teams can subscribe to |
| PRD-04 | Every customer-facing action that changes data is idempotent (safe to retry) |
| PRD-05 | Each customer is served by exactly one dark store, decided by the **delivery address they choose** (not their current location). They only see and can only buy what that store lists |
| PRD-07 | Customers can order for any served address, including someone else's (recipient name + phone) |
| PRD-06 | All monetary amounts are stored as integers in minor units with a currency code |

## 3. Non-functional requirements (initial targets, to be reviewed)
| Area | Target |
|---|---|
| Availability (prod, customer APIs) | 99.5% monthly |
| Latency | Browse p99 < 300 ms (cached); checkout p99 < 1 s |
| Load (test target) | 300 req/s browsing, 200 orders/min, 2,000 rider location updates/s |
| Correctness | 0 oversells, 0 duplicate orders, 0 double charges in load and chaos tests |
| Durability | Orders and payments: point-in-time recovery enabled; RPO 5 min, RTO 1 h |
| Security | Least-privilege IAM per service; encryption at rest and in transit; no secrets in code; PII never in logs |
| Observability | Every service: structured logs with correlation ID, golden-signal dashboard, standard alarms, traces across services |
| Delivery | Every repo deploys dev -> approval -> prod through a pipeline; automatic rollback on alarm |
| Cost | Stay within AWS Free plan credits; tear down expensive resources between work sessions |

## 4. Constraints
- **AWS Region:** ap-southeast-2 only (fixed by the AWS project). Customers in the story are in
  an Indian city, so real latency would be higher; acceptable for a learning project and noted
  as an ADR candidate.
- **AWS plan:** Free plan with limited credits. Amazon MSK, Kinesis and SMS are not available,
  so Kafka is self-managed (local / EC2 / Kubernetes). See ADR-0006.
- **One AWS account:** dev and prod are isolated by stack, naming and tags (ADR-0004).
- **Team size:** 1 engineer, possibly 3-4 friends; part-time (~8 h/week).
- **Data:** synthetic or openly licensed data only; no real personal data.

## 5. Out of scope (whole product)
Real payments, native mobile apps, multiple cities/regions, marketing campaigns, seller marketplace.

## 6. Assumptions
- Users are simulated with load-test scripts and simulators (customers, riders).
- One city area (Bengaluru South), 10 dark stores, ~5,000 products in the city catalog, each store listing a subset.
