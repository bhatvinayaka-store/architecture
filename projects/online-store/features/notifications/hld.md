# Notifications - High-Level Design

**Status:** Draft v0.2 - in review (round-3 fixes and AWS checks 2026-11-22) · **Owner:** Engagement team · **Last updated:** 2026-11-22
**Requirements:** [requirements.md](requirements.md) · **Builds on:** [system HLD platform defaults](../../system-hld.md#3-platform-defaults)

## 1. Summary
An event-driven Python service: EventBridge rules route the events that need a message into one
SQS queue; a Lambda decides who gets what, renders a template, checks preferences and
de-duplication, and sends email through SES.

## 2. Goals and non-goals
**Goals (R3):** NTF-01, NTF-04, NTF-05; NTF-02 (payment failed) comes with Payments. **(Later, P2):** NTF-03, NTF-06.
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
| Bounces | SES -> SNS topic -> SQS -> feedback Lambda | Standard SES feedback pattern (the first use of SNS) |

**SES sandbox:** new SES setups can only send to verified addresses until production access is
granted. For a learning project, verifying your own and your friends' emails is enough.

**Sender:** an address on a **project domain** verified in SES with **Easy DKIM**, plus SPF (custom
MAIL FROM) and a DMARC record, so messages pass DMARC. A personal mailbox (e.g. Gmail) as the From
address fails DMARC alignment when sent through SES, so mail lands in spam or is rejected. Cost: a
domain (~$10-15 a year) and a Route 53 hosted zone ($0.50 a month). Checked 2026-11-22: SES is on
the Free plan and this account is in the sandbox (verified recipients only, 200 emails a day, 1 a
second); Route 53 refuses domain registration on the Free plan, so the domain is registered with
another registrar (or after upgrading) and its DNS is hosted in Route 53. Still to check before R3:
whether production access is granted on the Free plan.

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
| SNS fan-out per channel | Not needed with one channel (email) in R3; becomes useful when SMS/push are added |
| Each team sends its own emails | Rejected: duplicated code, inconsistent branding, no central preferences |
| Amazon Pinpoint / End User Messaging | Not needed for email-only R3 |

## 12. Risks and open questions
1. ~~Sender domain~~: decided 2026-11-22, a project domain with Easy DKIM and DMARC (§5); a personal
   mailbox as the sender would fail DMARC. Domain name to choose before R3.

## Change log
Record every design change here with its reason ([scope control](../../scope-control.md)).

| Date | Change | Why (story / requirement) | Approved |
|---|---|---|---|
| 2026-11-14 | v0.1 first draft | - | Pending review |
| 2026-11-22 | v0.2 (round-3 fixes): release labels match the plan (order emails in R3; payment emails with Payments); sender on a project domain with Easy DKIM, SPF and DMARC instead of a personal mailbox | [Design review log §14](../../design-review-log.md#14-design-review-fixes-round-3) (M-24, L-28) | Applied 2026-11-22, for review |
| 2026-11-22 | v0.2 AWS checks: SES works on the Free plan in the sandbox (200 a day, verified recipients); Route 53 cannot register domains on the Free plan, so the domain comes from another registrar | [Design review log §15](../../design-review-log.md#15-aws-checks) | Applied 2026-11-22, for review |
