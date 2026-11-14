# Online Store - System High-Level Design

**Status:** Draft v0.2 - in review · **Last updated:** 2026-11-14

How all features fit together, and the **platform defaults** every feature HLD builds on.
Feature HLDs only describe where they differ from these defaults.

## 1. Context
```
 Customer / staff / rider (browser)
        |
  CloudFront + S3 ── web shell (Platform) loads each team's micro-frontend
        |
  Team HTTP APIs (API Gateway) ── Cognito JWT for users · IAM (SigV4) for service-to-service
        |
 +------------+-----------+-----------+----------+----------+-----------+-----------+
 |            |           |           |          |          |           |           |
 Store       Identity   Catalog   Inventory   Cart &    Payments   Procurement  Support
 Network                                     Checkout                (R2)        (R4)
 |            |           |           |          |          |           |           |
 +------------+-----------+---- EventBridge bus "shop-<stage>" ---------+-----------+
                                  |              |                |
                            Notifications   Data & Analytics   Fulfillment & Delivery (R3)
                                            (S3 + Athena, R2)  Kafka on EC2 + EKS (learning stint)
```

## 2. Teams, features and data ownership
| Team | Feature | Release | Owns (data) | Compute |
|---|---|---|---|---|
| Platform | Platform | R0 | Event bus, shared Aurora cluster (hosting only), web hosting, alarm topics, budgets | CDK |
| Logistics | Store Network & Serviceability | R1 | Stores, zones (GeoJSON in S3), store status (DynamoDB) | Lambda (Java) |
| Identity | Identity & Accounts | R1 | Cognito user pool, profiles + addresses (DynamoDB) | Lambda (Java) |
| Catalog | Catalog & Search | R1 / R2 | Products, categories, assortment (Aurora PostgreSQL), images (S3) | Lambda (Java) |
| Inventory | Inventory | R1 / R2 | Stock, reservations, movements (DynamoDB) | Lambda (Java) |
| Commerce | Cart & Checkout | R1 | Carts, orders (DynamoDB), checkout workflow (Step Functions) | Lambda (Java) |
| Payments | Payments | R1 | Payments, refunds (DynamoDB), charge queue (SQS) | Lambda (Java) |
| Engagement | Notifications | R1 | Preferences, sent log (DynamoDB), templates (S3) | Lambda (Python) |
| Supply | Supply & Procurement | R2 | Suppliers, POs, receipts (Aurora PostgreSQL) | Lambda (Java) + Step Functions |
| Data | Data & Analytics | R2 | Data lake (S3), Glue catalog | Lambda (Python) + Athena |
| Logistics | Fulfillment & Delivery | R3 | Deliveries, rider state (DynamoDB), GPS stream (Kafka) | Containers on EKS + Lambda |
| Customer Experience | Support & AI Assistant | R4 | Conversations, tickets (DynamoDB), knowledge base | Lambda (Python) + Bedrock |

**Rules**
- No team reads another team's database. Only APIs, events and published datasets.
- Shared infrastructure (the Aurora cluster, the event bus) is **hosted** by Platform; the data in
  it belongs to the team that writes it (separate database and credentials per team).

## 3. Platform defaults
| Area | Default | Why |
|---|---|---|
| **Compute** | AWS Lambda. Java teams: **Spring Boot 3 on Lambda** (`aws-serverless-java-container`) with **SnapStart**; Python teams: Python 3.13 | Pay per request (no idle cost). The same Spring Boot app also runs locally as a normal app. SnapStart cuts Java cold starts (verify Spring + SnapStart behaviour) |
| **APIs** | Each team owns one **API Gateway HTTP API** per stage. User routes: Cognito JWT authorizer. Internal routes (`/internal/...`): IAM auth | Teams deploy independently; no shared API to coordinate |
| **Service-to-service auth** | IAM SigV4-signed requests; callers get `execute-api:Invoke` on specific internal routes only | No shared secrets to store or rotate |
| **Default database** | **DynamoDB** on-demand, one table per feature per stage; point-in-time recovery for orders, payments, inventory | No idle cost, scales automatically, fits key-based access |
| **Relational database** | One **Aurora PostgreSQL Serverless v2** cluster per stage with **auto-pause**, a database + credentials per team, accessed through the **RDS Data API** | Relational where it fits (Catalog, Procurement) without paying for an idle server; Lambdas need no VPC. **Verify** auto-pause and Data API support before building (ADR-0011) |
| **Events** | One **EventBridge** custom bus per stage (`shop-dev`, `shop-prod`), Schema Registry with discovery, **archive** enabled for replay | Decoupled pub/sub; archive lets Analytics rebuild datasets |
| **Work queues** | **SQS** per consumer, each with a DLQ (`maxReceiveCount` 4) and an alarm on it | Reliable retries, buffering |
| **Workflows** | **Step Functions Standard** for multi-step processes with waits or compensation | Built-in retries, timeouts, visual history |
| **Streams** | **Kafka** only for the rider GPS stream (R3), self-managed (ADR-0006) | Only place with high-volume ordered data |
| **Observability** | Powertools for AWS Lambda (Java/Python): JSON logs, metrics (EMF), X-Ray traces; `correlationId` passed in headers and event metadata | One way of logging and tracing across all teams |
| **Secrets** | Secrets Manager only for real secrets (database credentials) | Most access is IAM, so few secrets |
| **Networking** | Lambdas run **outside** a VPC; only Aurora sits in a VPC (isolated subnets, no internet). **No NAT gateway** | NAT costs more per month than our entire budget |
| **Web** | CloudFront + S3; Platform shell + team micro-frontends; `config.json` lists API URLs and module URLs per stage | Teams ship UI independently |

## 4. Event conventions
Every event on the bus uses the same envelope (`detail-type` = event name):
```json
{
  "eventId": "uuid",            // consumers de-duplicate on this
  "eventType": "OrderConfirmed",
  "version": 1,                 // bump only for breaking changes; add fields freely
  "occurredAt": "2026-11-14T10:15:00Z",
  "producer": "commerce",
  "correlationId": "uuid",      // follows one customer action across all services
  "data": { }
}
```
- Delivery is **at least once**: every consumer must be idempotent.
- Events carry the data consumers need (e.g. `OrderConfirmed` includes order lines), so consumers
  rarely need to call back.
- No personal data in events beyond IDs (no emails, phone numbers, exact coordinates).

## 5. Key cross-team flows
**5.1 Which store serves the customer (R1)**
```
App: delivery address chosen (phone location only as a default)
  -> Store Network: GET /serviceability(lat,lng) -> storeId | not served (+ waitlist)
  -> Catalog: GET /stores/{storeId}/products       (only what that store lists)
  -> Cart bound to storeId
  -> Checkout re-derives the store from the delivery address (client storeId ignored)
```

**5.2 Checkout (R1)**
```
POST /checkout (Idempotency-Key)
  Commerce: idempotency check -> address (Identity) -> store (Store Network) -> prices (Catalog)
         -> order PENDING -> start checkout workflow (execution name = orderId)
  Workflow: reserve stock (Inventory, sync) ── fails -> order CANCELLED (OUT_OF_STOCK)
         -> ChargeOrder (Payments, SQS) -> wait for PaymentSucceeded / PaymentFailed (10 min timeout)
         -> success: order CONFIRMED -> OrderConfirmed
         -> failure/timeout: order CANCELLED -> OrderCancelled
  OrderConfirmed -> Inventory commits stock · Notifications emails · Analytics · Fulfillment (R3)
  OrderCancelled -> Inventory releases stock · Payments refunds if money was taken
```

**5.3 Stock status reaches the catalog (R1)**
```
Inventory stock changes -> (DynamoDB Streams) -> StockLevelChanged {storeId, productId, inStock, fewLeft}
  -> Catalog updates the store's availability -> customers see "in stock / only a few left / out"
Checkout never trusts the catalog flag; Inventory's reservation is the source of truth.
```

**5.4 Restocking (R2)**
```
Inventory --StockLow--> Procurement: qty = target - (available + on order)
  -> purchase order (approval if above threshold) -> supplier simulator
  -> staff record goods received --GoodsReceived--> Inventory: on hand += received
  -> StockLevelChanged -> Catalog "in stock", Notifications "back in stock" (P2)
Inventory is the only writer of stock counts (ADR-0008).
```

**5.5 New product onboarding (R1 / R2)**
```
Catalog: merchandiser creates product -> lists it in stores -> AssortmentChanged
  -> Inventory creates stock records (on hand 0) for those stores
  -> (R2) Procurement links a supplier + cost price, sets reorder rule -> first PO -> GoodsReceived
```

## 6. Environments and delivery
- Stages `dev` and `prod` as separate stacks in one AWS account (ADR-0004); names
  `<team>-<feature>-<stage>`, tags `Project=shop`, `Team`, `Stage`; IAM scoped by name prefix.
- One pipeline per team, several repo sources (ADR-0002): build -> dev -> tests -> approval -> prod.
- Lambda deployments shift traffic gradually (canary) and roll back automatically on alarm.

## 7. Cost budget
**Budget:** $120 of credits until 2027-05-13, about **$20 per month**. Rough estimates below;
verify with the AWS pricing calculator before each release.

| Item | Idle cost | Notes |
|---|---|---|
| Lambda, API Gateway, DynamoDB, SQS, EventBridge, Step Functions | ~$0 | Pay per request; our traffic is tiny outside load tests |
| Aurora Serverless v2 (2 clusters, auto-paused) | ~$1-3 | Storage + backups only while paused (verify) |
| Secrets Manager | ~$2 | A few secrets |
| CloudWatch alarms | ~$4-6 | ~40-60 alarms, mostly in prod |
| CloudWatch dashboards | $0 | **Only 3 dashboards** (within the free allowance): prod system, prod business, dev |
| CodePipeline / CodeBuild | ~$2-5 | Depends on how often you push |
| **R1 total (estimate)** | **~$10-15/month** | |

**Learning stints** (created for the stint, destroyed afterwards with `cdk destroy`):
| Stint | Rough cost while running |
|---|---|
| OpenSearch (R2 search) | ~$1/day |
| ElastiCache (R2 cache) | ~$0.5/day |
| EKS + nodes (R3) | ~$3-4/day |
| Kafka on EC2 (R3) | ~$0.5/day |
| Bedrock (R4) | Per token; capped per conversation |

Guardrails: AWS Budgets alerts at 50 / 80 / 100% of $20/month; monthly check of remaining
credits; every stack has a documented teardown.

## 8. Decisions
ADR-0001..0013 in [adr/](adr/). New in this version: ADR-0009 updated (zones evaluated in memory),
ADR-0010 serverless-first, ADR-0011 shared Aurora cluster with Data API, ADR-0012 IAM for
service-to-service calls.

## 9. Open questions for review
1. **Budget:** is ~$20/month (credits only) the real limit, or will you add your own money later?
   This decides how long learning stints can run.
2. **Region:** ap-southeast-2 (fixed by the AWS project) with India-based customers in the story;
   accepted for a learning project?
3. **Spring Boot on Lambda** vs plain Java handlers: Spring keeps the skills most Indian
   employers ask for; plain Java starts faster. Proposed: Spring Boot + SnapStart.
4. Should Cart and Checkout be one feature or two? (Proposed: one.)

## Change log
| Date | Change | Why | Approved |
|---|---|---|---|
| 2026-11-14 | v0.1 first draft | - | - |
| 2026-11-14 | v0.2: platform defaults, serverless-first, event conventions, cost budget, onboarding flow; Kafka limited to GPS stream | ~$20/month budget makes always-on servers impossible; simplification | Pending review |
