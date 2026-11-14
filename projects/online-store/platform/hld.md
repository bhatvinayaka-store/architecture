# Platform - High-Level Design

**Status:** Draft v0.1 - in review · **Owner:** Platform team · **Last updated:** 2026-11-14
**Requirements:** [requirements.md](requirements.md) · **Defaults described in:** [system HLD](../system-hld.md#3-platform-defaults)

## 1. Summary
Platform turns the system HLD's defaults into reusable code: a TypeScript CDK construct library,
a pipeline template per team, shared stacks per stage, a web shell for micro-frontends, and
observability and cost guardrails. Its success measure is simple: **a team can go from a new
repo to a monitored service in dev in under a day.**

## 2. Goals and non-goals
**Goals (R0):** PLT-01 to PLT-06.
**Non-goals:** multi-account landing zone, self-service portal (e.g. Backstage), custom domains.

## 3. Context
```
 GitHub repos (per team) ──CodeConnections──> team CodePipeline ──> CodeBuild (build, test, synth)
                                                     |                   uses @shop/cdk-constructs (CodeArtifact)
                                                     v
                                         dev stacks ──> tests ──> approval ──> prod stacks (canary)
 Platform shared stacks per stage:
   network (VPC only for Aurora) · data (Aurora cluster) · events (bus, archive, registry)
   web (CloudFront, S3, shell, config.json) · observability (alarm topics, dashboards) · budget
 Discovery: SSM /shop/<stage>/* <── written by Platform and by each team's stacks
```

## 4. What drives the design
| Driver | Consequence |
|---|---|
| Many teams, one way of doing production things | Constructs with good defaults that are hard to get wrong |
| Teams deploy independently | No shared API or shared stack that every team edits; discovery through SSM |
| ~$20/month | Serverless shared resources; only 3 dashboards; alarms mostly in prod; teardown scripts |
| Single AWS account | Stage isolation by naming, tags and IAM scoping (ADR-0004) |

## 5. Architecture
### 5.1 Shared stacks (per stage)
| Stack | Contents |
|---|---|
| `platform-network-<stage>` | Small VPC with isolated subnets (2 AZs) used only by Aurora; no NAT |
| `platform-data-<stage>` | Aurora PostgreSQL Serverless v2 cluster (auto-pause, verify), Data API on, backups; admin secret |
| `platform-events-<stage>` | EventBridge bus `shop-<stage>`, archive (90 days), schema registry with discovery |
| `platform-web-<stage>` | CloudFront + S3 (shell + `/mf/<team>/` paths), `config.json` generator |
| `platform-observability-<stage>` | SNS alarm topics with email subscriptions; prod system + business dashboards; dev dashboard |
| `platform-budget` | AWS Budgets $20/month, alerts at 50/80/100% + forecast |

### 5.2 Team pipeline template
```
Sources: <team>-backend, <team>-web, <team>-infra (+ <team>-data) via CodeConnections
 -> Synth/Build (CodeBuild): unit tests, Jira-key check on commits, build Java/Python + web,
                             cdk synth, cdk-nag, unit tests for infra
 -> Deploy dev (all team stacks)
 -> Tests on dev: integration tests + contract tests (Pact) + smoke tests
 -> Manual approval (prod)
 -> Deploy prod: Lambda aliases shift 10% for 5 min, then 100%; any alarm -> automatic rollback
 -> Post-deploy smoke test
```
CDK Pipelines (self-updating) with `additionalInputs` for the extra repos. Build once; the same
artifacts go to dev and prod.

### 5.3 Micro-frontends
- Shell (React + TypeScript) owns layout, navigation, Cognito login and the token.
- Each team builds an ES-module bundle and deploys it to `/mf/<team>/<version>/` with `MicroFrontend`.
- `config.json` (per stage) lists module URLs and API URLs; the shell loads modules at runtime and
  passes them the token and the selected store.

### 5.4 Observability standards
| Item | Standard |
|---|---|
| Logs | JSON (Powertools), fields: service, team, stage, correlationId, requestId; retention dev 7 days, prod 30 days |
| Metrics | EMF, namespace `shop/<team>`; dimensions limited to service + operation (cost) |
| Traces | X-Ray via Powertools; sampling 5% + 1 request/s |
| Dashboards | **3 only** (free allowance): prod system (row per team: latency, errors, traffic, DLQs), prod business (checkout funnel, orders/min, payment failures), dev overview |
| Alarms | Standard set per construct; prod alarms -> `alerts-prod-high` / `-low`; dev only DLQ alarms; every alarm description links to its runbook |

## 6. Data model
- SSM parameters: `/shop/<stage>/events/busArn`, `/shop/<stage>/data/clusterArn`,
  `/shop/<stage>/<team>/apiUrl`, `/shop/<stage>/<team>/apiArn`, `/shop/<stage>/mf/<team>/url`.
- Tags on every resource: `Project=shop`, `Team`, `Stage`, `CostCenter=<team>`.

## 7. Interfaces
- Construct library: semantic versioning; breaking changes only in major versions, with a
  migration note; Renovate opens upgrade PRs in team repos.
- Teams read shared ids only through `PlatformLookup` (never hard-coded).

## 8. Key flows
**8.1 New team service**
```
create repos from service template -> add team to pipeline config -> push
 -> pipeline creates dev stacks (LambdaService + TeamHttpApi + Table) -> service registered in SSM + dashboard row
```
**8.2 Bad prod deployment**
```
canary 10% -> error alarm fires -> CodeDeploy rolls the alias back -> pipeline marked failed -> alert email
```
**8.3 Learning stint (e.g. EKS)**
```
deploy stint stack (tagged Stint=eks) -> work -> run teardown script (cdk destroy + check for leftovers by tag)
```

## 9. Failure handling
| Failure | Handling |
|---|---|
| Construct release breaks a team | Teams pin versions; upgrade via PR with pipeline tests |
| Shared bus misconfigured | Events archive allows replay after a fix |
| Budget alert at 80% | Pause stints; check Cost Explorer by `Team` tag |

## 10. Non-functional design
| Concern | Design |
|---|---|
| Security | cdk-nag in every build; IAM scoped by name prefix and stage; no long-lived credentials (CodeBuild roles; humans use `aws login`) |
| Cost | Serverless shared resources; 3 dashboards; prod-focused alarms; stint teardown scripts; budget alerts |
| Reliability | Shared resources are managed regional services; Aurora backups enabled |
| Developer experience | One command to start a service from the template; same local workflow for every team (docker-compose) |

## 11. Alternatives considered
| Option | Decision |
|---|---|
| One shared API Gateway for all teams | Rejected: every team would edit one resource; harder independent deploys |
| GitHub Actions instead of CodePipeline | Valid and popular; CodePipeline chosen to learn AWS CI/CD |
| One dashboard per team | Rejected for cost in R1; sections in a shared dashboard instead |
| Module Federation (webpack) for micro-frontends | Possible; plain ES modules + `config.json` is simpler |

## 12. Risks and open questions
1. Aurora auto-pause and Data API support to verify before R0 (ADR-0011).
2. Email for alarm notifications: your personal email (proposed).
3. Construct library scope for R0: only what R1 features need (LambdaService, TeamHttpApi, Table,
   EventSubscription, EventPublisher, Workflow, TeamDatabase, MicroFrontend).

## Change log
Record every design change here with its reason ([scope control](../scope-control.md)).

| Date | Change | Why (story / requirement) | Approved |
|---|---|---|---|
| 2026-11-14 | v0.1 first draft | - | Pending review |
