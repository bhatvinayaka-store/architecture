# UX Design Rules (customer side)

**Status:** Draft v0.4 - for review (no store names, delivery estimate, checkout rules 2026-11-22) · **Owner:** shared; each section names its owner team · **Last updated:** 2026-11-22
**Applies to:** every customer screen (shell + team UIs). Staff screens: staff-side design. **Standard:** WCAG 2.2 AA.
**Builds on:** [ADR-0015](adr/0015-micro-frontends-with-central-shell.md) (shell, `ctx`, `common/ui`) · [design review log §12](design-review-log.md#12-design-review-fixes)

## 1. Scope
- Customers on phones first (360-430 px wide), then desktop; English (`en-IN`) only in R1.
- Shared primitives in `common/ui` (Button, Dialog, QuantityStepper, Toast, tokens, messages) carry
  most of the accessibility and look, so every team gets them for free.
- Wireframes are still to do; this document fixes the behaviour that wireframes and code must follow.

## 2. URLs and owners
| URL | Screen | Owner (UI) |
|---|---|---|
| `/` | Home: category menu and highlights | Catalog |
| `/location?next=<path>` | Location picker | Shell |
| `/c/<category>[/<subcategory>]?cursor=` | Category page | Catalog |
| `/p/<productId>` | Product page | Catalog |
| `/cart` | Cart | Ordering |
| `/checkout` | Checkout (signed in) | Ordering |
| `/orders` · `/orders/<orderId>` | Order history · order page | Ordering |
| `/account/addresses` | Saved addresses | Identity |
| `/help` | R1: static help page (FAQ, contact email; §11). R2: Support chat and tickets (signed in) | Shell in R1, Support from R2 |
| anything else | "Page not found" with links to Home and Help | Shell |

- The URL carries the state that matters (category, subcategory, page cursor), so Back, refresh and
  shared links work.
- **Deep links and refresh work on every route:** a CloudFront Function serves the shell for app
  routes ([ADR-0015](adr/0015-micro-frontends-with-central-shell.md)); a route that doesn't exist
  shows the shell's "Page not found".
- **Deep links survive the location step:** opening `/p/P-1001` with no active location goes to
  `/location?next=/p/P-1001` and returns there afterwards.
- **Not available here** (shared link, or the customer moved): a "Not available at your location"
  page with "Browse similar" (its category) and "Change location", never a blank page.
- Every route change calls `ctx.setTitle(...)` ("Milk · ShopLite"): the page title updates and
  focus moves to the page heading, so screen-reader users hear where they are.

## 3. Location picker
**Owner:** shell. Replaces "map pin only", which keyboard and screen-reader users could not finish.
It is step 1 of every order, so it must work for everyone.

1. **Use my current location** (primary button). The browser permission is asked only when
   pressed, with the reason ("to check that we deliver to you"). Denied or unavailable →
   a message, and the other options stay.
2. **Saved addresses** (signed in): one tap each.
3. **Map:** tap to place the pin or drag it. Keyboard: the map is one focusable element
   (`role="application"`, label "Map. Arrow keys move the map under the pin. Enter uses this
   location"), so arrow keys pan the map under a fixed centre pin without fighting screen-reader
   browse keys; "Use this location" confirms. Zoom buttons have labels. Options 1 and 2 always work
   without the map.
4. **Result in words:** "We deliver here · about 10–15 min" (the delivery estimate from
   serviceability), announced in a polite live region. Store names and distances are never shown
   (D17). Not served → "We don't deliver here yet. Try another address". No store open now → §4.

- The map (Leaflet + OpenStreetMap tiles) loads only when the picker opens; OSM attribution shown.
- No address search (geocoding) in R1 ([parking lot](parking-lot.md)).
- The header shows the active location and the estimate ("Delivering to Home · about 10–15 min";
  nothing open: "Delivering to Home · from 7:00 AM") as a button that opens the picker.

## 4. State matrix
Every data view handles these states; wording comes from the copy deck (§6).

| State | Shows | Actions |
|---|---|---|
| Loading | Skeletons the size of the content (no layout shift); "Still loading…" after 5 s; the section's failure state at 10 s (bundle timeout, [ADR-0015](adr/0015-micro-frontends-with-central-shell.md)) | - |
| Empty (empty cart, no orders) | A plain message and the next step | "Start shopping" |
| Error | A human message, no codes | Retry |
| Section failed to load (team bundle) | "This section didn't load." The rest of the page works | Retry |
| Store closed now (`OUTSIDE_HOURS`: no store in range is open now) | Banner "Temporarily closed · Delivery from 7:00 AM" (the catalog of the store that opens soonest, D16) | Browsing and adding to cart allowed; Place order disabled with that reason |
| Store paused, no other store open nearby (`PAUSED`) | Banner "Temporarily closed. Please check back soon." | Browsing allowed; checkout disabled |
| Store changed (the cart's store closed for the day, paused or shut down while another store in range is open now) | Banner "Delivery time updated: about 20–25 min. Some items or prices have changed." | "Review cart"; the cart moved, missing items shown as "Out of stock" (ORD-02) and does not move back when the first store reopens |
| Not served | "We don't deliver here yet" | "Try another address" |
| Out of stock | Shown in place: **only the product image is dimmed**; name, price and the "Out of stock" label keep full text contrast (≥ 4.5:1); the Add button is replaced by the label (never colour alone) | - (notify-me later) |
| Few left | "Only 2 left" | The stepper stops at the cap |
| At the limit | "+" disabled, with the text "Max 3 per order" next to it | - |
| Quantity reduced | Line note "Reduced to 1: only 1 left" | - |
| Price changed | Line note "Price changed ₹26 → ₹28" | Confirm the new total |
| Session expired | "Please sign in again." The cart is kept | Sign in (returns to the same page) |
| Cart unavailable (cart module failed to load) | "Cart unavailable" in the header; every "Add" button disabled with that text; the saved cart is untouched | Retry |

**Decision (2026-11-21; contrast fixed 2026-11-22):** out-of-stock items stay in place (dimmed image +
label) instead of being hidden: the page doesn't jump when stock changes, and customers learn what the
store sells. Greyed text would fail WCAG 1.4.3, so only the image is dimmed (an `out-of-stock` token
in `common/ui`).

## 5. Cart and checkout
**Owner:** Ordering (cart module, cart and checkout pages).
- Fees are visible in the cart (from `GET /api/ordering/fees`): delivery fee, platform fee, total so far.
- The free-delivery hint is information only: "Add ₹45 more for free delivery". No pre-selected
  extras and no pushy upsell.
- Next to Place order: "Cash on delivery · Orders can't be cancelled once placed".
- **Place order:** a new Idempotency-Key per press; the button is disabled and shows "Placing
  order…" while submitting; one automatic retry with the same key after a timeout (15 s, set in
  [ADR-0015](adr/0015-micro-frontends-with-central-shell.md)) or network error; then "We couldn't
  place your order. Your cart is safe. Try again".
- **A 409** shows a banner at the top of checkout with `role="alert"` and focus moved to it. It lists
  what changed (from the 409 body) and offers one action ("Update cart", "Confirm new total
  ₹312", "Change address"). An error never empties the cart.
- **Out-of-stock lines at checkout** (D18): they stay in the list with the label "Out of stock"
  (image dimmed, text keeps 4.5:1) and are left out of the total; "Remove out-of-stock items" clears
  them in one tap; Place order sends only the available lines. If another store serves the address
  now, the preview has already moved the cart and checked the lines there.
- Quantity stepper buttons are labelled "Decrease quantity of Nandini Milk" / "Increase …"; the
  new quantity is announced; targets are 44×44 px.

### 5.1 Delivery address step
The first part of `/checkout` (page owned by Ordering; addresses saved through Identity's API).
- **Choosing:** if a saved address has the active location's pin, it is preselected; otherwise the
  default address, if the same store serves it; otherwise the customer picks from a radio list
  (label, first line, recipient) or adds a new one. Changing the address re-runs the preview; a
  different store shows the `STORE_CHANGED` banner (§6).
- **New address form**, in this order (the pin is the active location, shown with "Change location"
  → `/location?next=/checkout`; no geocoding in R1, so the customer types the text):

| Field | Required | Input |
|---|---|---|
| Flat / house no., building (`line1`) | Yes | `autocomplete="address-line1"` |
| Street (`line2`) | No | `autocomplete="address-line2"` |
| Area / locality (`area`) | Yes | e.g. "Koramangala 5th Block"; shown in address and order lists |
| Landmark ("Near …") | No | - |
| City | - | Shown as text from the serving store's `cityName` ("Bengaluru"), not an input; saved as the store's city code |
| PIN code | Yes | 6 digits; `autocomplete="postal-code"`, `inputmode="numeric"` |
| Recipient name | Yes | Prefilled from the profile; `autocomplete="name"` |
| Recipient phone | Yes | Indian mobile, 10 digits starting 6-9, shown with +91; spaces, dashes and a leading `+91`, `91` or `0` (typed or pasted) are removed before checking, and the 10 digits are stored; `autocomplete="tel-national"`, `inputmode="tel"`; hint "The delivery partner will call this number" |
| Label | Yes | Home / Work / Other (radio, default Home) |
| Make this my default address | No | Checkbox; checked and fixed for the first address |

- **Deliver to someone else** (PRD-07): change the recipient name and phone; nothing else differs.
- **Validation** on blur and on submit, never on every keystroke. Each error sits under its field
  (`aria-describedby`, `aria-invalid="true"`) and says how to fix it ("Enter a 10-digit mobile
  number"). On submit with errors, an error summary at the top lists them as links and gets focus.
  Typed values are always kept.
- **Limits and failures:** at 10 saved addresses, "Add a new address" says "You can save up to 10
  addresses. Remove one to add another." A failed save keeps the form filled: "We couldn't save
  the address. Try again."

## 6. Copy deck
Every error code has one agreed message and action. The list lives in `common/ui/messages`;
each team owns the rows for its codes. Raw codes, IDs and stack traces are never shown.

| Code / event | Message | Action |
|---|---|---|
| `TOTAL_CHANGED` | "Your total changed from ₹298 to ₹312. Nandini Milk: ₹26 → ₹28." | "Confirm new total" |
| `OUT_OF_STOCK` | "Nandini Curd is out of stock." / "Only 1 Nandini Curd left. We've updated your cart." | "Review cart" |
| `ITEM_UNAVAILABLE` | "Brown Bread is out of stock." (same words as `OUT_OF_STOCK`: customers don't see stores) | "Remove out-of-stock items" |
| `STORE_CHANGED` | "Delivery time updated: about 20–25 min. Some items or prices have changed." | "Review cart" |
| `STORE_UNAVAILABLE` (`OUTSIDE_HOURS`) | "We're closed right now. Delivery from 7:00 AM. Your cart is saved." | - (Place order disabled until then) |
| `STORE_UNAVAILABLE` (`PAUSED`) | "Temporarily closed. Please check back soon." | "Try another address" |
| `STORE_UNAVAILABLE` (`NOT_SERVED`) | "We don't deliver to this address right now." | "Change address" |
| `LIMIT_EXCEEDED` | "You can order up to 3 of this item." / "Up to 35 different items per order." | - |
| `BUSY`, `TRY_AGAIN`, `UPSTREAM_UNAVAILABLE` | "Something went wrong on our side. Your cart is safe." | "Try again" |
| 429 (too many requests right now) | "Busy right now. Try again in a moment." | "Try again" (loading data retries once by itself) |
| `RATE_LIMITED` (chat) | "You've reached the message limit. Try again in 20 minutes, or create a ticket." | "Create a ticket" |
| 401 (session expired) | "Please sign in again." | "Sign in" |
| Not served | "We don't deliver here yet." | "Try another address" |
| Location denied | "We couldn't get your location. Choose it on the map or pick a saved address." | - |
| Cart unavailable | "Cart unavailable right now." | "Retry" |
| Sign out with items in the cart | Dialog: "Sign out? The 3 items in your cart on this device will be cleared." | "Sign out" / "Cancel" |

## 7. After placing an order
- The confirmation page (`/orders/<orderId>`) shows the order summary and "Cash on delivery: ₹312".
- **What happens next**, on the order page: "Pay ₹312 in cash when your order arrives. Orders can't
  be cancelled once placed. Something wrong? Need help?" The link opens `/help?order=<orderId>`.
  No live delivery tracking in R1 (until Fulfillment); the delivery estimate is shown before ordering
  (header, checkout), not on the order page.
- For 30 s after placing, the page re-fetches the order every 5 s, so an adjustment from the
  commit (ORD-10) shows up quickly; after that, only on page load.
- An adjusted order has an "Adjusted" label in history and on the order page, with what was removed
  and the new total, plus a one-time banner the next time the customer opens it ("We removed Curd
  (out of stock). New total ₹286").

## 8. Accessibility rules
Built into `common/ui` where possible. Checked by axe in every UI pipeline and by a manual keyboard
and screen-reader pass (VoiceOver on iOS, TalkBack or NVDA) on the main journey each release.
- **Semantics:** one `h1` per page; landmarks (`header`, `nav`, `main`); buttons for actions,
  links for navigation; `lang="en-IN"`.
- **Keyboard:** everything reachable; visible focus (`:focus-visible`, 3:1 contrast); dialogs trap
  focus, close on Esc and return focus; a skip link to the main content.
- **Names:** every icon button has a label; product images use the product name as `alt`;
  decorative images `alt=""`.
- **Colour:** text 4.5:1, controls 3:1; status is never shown by colour alone (badges have text).
- **Live regions:** cart count ("Cart: 3 items"), toasts, the location result and the chat waiting
  state are announced politely; checkout errors use `role="alert"`.
- **Toasts:** info toasts stay 6 s and pause while hovered or focused; error toasts never disappear
  on their own (WCAG 2.2.1); every toast has a close button.
- **Forms** (address): visible labels (no placeholder-only fields), `autocomplete` (`name`, `tel`,
  `postal-code`, `address-line1`), errors next to their field saying how to fix them.
- **Size:** targets at least 24×24 px (44×44 for steppers and main buttons); works at 320 px wide
  and 200% zoom; respects `prefers-reduced-motion`.

## 9. Formatting
- Money: `Intl.NumberFormat('en-IN', {style: 'currency', currency: 'INR'})` from paise (₹1,234.50;
  whole rupees without decimals).
- Time: in the store's timezone `Asia/Kolkata` ("Opens at 7:00 AM", "21 Nov, 6:15 PM"), from UTC instants.
- Pack size: the `unit` text Catalog sends ("500 ml", built from `netQty` + `netUnit`).

## 10. Sign-in page
Cognito managed login (Essentials plan) styled with the branding editor: logo, colours from the
design tokens, light and dark mode. At checkout the shell explains why ("Sign in to place your
order. Your cart is saved."); after sign-in the customer lands on the same page with the cart intact.

**Sign-out** clears the cart on this device ([Identity HLD 8.4](features/identity/hld.md#8-key-flows)):
the R1 cart is not tied to an account, so the next person on a shared device would see it. With
items in the cart, a dialog confirms first (§6); with an empty cart, sign-out happens at once.

## 11. Help and Support chat
**R1: static help page** (`/help`, owner: shell). Customers need a way to get help from day one,
and orders can't be cancelled.
- FAQ: delivery area, cash on delivery, no cancellation, adjusted orders, out of stock, account and
  addresses. Written as Markdown in `common/web-shell/help/`; in R2 it moves to Support's
  `support-kb/` and becomes the first Knowledge Base documents.
- Contact: **a placeholder in R1**: `help@shoplite.example` is fictional and cannot receive mail (fine
  while customers are simulated); a real mailbox replaces it before any real users. "Include your
  order number".
- "Need help?" in the footer and on every order page; from an order, `/help?order=<orderId>` shows
  that order number ready to copy.
- No chat, no tickets and no personal data on this page in R1.

**R2: chat and tickets** (owner: Support).
- Says it is an AI assistant at the start; "Talk to a person" is always visible (creates a ticket).
- While waiting: "Assistant is typing…" (polite live region), Send disabled; the typed text is kept
  if sending fails.
- Answers are plain text with allowed formatting only; sources are links to our help pages.
- When `remainingThisHour` ≤ 5: "5 messages left this hour".
- Timeout (no answer within 22 s, set in [ADR-0015](adr/0015-micro-frontends-with-central-shell.md)): "Sorry, that took too long. Try again or create a ticket."

## 12. Open items
| Item | When |
|---|---|
| Wireframes for the screens in §2 | UI design pass |
| Search UI | With Catalog search |
| Staff screens (admin, store manager, agent console) and where they are hosted | Staff-side design |
| "Notify me when back in stock" | Later |
| R1 help page content (FAQ text; a real contact mailbox before any real users) | Before R1 |

## Change log
| Date | Change | Why | Approved |
|---|---|---|---|
| 2026-11-21 | v0.1 first version | UI/UX and front-end review findings ([log §12](design-review-log.md#12-design-review-fixes)) | For review |
| 2026-11-21 | v0.2 (round-2 fixes): R1 static help page and "what happens next" on the order page; checkout address step (fields, order, validation, saved address, someone else); `STORE_UNAVAILABLE` copy for `OUTSIDE_HOURS` / `PAUSED` / `CLOSED`; client timeouts; deep links; cart-unavailable state; sign-out clears the device cart with a confirmation | [Design review log §13](design-review-log.md#13-design-review-fixes-round-2) (UX-8, UX-9, UX-11, BE-12, FE-8, FE-10, FE-14) | For review |
| 2026-11-22 | v0.3 (round-3 fixes): store changes follow the one-store-per-order choice rule (backup store shown in words, `STORE_CHANGED` names the new store, `NOT_SERVED` replaces `CLOSED`); out-of-stock dims only the image (text keeps 4.5:1); address form matches Identity (`line1`, `line2`, `area`, city from the store); phone normalisation; toast timing; "Still loading…" at 5 s; map keyboard mode labelled; 429 copy; help mailbox marked as a placeholder | [Design review log §14](design-review-log.md#14-design-review-fixes-round-3) (D11, M-2, M-12, M-21, L-23, L-24, L-25, L-26) | For review |
| 2026-11-22 | v0.4: no store names or distances anywhere; delivery estimate in the location result and header; nothing open → the store that opens soonest ("Temporarily closed · Delivery from 7:00 AM"); one "Out of stock" message for no stock and not sold; out-of-stock lines left out at checkout so the rest can be ordered | [Design review log §16](design-review-log.md#16-catalog-lld-walkthrough-and-customer-store-decisions) (D16-D18) | For review |
