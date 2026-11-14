# ADR-0011: One Aurora PostgreSQL Serverless v2 cluster per stage, database per team, Data API

**Status:** Proposed - **verify AWS details before building** · **Date:** 2026-11-14

## Context
Catalog (R1) and Procurement (R2) have relational data (category trees, joins, purchase orders
with lines, reports). A database server per team per stage would exceed the budget.

## Decision
- Platform hosts **one Aurora PostgreSQL Serverless v2 cluster per stage**, configured to
  **auto-pause** when idle.
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
