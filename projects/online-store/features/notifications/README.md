# Notifications

> Tells customers and staff what they need to know, through the right channel, exactly once,
> respecting their preferences. No other team sends email itself.

| | |
|---|---|
| **Owner team** | Engagement |
| **Status** | HLD draft v0.1 - in review |
| **Release** | R1 (order emails) · R2 (low-stock alerts) · P2 (back in stock) |
| **Stack** | Python 3.13 (Lambda, Powertools), Amazon SES (email), DynamoDB, S3 (templates), SQS |
| **Jira** | [STORE board](https://bhatvinayaka312.atlassian.net/jira/software/projects/STORE/boards/2) · Component `Engagement` · Epic: TBD |

## What it does
- Listens to business events and turns them into messages using templates.
- R1 channel: **email** via Amazon SES.
- Respects preferences: transactional messages always sent; optional ones (e.g. "back in stock")
  only if the user opted in.
- De-duplicates: the same event never produces two messages.

## Messages
| Trigger event | Message | To | Release |
|---|---|---|---|
| `OrderConfirmed` | Order confirmation with items and total | Customer | R1 |
| `PaymentFailed` | Payment failed, please try again | Customer | R1 |
| `OrderCancelled` | Order cancelled (+ refund note if paid) | Customer | R1 |
| `RefundIssued` | Refund completed | Customer | R1 |
| `StockLow` | Low-stock digest (max one per product per hour) | Store manager | R2 |
| `StockLevelChanged` (out -> in) | Back in stock | Customers who asked | P2 |
| `OrderDispatched`, `OrderDelivered` | Delivery updates | Customer | R3 |
| `TicketUpdated` | Support reply | Customer | R4 |

## Scope by release
| Release | In scope |
|---|---|
| R1 | Email for order/payment/refund events, preferences, templates, de-duplication |
| R2 / P2 | Store-manager digests, back-in-stock subscriptions |
| Parking lot | SMS, WhatsApp, mobile push (need the paid plan / a mobile app) |

## Owns (data)
| Data | Store |
|---|---|
| Preferences, sent log (TTL 30 days), back-in-stock subscriptions | DynamoDB `notifications-<stage>` |
| Email templates (versioned) | S3 `notifications-templates-<stage>` |

## APIs
| Method + path | Called by | Auth | Purpose |
|---|---|---|---|
| `GET /preferences` · `PUT /preferences` | Web app | User JWT | My notification preferences |
| `POST /notify-me` {storeId, productId} · `DELETE ...` (P2) | Web app | User JWT | Back-in-stock subscription |
| `GET /admin/sent?userId=` | Support / admin | support_agent, admin | What was sent to a user (troubleshooting) |

## Events published
| Event | When | Key data | Consumers |
|---|---|---|---|
| `NotificationSent` | Message accepted by SES | messageId, userId, template, channel | Analytics |
| `NotificationFailed` | Permanent failure (e.g. bounce) | userId, template, reason | Analytics, Support |

## Depends on
| On | Why |
|---|---|
| Identity `GET /internal/users/{userId}` | Email address and name (not in events) |
| Events from Commerce, Payments, Inventory | Triggers |

## Service levels
| Measure | Target |
|---|---|
| Event to email accepted by SES | p95 < 60 s |
| Duplicates | 0 per event and channel |

## Links
| What | Link |
|---|---|
| Repos | Planned (created when development starts) in [bhatvinayaka-store](https://github.com/bhatvinayaka-store): `notifications-backend`, `notifications-infra` · find them with topic `feature-notifications` |
| Pipeline | TBD (Engagement team pipeline) |
| Dashboard section | Prod system dashboard -> "Notifications" |
| Runbook | TBD |

## Local setup
1. `docker compose up` -> DynamoDB Local + ElasticMQ + MailHog (local SMTP inbox)
2. `pip install -e .` then `pytest`; `scripts/send-sample OrderConfirmed` renders and "sends" to MailHog

## Documents
- [Requirements](requirements.md) · [High-level design](hld.md) · [Decisions](adr/)
- Low-level design: written when development of this feature starts (kept in sync with what is built, see [scope control](../../scope-control.md))
