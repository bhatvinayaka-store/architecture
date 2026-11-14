# Customer Support & AI Assistant - Requirements

**Status:** Draft v0.1 · **Owner:** Customer Experience team · **Last updated:** 2026-11-14

## Goal
Answer customer questions instantly (policies and 'where is my order?') with an AI assistant grounded in our data, and hand off to a human agent when needed.

## User stories
Each story becomes one Jira story in project `STORE`; start the Jira summary with the story ID (e.g. `INV-01: ...`).

| ID | Story | Acceptance criteria | Priority |
|---|---|---|---|
| SUP-01 | As a customer, I can ask policy questions and get answers with sources | Answers cite the policy doc; says 'I don't know' when unsure | P0 |
| SUP-02 | As a customer, I can ask 'where is my order?' and get live status | Assistant calls Orders/Delivery APIs for **my** orders only | P0 |
| SUP-03 | As a customer, I can ask for a human | Ticket created with conversation transcript | P0 |
| SUP-04 | As a support agent, I can see and reply to open tickets | Agent role only | P1 |
| SUP-05 | As the business, the assistant never leaks other users' data or goes off-topic | Guardrails + authz tests (prompt-injection test set) | P0 |

## Non-functional requirements
- First token < 3 s
- Grounded-answer rate measured on a fixed evaluation set
- Monthly AI cost tracked per conversation

## Out of scope
- Voice support
- Automatic refunds by the AI (human approval required)

## Open questions
- TBD during review
