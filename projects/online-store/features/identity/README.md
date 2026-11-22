# Identity & Accounts

> Who the customer is, how they stay signed in safely, and where they want things delivered.

| | |
|---|---|
| **Owner team** | Identity |
| **Status** | HLD draft v0.5 - customer side agreed in design review; round-3 fixes 2026-11-22 for review; staff side after R1 |
| **Release** | R1: designed after Inventory; built third in the build order |
| **Stack** | Amazon Cognito (two user pools, managed login), **TypeScript BFF** (Lambda), Java (Spring Boot 3 on Lambda + SnapStart), DynamoDB |
| **Jira** | [STORE board](https://bhatvinayaka312.atlassian.net/jira/software/projects/STORE/boards/2) · Component `Identity` · Epic: TBD |

## What it does
- Customer sign-up with email verification, sign-in, sign-out, password reset through **Cognito
  managed login** (hosted pages).
- The **BFF** keeps each customer's session on the server (tokens never reach the browser) and
  forwards signed-in calls to every team's API with the access token.
- Customer profile and **delivery addresses** with map pins, including addresses for someone else.
- Trusted user and address lookups for other teams (internal APIs).
- Staff accounts live in a separate pool, built after R1; until then an operator sets up data with IAM-signed scripts.

## Scope by release
| Release | In scope |
|---|---|
| R1 | Customer pool + managed login, BFF (sessions, proxy, CSRF defence), profile, addresses, internal lookups |
| Later | Staff side (pool, roles, MFA, store scoping), WAF |
| Parking lot | Social login, passkeys / email codes, phone/SMS login, custom login domain |

## Owns (data)
| Data | Store |
|---|---|
| Customer credentials, email | Cognito user pool `shop-customers-<stage>` |
| Staff credentials (later) | Cognito user pool `shop-staff-<stage>` |
| Profiles, addresses | DynamoDB `identity-users-<stage>` |
| BFF sessions and login state | DynamoDB `identity-bff-sessions-<stage>` (TTL) |

## APIs
| Method + path | Called by | Auth | Purpose |
|---|---|---|---|
| `GET /api/auth/login` · `GET /api/auth/callback` · `POST /api/auth/logout` · `GET /api/auth/me` | Web shell | Session cookie | Sign in / out, current user (BFF) |
| `/api/<team>/...` | Web app | Session cookie | Forwarded by the BFF with the access token |
| `GET /me`, `PATCH /me` | Web app (via BFF) | Customer JWT | Own profile |
| `GET /me/addresses`, `POST /me/addresses`, `PUT /me/addresses/{addressId}`, `DELETE ...` | Web app (via BFF) | Customer JWT | Own delivery addresses |
| `PUT /me/addresses/{addressId}/default` | Web app (via BFF) | Customer JWT | Set default address |
| `GET /internal/users/{userId}` | Notifications, Support | IAM | Contact details (email, name) |
| `GET /internal/users/{userId}/addresses/{addressId}` | Ordering | IAM | Address with lat/lng; 404 if not that user's |

## Events published
| Event | When | Key data | Consumers |
|---|---|---|---|
| `UserRegistered` | Email verified | userId | Analytics, Notifications (later) |
| `AddressAdded` / `AddressUpdated` / `AddressRemoved` | Address change | userId, addressId, area | Analytics |

No email, phone or exact coordinates in events.

## Depends on
- None (other teams depend on Identity). The BFF's route map lists each team's API URL.

## Service levels
| Measure | Target |
|---|---|
| Sign-in (Cognito) | p99 < 500 ms |
| BFF overhead | < 30 ms (warm) |
| Internal address lookup | p99 < 100 ms |
| Availability | 99.9% |

## Links
| What | Link |
|---|---|
| Repos | Planned (created after the design is finalised) in [bhatvinayaka-store](https://github.com/bhatvinayaka-store): `identity-backend`, `identity-bff`, `identity-web`, `identity-infra` · find them with topic `feature-identity` |
| Pipeline | TBD (defined in the team's CDK package) |
| Decisions | [ADR-0018](../../adr/0018-customer-sign-in-with-managed-login-and-bff.md), [ADR-0019](../../adr/0019-separate-user-pools-for-customers-and-staff.md), [design review log](../../design-review-log.md#9-identity-customer-side) |
| Runbook | TBD |

## Local setup
1. `docker compose up` -> DynamoDB Local
2. Run the Spring Boot app; the local profile accepts a test JWT signed by a local key (real Cognito only in dev/prod)
3. Run the BFF locally against the dev customer pool (`npm run dev`)
4. Seed test customers: `scripts/seed-users`

## Documents
- [Requirements](requirements.md) · [High-level design](hld.md) · [Decisions](adr/)
- Low-level design: written when development of this feature starts (kept in sync with what is built, see [scope control](../../scope-control.md))
