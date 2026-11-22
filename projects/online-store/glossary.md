# Glossary

| Term | Meaning |
|---|---|
| Dark store | Small warehouse that only serves online orders |
| SKU | Stock-keeping unit: one sellable product variant |
| Reservation | Stock held for an order at checkout; committed when the order is confirmed or released when cancelled/abandoned |
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
| Delivery zone | Polygon on the map that a store delivers to (later; R1 uses a radius) |
| Goods receipt (GRN) | Record of what actually arrived from a supplier |
| On order | Quantity already ordered from suppliers but not yet received |
| PostGIS | Postgres extension for geographic data and queries |
| Listing | One row saying a store sells a product, with sort rank, `maxPerOrder` and stock badge |
| `maxPerOrder` | Most units of a product one order may contain in a store; also the "only N left" trigger |
| Stock badge | In stock / Only N left / Out of stock, shown while browsing |
| Available stock | On hand minus reserved |
| Batch | Units of one product received together, sharing an expiry date |
| FEFO | First expired, first out: sell the batch that expires soonest first |
| Minimum shelf life | Time before expiry when a batch stops being sold (e.g. milk 12 h) |
| Geohash | A short string naming a square cell on the map; nearby points share a prefix |
| Haversine | Formula for the straight-line distance between two lat/lng points |
| CQRS | Separate models for writing and reading (Inventory writes stock; Catalog serves a read copy) |
| Sparse index | A DynamoDB index that only contains items that have its key attributes |
| Soft delete | Marking a record inactive instead of removing it |
| `SETUP` (store status) | A store being prepared; invisible to customers until opened |
| Par level | Target stock level for a product (replaced here by `maxPerOrder` for badges) |
| Web shell | The central web app that loads each team's micro-frontend |
| Managed login | Sign-up and sign-in pages hosted by Cognito; the app redirects there and back |
| PKCE | A one-time secret that makes a stolen authorization code useless |
| BFF (Backend for Frontend) | A small server in front of the APIs; here it keeps the session and tokens so the browser never sees them |
| Session cookie | `HttpOnly`, `Secure`, `SameSite` cookie holding only a random session ID |
| XSS | An attacker's script running inside our page |
| CSRF | Another site making the user's browser send a request that carries our cookies |
| CSP (Content-Security-Policy) | A header listing which scripts the browser may run on our pages |
| IDOR | Reading someone else's data by changing an ID in a request |
| WAF | Web Application Firewall: rules that block abusive requests before they reach the API |
| MRP | Maximum Retail Price printed on packaged goods; selling price may not exceed it |
| Platform fee | A small fixed fee per order |
| Checkout preview | A live check of the cart on the checkout page; reserves nothing |
| RAG | Retrieval-augmented generation: find relevant documents, then answer from them |
| Knowledge Base | Bedrock's managed document store and search used for RAG |
| Guardrails | Bedrock filters for prompt attacks, denied topics and sensitive data |
| Tool use | The model asks our code to run a named function (e.g. look up my orders) |
| WCAG 2.2 AA | Web Content Accessibility Guidelines 2.2, level AA: the accessibility standard every screen meets |
| Live region | Part of a page whose changes screen readers announce (e.g. "Cart: 3 items") |
| Import map | A browser feature that tells ES modules where to load shared libraries (e.g. React) from (not used in R1: each team bundles React) |
| Copy deck | The agreed list of user-facing messages; here one message and action per error code |
| Chunked commit | Inventory commits a big order in several transactions of ≤ 100 items; line status makes retries safe |
| Timeout budget | The total time a request may take, split across the calls it makes; outer limits are longer than inner ones |
| Cart module | Ordering's small browser library that owns the cart; the shell passes it to every team UI |
| CloudFront Function | A tiny script run by CloudFront on each request; here it sends app routes (deep links) to the shell's `index.html` |
| OAC (origin access control) | CloudFront signs its requests so an S3 bucket or Lambda function URL accepts only CloudFront |
| Deep link | A URL that opens a specific page directly (e.g. a shared product link), not only the home page |
| Reserved concurrency | The most copies of a Lambda function that may run at once; used to cap the BFF |
| Iterator age | How far behind a stream consumer is; a rising value means events are waiting |
| Reconciliation job | A periodic job that compares or re-sends current state to repair a copy that missed an event |
| Reservation `CLOSED` | Final reservation status: the order was cancelled, or its commit took nothing; later events are ignored |
| Inference profile (Bedrock) | A Bedrock model ID that sends each request to one of a set of Regions; `au.` profiles stay within Australia (Sydney, Melbourne) |
| SCP (service control policy) | An account-wide guardrail policy; in this project AWS manages it and, for example, limits most actions to the selected Region |

