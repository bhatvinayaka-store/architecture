# ADR-0010: Serverless-first compute and data

**Status:** Proposed · **Date:** 2026-11-14

## Context
The budget is about $20/month (AWS credits). Always-on resources (load balancers, containers,
database servers, NAT gateways) would each consume a large part of it even with no traffic.

## Decision
- Default compute is **AWS Lambda** (Java teams: Spring Boot 3 on Lambda with SnapStart; Python
  teams: Python 3.13). Default database is **DynamoDB on-demand**. Messaging uses EventBridge,
  SQS and Step Functions, all pay-per-use.
- Containers, EC2, Kubernetes, OpenSearch and ElastiCache are used as **time-boxed learning
  stints** (R2/R3): created for the stint and destroyed after.
- Docker is used everywhere for **local development** (docker-compose, Testcontainers).

## Consequences
Near-zero idle cost; teams deploy small independent units. Java cold starts must be managed
(SnapStart). Long-running containers, EC2 and Kubernetes are learned in R2/R3 rather than R1.
