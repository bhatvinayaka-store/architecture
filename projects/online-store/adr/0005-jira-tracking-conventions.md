# ADR-0005: Jira for tracking with key conventions

**Status:** Accepted (revised 2026-11-22) · **Date:** 2026-11-14

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
  links branches, commits and PRs to the issue automatically; a PR check enforces the key in the
  PR title (the `Docs checks` workflow in the architecture repo; code repos copy it).
- **Use the task or story key, never the epic key**, in branches, commits and PRs (e.g. epic
  `STORE-1`, task `STORE-2` → branch `STORE-2`).
- **Jira automation** comments on the task when a PR is created, merged or declined.

**Revision:** the placeholder key `SHOP` was replaced by the real project key `STORE`; Kanban
instead of 2-week sprints (simpler for part-time work). 2026-11-14 (later): task keys only in
branches/PRs; PR automation rules added. 2026-11-22: the PR-title check exists as the `Docs checks`
workflow ([design review log §14](../design-review-log.md#14-design-review-fixes-round-3), M-26).

## Consequences
Traceability like a real company; requires discipline and the GitHub for Jira app. The board
link lives in docs; the Jira site itself stays private unless shared, even if this repo is public.
