# ADR-0011: One Aurora PostgreSQL Serverless v2 cluster per stage, database per team, Data API

**Status:** Proposed (deferred: only Procurement needs it, not before its release) - **verify AWS details before building** · **Date:** 2026-11-14

## Context
Procurement has relational data (suppliers, purchase orders with lines, receipts, reports).
(Catalog was originally included; it moved to DynamoDB on 2026-11-15, see
[catalog ADR-0001](../features/catalog/adr/0001-dynamodb-two-tables.md). With Platform not needed
for now, the cluster would be owned by the team that needs it.) A database server per team per stage would exceed the budget.

## Decision
- The team that needs it (Procurement) hosts **one Aurora PostgreSQL Serverless v2 cluster per
  stage**, configured to **auto-pause** when idle. If more teams need relational data, the cluster
  moves to `common` ([ADR-0014](0014-common-repo-for-shared-infrastructure.md)).
- Each team gets **its own database and credentials** (Secrets Manager). No team may connect to
  another team's database.
- Lambdas access it through the **RDS Data API** (HTTPS + IAM), so Lambdas need no VPC and there
  is no connection pooling problem.

**To verify:** auto-pause (scale to 0 capacity) and Data API support for the chosen Aurora
PostgreSQL version in ap-southeast-2, resume time after a pause, and Data API limits.
**Fallback:** one small RDS PostgreSQL instance per stage, stopped when not in use, with Lambdas
in the VPC.

## Consequences
Relational modelling without an idle server bill. Teams share a cluster's capacity (noisy
neighbour risk, acceptable at our scale). The Data API means plain SQL (no JPA/Hibernate). The
first request after a pause waits for the database to resume.

**Revised 2026-11-22** ([design review log §14](../design-review-log.md#14-design-review-fixes-round-3), M-23): status Proposed, since ADR-0001 allows only Proposed, Accepted and Superseded; hosted by Procurement, not Platform.
