# Customer Support & AI Assistant - High-Level Design

**Status:** Draft v0.4 - customer side agreed in design review; round-3 fixes 2026-11-22 for review; Bedrock checked 2026-11-22 (Claude through the `au.` profile, D15) · **Owner:** Customer Experience team · **Last updated:** 2026-11-22
**Requirements:** [requirements.md](requirements.md) · **Builds on:** [system HLD platform defaults](../../system-hld.md#3-platform-defaults) · **Decisions:** [design review log §11](../../design-review-log.md#11-support-r2)

## 1. Summary
A chat assistant on Amazon Bedrock for signed-in customers. It answers policy questions from a
**Bedrock Knowledge Base** of our help documents and order questions by **calling Ordering as a
tool** for the signed-in customer only, and creates a ticket when a person is needed. Written in
**Java** with our own tool-use loop on the Converse API. Safety comes from authorization in our code,
Bedrock Guardrails, hard limits and an evaluation set in the pipeline.

## 2. Goals and non-goals
**Goals (R2):** SUP-01 to SUP-03, SUP-05, SUP-06.
**Later:** agent console (SUP-04, staff side), streaming answers, delivery-status and payment tools.
**Non-goals:** voice, refunds or cancellations by the AI, languages other than English, guests.

## 3. Context
```
 Browser (signed in) ── POST /api/support/conversations/{id}/messages ──> BFF (cookie -> token) ──> Support API (Lambda, Java)
                                                                                   │ 1. conversation + limits (DynamoDB)
                                                                                   │ 2. Bedrock Converse + Guardrail
                                                                                   │ 3. tools, run by OUR code:
                                                                                   │      search_policies -> Knowledge Base Retrieve
                                                                                   │      list_my_orders / get_order -> Ordering (IAM)
                                                                                   │      create_ticket -> support-tickets
                                                                                   │ 4. answer + sources
 support-kb/ (git) ── pipeline ──> S3 ──> ingestion job ──> Knowledge Base ──> evaluation set
```

## 4. What drives the design
| Driver | Consequence |
|---|---|
| Answers about **this** customer only | Tools run with the userId from the token; Ordering checks ownership too |
| Answers must be grounded | Policies come from the Knowledge Base with sources; "I'm not sure" + ticket when nothing relevant |
| Prompt injection, off-topic use | Guardrails (prompt-attack filter, denied topics) + tool allow-list + evaluation set |
| Every message costs money | Hard limits per user and a global daily cap; signed-in only; daily cost alarm |
| One Region for data | Conversations, tickets, the Knowledge Base, its documents and embeddings stay in ap-southeast-2. Claude is not offered on-demand in Sydney, so model calls use the Australia (`au.`) inference profile and run in Sydney or Melbourne, never outside Australia (D15) |

## 5. Architecture
| Component | Choice | Why |
|---|---|---|
| Transport | Request/response through the BFF (20 s budget); Support Lambda 18 s, answer deadline 15 s, then "Sorry, that took too long. Try again or create a ticket". While waiting the UI shows "Assistant is typing…" in a polite live region and disables Send. The chat says it is an AI assistant and always offers "Talk to a person" (creates a ticket) | Simple; accessible; honest; streaming later |
| Chat UI | Answers rendered as **plain text** with a small allow-list of formatting (paragraphs, lists, bold, links to our own help pages); never raw HTML; the same component is reused in the agent console | Model output is untrusted (XSS) |
| Orchestration | **Java** (Spring Boot 3 on Lambda + SnapStart), AWS SDK v2 **Converse API** with tool use, our own loop | One backend language; few tools; easy to test |
| Model | A small, fast Claude model through the **`au.` cross-Region inference profile** (e.g. `au.anthropic.claude-haiku-5-5`, listed in the account on 2026-11-22), chosen in the LLD with the evaluation set; `maxTokens` always set. Fallback: an Amazon Nova model on-demand in Sydney, same Converse API | Claude is offered in Sydney only through inference profiles, and the project's SCP allows Bedrock calls across Regions (D15); cost |
| Policies | **Bedrock Managed Knowledge Base** over Markdown docs in S3 (available in Sydney, checked 2026-11-22); fallback: self-managed KB with **S3 Vectors** (its API answers in Sydney); never OpenSearch Serverless | Chosen in review; budget |
| Safety | Bedrock Guardrails on input and output: prompt-attack filter + denied topics (medical, legal, off-topic) | Agreed |
| Data | DynamoDB `support-conversations` (TTL 30 days), `support-tickets` | Platform default |

**Tools** (the model can only ask for these; our code runs them)
| Tool | Does | Data scope |
|---|---|---|
| `search_policies(query)` | Knowledge Base `Retrieve`, top 4 chunks with document title and section | Public policies |
| `list_my_orders(limit)` | Ordering `GET /internal/users/{userId}/orders` | userId **from the token** |
| `get_order(orderId)` | Ordering `GET /internal/orders/{orderId}?userId=` | Ordering checks ownership |
| `create_ticket(summary)` | Creates a ticket with the conversation | This customer |

Tool results are trimmed to what the customer needs (no internal IDs beyond orderId).

**Limits:** 20 turns per conversation · 3 tool calls per turn · 512 output tokens per answer ·
30 messages per user per hour · **a global daily cap** across all users (starts at 100 messages a
day; an SSM value sized from the R2 Bedrock budget) · daily cost alarm. Both counters are hard
stops: before each model call one transaction adds 1 to the user's hourly counter and to the global
daily counter, each with a condition (`count < :limit`); if either fails, the model is not called
and the customer is offered a ticket. Self sign-up lets one person open many accounts, so the global
cap is what bounds the bill.

**Help documents** (`support-kb/` in the team repo, changed by PR): delivery-and-fees,
ordering-and-limits, cancellation (not available yet), out-of-stock, prices-and-mrp,
damaged-or-wrong-items, serviceability, account-and-privacy.

## 6. Data model
| Table | Keys | Attributes |
|---|---|---|
| `support-conversations` | pk `conversationId`, sk `META` / `MSG#<time>` | userId, startedAt, turns, tokensIn/Out, costEstimate, TTL 30 days · role, text, toolCalls, sources |
| `support-tickets` | pk `ticketId`, sk `META` / `MSG#<time>` | userId, conversationId, summary, status (`OPEN`/`WAITING`/`CLOSED`), createdAt · author, text (the conversation is copied in when the ticket is created and kept with the ticket for 12 months, after the conversation itself expires at 30 days) |
| `support-limits` | pk `USER#<userId>#<UTC hour>` (per user, hourly) or `GLOBAL#<UTC date>` (daily cap) | count (conditional `ADD`, both in one transaction), TTL 2 days |

Index on `support-tickets` by userId (customer's tickets); by status for the agent console later.
Message text is **never logged** (Guardrail PII masking does not stop text reaching logs).

## 7. Interfaces
All routes through the BFF (`/api/support/...`), signed-in customers only.

| Method + path | Purpose |
|---|---|
| `POST /conversations` | Start a conversation |
| `POST /conversations/{id}/messages` `{text}` (≤ 1,000 chars) | Send a message → answer + sources (+ ticketId if one was created) + `remainingThisHour` (the UI warns at 5 left); over either limit → 429 `RATE_LIMITED {retryAfterSeconds}` (next hour, or the next UTC day for the global cap) and a ticket offer |
| `GET /conversations/{id}` | Conversation history (mine only) |
| `GET /tickets` · `GET /tickets/{ticketId}` | My tickets |

**Events published:** `TicketCreated {ticketId, userId}` (agent console, Notifications later).

## 8. Key flows
**8.1 Policy question**
```
"Is delivery free?" -> model calls search_policies("delivery fee free") -> top chunks
 -> "Delivery is free on orders of ₹199 or more; below that it is ₹25. (Source: Delivery and fees)"
 -> no relevant chunk -> "I'm not sure. Shall I create a ticket?"
```
**8.2 Order question**
```
"Why is my total lower?" -> list_my_orders(userId from token) -> get_order -> line UNAVAILABLE
 -> "Milk was out of stock when we packed your order, so it was removed and your total is now ₹96."
```
**8.3 Hand-off:** "I want a person" → `create_ticket` → `TicketCreated` → visible under My tickets;
agents reply once the agent console exists.

## 9. Failure handling
| Failure | Handling |
|---|---|
| Bedrock throttling / errors | Adaptive retry; then "I'm having trouble, shall I create a ticket?" |
| Knowledge Base empty / ingestion failed | Pipeline blocks the deploy (evals fail); alarm on ingestion failure |
| Ordering down | Model told the tool failed; offers a ticket |
| Guardrail blocks | Safe refusal; counted (no text logged) |
| Limits reached (per user or global) | Model not called; suggest a ticket |

## 10. Non-functional design
| Concern | Design |
|---|---|
| Security | BFF session + JWT; tools fixed and run by our code; userId never from the model; IAM to Ordering; least-privilege Bedrock permissions |
| Privacy | Conversations expire after 30 days (a copy attached to a ticket is kept with the ticket, 12 months); message text never logged; CloudTrail data events on the Knowledge Base |
| Quality | Evaluation set (~40 cases: policies, orders, prompt injection, other users' data) after every ingestion and deploy; a lower score blocks the deploy |
| Cost | Hard caps (per user per hour, global per day) stop model calls, not just an alarm; signed-in only; cost estimate per conversation; daily alarm |
| Observability | Conversations, resolved without ticket %, tool calls/failures, guardrail blocks, tokens and cost, latency. **Alarms:** Bedrock errors > 5%, daily cost over limit, global daily cap reached, eval score below threshold, ingestion failure |

## 11. Alternatives considered
| Option | Decision |
|---|---|
| Policies in the system prompt with prompt caching | Simpler for ~8 pages; Knowledge Base chosen in review |
| Python | Common for AI teams; Java chosen to keep one backend language |
| Classic Bedrock Agents | Rejected: in maintenance mode |
| AgentCore Harness | Rejected for now: overkill for 4 tools; Region availability unverified |
| WebSocket streaming | Later; request/response fits the BFF |
| OpenSearch Serverless vector store | Rejected: minimum cost |
| Guests can chat | Rejected: order tools need a user; cost and abuse |

## 12. Risks and open questions
1. **Checked 2026-11-22** ([log §15](../../design-review-log.md#15-aws-checks)): Bedrock is on the
   Free plan; Claude is offered in Sydney only through inference profiles, so the `au.` profile is
   used (D15); Managed Knowledge Bases, S3 Vectors and the embedding models are available in Sydney.
   Still to confirm in the LLD: the first Claude call (it creates the Marketplace subscription) and
   the Knowledge Base storage price.
2. Agent console and ticket replies: staff side.

## Change log
Record every design change here with its reason ([scope control](../../scope-control.md)).

| Date | Change | Why (story / requirement) | Approved |
|---|---|---|---|
| 2026-11-14 | v0.1 first draft (Python, WebSocket, R4) | - | - |
| 2026-11-21 | v0.2: R2 right after Ordering; Java with Converse; Managed Knowledge Base via a `search_policies` tool; request/response through the BFF; signed-in only; Guardrails; limits; scope without delivery/payment tools; agent console moved to the staff side | [Design review log §11](../../design-review-log.md#11-support-r2) | Agreed in design review 2026-11-21 |
| 2026-11-21 | v0.3 (design review fixes): timeout budget (BFF 20 s, Lambda 18 s, deadline 15 s); plain-text rendering with allow-listed formatting; accessible waiting state; AI disclosure + "Talk to a person"; `remainingThisHour` and 429 body | [Design review log §12](../../design-review-log.md#12-design-review-fixes) | Agreed 2026-11-21 |
| 2026-11-21 | Context diagram path corrected to `POST /api/support/conversations/{id}/messages` (matches §7 and the BFF timeout rule) | [Design review log §13](../../design-review-log.md#13-design-review-fixes-round-2) (BE-13) | Applied 2026-11-21 |
| 2026-11-22 | v0.4 (round-3 fixes): a global daily cap and the per-user hourly counter as hard stops (`support-limits`, one transaction before each model call); chat text copied into a ticket follows ticket retention | [Design review log §14](../../design-review-log.md#14-design-review-fixes-round-3) (M-20, L-18) | Applied 2026-11-22, for review |
| 2026-11-22 | v0.4 Bedrock checked: Claude through the `au.` inference profile (not offered on-demand in Sydney), Amazon Nova as the fallback; data and the Knowledge Base stay in Sydney | [Design review log §15](../../design-review-log.md#15-aws-checks) (D15) | Your decision 2026-11-22 |
