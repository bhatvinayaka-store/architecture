# Inventory ADR-0001: Stock tracked by batch with expiry, sold first-expired-first-out

**Status:** Accepted (revised 2026-11-22) · **Date:** 2026-11-21

## Context
Groceries expire: two batches of the same milk can expire a day apart. A single stock count cannot
say how much stock is still sellable tomorrow, or which packet to pick. Adding batches later would
mean migrating the core stock data. A [sample dataset walkthrough](../../../data/seed/inventory-sample.md)
confirmed the need.

## Decision
- Stock is held as **batches** (`inventory-batches`: qty, expiry date, received at), plus a
  summary row per (store, product) in `inventory-stock` (`onHand`, `reserved`).
- `onHand` counts only batches that are still sellable. A batch stops being sellable at
  **expiry − minimum shelf life** (per product, category defaults: milk 12 h, curd/bread 24 h,
  chips 7 days, rice 30 days; non-perishables have none).
- **Reservations touch only the summary row** (keeps the hot path to one row per product).
- **Commit takes stock from the earliest-expiring batch first (FEFO)**, with a condition on the
  batch quantity; on conflict it re-reads and retries.
- An **hourly expiry job** writes off batches 1 hour before their stop-selling time (reason `EXPIRED`),
  querying a fixed window of dates so a missed run is caught up.
- Stock past its stop-selling time never counts: a delivery with such a line is refused, a raised
  minimum shelf life writes off affected batches in the same transaction, and commit skips any batch
  past its stop-selling time even if the job has not run yet.
- If expiry leaves a reserved item without stock, commit uses the next good batch; if none is
  left, that line fails and `StockCommitFailed` is published so Ordering corrects the order.

## Consequences
Correct sellable counts and less waste. Commit becomes a read-then-conditional-write (retry on
conflict). Changing a product's minimum shelf life requires recomputing the stop-selling time of
its open batches, and writing off those already past it.

**Revised 2026-11-22** ([design review log §14](../../../design-review-log.md#14-design-review-fixes-round-3), H-3): short-dated deliveries refused; shelf-life changes write off at once; fixed-window expiry job; commit checks `sellUntil`.
