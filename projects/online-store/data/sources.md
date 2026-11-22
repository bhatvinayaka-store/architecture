# Data Sources

Record every dataset: where it came from, licence/terms, date, and how to re-create it.
Commit only small samples to `seed/`; large data goes to S3. **No real personal data.**

| Dataset | Source | Licence / terms | Status | How to re-create |
|---|---|---|---|---|
| Products (names, categories, images) | Candidate: Open Food Facts public export | ODbL (attribution + share-alike for the database); check image licences | Not extracted | TBD script |
| Products (fallback) | Synthetic generator (Faker) | Own | Not created | TBD script |
| Dark stores | 10 fictional stores in real Bengaluru South neighbourhoods: Jayanagar, Basavanagudi, Banashankari, JP Nagar, BTM Layout, Koramangala, HSR Layout, Bannerghatta Road, Kumaraswamy Layout, Uttarahalli (IDs BLR-S-01..10); **R1 uses BLR-S-01 only** | Own (made-up coordinates) | Not created | TBD |
| Delivery zones | Hand-drawn GeoJSON polygons (later; R1 uses a radius) | Own; basemap tiles not stored | Not needed for R1 | TBD |
| Inventory sample (batches, expiry, scenarios) | Written in design review | Own | [seed/inventory-sample.md](seed/inventory-sample.md) | Hand-written |
| Customer addresses | Synthetic map pins inside and just outside store radii (to test "not served") | Own | Not created | TBD |
| Users | Synthetic (Faker) | Own | Not created | TBD |
| Policy / FAQ docs for AI assistant | Written by us | Own | Not written | - |
| Road network / travel times | Amazon Location Service (API, not stored) | AWS terms | - | - |
