# ADR-0016: Spring Boot 3 on Lambda for Java services

**Status:** Accepted (revised 2026-11-21) · **Date:** 2026-11-20 · Resolves system HLD open question 3

## Context
Java services run on Lambda (ADR-0010). Options were plain Java Lambda handlers (fastest cold
start, tied to Lambda) or Spring Boot with a Lambda adapter (heavier start, portable, the skill
set most employers ask for).

## Decision
- Every Java service is a normal **Spring Boot 3** application, run on Lambda through
  `aws-serverless-java-container`, with **SnapStart** to cut cold starts.
- The same application runs locally as a normal Spring Boot app (and could run in a container).

## Consequences
Portable code and familiar tooling. Cold starts must be measured; SnapStart behaviour with Spring
Boot 3 (startup hooks, refreshing cached data after restore) is **to verify** at the start of development.

**SnapStart rules** (checked in the AWS docs, 2026-11-21): a snapshot copies initialised state to
every restored instance, so IDs, secrets and random seeds are created **per request** (or re-created
in an after-restore hook), never during init. The build runs AWS's open-source SnapStart scanning
rules (SpotBugs). Every function sets its timeout and memory explicitly; priming hooks warm Spring,
Jackson and the SDK clients if cold starts are too slow.
