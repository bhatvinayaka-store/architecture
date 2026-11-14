# Platform

> The paved road: shared infrastructure, CDK building blocks, pipelines, the web shell and
> monitoring standards, so every team ships production-ready services by default.

| | |
|---|---|
| **Owner team** | Platform |
| **Status** | HLD draft v0.1 - in review |
| **Release** | R0 (before any feature) and ongoing |
| **Stack** | TypeScript (AWS CDK), CodePipeline V2 + CodeBuild, CodeConnections (GitHub), CodeArtifact, EventBridge, Aurora PostgreSQL Serverless v2, CloudFront + S3, CloudWatch, AWS Budgets |
| **Jira** | [STORE board](https://bhatvinayaka312.atlassian.net/jira/software/projects/STORE/boards/2) · Component `Platform` · Epic: TBD |

## What it provides
| Capability | For teams |
|---|---|
| **CDK construct library** `@shop/cdk-constructs` | Lambda services, HTTP APIs, tables, event subscriptions, workflows, team databases, micro-frontends: each with logging, tracing, alarms and least-privilege IAM built in |
| **Team pipeline template** | One CodePipeline per team, several GitHub repos as sources: build -> dev -> tests -> approval -> prod (canary + automatic rollback) |
| **Shared resources per stage** | Event bus `shop-<stage>` (+ archive, schema registry), Aurora cluster (hosting only), alarm topics, web hosting |
| **Discovery** | SSM parameters `/shop/<stage>/...` for every shared resource and every team's API URL/ARN |
| **Web shell** | Header, navigation, login and the loader for team micro-frontends; `config.json` per stage |
| **Observability standards** | Log format, metric names, trace propagation, 3 shared dashboards, standard alarms |
| **Cost guardrails** | Monthly budget alerts, teardown scripts for learning stints |
| **Service template repo** | New team repos start with layout, pipeline config, PR template, CODEOWNERS, Jira-key check |

## Scope by release
| Release | In scope |
|---|---|
| R0 | Construct library v1, team pipeline template, shared stacks (dev + prod), web shell, budgets, service template |
| R1-R4 | New constructs as features need them (e.g. WebSocket API in R3/R4, EKS + Kafka stint stacks in R3) |
| Parking lot | Multi-account setup (not available on this AWS plan), open-source SQS <-> Kafka bridge |

## Owns
| Resource | Notes |
|---|---|
| EventBridge bus `shop-<stage>`, archive, schema registry | Teams publish/subscribe; Platform owns the bus |
| Aurora PostgreSQL Serverless v2 cluster per stage | Platform hosts; each team owns its database inside |
| SNS topics `alerts-prod-high`, `alerts-prod-low`, `alerts-dev` | Alarm notifications (email) |
| CloudFront distribution + S3 buckets for the web shell and micro-frontends | Teams deploy into their own path |
| CodeArtifact domain/repository | Private npm packages (constructs) |
| AWS Budgets | $20/month with alerts at 50/80/100% |

## Key constructs
| Construct | Creates |
|---|---|
| `LambdaService` | Lambda (Java + SnapStart or Python), Powertools config, alias + canary deployment, log retention, standard alarms |
| `TeamHttpApi` | HTTP API with Cognito JWT authorizer, IAM-authorized `/internal/*` routes, throttling, access logs, SSM registration |
| `Table` | DynamoDB on-demand, encryption, optional PITR/Streams/TTL, throttle + error alarms |
| `EventSubscription` | EventBridge rule -> SQS (+ DLQ) -> Lambda, partial batch failures, DLQ and age alarms |
| `EventPublisher` | Grants `PutEvents` on the bus with the team's `source` |
| `Workflow` | Step Functions Standard with logging, tracing, failure alarms |
| `TeamDatabase` | Database + user on the shared Aurora cluster, secret, Data API grants |
| `MicroFrontend` | Deploys a team's UI bundle to its S3 path, registers it in `config.json`, invalidates the cache |
| `StageConfig` / `PlatformLookup` | Stage settings (sizes, thresholds, alarm topics) / reads shared resource ids from SSM |

## Service levels
| Measure | Target |
|---|---|
| New team service to dev using the template | < 1 day |
| Pipeline: merge to dev deployed | < 15 min |
| Monthly cost (R1, idle + light use) | <= $20 |

## Links
| What | Link |
|---|---|
| Repos | Planned (created when development starts) in [bhatvinayaka-store](https://github.com/bhatvinayaka-store): `platform-infra`, `platform-cdk-constructs`, `platform-web-shell`, `platform-service-template` · find them with topic `feature-platform` |
| Pipeline | TBD (Platform team pipeline) |
| Dashboards | Prod system, prod business, dev overview |
| Runbook | TBD (incl. "learning stint teardown") |

## Local setup
1. `npm ci` in `platform-cdk-constructs`; `npm test` runs construct unit tests + cdk-nag
2. `npx cdk synth` in `platform-infra` to check templates without deploying
3. Web shell: `npm run dev` with a local `config.json` pointing at local or dev APIs

## Documents
- [Requirements](requirements.md) · [High-level design](hld.md) · [Decisions](adr/)
- Low-level design: written when development starts (kept in sync with what is built, see [scope control](../scope-control.md))
