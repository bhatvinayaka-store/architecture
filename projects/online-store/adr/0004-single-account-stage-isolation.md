# ADR-0004: Single AWS account with stage isolation

**Status:** Accepted · **Date:** 2026-11-14

## Context
Companies use one AWS account per stage; our AWS project is a single account.

## Decision
Isolate dev and prod by separate stacks, resource name prefixes, tags and separate resources (tables, queues, user pools). Revisit if multi-project deployment becomes possible.

## Consequences
Close to multi-account in practice; a mistake in IAM could cross stages, so policies must be scoped by name/tag.
