# Platform - Requirements

**Status:** Draft v0.1 · **Owner:** Platform team · **Last updated:** 2026-11-14

## Goal
Give every team a paved road: shared network, event bus, CDK constructs, pipeline template, observability standards, and the web shell, so teams ship production-ready services by default.

## User stories
Each story becomes one Jira story in project `STORE`; start the Jira summary with the story ID (e.g. `INV-01: ...`).

| ID | Story | Acceptance criteria | Priority |
|---|---|---|---|
| PLT-01 | As a team, I can create a new service from the template with pipeline, dashboard and alarms in < 1 day | Golden path documented and tested | P0 |
| PLT-02 | As a team, I can look up the VPC, event bus and Cognito IDs without hard-coding | SSM parameters per stage | P0 |
| PLT-03 | As on-call, every service has the same golden-signal dashboard and standard alarms | Built into constructs; cdk-nag passes | P0 |
| PLT-04 | As a team, I can deploy dev -> prod with approval and automatic rollback | Canary + alarm rollback | P0 |
| PLT-05 | As a team, I can deploy my micro-frontend independently | Shell loads remote modules from team S3 paths | P1 |
| PLT-06 | As the owner, I get budget alerts before credits run out | Alerts at 50% and 80% | P0 |

## Non-functional requirements
- New service to dev in < 1 day using the template
- Construct library has unit tests + cdk-nag; semantic versioning

## Out of scope
- Multi-account landing zone (not available on this AWS plan)

## Open questions
- TBD during review
