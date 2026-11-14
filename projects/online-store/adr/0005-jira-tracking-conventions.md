# ADR-0005: Jira for tracking with key conventions

**Status:** Accepted (revised 2026-11-14) · **Date:** 2026-11-14

## Context
Work must be traceable from requirement to code to deployment, for 1-5 people.

## Decision
- **Jira** (free plan), project key **`STORE`**, on a **Kanban board grouped by epic**:
  https://bhatvinayaka312.atlassian.net/jira/software/projects/STORE/boards/2
- **Epics:** one per feature per release, e.g. `R1 · Inventory`, `R0 · Platform`. Design work
  (HLD reviews) is tracked as stories under the feature's epic.
- **Issue types:** Epic, Story, Task, Bug, Spike (learning/research).
- **Teams:** a component per team (or a `team-<name>` label if the project type has no components).
- **Stories from the docs:** each `requirements.md` story (e.g. `INV-01`) becomes one Jira story
  whose summary starts with that ID.
- **Git conventions:** every branch, commit and PR title includes the Jira key
  (`STORE-12-stock-reservations`, `STORE-12: add reservation endpoint`). The GitHub for Jira app
  links branches, commits and PRs to the issue automatically; a PR check enforces the key.

**Revision:** the placeholder key `SHOP` was replaced by the real project key `STORE`; Kanban
instead of 2-week sprints (simpler for part-time work).

## Consequences
Traceability like a real company; requires discipline and the GitHub for Jira app. The board
link lives in docs; the Jira site itself stays private unless shared, even if this repo is public.
