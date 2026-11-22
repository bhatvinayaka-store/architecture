# ADR-0013: GitHub organisation, public repos and repo conventions

**Status:** Accepted (revised 2026-11-22) · **Date:** 2026-11-14

## Context
We need a home for 30+ repos owned by different teams, with access control per team, free
branch protection, and visibility for the portfolio. GitLab (nested subgroups) was considered.

## Decision
- **GitHub organisation:** [bhatvinayaka-store](https://github.com/bhatvinayaka-store) (free plan).
- **Public repos** with secret scanning + push protection, a **gitleaks** pre-commit hook (opt-in)
  and the same scan in CI on every PR (the gate).
  Public repos get free branch protection and act as the portfolio.
- **Naming:** `<feature>-<part>`, using the feature folder names from this architecture repo
  (e.g. `inventory-backend`, `inventory-web`, `inventory-infra`, `platform-cdk-constructs`).
  Feature names are stable; team names may change.
- **Topics on every repo:** `feature-<feature>`, `team-<team>`, `release-r<n>`, `type-<part>`
  (find a feature's repos with `gh repo list bhatvinayaka-store --topic feature-inventory`).
- **Access:** organisation base permission "No permission"; GitHub teams grant access
  (`all-engineers` read on `architecture`; each feature team write on its own `<feature>-*` repos).
  CODEOWNERS points at teams.
- **Branch protection on `main`:** pull request required, status checks required (tests; the
  `Docs checks` workflow: Jira key in the PR title, gitleaks, links), no direct pushes, no force pushes.
- **Repos are created only after the design of all features is finalised** (ADR-0002); a
  service template repo may come later if copy-paste between teams becomes painful.
- **Local layout mirrors features:** `~/workspace/<feature>/<part>/`.
- **Names are lowercase kebab-case**, no project prefix (the org name already scopes them; ECR,
  S3 and npm names must be lowercase). Exception: the shared **`common`** repo (ADR-0014).
- **Commit email:** use the GitHub no-reply address in public repos so personal emails are not
  exposed in history.
- **Reviews:** a Claude Code review workflow comments on every non-draft PR; a human reviews and
  merges. Workflow actions are pinned to commit SHAs (a tag can be moved to other code while the job
  holds the OAuth token); one review per PR at a time (`cancel-in-progress`), 15-minute timeout.
  Merged branches are deleted ("Automatically delete head branches").
- A new repo starts with an empty commit on `main`; all content arrives through PRs.

## Consequences
Free, visible, and enforced by GitHub. Grouping is by naming and topics rather than nested
groups. Public repos mean a committed secret is exposed immediately, hence push protection and
gitleaks. GitLab remains a reasonable alternative (better nesting, free protection on private repos).

**Revised 2026-11-22** ([design review log §14](../design-review-log.md#14-design-review-fixes-round-3), M-25, M-26): gitleaks also runs in CI; the `Docs checks` workflow; workflow actions pinned to commit SHAs, with concurrency and timeouts.
