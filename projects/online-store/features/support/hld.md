# Customer Support & AI Assistant - High-Level Design

**Status:** Draft v0.1 - in review · **Owner:** Customer Experience team · **Last updated:** 2026-11-14
**Requirements:** [requirements.md](requirements.md) · **Builds on:** [system HLD platform defaults](../../system-hld.md#3-platform-defaults)

## 1. Summary
A chat assistant built on Amazon Bedrock. It answers policy questions from a **knowledge base**
(retrieval-augmented generation) and answers order questions by **calling other teams' APIs as
tools** on behalf of the signed-in customer. Safety comes from three layers: authorization in
our code, Bedrock Guardrails, and a fixed evaluation set run in the pipeline.

## 2. Goals and non-goals
**Goals (R4):** SUP-01 to SUP-05.
**Non-goals:** voice, autonomous refunds, multilingual support (English only in R4).

## 3. Context
```
 Web chat ── WebSocket ──> API Gateway WebSocket ──> chat Lambda (Python)
                                                       |  1. load conversation (DynamoDB)
                                                       |  2. Bedrock Converse (streaming) + Guardrail
                                                       |       model may request a tool
                                                       |  3. run tool with session userId (IAM call to Commerce / Payments / Logistics)
                                                       |  4. knowledge base retrieve (policies) with citations
                                                       |  5. stream answer back to the browser
                                                       └─ tickets, events -> EventBridge
 Help docs (S3) ──> Bedrock Knowledge Base (ingestion on change)
 Agent console ──> /agent/... (Lambda) ──> tickets
```

## 4. What drives the design
| Driver | Consequence |
|---|---|
| Answers must be about **this** customer's data only | Tools run with the userId from the verified session; called APIs enforce ownership too |
| Answers must be grounded | Knowledge base retrieval with citations; "I don't know" when nothing relevant is found |
| Prompt injection and leaks | Guardrails (denied topics, PII filters, prompt-attack filter) + tool allow-list + evaluation set |
| Cost per conversation | Token limits, max tool calls per turn, max turns, small model where possible |
| Project constraint: one Region | Only models available **on-demand in ap-southeast-2**; no cross-Region inference |

## 5. Architecture
| Component | Choice | Why |
|---|---|---|
| Chat transport | API Gateway WebSocket API | Streams tokens to the browser |
| Orchestration | Python Lambda with Bedrock **Converse API** + tool use (no agent framework in R4) | Few tools; easy to read and test |
| Model | A Claude model available on Bedrock in ap-southeast-2 (choose at build time; verify Region availability) | Strong tool use; must stay in-Region |
| Knowledge base | Bedrock Knowledge Base over Markdown help docs in S3 | Managed chunking, embeddings and retrieval |
| Vector store | **To verify:** Amazon S3 Vectors (cheapest, if available in-Region) or a `support_kb` database with pgvector on the shared Aurora cluster. Not OpenSearch Serverless (high minimum cost) | Budget |
| Safety | Bedrock Guardrails on input and output | Managed filters |
| Data | DynamoDB conversations + tickets | Platform default |

## 6. Data model
**DynamoDB `support-<stage>`**
| PK | SK | Attributes |
|---|---|---|
| `CONV#<conversationId>` | `META` | userId, startedAt, status, tokensIn/Out, costEstimate, TTL 90 days |
| `CONV#<conversationId>` | `MSG#<ts>` | role, text, toolCalls, citations |
| `TICKET#<ticketId>` | `META` | userId, conversationId, status (OPEN / WAITING / CLOSED), assignedTo, createdAt |
| `TICKET#<ticketId>` | `MSG#<ts>` | author (customer / agent), text |

GSIs: tickets by status (agent console), tickets by userId.

## 7. Interfaces
See the [README](README.md) (APIs, events, tool list). Design rules:
- The model never sees other users' data because tools cannot fetch it.
- Tool results are summarised to what the customer needs (no internal IDs beyond orderId).
- Every answer from the knowledge base carries document citations.

## 8. Key flows
**8.1 "Where is my order?"**
```
user: "where is my order?" -> Converse(+guardrail) -> tool list_my_orders(userId from session)
 -> latest order CONFIRMED -> tool get_order_status -> (R3) get_delivery_status -> ETA 12 min
 -> "Your order from JP Nagar is on the way, about 12 minutes."
```
**8.2 Policy question**
```
"Can I cancel after paying?" -> knowledge base retrieve -> answer + citation (cancellation-policy.md)
```
**8.3 Hand-off**
```
"I want to talk to a person" -> create_ticket(transcript) -> TicketCreated -> agent console
 -> agent replies -> TicketUpdated -> Notifications emails the customer
```

## 9. Failure handling
| Failure | Handling |
|---|---|
| Bedrock throttling / errors | Retry with backoff; then "I'm having trouble, want me to create a ticket?" |
| Tool API down | Model told the tool failed; offers hand-off |
| Guardrail blocks | Safe refusal message; logged (without personal data) for review |
| Conversation exceeds limits | Suggest hand-off; stop calling the model |

## 10. Non-functional design
| Concern | Design |
|---|---|
| Security | Session JWT verified at `$connect`; chat Lambda may call only the listed internal routes; agent routes need `support_agent` |
| Privacy | Conversations expire after 90 days; personal data masked in logs |
| Quality | **Evaluation set** in the repo (policy questions, order questions, injection attempts, other-user requests) run in the pipeline; a drop in score blocks the deploy |
| Cost | Token limits per turn and per conversation; cost estimate per conversation recorded; budget alarm |
| Observability | Metrics: conversations, resolved without hand-off %, tool calls and failures, guardrail blocks, tokens and cost per conversation, first-token latency. **Alarms:** Bedrock error rate > 5%, cost per day over limit, eval score below threshold |

## 11. Alternatives considered
| Option | Decision |
|---|---|
| Bedrock Agents / AgentCore | Valid; plain Converse + tools is simpler to understand for a first version |
| Fine-tuning a model on support data | Not needed: retrieval + tools cover the use cases |
| OpenSearch Serverless as the vector store | Rejected for cost |

## 12. Risks and open questions
1. **Model availability in ap-southeast-2** without cross-Region inference must be confirmed
   before R4 starts.
2. Vector store choice (S3 Vectors vs pgvector) to confirm against Region support and Knowledge
   Base integration.
3. Moving R4 earlier (right after R1) is possible because it only needs Commerce and Payments APIs.

## Change log
Record every design change here with its reason ([scope control](../../scope-control.md)).

| Date | Change | Why (story / requirement) | Approved |
|---|---|---|---|
| 2026-11-14 | v0.1 first draft | - | Pending review |
