# ADR-0007: Architecture docs as code, one folder per project

**Status:** Accepted · **Date:** 2026-11-14

## Context
We need one place for all architecture docs with reviews and history.

## Decision
One `architecture` repo; each project is a folder under `projects/`; changes go through short-lived branches named with the Jira key and PR review into `main`. Not one branch per project.

## Consequences
Searchable, linkable, reviewable docs; all candidates kept side by side with their status.
