# Glossary

| Term | Meaning |
|---|---|
| Dark store | Small warehouse that only serves online orders |
| SKU | Stock-keeping unit: one sellable product variant |
| Reservation | Stock held for an order for a limited time until payment completes |
| Reorder point | Stock level that triggers a purchase order |
| Purchase order (PO) | Order placed with a supplier to restock |
| Saga | Multi-step process where each step has an "undo" (compensation) |
| Idempotency key | Client-supplied ID that makes a retried request return the same result |
| Outbox pattern | Publishing an event reliably together with a database write |
| DLQ | Dead-letter queue: where messages go after repeated failures |
| Golden signals | Latency, traffic, errors, saturation |
| SLO / error budget | Reliability target and the amount of failure allowed against it |
| WISMO | "Where is my order?" support contacts |
| Paved road / golden path | The supported, ready-made way to build a service |
| Micro-frontend | Part of a web UI built and deployed independently by one team |
| Canary deploy | Sending a small share of traffic to a new version before all traffic |
| Assortment | The subset of the city catalog that one store lists |
| Serviceability | Whether (and by which store) an address can be delivered to |
| Delivery zone | Polygon on the map that a store delivers to |
| Goods receipt (GRN) | Record of what actually arrived from a supplier |
| On order | Quantity already ordered from suppliers but not yet received |
| PostGIS | Postgres extension for geographic data and queries |
