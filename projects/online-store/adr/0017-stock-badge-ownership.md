# ADR-0017: Stock badge: Catalog owns the limit, Inventory decides the status (CQRS)

**Status:** Accepted (revised 2026-11-21) · **Date:** 2026-11-21

## Context
Customers must see "In stock / Only N left / Out of stock" while browsing and searching, and the
cart must stop them adding more than they can buy, **without** calling Inventory before checkout.
Inventory alone knows exact stock and is the only writer (ADR-0008). Browsing is very read-heavy.

## Decision
- **`maxPerOrder`** is set per store + product by the merchandiser in **Catalog** (listing row),
  and is fixed (not recalculated from stock). It is both the purchase limit and the trigger for
  "few left".
- Catalog sends `maxPerOrder` to Inventory in `AssortmentChanged` / `ListingUpdated`; Inventory
  keeps a **copy** on its stock row.
- Inventory computes the status from **available = onHand − reserved** (reservation-aware):
  `OUT` if 0 · `FEW` if available < maxPerOrder · otherwise `IN`.
- Inventory's stream publisher sends **`StockLevelChanged` only when the status changes**, or when
  the count changes while `FEW` (then it includes `availableQty`). Every other stock change sends nothing.
- Catalog stores `stockStatus` (+ `availableQty` when few left) on the listing row and returns it
  in browse, search and product responses. The cart allows at most
  `min(maxPerOrder, availableQty)` when few are left, `maxPerOrder` otherwise, 0 when out. The rule
  is applied in one place, Ordering's cart module ([ADR-0015](0015-micro-frontends-with-central-shell.md)); Catalog's responses carry
  `maxPerOrder` and `stock` for it.
- Checkout's reservation remains the final answer; the badge is a strong hint.
- **No read replicas**: DynamoDB keeps three copies per item and spreads reads; customer reads go
  to Catalog's copy behind CloudFront, not to Inventory.

## Consequences
Few events (a handful per product per day instead of one per checkout), no surprise limits at the
cart, and Inventory stays the only owner of stock logic. The badge can be up to ~60 s stale
(event + CloudFront); a race for the last units is resolved cleanly at checkout.
