# Identity & Accounts

> Who the user is, what they are allowed to do, and where they want things delivered.

| | |
|---|---|
| **Owner team** | Identity |
| **Status** | HLD draft v0.1 - in review |
| **Release** | R1 |
| **Stack** | Amazon Cognito (user pool, managed login), Java (Spring Boot 3 on Lambda + SnapStart), DynamoDB |
| **Jira** | [STORE board](https://bhatvinayaka312.atlassian.net/jira/software/projects/STORE/boards/2) · Component `Identity` · Epic: TBD |

## What it does
- Sign-up with email verification, sign-in, sign-out, password reset (Cognito).
- Roles via Cognito groups: `customer`, `picker`, `rider`, `store_manager`, `buyer`,
  `merchandiser`, `support_agent`, `admin`.
- User profile (name, phone) and **delivery addresses** with map coordinates, including
  addresses for someone else (recipient name + phone).
- Gives other teams trusted user and address data through internal APIs.

## Scope by release
| Release | In scope |
|---|---|
| R1 | Email sign-up/sign-in, groups, profile, addresses, role assignment by admin, MFA for staff |
| Parking lot | Social login, phone/SMS OTP login |

## Owns (data)
| Data | Store |
|---|---|
| Credentials, email, groups, MFA | Cognito user pool `shop-users-<stage>` |
| Profiles, addresses | DynamoDB `identity-<stage>` |

## APIs
| Method + path | Called by | Auth | Purpose |
|---|---|---|---|
| Cognito managed login (sign-up / sign-in / reset) | Web app | - | Hosted login pages, authorization code + PKCE |
| `GET /me`, `PATCH /me` | Web app | User JWT | Own profile |
| `GET /me/addresses`, `POST /me/addresses`, `PUT /me/addresses/{addressId}`, `DELETE ...` | Web app | User JWT | Own delivery addresses |
| `PUT /me/addresses/{addressId}/default` | Web app | User JWT | Set default address |
| `GET /internal/users/{userId}` | Notifications, Support | IAM | Contact details (email, name) |
| `GET /internal/users/{userId}/addresses/{addressId}` | Cart & Checkout, Fulfillment | IAM | Address with lat/lng, ownership checked |
| `POST /admin/users/{userId}/groups` · `DELETE ...` | Admin UI | admin | Assign / remove roles |

## Events published
| Event | When | Key data | Consumers |
|---|---|---|---|
| `UserRegistered` | Email verified | userId, createdAt | Analytics, Notifications (welcome email, optional) |
| `AddressAdded` / `AddressUpdated` / `AddressRemoved` | Address change | userId, addressId, rough area | Analytics |
| `UserRoleChanged` | Group added/removed | userId, group, action | Analytics (audit) |

No email, phone or exact coordinates in events.

## Depends on
- None (other teams depend on Identity).

## Service levels
| Measure | Target |
|---|---|
| Sign-in (Cognito) | p99 < 500 ms |
| Internal address lookup | p99 < 100 ms |
| Availability | 99.9% |

## Links
| What | Link |
|---|---|
| Repos | Planned (created when development starts) in [bhatvinayaka-store](https://github.com/bhatvinayaka-store): `identity-backend`, `identity-web`, `identity-infra` · find them with topic `feature-identity` |
| Pipeline | TBD (Identity team pipeline) |
| Dashboard section | Prod system dashboard -> "Identity" |
| Runbook | TBD |

## Local setup
1. `docker compose up` -> DynamoDB Local
2. Run the Spring Boot app; local profile accepts a test JWT signed by a local key
   (real Cognito only in dev/prod)
3. Seed test users: `scripts/seed-users` (customer, store_manager, admin)

## Documents
- [Requirements](requirements.md) · [High-level design](hld.md) · [Decisions](adr/)
- Low-level design: written when development of this feature starts (kept in sync with what is built, see [scope control](../../scope-control.md))
