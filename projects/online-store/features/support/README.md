# Customer Support & AI Assistant

> Answers signed-in customers' questions instantly (policies and their own orders) with an AI
> assistant grounded in our data, and hands off to a person when needed.

| | |
|---|---|
| **Owner team** | Customer Experience |
| **Status** | HLD draft v0.4 - customer side agreed in design review; round-3 fixes 2026-11-22 for review; Bedrock checked 2026-11-22 (Claude through the `au.` profile, D15) |
| **Release** | R2: next after Ordering in the build order |
| **Stack** | Java (Spring Boot 3 on Lambda + SnapStart), Amazon Bedrock (Converse API with tool use, Managed Knowledge Base, Guardrails), DynamoDB, S3 |
| **Jira** | [STORE board](https://bhatvinayaka312.atlassian.net/jira/software/projects/STORE/boards/2) · Component `CustomerExperience` · Epic: TBD |

## What it does
- **Chat** for signed-in customers (request/response through the BFF).
- **Policy answers** from our help documents in a Bedrock Knowledge Base, with sources.
- **Order help:** reads the signed-in customer's own orders through Ordering ("tools").
- **Hand-off:** creates a ticket with the conversation.
- **Safety and cost:** Guardrails, fixed tools, hard limits, evaluation set in the pipeline.

## Scope by release
| Release | In scope |
|---|---|
| R2 | Chat, Knowledge Base, order tools, tickets (customer view), Guardrails, limits, evaluation set |
| Later | Agent console (staff side), streaming answers, delivery-status and payment tools |
| Parking lot | Voice; refunds by the AI (always needs a human) |

## Owns (data)
| Data | Store |
|---|---|
| Conversations (TTL 30 days) | DynamoDB `support-conversations-<stage>` |
| Tickets and ticket messages | DynamoDB `support-tickets-<stage>` |
| Message counters (per user per hour, global per day; TTL 2 days) | DynamoDB `support-limits-<stage>` |
| Help documents (source of truth) | `support-kb/` in git → S3 `support-kb-<stage>` |
| Knowledge base index | Bedrock Managed Knowledge Base (fallback: S3 Vectors) |
| Evaluation set + results | `support-evals/` in the repo |

## APIs
| Method + path | Called by | Auth | Purpose |
|---|---|---|---|
| `POST /conversations` · `POST /conversations/{id}/messages` · `GET /conversations/{id}` | Web app | Customer (BFF) | Chat |
| `GET /tickets` · `GET /tickets/{ticketId}` | Web app | Customer (BFF) | My tickets |

## Tools the assistant can use
| Tool | Calls | Notes |
|---|---|---|
| `search_policies` | Knowledge Base `Retrieve` | Top 4 chunks with sources |
| `list_my_orders` · `get_order` | Ordering `/internal/...` (IAM) | userId from the token; ownership checked by Ordering |
| `create_ticket` | Own table | Includes the conversation |

## Events published
| Event | When | Key data | Consumers |
|---|---|---|---|
| `TicketCreated` | Hand-off | ticketId, userId | Agent console (later), Notifications (later), Analytics |

## Service levels
| Measure | Target |
|---|---|
| Answer latency | < 8 s p95 |
| Resolved without a ticket | > 60% (evaluation + production metric) |
| Cost | Hard caps: per user per hour and a global daily cap |

## Links
| What | Link |
|---|---|
| Repos | Planned (created after the design is finalised) in [bhatvinayaka-store](https://github.com/bhatvinayaka-store): `support-backend`, `support-web`, `support-infra` · find them with topic `feature-support` |
| Pipeline | TBD (sync docs → ingestion → evaluation → deploy) |
| Decisions | [Design review log §11](../../design-review-log.md#11-support-r2) |
| Runbook | TBD |

## Local setup
1. `docker compose up` -> DynamoDB Local
2. Run the Spring Boot app against the dev Bedrock model and Knowledge Base, Ordering stubbed (WireMock)
3. `./gradlew evals` runs the evaluation set

## Documents
- [Requirements](requirements.md) · [High-level design](hld.md) · [Decisions](adr/)
- Low-level design: written when development of this feature starts (kept in sync with what is built, see [scope control](../../scope-control.md))
