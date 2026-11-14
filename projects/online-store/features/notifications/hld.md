# Notifications - High-Level Design

**Status:** Draft v0.1 - in review · **Owner:** Engagement team · **Last updated:** 2026-11-14
**Requirements:** [requirements.md](requirements.md) · **Builds on:** [system HLD platform defaults](../../system-hld.md#3-platform-defaults)

## 1. Summary
An event-driven Python service: EventBridge rules route the events that need a message into one
SQS queue; a Lambda decides who gets what, renders a template, checks preferences and
de-duplication, and sends email through SES.

## 2. Goals and non-goals
**Goals (R1):** NTF-01, NTF-02, NTF-04, NTF-05. **(R2/P2):** NTF-03, NTF-06.
**Non-goals:** SMS, WhatsApp, push, marketing campaigns.

## 3. Context
```
 EventBridge shop-<stage>
   rule: OrderConfirmed | PaymentFailed | OrderCancelled | RefundIssued (| StockLow | StockLevelChanged ...)
        |
        v
   SQS notifications-<stage> (DLQ) ──> notifier Lambda (Python)
                                          |  1. which template + recipient(s)?
                                          |  2. preferences + de-duplication (DynamoDB)
                                          |  3. email + name from Identity (IAM)
                                          |  4. render template (S3, cached)
                                          |  5. send via SES ──> customer inbox
                                          └─> NotificationSent / NotificationFailed
 SES bounce/complaint notifications ──> SNS ──> SQS ──> feedback Lambda (mark address undeliverable)
```

## 4. What drives the design
| Driver | Consequence |
|---|---|
| One place that sends messages | All teams publish events; only this team talks to SES |
| At-least-once events | De-duplication record per (eventId, template, recipient) written **before** sending |
| Personal data stays with Identity | Fetch email at send time; never store it here except in the SES send |
| Many event types, one pipeline | Routing table (event type -> template, audience, channel, optional?) in code |

## 5. Architecture
| Component | Choice | Why |
|---|---|---|
| Routing | EventBridge rule(s) -> one SQS queue | Simple; one consumer; DLQ |
| Worker | Python Lambda with Powertools (batch processing with partial failures, idempotency utility) | Python is fast to write and starts quickly |
| Templates | Jinja2 templates in S3, versioned; cached in memory for 5 min | Change wording without redeploying |
| Email | Amazon SES | Managed email sending; bounce/complaint feedback |
| Bounces | SES -> SNS topic -> SQS -> feedback Lambda | Standard SES feedback pattern (this is the R1 use of SNS) |

**SES sandbox:** new SES setups can only send to verified addresses until production access is
granted. For a learning project, verifying your own and your friends' emails is enough.

## 6. Data model
**DynamoDB `notifications-<stage>`**
| PK | SK | Attributes |
|---|---|---|
| `USER#<userId>` | `PREFS` | optional channels on/off (e.g. backInStock), updatedAt |
| `SENT#<eventId>#<template>#<userId>` | `SENT` | status (SENDING / SENT / FAILED), sesMessageId, sentAt, TTL 30 days |
| `NOTIFYME#<storeId>#<productId>` | `USER#<userId>` | createdAt, TTL 30 days (P2) |
| `SUPPRESS#<userId>` | `EMAIL` | reason (bounce/complaint), since |

## 7. Interfaces
See the [README](README.md). Design rules:
- Producers never call Notifications; they just publish events with enough data to render
  (e.g. `OrderConfirmed` has line items).
- Every message has a template id and version, recorded in the sent log.

## 8. Key flows
**8.1 Order confirmation**
```
OrderConfirmed -> SQS -> notifier: template order-confirmed, recipient = userId
 -> Put SENT#... (condition: not exists)   [exists and SENT -> skip]
 -> Identity: email, name -> render -> SES send -> SENT -> NotificationSent
```
**8.2 Bounce**
```
SES bounce -> SNS -> SQS -> feedback Lambda -> SUPPRESS#user -> future sends skipped -> NotificationFailed
```
**8.3 Back in stock (P2)**
```
StockLevelChanged {inStock: true} -> query NOTIFYME#store#product -> one email per subscriber -> delete subscriptions
```

## 9. Failure handling
| Failure | Handling |
|---|---|
| Duplicate event | `SENT#` conditional write |
| Crash after SES send, before marking SENT | Record left as `SENDING`; on retry, a `SENDING` older than 5 min is treated as sent (prefer a rare missed email over a duplicate) |
| Identity unavailable | Message retried with backoff; DLQ after 4 tries |
| SES throttling | Retries; SES sending rate monitored |
| Template missing / broken | Message to DLQ + alarm; fix template, redrive |

## 10. Non-functional design
| Concern | Design |
|---|---|
| Privacy | Emails fetched at send time; not logged; sent log keeps userId only |
| Security | Only this team's role may send through SES; templates bucket private |
| Cost | SES + Lambda + DynamoDB: cents at our volume |
| Observability | Metrics: messages by template and outcome, event-to-send latency, suppressions. **Alarms:** DLQ > 0, send failures > 5% for 10 min, oldest message age > 2 min |

## 11. Alternatives considered
| Option | Decision |
|---|---|
| SNS fan-out per channel | Not needed with one channel (email) in R1; becomes useful when SMS/push are added |
| Each team sends its own emails | Rejected: duplicated code, inconsistent branding, no central preferences |
| Amazon Pinpoint / End User Messaging | Not needed for email-only R1 |

## 12. Risks and open questions
1. Sender domain: SES needs a verified sender identity; without a custom domain, use a verified
   personal email address as the sender in R1.

## Change log
Record every design change here with its reason ([scope control](../../scope-control.md)).

| Date | Change | Why (story / requirement) | Approved |
|---|---|---|---|
| 2026-11-14 | v0.1 first draft | - | Pending review |
