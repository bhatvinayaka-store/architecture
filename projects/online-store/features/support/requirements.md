# Customer Support & AI Assistant - Requirements

**Status:** Draft v0.2 · **Owner:** Customer Experience team · **Last updated:** 2026-11-21

## Goal
Answer signed-in customers' questions instantly (policies and their own orders) with an AI assistant grounded in our data, and hand off to a person when needed.

## User stories
Each story becomes one Jira story in project `STORE`; start the Jira summary with the story ID (e.g. `SUP-01: ...`).

| ID | Story | Acceptance criteria | Priority |
|---|---|---|---|
| SUP-01 | As a customer, I can ask policy questions and get answers with sources | Answers come from the Knowledge Base and cite the document; "I'm not sure" when nothing relevant is found | P0 |
| SUP-02 | As a customer, I can ask about my orders | Assistant reads **my** orders only (status, items, total, removed items); live ETA later | P0 |
| SUP-03 | As a customer, I can ask for a person | Ticket created with the conversation; visible under My tickets | P0 |
| SUP-04 | As a support agent, I can see and reply to open tickets | Staff side | Later |
| SUP-05 | As the business, the assistant never leaks other users' data or goes off-topic | userId from the token only; Guardrails; evaluation set with injection and other-user cases blocks bad deploys | P0 |
| SUP-06 | As the business, chat cost stays within budget | Signed-in only; turn, tool-call, token and hourly limits; daily cost alarm | P0 |

## Non-functional requirements
- Answer in < 8 s p95 (request/response)
- Grounded-answer rate measured on the evaluation set
- AI cost tracked per conversation

## Out of scope
- Voice support; guests; non-English
- Refunds or cancellations by the AI

## Open questions
- ~~Bedrock availability on the Free plan and in ap-southeast-2~~ Checked 2026-11-22: available; Claude through the `au.` inference profile (D15)
