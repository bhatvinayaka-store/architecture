# ADR-0006: Self-managed Kafka

**Status:** Accepted · **Date:** 2026-11-14

## Context
Amazon MSK is not available on the AWS Free plan.

## Decision
Run Kafka locally in Docker for development, on a single EC2 instance or on Kubernetes (Strimzi) when deployed. Use EventBridge/SQS for domain events and work queues; Kafka for high-volume streams.

## Consequences
Learn Kafka operations; we own upgrades and failures; not production-grade HA on one broker.
