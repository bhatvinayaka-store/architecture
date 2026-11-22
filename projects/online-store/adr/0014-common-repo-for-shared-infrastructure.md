# ADR-0014: A `common` repo for shared infrastructure, web shell and contracts

**Status:** Accepted (revised 2026-11-22) · **Date:** 2026-11-20

## Context
A full Platform team (construct library, pipeline template, shared stacks) is not needed for now:
each team owns its own repo, pipeline and infrastructure. A few things still have exactly one copy
and must be owned by someone: the event buses, the budget alert, alarm topics, the central web
shell, and the event contracts teams publish to each other. Creating them by hand in the console
would leave them out of code and let `dev` and `prod` drift apart.

## Decision
One repo, **`common`**, in the `bhatvinayaka-store` org:
```
common/
├── infra/
│   ├── foundation/  CDK (TypeScript) stack: event buses shop-dev / shop-prod (+ archive), budget
│   │                alert ($20/month at 50/80/100%), alarm SNS topics. Deployed first
│   └── edge/        CDK stack: the web CloudFront distribution (shell, /mfe/<team>/* from each
│                    team's UI bucket, /api/* routing to team APIs and the BFF; ADR-0015, ADR-0018),
│                    its security headers (strict CSP, written out in ADR-0015) and the deep-link CloudFront Function.
│                    Deployed after the team services
├── web-shell/   central UI: header, navigation, location picker, error boundaries, a placeholder
│                per team, config.json per stage (team bundle URLs), help/ (R1 static help page)
├── ui/          shared UI package: design tokens, accessible primitives, error-message list (ADR-0015)
├── contracts/   event envelope + JSON Schema for every event (StoreCreated, StockLevelChanged, ...)
└── README.md    what lives here, who may change what, how to deploy
```
- Owner: the `common` owner (CODEOWNERS); other teams change it **only by PR**, e.g. adding
  their event schema to `contracts/`.
- **Two stacks, deployed in this order:** `foundation` before any team service (the event bus must
  exist first) → team services, each publishing its API URL and UI bucket name to SSM
  (`/shop/<stage>/<team>/api-url`, `/shop/<stage>/<team>/ui-bucket`) → `edge`, which reads those
  parameters and adds a team's paths only when they exist (a missing team is skipped, not an
  error). Re-run `edge` when a team adds or changes an origin. One stack would have needed the
  team origins before the teams could deploy, and the teams need the bus first: a loop.
- The pipeline builds only the folder that changed (file-path filters on CodePipeline V2 triggers, checked 2026-11-22).
- Not allowed in `common`: team business logic, team UIs, shared databases, backend libraries
  every service is forced to use. The small `ui/` package is the one deliberate exception (shared
  look and accessibility); teams pin its version.
- Naming exception to ADR-0013: `common` is not a feature, so it has no `<feature>-<part>` name.

## Consequences
Shared pieces are in code and reviewed. It is a small, deliberate "platform"; if it grows a
construct library or pipeline template, revisit the Platform docs.

**Revised 2026-11-21** (design review fixes, [log §12](../design-review-log.md#12-design-review-fixes)): `ui/` package added; team UI bundles served at `/mfe/<team>/*` by the web distribution.

**Revised 2026-11-21 (round 2)** ([log §13](../design-review-log.md#13-design-review-fixes-round-2), BE-11, FE-8, FE-9, decision D9): `infra` split into `foundation` and `edge` stacks to break the deploy loop; deep-link CloudFront Function added; no shared import map in R1.

**Revised 2026-11-22 (round 3)** ([log §14](../design-review-log.md#14-design-review-fixes-round-3), L-21, L-26): Content-Security-Policy written out in ADR-0015; `web-shell/help/` holds the R1 help page. CodePipeline V2 file-path filters checked the same day ([log §15](../design-review-log.md#15-aws-checks)).
