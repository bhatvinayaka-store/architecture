# Fulfillment & Delivery - High-Level Design

**Status:** Draft v0.2 - in review (deferred) · **Owner:** Logistics team · **Last updated:** 2026-11-22
**Requirements:** [requirements.md](requirements.md) · **Builds on:** [system HLD platform defaults](../../system-hld.md#3-platform-defaults)

## 1. Summary
The one feature that deliberately breaks from the serverless default: high-volume, ordered rider
location data flows through **Kafka**, and long-running stream processors run as containers on
**Kubernetes (EKS)**. This is where EC2, Docker, Kubernetes and Kafka are learned, as a
**time-boxed learning stint** (ADR-0010): the cluster and broker exist only while Fulfillment is
being built and tested.

## 2. Goals and non-goals
**Goals (phase A):** FUL-02, FUL-05. **(phase B):** FUL-01, FUL-03, FUL-04.
**Non-goals:** real rider apps, payroll, traffic-aware re-routing, multi-broker Kafka HA.

## 3. Context
```
 Rider simulator pods ── produce ──> Kafka on EC2 (topic rider-locations, 12 partitions by riderId)
                                          |
                     +--------------------+---------------------+
                     v                                          v
         dispatch service (EKS, Kafka Streams)        tracking service (EKS)
           latest position + availability per rider      latest position per order's rider
           assign rider / batch / call optimiser          push to WebSocket connections
                     |                                          |
              DynamoDB fulfillment-<stage>            API Gateway WebSocket ──> customer map
                     |
 Ordering: OrderConfirmed ──> EventBridge ──> SQS ──> delivery creator ─┘
 Route optimiser (Python Lambda, Amazon Location route matrix)
 Events out: RiderAssigned, OrderDispatched, OrderDelivered, DeliveryStatusChanged, StoreCapacityLow
```

## 4. What drives the design
| Driver | Consequence |
|---|---|
| ~2,000 location updates/s, per-rider ordering, replay for debugging | Kafka, partitioned by riderId |
| Continuous stream processing with state (latest positions) | Kafka Streams in long-running containers, not Lambda |
| Learning goals: EC2, Docker, Kubernetes, Kafka | EKS + Kafka on EC2 here, and only here |
| Budget | Everything in this section is created for the stint and destroyed after |
| Nearest-rider search over ~100-200 riders per city | In-memory distance check in the dispatch service; no geo database needed |

## 5. Architecture
| Component | Choice | Why |
|---|---|---|
| Kafka | Single broker, KRaft mode, Docker on one small Graviton EC2 instance, EBS volume | MSK not on the Free plan (ADR-0006); single broker is enough to learn; not HA |
| Kubernetes | EKS with a small managed node group (2 small nodes), public subnets, no NAT | Learn deployments, services, HPA, Helm; no NAT for budget |
| Dispatch service | Spring Boot + **Kafka Streams**: KTable of latest rider positions + availability; assignment logic | Stateful stream processing |
| Tracking service | Spring Boot consumer: pushes positions to customers' WebSocket connections (API Gateway management API) | Live map |
| Route optimiser | Python Lambda: travel-time matrix from Amazon Location Service; nearest-stop-first, improved with 2-opt, respecting promised times | Clear algorithm to measure and explain |
| Rider simulator | Pods that move riders along roads between store and drop-offs and publish every 5 s | Load and realism |
| Delivery records | DynamoDB | Platform default |

**Dispatch rules (phase B)**
1. A delivery becomes assignable when its pick task is done.
2. Candidates: free riders at the same store within 3 km, or riders with < 3 orders whose route
   still meets every promised time if this stop is added.
3. Pick the candidate with the smallest added travel time; ask the optimiser for the stop order.
4. Re-plan when a stop is added or a rider falls behind by > 5 min.

## 6. Data model
**Kafka:** `rider-locations` (key riderId, retention 24 h), `rider-status` (key riderId: free/busy, compacted).

**DynamoDB `fulfillment-<stage>`**
| PK | SK | Attributes |
|---|---|---|
| `DELIVERY#<orderId>` | `DELIVERY` | storeId, addressId, drop lat/lng, promisedBy, status (PICKING / READY / ASSIGNED / DISPATCHED / DELIVERED / CANCELLED), riderId, stopIndex |
| `PICK#<storeId>` | `<createdAt>#<orderId>` | lines, status |
| `RIDER#<riderId>` | `STATE` | storeId, current deliveries, last position (copied every 30 s for the API) |

**DynamoDB `fulfillment-ws-<stage>`:** `ORDER#<orderId>` -> connectionIds (TTL 2 h).

## 7. Interfaces
See the [README](README.md). Design rules:
- Location messages never leave the cluster; only summaries (statuses, ETA) go on EventBridge.
- Customers can subscribe to tracking only for their own orders (checked at connect).
- Delivery statuses flow to Ordering via `DeliveryStatusChanged`; Ordering owns the order timeline.

## 8. Key flows
**8.1 Order to delivery**
```
OrderConfirmed -> delivery PICKING + pick task -> picker done -> OrderPicked -> READY
 -> dispatch assigns rider (+ optimiser order) -> RiderAssigned -> rider pickup -> OrderDispatched
 -> rider drop-off -> OrderDelivered -> DeliveryStatusChanged(DELIVERED) -> Ordering timeline
```
**8.2 Live tracking**
```
app opens wss://.../track?orderId -> connect handler checks ownership -> store connection
rider-locations -> tracking service -> rider of that order? -> PostToConnection {lat, lng, eta}
```
**8.3 No riders free**
```
dispatch: store has 0 free riders for > 5 min -> StoreCapacityLow -> Store Network pauses the store
```

## 9. Failure handling
| Failure | Handling |
|---|---|
| Kafka broker down | Simulators buffer and retry; tracking freezes; deliveries keep their last state. Single broker = known limitation |
| Dispatch pod restarts | Kafka Streams restores state from its changelog topic; consumer group rebalances |
| Optimiser fails / times out | Fall back to nearest-stop-first order |
| WebSocket connection gone | `GoneException` -> remove connection |

## 10. Non-functional design
| Concern | Design |
|---|---|
| Scale | 12 partitions allow up to 12 consumers per group; HPA on consumer lag |
| Latency | Location to customer map < 3 s |
| Security | Kafka reachable only from the cluster's security group; pods use IAM roles for service accounts |
| Cost | EKS control plane + 2 small nodes + 1 EC2 broker ≈ $3-4/day while running; **destroy at the end of each session** (scripted) |
| Observability | Metrics: consumer lag, ingest rate, assignment time, on-time %, optimiser savings vs nearest-first. **Alarms:** lag > 10 s, broker disk > 70%, assignment > 30 s |

## 11. Alternatives considered
| Option | Decision |
|---|---|
| Kinesis Data Streams | Paid plan only; Kafka is the learning goal |
| Redis GEO for rider positions | Not needed at ~200 riders; parking lot |
| Lambda consumers for Kafka | Not a fit for stateful, continuous processing |
| ECS instead of EKS | Simpler and cheaper, but Kubernetes is the learning goal |

## 12. Risks and open questions
1. **Fulfillment is the heaviest feature** (Kafka, Kubernetes, EC2, Location Service, WebSockets,
   optimisation): split into phases A and B as above.
2. Promised time per order: store ETA + 10 min buffer (proposed).

## Change log
Record every design change here with its reason ([scope control](../../scope-control.md)).

| Date | Change | Why (story / requirement) | Approved |
|---|---|---|---|
| 2026-11-14 | v0.1 first draft; serviceability moved to Store Network | Store Network owns stores and zones | Pending review |
| 2026-11-22 | v0.2: release labels (Later, in phases A and B) and team name (Commerce is now Ordering) updated | [Design review log §14](../../design-review-log.md#14-design-review-fixes-round-3) (L-28) | Applied 2026-11-22, for review |
