# ADR-0002: Polyrepo with team ownership

**Status:** Accepted · **Date:** 2026-11-14

## Context
We want to simulate multiple teams that own features end to end and cannot change each other's code.

## Decision
Each team owns its own repos (backend, web, infra, data) and one team pipeline with multiple repo sources. Teams interact only through APIs, events, published schemas and packages. The architecture repo is readable by everyone.

## Consequences
Realistic boundaries and independent releases; more repos and pipelines to maintain; cross-team changes need contract tests and versioning. May split a team pipeline per repo later if it slows releases.
