# Fulfillment & Delivery

> Gets confirmed orders picked in the dark store and delivered by riders on time, with live
> tracking and a planned route when a rider carries several orders.

| | |
|---|---|
| **Owner team** | Logistics |
| **Status** | HLD draft v0.1 - in review |
| **Release** | R3 (split into R3a tracking, R3b dispatch + routes) |
| **Stack** | Java (Spring Boot 3 + Kafka Streams) in containers on **EKS**, **Kafka** on **EC2** (Docker), Python (route optimiser, Lambda), DynamoDB, API Gateway WebSocket, Amazon Location Service |
| **Jira** | [STORE board](https://bhatvinayaka312.atlassian.net/jira/software/projects/STORE/boards/2) · Component `Logistics` · Epic: TBD |

## What it does
- **Picking:** each confirmed order becomes a pick task for the store's pickers.
- **Rider tracking:** riders (simulated) send their location every 5 s through Kafka.
- **Dispatch:** assigns the nearest free rider at the store; batches up to 3 orders per rider.
- **Route planning:** orders a rider's stops to meet promised delivery times.
- **Live tracking:** customers see the rider on a map with an ETA.
- **Status updates** back to Commerce (picking, dispatched, delivered).

## Scope by release
| Release | In scope |
|---|---|
| R3a | Kafka on EC2, rider simulator, location ingest + latest positions, live tracking WebSocket, EKS cluster |
| R3b | Pick tasks, dispatch, batching (max 3), route optimisation, delivery statuses, automatic store pause signal |
| Parking lot | Real rider mobile app, rider payroll, traffic-aware re-routing |

## Owns (data)
| Data | Store |
|---|---|
| Rider GPS stream | Kafka topic `rider-locations` (partitioned by riderId) |
| Latest rider positions + availability | Kafka Streams state store (in the dispatch service) + DynamoDB copy |
| Deliveries, pick tasks, rider assignments | DynamoDB `fulfillment-<stage>` |
| Tracking connections | DynamoDB `fulfillment-ws-<stage>` |

## APIs
| Interface | Called by | Auth | Purpose |
|---|---|---|---|
| `GET /stores/{storeId}/pick-tasks` · `POST /pick-tasks/{taskId}/done` | Picker UI | picker | Pick lists and completion |
| `POST /riders/me/deliveries/{deliveryId}/pickup` · `/delivered` | Rider UI / simulator | rider | Rider actions |
| Kafka `rider-locations` {riderId, lat, lng, ts} | Rider simulator | Cluster-internal | Location updates |
| WebSocket `wss://.../track?orderId=` | Web app | User JWT (own order) | Live position + ETA |
| `GET /internal/deliveries/{orderId}` | Support, Commerce | IAM | Delivery status and ETA |

## Events published
| Event | When | Key data | Consumers |
|---|---|---|---|
| `OrderPicked` | Pick task done | orderId, storeId | Analytics |
| `RiderAssigned` | Rider assigned | orderId, riderId, etaMinutes | Notifications, Analytics |
| `OrderDispatched` / `OrderDelivered` | Pickup / drop-off | orderId, riderId, at, promisedBy | Commerce, Notifications, Analytics |
| `DeliveryStatusChanged` | Any delivery status change | orderId, status | Commerce (order timeline) |
| `StoreCapacityLow` | No free riders at a store for > 5 min | storeId | Store Network (automatic pause) |

## Events / APIs consumed
| From | What |
|---|---|
| Commerce | `OrderConfirmed` (creates a delivery + pick task), `OrderCancelled` (stop it) |
| Identity | `GET /internal/users/{userId}/addresses/{addressId}` (drop-off point) |
| Store Network | `GET /stores` (store locations) |
| Amazon Location Service | Route matrix (travel times between points) |

## Service levels
| Measure | Target |
|---|---|
| Location ingest | 2,000 updates/s in the load test (simulated riders) |
| Rider assignment | < 5 s after picking completes |
| Tracking delay | Map < 3 s behind the rider |
| On time | > 95% of simulated orders delivered by the promised time |

## Links
| What | Link |
|---|---|
| Repos | Planned (created when development starts) in [bhatvinayaka-store](https://github.com/bhatvinayaka-store): `fulfillment-backend`, `fulfillment-route-optimiser`, `fulfillment-web`, `fulfillment-infra` · find them with topic `feature-fulfillment` |
| Pipeline | TBD (Logistics team pipeline) |
| Dashboard section | Prod system dashboard -> "Fulfillment" |
| Runbook | TBD (incl. Kafka broker restart, EKS teardown) |

## Local setup
1. `docker compose up` -> Kafka (KRaft, single broker) + DynamoDB Local
2. Or `kind create cluster` + Helm charts from the infra repo to run everything on local Kubernetes
3. `scripts/simulate-riders --count 50` starts rider simulators

## Documents
- [Requirements](requirements.md) · [High-level design](hld.md) · [Decisions](adr/)
- Low-level design: written when development of this feature starts (kept in sync with what is built, see [scope control](../../scope-control.md))
