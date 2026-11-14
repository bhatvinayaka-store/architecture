# ADR-0008: Split Procurement from Inventory; Inventory is the only writer of stock

**Status:** Accepted · **Date:** 2026-11-14

## Context
Restocking (suppliers, purchase orders, receipts) is a slow, low-volume workflow; stock reservation is a fast, high-contention hot path. Different users, speeds and reasons to change.

## Decision
Create a Supply & Procurement team. Procurement never changes stock counts; it publishes `GoodsReceived` / `StockTransferred` and Inventory applies them idempotently.

## Consequences
One source of truth for stock; Inventory stays simple and fast. Restocking becomes eventually consistent (seconds), which is acceptable.
