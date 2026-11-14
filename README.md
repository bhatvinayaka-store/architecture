# Architecture

Single source of truth for product and architecture documents. Docs are Markdown, reviewed
through pull requests ("docs as code").

## Projects
| Project | Status | Folder |
|---|---|---|
| Online Store (ShopLite) | Candidate (under evaluation) - requirements draft | [projects/online-store](projects/online-store/README.md) |

Other candidates (housing society, school van tracking, clinic queue, tiffin service) can be
added as one-page `README.md` files under `projects/` with status `proposed` or `rejected`.

## Layout
```
templates/                 copy these when starting a project, feature or decision
projects/<project>/
  README.md                what it is, problem statement, users, features, releases
  requirements.md          product-wide goals, rules, non-functional requirements
  system-hld.md            how all features fit together
  adr/                     project-wide decisions
  features/<feature>/
    README.md              owner, status, links hub (repos, Jira, pipeline, dashboards), local setup
    requirements.md        user stories + acceptance criteria + NFRs
    hld.md                 feature architecture
    lld.md                 added when development of the feature starts
    adr/                   feature-level decisions
  platform/                same structure, for the platform team
  data/                    data sources and small seed samples
  operational-readiness.md checklist before prod
  scope-control.md         the main goal and how designs change as we build
  parking-lot.md           good ideas deferred to later releases
  glossary.md
```

## Where the code lives
All repos are in the GitHub organisation [bhatvinayaka-store](https://github.com/bhatvinayaka-store), named `<feature>-<part>`
(e.g. `inventory-backend`) and tagged with topics. Each feature README lists its repos.

## Work tracking
All work, including design docs, is tracked on the [STORE Kanban board in Jira](https://bhatvinayaka312.atlassian.net/jira/software/projects/STORE/boards/2)
(project key `STORE`, board grouped by epic). Conventions: [ADR-0005](projects/online-store/adr/0005-jira-tracking-conventions.md).

## How to change a document
1. Create a Jira ticket (e.g. `STORE-12`).
2. Branch from `main`: `STORE-12-inventory-hld`.
3. Edit, open a PR titled `STORE-12: Inventory HLD`, request review.
4. Resolve comments, merge. `main` always holds the reviewed version.

## Document statuses
`Not started` -> `Draft` -> `In review` -> `Approved` -> `Superseded`

## First-time setup
Run `scripts/install-hooks.sh` once after cloning: it adds a pre-commit hook that blocks
commits containing secrets (needs `brew install gitleaks`).

## Rules
- Never commit secrets, credentials or real personal data. Describe how to get access instead.
- Record important decisions as ADRs.
- Stay focused on the main goal. When a design must change, update the docs in the same PR with the reason (`projects/<project>/scope-control.md`).
