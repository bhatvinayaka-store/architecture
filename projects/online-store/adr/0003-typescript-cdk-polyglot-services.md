# ADR-0003: TypeScript CDK for infrastructure, polyglot services

**Status:** Accepted · **Date:** 2026-11-14

## Context
Teams should pick the right language per feature, but infrastructure must stay consistent.

## Decision
All infrastructure is AWS CDK in TypeScript using a shared construct library from the Platform team. Services use a paved road of Java (Spring Boot) for core business services and Python for AI, analytics and small handlers; React + TypeScript for web.

## Consequences
Consistent infra and built-in production defaults; engineers need TypeScript for infra even in Java/Python teams.
