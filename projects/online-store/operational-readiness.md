# Operational Readiness Checklist

Every service must pass this before its first **prod** deployment. Copy into the PR description.

## Ownership
- [ ] Owner team and on-call contact listed in the feature README
- [ ] Runbook exists for every alarm

## Deployment
- [ ] Deployed through the team pipeline (no manual deploys)
- [ ] Same artifact promoted dev -> prod
- [ ] CodeDeploy pre-traffic hook runs the smoke test against the new version; automatic rollback on hook failure or alarm (canary or linear rollout once traffic is high enough to judge)
- [ ] Rollback tested at least once
- [ ] Account quotas checked before the first deploy: Lambda concurrent executions raised from the new-account 10 (1,000 requested 2026-11-22, D14); the BFF cap needs at least 140 and the checkout load test about 150

## Observability
- [ ] Structured JSON logs with correlation ID; no PII in logs
- [ ] Golden-signal dashboard (latency, traffic, errors, saturation)
- [ ] Alarms: error rate, p99 latency, DLQ depth, queue age, throttles, DB health
- [ ] Traces visible end to end in X-Ray
- [ ] SLO defined and tracked
- [ ] Custom metrics only for alarmed or dashboarded signals, in prod, without high-cardinality dimensions ([metrics rule](system-hld.md#3-platform-defaults))

## Resilience
- [ ] Retries with backoff and timeouts on all outbound calls
- [ ] Every Lambda sets its timeout and memory explicitly (never the 3 s default)
- [ ] Timeout budget written in the LLD for each synchronous flow (outer limits longer than inner)
- [ ] Every queue has a DLQ and an alarm on it
- [ ] Stream publishers: retry until success, no max record age, iterator-age alarm; **replay runbook
      tested once** in dev (block the publisher, write rows, read the shard/sequence numbers from the
      on-failure queue, re-read and re-publish them within 24 h; events arrive once, in order)
- [ ] Idempotent handlers (tested with duplicate messages)
- [ ] Chaos drill done (dependency down, duplicate event, instance killed)
- [ ] Load test run against targets in requirements

## Security
- [ ] Least-privilege IAM role; cdk-nag passes
- [ ] Secrets in Secrets Manager; none in code or config
- [ ] Encryption at rest and in transit
- [ ] Input validation and authz checks on every API
- [ ] No unauthenticated admin routes in any stage: IAM authorizer for the operator scripts until the staff side exists (D10); admin writes record the actor

## Data
- [ ] PITR + deletion protection + CDK `RETAIN` on every prod table
- [ ] Restore drill done with the runbook: restore to a new table → turn on Streams and re-create the
      stream's event source mapping (new stream ARN) → TTL, PITR, deletion protection, tags → alarms
      → check IAM policies that name the table ARN → switch the name in SSM and redeploy → run the
      feature's reconciliation → check the service (a restored table comes back without Streams, TTL
      and auto scaling)
- [ ] Short-lived tables without PITR are only the named ones (`identity-bff-sessions`, `ordering-idempotency`)
- [ ] Data retention and log retention set; personal data listed in [system HLD §3.1](system-hld.md#31-personal-data-and-retention)
- [ ] Data-deletion runbook tested once (Cognito user, profile, addresses, sessions, order addresses, tickets)

## Accessibility (UI repos)
- [ ] axe checks pass in the pipeline
- [ ] Keyboard-only and screen-reader pass on the main journey ([UX design §8](ux-design.md#8-accessibility-rules))

## Feature checks (R1)
- [ ] Inventory oversell chaos test: stop the commit consumer for 20 min during orders; no stock freed for confirmed orders ([sample S10](data/seed/inventory-sample.md))
- [ ] Inventory: a 35-line order commits in chunks, and a crash between chunks recovers (S9)
- [ ] Inventory: expiry across midnight IST (S11)
- [ ] Ordering: checkout fails within 8 s when a downstream team is down
- [ ] Inventory: one-line order whose only batch expired → `StockCommitFailed` → cancel returns nothing (S12)
- [ ] Inventory: nightly reconciliation fixes a deliberately wrong Catalog badge in dev (`BadgeCorrected` = 1, alarm fires)
- [ ] Ordering: fault-inject the order write after the reservation → hold released at once; a retry with the same key places the order
- [ ] BFF: concurrency cap (or HTTP API throttling, decision D6) set; a flood test is throttled while team APIs keep working, and the UI shows "Busy right now" on 429
- [ ] BFF: 20 parallel requests on a session due for refresh → one Cognito refresh, nobody signed out
- [ ] Web: deep link and refresh on `/p/<id>` and `/orders/<id>` work; an unknown API path still returns a JSON 404
- [ ] Web: cart module blocked → "Cart unavailable", Add disabled, saved cart intact; sign-out clears the cart after the dialog
- [ ] Web: R1 help page reachable from the footer and every order page; browser errors appear in the telemetry log with no personal data
- [ ] Store Network: two stores in range; the nearer one closes for the night while a cart has items → the cart moves to the open store, and stays there when the nearer one reopens
- [ ] Inventory: a receipt with a batch already past its stop-selling time → 422 `EXPIRES_TOO_SOON`; raising a minimum shelf life writes off batches past their new stop-selling time at once
- [ ] Inventory: expiry job stopped for 3 h in dev → heartbeat alarm fires; the next run writes off everything due
- [ ] Catalog: forged cursor, unsupported `limit` or unsorted `ids` → 400 without a DynamoDB read; the hourly read-units alarm fires in a dev flood test

## Cost
- [ ] Monthly cost estimate written down
- [ ] Dev resources can scale to zero or be torn down
