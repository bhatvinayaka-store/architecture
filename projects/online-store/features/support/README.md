# Customer Support & AI Assistant

> Answers customer questions instantly (policies and "where is my order?") with an AI assistant
> grounded in our own data, and hands off to a human agent when needed.

| | |
|---|---|
| **Owner team** | Customer Experience |
| **Status** | HLD draft v0.1 - in review |
| **Release** | R4 (could be pulled forward to right after R1) |
| **Stack** | Python 3.13 (Lambda), Amazon Bedrock (Converse API with tool use, Knowledge Base, Guardrails), API Gateway WebSocket, DynamoDB, S3 |
| **Jira** | [STORE board](https://bhatvinayaka312.atlassian.net/jira/software/projects/STORE/boards/2) · Component `CustomerExperience` · Epic: TBD |

## What it does
- **Chat** in the web app, with streamed answers.
- **Policy answers** from our help documents (refunds, delivery times, cancellations), with sources.
- **Order help:** looks up the signed-in customer's own orders, payments and delivery status
  through other teams' APIs ("tools").
- **Hand-off:** creates a ticket with the conversation for a human support agent.
- **Agent console:** support agents see and answer tickets.
- **Safety:** guardrails against off-topic answers, personal-data leaks and prompt injection.

## Scope by release
| Release | In scope |
|---|---|
| R4 | Chat, knowledge base, order/payment/delivery tools, tickets, agent console, guardrails, evaluation set |
| Parking lot | Voice support; refunds issued by the AI (always needs a human) |

## Owns (data)
| Data | Store |
|---|---|
| Conversations (TTL 90 days), tickets, ticket messages | DynamoDB `support-<stage>` |
| Help documents (source of truth) | S3 `support-kb-<stage>` (Markdown) |
| Knowledge base index | Bedrock Knowledge Base + vector store (choice to verify, see HLD) |
| Evaluation set + results | S3 / repo `support-evals` |

## APIs
| Interface | Called by | Auth | Purpose |
|---|---|---|---|
| WebSocket `wss://.../chat` (`sendMessage`, streamed replies) | Web app | User JWT | Chat with the assistant |
| `POST /tickets` · `GET /tickets` · `GET /tickets/{id}` | Web app | User JWT | My tickets |
| `GET /agent/tickets?status=` · `POST /agent/tickets/{id}/reply` · `/close` | Agent console | support_agent | Work tickets |

## Events published
| Event | When | Key data | Consumers |
|---|---|---|---|
| `TicketCreated` / `TicketUpdated` | Ticket changes | ticketId, userId, status | Notifications, Analytics |
| `AssistantConversationEnded` | Chat ends | conversationId, resolved (yes/no), handedOff, toolsUsed | Analytics |

## Tools the assistant can call (other teams' APIs)
| Tool | API | Owner |
|---|---|---|
| `list_my_orders` | `GET /internal/users/{userId}/orders` | Commerce |
| `get_order_status` | `GET /internal/orders/{orderId}?userId=` | Commerce |
| `get_payment_status` | `GET /internal/payments/{orderId}` | Payments |
| `get_delivery_status` (R3+) | `GET /internal/deliveries/{orderId}` | Logistics |
| `create_ticket` | own | Customer Experience |

`userId` always comes from the verified chat session, never from the model or the message text.

## Service levels
| Measure | Target |
|---|---|
| First token | < 3 s |
| "Where is my order?" solved without a human | > 60% (evaluation set + real chats) |
| Unsafe / other-user data answers | 0 on the evaluation set |
| AI cost | Tracked per conversation; hard limits on turns and tokens |

## Links
| What | Link |
|---|---|
| Repos | Planned (created when development starts) in [bhatvinayaka-store](https://github.com/bhatvinayaka-store): `support-backend`, `support-web`, `support-infra`, `support-evals` · find them with topic `feature-support` |
| Pipeline | TBD (Customer Experience team pipeline) |
| Dashboard section | Prod business dashboard -> "Support" |
| Runbook | TBD |

## Local setup
1. `docker compose up` -> DynamoDB Local
2. Bedrock is called in AWS even from local (`aws login --profile <your-profile>`); other teams'
   APIs are stubbed locally
3. `pytest` + `python -m evals.run` runs the evaluation set

## Documents
- [Requirements](requirements.md) · [High-level design](hld.md) · [Decisions](adr/)
- Low-level design: written when development of this feature starts (kept in sync with what is built, see [scope control](../../scope-control.md))
