# Data & Analytics - High-Level Design

**Status:** Draft v0.1 - in review · **Owner:** Data team · **Last updated:** 2026-11-14
**Requirements:** [requirements.md](requirements.md) · **Builds on:** [system HLD platform defaults](../../system-hld.md#3-platform-defaults)

## 1. Summary
A small, serverless data lake. Every business event is copied from EventBridge into S3
(pseudonymised), registered in the Glue catalog, compacted to Parquet, and turned into report
datasets by scheduled Athena queries. Nothing runs when nobody is querying.

## 2. Goals and non-goals
**Goals (R2):** ANL-01 to ANL-05 (sales, demand where we don't deliver, purchased vs sold,
stockouts, replay). **(R3):** on-time delivery.
**Non-goals:** real-time dashboards, BI tool licences, machine learning.

## 3. Context
```
 EventBridge shop-<stage> (archive on)
   └─ rule: all domain events ──> SQS analytics-<stage> ──> ingest Lambda (Python, batches of up to 5 min)
                                                              |  drop/hash personal data
                                                              v
                                          S3 raw/eventType=.../dt=.../hour=.../*.json.gz
                                                              |
                     hourly EventBridge Scheduler ──> transform Lambda: Athena INSERT INTO curated (Parquet)
                                                              |
                                           report queries (Athena) ──> S3 reports/*.json
                                                              |
                         Reports API (Lambda) ──> admin "Reports" page (micro-frontend)
 Backfill: EventBridge archive replay ──> same ingest path (idempotent by eventId)
```

## 4. What drives the design
| Driver | Consequence |
|---|---|
| Budget: no always-on clusters | S3 + Athena (pay per query) + Lambda; no Redshift, no Glue crawlers |
| Kinesis Data Firehose is not on the Free plan | Ingestion with SQS + Lambda batching instead |
| Must be rebuildable | EventBridge archive + idempotent ingest keyed by eventId |
| No personal data in analytics | Pseudonymise at ingest; user ids replaced by HMAC values |

## 5. Architecture
| Component | Choice | Why |
|---|---|---|
| Ingestion | EventBridge rule -> SQS -> Lambda with batching window | Cheap, retries, DLQ |
| Storage | S3 raw (gzip JSON) and curated (Parquet) zones | Standard lake layout |
| Catalog | Glue Data Catalog tables with **partition projection** (no crawlers) | No crawler cost; new partitions found automatically |
| Transform | Scheduled Lambda running Athena `INSERT INTO` / CTAS from raw to curated | SQL-only transformations, easy to review |
| Reports | Scheduled Athena queries write small JSON results; a Lambda API serves them | Reports page never runs Athena on page load |
| Charts | Simple charts in the admin micro-frontend | No BI licence needed |

## 6. Data model
**Raw tables:** one per event type, columns = envelope fields + `data` as JSON.
**Curated (Parquet, partitioned by `dt`):**
| Table | Grain | Key columns |
|---|---|---|
| `orders` | One row per order (latest status) | order_id, user_key (pseudonymised), store_id, status, cancel_reason, total_paise, placed_at, confirmed_at |
| `order_lines` | One row per order line | order_id, product_id, qty, price_paise, store_id, dt, hour |
| `stock_changes` | One row per bucket change | store_id, product_id, in_stock, few_left, at |
| `goods_receipts` | One row per receipt line | receipt_id, store_id, product_id, qty, at |
| `serviceability_misses` | One row per miss | rough_area, at |
| `deliveries` (R3) | One row per delivery | order_id, store_id, promised_by, delivered_at, on_time |

## 7. Interfaces
See the [README](README.md). Design rules:
- The lake is the Data team's; other teams get **read-only** access to curated tables, never write.
- Producers do not change for analytics: new questions use events that already exist, or a new
  event is requested from the owning team through a normal change.

## 8. Key flows
**8.1 Ingest**
```
OrderConfirmed -> SQS -> ingest Lambda: dedupe by eventId within batch, hash userId, write
raw/eventType=OrderConfirmed/dt=2026-11-14/hour=10/<batch>.json.gz
```
**8.2 Hourly refresh**
```
scheduler -> transform: INSERT new raw rows into curated (Parquet) -> report queries -> reports/*.json
```
**8.3 Backfill**
```
POST /admin/backfill {from, to} -> EventBridge replay -> ingest (duplicates removed in curated by eventId) -> re-run reports
```

## 9. Failure handling
| Failure | Handling |
|---|---|
| Ingest Lambda fails | SQS retries; DLQ + alarm; no data loss (events also in the archive) |
| Duplicate events | Curated tables de-duplicate on eventId |
| Bad transformation SQL | Curated is rebuildable from raw; reports flagged stale |
| Schema change in an event (new field) | Raw keeps `data` as JSON; curated SQL updated in a normal change |

## 10. Non-functional design
| Concern | Design |
|---|---|
| Privacy | Pseudonymised user keys; no emails, phones or coordinates; a weekly scan job checks for patterns that look like personal data |
| Security | Lake bucket private, encrypted; read-only Athena workgroup for other teams with a scan limit per query |
| Cost | Athena per data scanned (Parquet + partitions keep it to cents); S3 lifecycle: raw to cheaper storage after 30 days |
| Observability | Metrics: events ingested by type, ingest lag, transform duration, Athena bytes scanned. **Alarms:** DLQ > 0, ingest lag > 30 min, transform failure, daily Athena spend above limit |

## 11. Alternatives considered
| Option | Decision |
|---|---|
| Kinesis Data Firehose to S3 | Ideal, but not on the Free plan (paid plan only) |
| Kafka as the analytics pipeline | Rejected: Kafka runs only during R3 stints; EventBridge archive covers replay |
| Redshift / QuickSight | Rejected for cost |
| Glue crawlers | Rejected: partition projection is cheaper and simpler |

## 12. Risks and open questions
1. Reports page charts: in the shell's admin area (proposed) or a separate micro-frontend.

## Change log
Record every design change here with its reason ([scope control](../../scope-control.md)).

| Date | Change | Why (story / requirement) | Approved |
|---|---|---|---|
| 2026-11-14 | v0.1 first draft; Kafka removed from analytics ingestion | Simplification; Kafka only for R3 GPS stream | Pending review |
