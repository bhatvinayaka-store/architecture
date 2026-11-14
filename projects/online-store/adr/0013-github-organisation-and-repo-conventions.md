# ADR-0013: GitHub organisation, public repos and repo conventions

**Status:** Accepted · **Date:** 2026-11-14

## Context
We need a home for 30+ repos owned by different teams, with access control per team, free
branch protection, and visibility for the portfolio. GitLab (nested subgroups) was considered.

## Decision
- **GitHub organisation:** [bhatvinayaka-store](https://github.com/bhatvinayaka-store) (free plan).
- **Public repos** with secret scanning + push protection and a **gitleaks** pre-commit hook.
  Public repos get free branch protection and act as the portfolio.
- **Naming:** `<feature>-<part>`, using the feature folder names from this architecture repo
  (e.g. `inventory-backend`, `inventory-web`, `inventory-infra`, `platform-cdk-constructs`).
  Feature names are stable; team names may change.
- **Topics on every repo:** `feature-<feature>`, `team-<team>`, `release-r<n>`, `type-<part>`
  (find a feature's repos with `gh repo list bhatvinayaka-store --topic feature-inventory`).
- **Access:** organisation base permission "No permission"; GitHub teams grant access
  (`all-engineers` read on `architecture`; each feature team write on its own `<feature>-*` repos).
  CODEOWNERS points at teams.
- **Branch protection on `main`:** pull request required, status checks required (tests, Jira-key
  check), no direct pushes, no force pushes.
- **Repos are created only when their feature's development starts**, from
  `platform-service-template`.
- **Local layout mirrors features:** `~/workspace/<feature>/<part>/`.

## Consequences
Free, visible, and enforced by GitHub. Grouping is by naming and topics rather than nested
groups. Public repos mean a committed secret is exposed immediately, hence push protection and
gitleaks. GitLab remains a reasonable alternative (better nesting, free protection on private repos).
