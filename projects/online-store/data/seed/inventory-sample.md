# Inventory sample dataset and test scenarios

**Source:** design review 2026-11-21 · **Used by:** [Inventory HLD](../../features/inventory/hld.md),
seed scripts, Inventory test cases (each event below is one test scenario).

The walkthrough was done before `maxPerOrder` replaced the fixed "1-5 = few left" rule; the
badges below use the **final rule** ([ADR-0017](../../adr/0017-stock-badge-ownership.md)):
`OUT` if available = 0 · `FEW` if available < maxPerOrder · otherwise `IN`.

**Times** are shown in IST (store time), as printed on packs. Inventory stores them once as UTC
instants: M-A's expiry `2026-11-21T06:00+05:30` is stored as `2026-11-21T00:30:00Z`, so its key is
`2026-11-21T00:30:00Z#M-A`. A pack printed with only a date expires at the end of that day (IST).
See [Inventory HLD §6](../../features/inventory/hld.md#6-data-model).

## Store BLR-S-01, 20 Nov 2026, 10:00 (times in IST)

**Products** (from Catalog; `maxPerOrder` set by the merchandiser, min shelf life in Inventory)
| productId | Product | Typical shelf life | Min shelf life | maxPerOrder |
|---|---|---|---|---|
| P-1001 | Nandini Milk (orange packet) 500 ml | 2-3 days | 12 hours | 3 |
| P-1002 | Nandini Curd 500 g | ~7 days | 24 hours | 2 |
| P-2001 | Brown Bread 400 g | ~4 days | 24 hours | 3 |
| P-3001 | Basmati Rice 5 kg | ~12 months | 30 days | 2 |
| P-4001 | Potato Chips 52 g | ~4 months | 7 days | 5 |
| P-5001 | Dishwash Liquid 500 ml | No expiry | - | 3 |

**`inventory-batches`**
| storeId#productId | expiry#batchId (IST; key stored in UTC) | qty | Stops selling at (sellUntil) |
|---|---|---|---|
| BLR-S-01#P-1001 | 2026-11-21T06:00#M-A | 8 | 20 Nov 18:00 |
| BLR-S-01#P-1001 | 2026-11-22T06:00#M-B | 30 | 21 Nov 18:00 |
| BLR-S-01#P-1002 | 2026-11-24#C-A | 3 | 23 Nov |
| BLR-S-01#P-2001 | 2026-11-22#B-A | 12 | 21 Nov |
| BLR-S-01#P-3001 | 2027-10-01#R-A | 6 | 1 Sep 2027 |
| BLR-S-01#P-4001 | 2027-03-15#K-A | 1 | 8 Mar 2027 |
| BLR-S-01#P-5001 | 9999-12-31#D-A | 20 | never |

`9999-12-31` (D-A) marks goods that never expire: stored as `9999-12-31T23:59:59Z`, no stop-selling
time, never in the expiry index.

**`inventory-stock`** (`onHand` = sum of sellable batches)
| productId | onHand | reserved | available | maxPerOrder | Badge |
|---|---|---|---|---|---|
| P-1001 milk | 38 | 0 | 38 | 3 | IN |
| P-1002 curd | 3 | 0 | 3 | 2 | IN |
| P-2001 bread | 12 | 0 | 12 | 3 | IN |
| P-3001 rice | 6 | 0 | 6 | 2 | IN |
| P-4001 chips | 1 | 0 | 1 | 5 | FEW (1) |
| P-5001 dishwash | 20 | 0 | 20 | 3 | IN |

## One day of events (test scenarios)
| # | Time | Event | Expected result | Event sent? |
|---|---|---|---|---|
| S1 | 10:05 | Customer A orders 2 milk + 1 bread (O-101) | Reserve: milk reserved 0→2, bread 0→1; O-101 `HELD`; batches untouched | No (still IN) |
| S2 | 10:07 | Customers B (O-102) and C (O-103) both buy the last chips | DynamoDB applies them one at a time: O-102 reserves (0→1); O-103's condition `1 - 1 >= 1` fails → 409 `OUT_OF_STOCK` | Yes: chips FEW → OUT |
| S3 | 10:08 | O-101 confirmed → commit (FEFO) | Milk from M-A (8→6), onHand 38→36, reserved 2→0; bread B-A 12→11; O-101 `COMMITTED` | No (commit does not change available) |
| S4 | 11:00 | Customer E orders 2 curd (O-105) | Curd available 3→1 < maxPerOrder 2 | Yes: curd IN → FEW (1); cart now allows at most 1 |
| S5 | 17:58 | Customer D reserves 3 milk (O-104) | Allowed (available 36) | No |
| S6 | 18:00 | Expiry job: M-A reaches its stop-selling time (6 left) | M-A `EXPIRED`, 6 written off; milk onHand 36→30, reserved 3, available 27 | No (still IN) |
| S7 | 18:02 | O-104 confirmed → commit (FEFO) | M-A is expired, so 3 come from M-B (30→27) | No |
| S8 | 18:10 | O-102 (chips) cancelled while `HELD` | Release: reserved 1→0, available 0→1; O-102 `CLOSED` | Yes: chips OUT → FEW (1) |
| S9 | 19:00 | Customer F orders 35 different products, 1-2 each (O-106) | Reserve: one transaction (35 stock updates + 35 movements + 1 reservation = 71 items). Commit: 2 chunks (≈ 20 + 15 lines, each ≤ 100 items). If the Lambda stops after chunk 1, the retry skips the 20 committed lines | Only for badges that change |
| S10 | 19:30 | O-107 (1 bread) reserved and confirmed, but `OrderConfirmed` is stuck (consumer down 20 min) | 19:45 the hold expires; the job asks Ordering → `CONFIRMED` → the job commits O-107 + alarm; the late event finds `COMMITTED` and does nothing. Bread is never sold twice | No |
| S11 | 01:00 (21 Nov) | Test batch M-C: printed expiry 21 Nov 14:00 IST, min shelf life 12 h → stops selling 21 Nov 02:00 IST = **20 Nov 20:30Z** | Indexed under UTC date `2026-11-20`; the 01:00 IST run (19:30Z) writes it off. Keyed by the IST date it would be missed until the next UTC day | Only if the badge changes |
| S12 | 21 Nov, 20:58-21:06 | Test batch B-T: the last 2 bread, stops selling 22:00. 20:58 O-109 reserves both (bread available 2→0). 21:00 the expiry job writes B-T off (inside its 1-h lead) before O-109's `OrderConfirmed` is processed (consumer slow). 21:05 commit: no sellable batch → line `FAILED`, RELEASE (reserved 2→0) → every line failed → O-109 **`CLOSED`** → `StockCommitFailed`. 21:06 Ordering cancels (`CANCELLED(OUT_OF_STOCK)`) → `OrderCancelled` finds `CLOSED` → nothing returned. Bread onHand stays 0 | No (bread already OUT) |
| S13 | 21 Nov, 09:00 | Test delivery r-T13: 10 milk printed 21 Nov 20:00 IST; min shelf life 12 h → stops selling 21 Nov 08:00, already past | 422 `EXPIRES_TOO_SOON {lines: [P-1001]}`, nothing written; the operator fixes the line and sends a new receiptId | No |
| S14 | 21 Nov, 09:30 | Test batch C-T: 4 curd printed 23 Nov (end of day IST). Curd's minimum shelf life raised 24 h → 72 h, so C-T now stops selling 20 Nov 23:59, already past | Same transaction as the setting change: C-T `EXPIRED`, onHand −4, EXPIRE movement; the expiry job is not needed | Yes, if the badge changes |

**Edge case S6b:** if M-A had been the only milk batch, expiry would leave onHand 0 while reserved
is 3. Commit then finds no sellable batch, so that line fails and Inventory publishes
`StockCommitFailed`; Ordering removes the line and lowers the total. Prevention:
the expiry job runs 1 hour before the stop-selling time. **S12** follows the one-line version to the
end: before Inventory HLD v0.4 the reservation ended `COMMITTED` and the cancel "returned" 2 bread
that never left the shelf, so the site would have sold stock that did not exist.

## What this dataset showed
1. **Batches + expiry are needed**: milk had two batches with different stop-selling times.
2. **A fixed "few left = 1-5" rule fails**: rice with 6 bags would flip to "few left" after one
   sale, while milk at 5 warns too late. Replaced by `maxPerOrder` per store + product.
3. **Expiry can collide with reservations**: commit falls back to the next batch, else the line
   fails cleanly; the expiry job runs early.
4. **Reserve → commit works without payments**: the race and the cancellation came out right.
5. **Minimum shelf life varies hugely** (12 h to 30 days): it must be per product, with category defaults.
6. **A failed commit must leave nothing to return** (S12): cancel works per line, and a commit that
   took nothing ends `CLOSED`.
7. **Short-dated stock must never be counted** (S13, S14): refused at receipt, written off at once when
   a shelf-life change makes it unsellable; the expiry job uses a fixed window, so a missed run is
   caught up (round-3 review, 2026-11-22).

## More scenarios to add
- A delivery arrives mid-day (receipt creates batch M-C; badge OUT → IN).
- Damaged-goods adjustment on one batch.
- Load test: 50 customers race for 30 milk packets (exactly 30 succeed, 0 oversell).
