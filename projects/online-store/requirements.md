# Online Store - Product Requirements

**Status:** Draft v0.5 (round-3 fixes 2026-11-22: PRD-01 operator scripts, PRD-02 roles, PRD-05 one store per order; latency, load, availability and durability rows) · **Last updated:** 2026-11-22

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
| PRD-01 | All customer and staff actions require sign-in, except browsing the catalog, store info and serviceability. Customers sign in at checkout (Cognito managed login, session held by the BFF). **R1 has no staff accounts:** an operator sets up the data (stores, products, prices, listings, stock) with scripts that send IAM-signed requests to the admin APIs, in every stage; records that need a person get the default actor `system-operator`. Staff use a separate pool once the staff side is built (after R1) |
| PRD-02 | Role-based access. R1 has customers only (the operator works through IAM-signed scripts, PRD-01). Staff roles come with the staff side ([ADR-0019](adr/0019-separate-user-pools-for-customers-and-staff.md)): staff, manager (own store), admin and regional manager (across stores). Pickers, riders and support agents are added with Fulfillment and Support's agent console |
| PRD-03 | Every important state change is published as an event other teams can subscribe to |
| PRD-04 | Every customer-facing action that changes data is idempotent (safe to retry) |
| PRD-05 | Each order is served by exactly **one dark store**, decided by the **delivery location the customer chooses** (current location, a saved address or a map pin) and the stores' opening hours: the nearest store in range that is open now. While the cart has items the store is kept unless it stops serving (closes for the day, pauses or shuts down); then the nearest other store open now takes over, with a message. The store never changes because the device's GPS moved. Customers only see and can only buy what their store lists |
| PRD-06 | All monetary amounts are stored as integers in minor units with a currency code |
| PRD-07 | Customers can order for any served address, including someone else's (recipient name + phone) |
| PRD-08 | Prices are set **per city**; a store shows its city's price |
| PRD-09 | Each order has at most 35 different products, and each product at most the store's `maxPerOrder`; customers see these limits while adding to the cart |
| PRD-10 | Nothing is hard-deleted: products, listings and stores are deactivated, unlisted or closed (exception: a customer's saved addresses, for privacy; orders keep their own copy) |
| PRD-11 | Every service takes the customer's identity only from the verified token, never from the request |
| PRD-12 | Selling prices never exceed the MRP of packaged goods; fresh produce is sold in fixed packs |
| PRD-13 | R1 orders are paid cash on delivery; fees: delivery ₹25 (free from ₹199 subtotal), platform fee ₹5, configurable per city; customers see the full bill before placing the order |
| PRD-14 | Precise customer coordinates are never logged or put in events (sent in request bodies, not URLs) |

## 3. Non-functional requirements (initial targets, to be reviewed)
| Area | Target |
|---|---|
| Availability (prod, customer APIs) | 99.5% monthly, end to end. A checkout crosses about five services, so each service targets 99.9% (0.999⁵ ≈ 99.5%) |
| Latency | Browse p99 < 300 ms (cached); checkout p99 < 1 s for warm requests, < 3 s including cold starts (measured separately) |
| Load (test target) | 300 req/s browsing, 200 orders/min, 2,000 rider location updates/s; load tests run in `dev`, while prod public routes stay throttled for cost ([system HLD §3](system-hld.md#3-platform-defaults)) |
| Correctness | 0 oversells, 0 duplicate orders, 0 double charges in load and chaos tests |
| Durability | Every prod table: deletion protection, and point-in-time recovery except the short-lived tables named in [system HLD §3](system-hld.md#3-platform-defaults) (BFF sessions, checkout idempotency keys); RPO 5 min, RTO 1 h; a restore drill before each release |
| Security | Least-privilege IAM per service; encryption at rest and in transit; no secrets in code; PII never in logs |
| Accessibility | WCAG 2.2 AA on every customer screen; keyboard-only and screen-reader pass on the main flow each release |
| Privacy | Personal data listed with retention rules ([system HLD §3.1](system-hld.md#31-personal-data-and-retention)); deleted on request (manual in R1) |
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
Real payments, native mobile apps, multiple AWS Regions, marketing campaigns, seller marketplace.
Multiple **cities** are supported by the data model (city prices, store city) but only Bengaluru is populated.

## 6. Assumptions
- Users are simulated with load-test scripts and simulators (customers, riders).
- One city area (Bengaluru South). **R1 runs with one store (`BLR-S-01`)**; up to 10 fictional
  stores are seeded later. The data model is sized for ~3,000 stores and 45-80K products.
- ~5,000 products in the city catalog, each store listing a subset.
- Customers set the delivery location with their current location (browser) or a map pin placed
  by tap or keyboard; no geocoding service in R1 ([UX design §3](ux-design.md#3-location-picker)).
