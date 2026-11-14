# Operational Readiness Checklist

Every service must pass this before its first **prod** deployment. Copy into the PR description.

## Ownership
- [ ] Owner team and on-call contact listed in the feature README
- [ ] Runbook exists for every alarm

## Deployment
- [ ] Deployed through the team pipeline (no manual deploys)
- [ ] Same artifact promoted dev -> prod
- [ ] Canary or linear rollout with automatic rollback on alarm
- [ ] Rollback tested at least once

## Observability
- [ ] Structured JSON logs with correlation ID; no PII in logs
- [ ] Golden-signal dashboard (latency, traffic, errors, saturation)
- [ ] Alarms: error rate, p99 latency, DLQ depth, queue age, throttles, DB health
- [ ] Traces visible end to end in X-Ray
- [ ] SLO defined and tracked

## Resilience
- [ ] Retries with backoff and timeouts on all outbound calls
- [ ] Every queue has a DLQ and an alarm on it
- [ ] Idempotent handlers (tested with duplicate messages)
- [ ] Chaos drill done (dependency down, duplicate event, instance killed)
- [ ] Load test run against targets in requirements

## Security
- [ ] Least-privilege IAM role; cdk-nag passes
- [ ] Secrets in Secrets Manager; none in code or config
- [ ] Encryption at rest and in transit
- [ ] Input validation and authz checks on every API

## Data
- [ ] Backups / point-in-time recovery enabled where data matters
- [ ] Data retention and log retention set

## Cost
- [ ] Monthly cost estimate written down
- [ ] Dev resources can scale to zero or be torn down
