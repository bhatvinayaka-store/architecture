# ADR-0010: Serverless-first compute and data

**Status:** Accepted (revised 2026-11-15) · **Date:** 2026-11-14

## Context
The budget is about $20/month (AWS credits). Always-on resources (load balancers, containers,
database servers, NAT gateways) would each consume a large part of it even with no traffic.

## Decision
- **Choose compute by workload shape.** Low or spiky traffic, short requests, little state →
  serverless. Steady high load, long-running work, long-lived connections or state → servers or containers.
- Applied: **every feature is serverless** (Lambda with Spring Boot 3 + SnapStart, ADR-0016;
  DynamoDB on-demand; EventBridge, SQS, Step Functions, Cognito, SES, Athena, Bedrock) **except
  Fulfillment's streaming parts**: Kafka broker on EC2, stream processing and rider tracking in
  containers (learning stints).
- **Never choose a technology just to learn it.** Relational databases (RDS/Aurora) are used only
  where data is truly relational; caches only where they help (Catalog uses CloudFront, not Redis).
- Docker is used everywhere for **local development** (docker-compose, Testcontainers).

**Revision (2026-11-15):** confirmed after comparing EC2 + Redis, a central routing server and
containers everywhere; added the workload-shape rule and the "never just to learn" principle.

## Consequences
Near-zero idle cost; teams deploy small independent units. Java cold starts must be managed
(SnapStart). Long-running containers, EC2 and Kubernetes are learned where the design needs them (Fulfillment).
