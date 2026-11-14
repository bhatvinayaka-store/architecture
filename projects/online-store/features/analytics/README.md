# Data & Analytics

> Answers the business questions: what sold, where and when, how much we bought versus sold,
> how often stores ran out, where customers want us but we don't deliver, and (R3) delivery performance.

| | |
|---|---|
| **Owner team** | Data |
| **Status** | HLD draft v0.1 - in review |
| **Release** | R2 (delivery metrics in R3) |
| **Stack** | Python 3.13 (Lambda), Amazon S3 (data lake), AWS Glue Data Catalog, Amazon Athena, EventBridge archive |
| **Jira** | [STORE board](https://bhatvinayaka312.atlassian.net/jira/software/projects/STORE/boards/2) · Component `Data` · Epic: TBD |

## What it does
- Collects **every business event** from the event bus into an S3 data lake.
- Removes personal data on the way in (user ids pseudonymised; no emails, phones or coordinates).
- Builds query-ready tables and daily/hourly **report datasets** with Athena.
- Serves pre-computed reports to an admin "Reports" page.
- Can **rebuild** everything from the event archive.

## Reports
| Report | Question | Built from |
|---|---|---|
| Sales by product / store / hour | What sold, where, when? | `OrderConfirmed`, `OrderCancelled` |
| Purchased vs sold | Did we buy what we sell? Days of stock left? | `GoodsReceived`, `OrderConfirmed`, stock snapshots |
| Stockouts | How often and how long were items out per store? | `StockLevelChanged` |
| Checkout funnel | Placed -> confirmed -> cancelled by reason | `OrderPlaced`, `OrderConfirmed`, `OrderCancelled` |
| Demand where we don't deliver | Where should the next store open? | `ServiceabilityMiss` |
| Delivery performance (R3) | On-time %, average delivery time | `OrderDispatched`, `OrderDelivered` |

## Scope by release
| Release | In scope |
|---|---|
| R2 | Ingestion, pseudonymisation, raw + curated tables, the reports above (except delivery), reports API, replay/backfill |
| R3 | Delivery performance report |
| Parking lot | Real-time dashboards, ML forecasting |

## Owns (data)
| Data | Store |
|---|---|
| Raw events (JSON, partitioned by event type / date / hour) | S3 `shop-lake-<stage>/raw/` |
| Curated tables (Parquet) and report outputs | S3 `shop-lake-<stage>/curated/`, `/reports/` |
| Table definitions | Glue Data Catalog database `shop_<stage>` |
| Pseudonymisation key | Secrets Manager |

## APIs
| Method + path | Called by | Auth | Purpose |
|---|---|---|---|
| `GET /reports/{reportId}?storeId=&from=&to=` | Admin "Reports" page | store_manager (own store), buyer, admin | Pre-computed report data (JSON) |
| `POST /admin/backfill` {from, to} | Data team | admin | Replay archived events and rebuild |

## Events consumed
All business events on `shop-<stage>` (one EventBridge rule matching every domain event).

## Datasets published
| Dataset | For |
|---|---|
| `curated.orders`, `curated.order_lines` | Reports; other teams may query via Athena with read-only access |
| `curated.stock_changes`, `curated.goods_receipts` | Purchased vs sold, stockouts |

## Service levels
| Measure | Target |
|---|---|
| Freshness | Raw events in S3 < 15 min; reports refreshed hourly |
| Personal data in the lake | None (checked by a scan job) |
| Athena cost per report run | Tracked; partitioned Parquet keeps scans small |

## Links
| What | Link |
|---|---|
| Repos | Planned (created when development starts) in [bhatvinayaka-store](https://github.com/bhatvinayaka-store): `analytics-pipelines`, `analytics-web`, `analytics-infra` · find them with topic `feature-analytics` |
| Pipeline | TBD (Data team pipeline) |
| Dashboard section | Prod system dashboard -> "Data" |
| Runbook | TBD (incl. backfill) |

## Local setup
1. `pip install -e .`; `pytest` runs transformations on sample events from `data/seed/events/`
2. DuckDB locally to run the same SQL as Athena on sample Parquet files

## Documents
- [Requirements](requirements.md) · [High-level design](hld.md) · [Decisions](adr/)
- Low-level design: written when development of this feature starts (kept in sync with what is built, see [scope control](../../scope-control.md))
