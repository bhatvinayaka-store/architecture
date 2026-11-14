# Identity & Accounts - High-Level Design

**Status:** Draft v0.1 - in review · **Owner:** Identity team · **Last updated:** 2026-11-14
**Requirements:** [requirements.md](requirements.md) · **Builds on:** [system HLD platform defaults](../../system-hld.md#3-platform-defaults)

## 1. Summary
Cognito handles everything about credentials (sign-up, verification, passwords, tokens, MFA).
A small Identity service owns what Cognito should not: profiles and delivery addresses, and
trusted internal lookups for other teams.

## 2. Goals and non-goals
**Goals (R1):** IDN-01 to IDN-06 (sign-up, sign-in, addresses incl. for someone else, roles,
service-to-service calls, MFA for staff).
**Non-goals:** social login, SMS/phone login, account deletion self-service (manual in R1).

## 3. Context
```
 Browser ── managed login ──> Cognito user pool ── JWT ──> every team's HTTP API (authorizer)
    |                              |
    |                       Post-confirmation trigger
    |                              v
    └── /me, /me/addresses ──> Identity service (Lambda) ── DynamoDB identity-<stage>
                                   ^         |
    Checkout, Fulfillment, ────────┘         └── UserRegistered, Address* events -> EventBridge
    Notifications, Support (IAM /internal)
```

## 4. What drives the design
| Driver | Consequence |
|---|---|
| Never store passwords ourselves | Cognito owns credentials and tokens |
| Every team needs to know "who is calling and what role" | Groups in the JWT (`cognito:groups`); each API checks roles |
| Addresses decide which store serves an order | Addresses must have reliable lat/lng and be readable server-side by Checkout |
| Personal data (email, phone, address) | Kept in one place; not in events or logs |

## 5. Architecture
| Component | Choice | Why |
|---|---|---|
| User pool | Cognito, email as username, email verification, managed login (authorization code + PKCE) | Standard, secure, free at our scale |
| Roles | Cognito groups | Appear in the token, no extra lookups |
| Profile/address service | Spring Boot on Lambda (SnapStart) | Platform default |
| Data | DynamoDB single table | Key-based access per user |
| Post-confirmation trigger | Small Lambda: create profile item, add `customer` group, emit `UserRegistered` | Keeps Cognito and our data in step |
| Tokens | Access token 60 min, refresh token 30 days, ID token for the web app only | Common defaults; refresh keeps users signed in |

**Coordinates for addresses:** the web app lets the user drop a pin on a map (Amazon Location
Service map tiles) and sends lat/lng with the address text. R1 does not geocode typed addresses.

**MFA:** TOTP MFA optional for customers; required for staff groups. Cognito sets MFA per pool,
so staff enforcement is done by the admin role-assignment flow (staff cannot be added to a group
until MFA is set up). Verify the cleanest Cognito option during LLD.

## 6. Data model
**DynamoDB `identity-<stage>`**
| PK | SK | Attributes |
|---|---|---|
| `USER#<sub>` | `PROFILE` | name, phone, createdAt, updatedAt |
| `USER#<sub>` | `ADDR#<addressId>` | label (Home/Work/Other), line1, line2, area, pincode, lat, lng, recipientName, recipientPhone, isDefault, updatedAt |

Access patterns: get profile, list addresses (query PK), get one address (PK+SK), set default
(transaction: unset old, set new). Max 10 addresses per user.

## 7. Interfaces
See the [README](README.md). Design rules:
- `/me...` routes take the user id **only from the verified token**, never from the URL or body.
- `/internal/users/{userId}/addresses/{addressId}` returns 404 if the address does not belong to
  that user, so Checkout cannot be tricked into using someone else's address.
- Internal responses include only what the caller needs (Notifications gets email + name, not addresses).

## 8. Key flows
**8.1 Sign-up**
```
managed login sign-up -> email code -> verified -> post-confirmation trigger
 -> PROFILE item, group "customer", UserRegistered -> redirect to app with tokens
```
**8.2 Add an address**
```
app: text + map pin -> POST /me/addresses -> validate lat/lng inside Bengaluru bounding box
 -> save -> AddressAdded -> app calls Store Network /serviceability to show the serving store
```
**8.3 Checkout uses an address**
```
Checkout -> GET /internal/users/{userId}/addresses/{addressId} (IAM) -> lat/lng
 -> Store Network decides the store
```
**8.4 Admin assigns a role**
```
admin -> POST /admin/users/{id}/groups {store_manager} -> Cognito AdminAddUserToGroup
 -> UserRoleChanged (audit) -> new role appears in the user's next token
```

## 9. Failure handling
| Failure | Handling |
|---|---|
| Post-confirmation trigger fails | Cognito sign-up fails visibly; trigger is idempotent (create-if-absent), user can retry |
| Profile missing for a valid token (trigger bug) | `/me` creates it lazily |
| Role change not yet in token | Documented: takes effect at next token refresh (max 60 min); admin can sign the user out globally |

## 10. Non-functional design
| Concern | Design |
|---|---|
| Security | No passwords stored by us; least-privilege IAM; JWT validated by API Gateway; staff MFA; PII encrypted at rest (DynamoDB default) and never logged |
| Privacy | Events carry IDs only; logs mask email/phone |
| Availability | Cognito + Lambda + DynamoDB, all regional managed services |
| Cost | Cognito free tier covers our users; rest pay-per-request |
| Observability | Metrics: sign-ups, sign-in failures (from Cognito), address writes, internal lookup latency/errors. **Alarms:** internal lookup 5xx > 1%, p99 > 300 ms, post-confirmation trigger errors > 0 |

## 11. Alternatives considered
| Option | Decision |
|---|---|
| Store profiles in Cognito custom attributes | Rejected: addresses are a list; Cognito attributes are limited and awkward to query |
| Build our own auth | Rejected: security risk, no learning benefit for the goal |
| Cognito client-credentials tokens for service-to-service | Rejected in favour of IAM (ADR-0012): no secrets to manage |

## 12. Risks and open questions
1. Map pin for coordinates requires a map in the web app (Amazon Location map tiles): acceptable,
   or use a fixed list of test locations in R1?
2. Staff MFA enforcement approach to confirm in LLD.

## Change log
Record every design change here with its reason ([scope control](../../scope-control.md)).

| Date | Change | Why (story / requirement) | Approved |
|---|---|---|---|
| 2026-11-14 | v0.1 first draft | - | Pending review |
