# ADR-0015: Micro-frontends loaded into a central shell

**Status:** Accepted (revised 2026-11-22) · **Date:** 2026-11-20

## Context
Teams own features end to end, including UI. Each team must be able to build, test and deploy its
screens without access to other teams' UI code, while customers see one website. The design review
of 2026-11-21 found gaps: nobody owned the cart across UIs, one broken bundle could break the whole
page, deploys could mix old and new files, and a change of delivery location was not handled.

## Decision
**Shell** (in the `common` repo, [ADR-0014](0014-common-repo-for-shared-infrastructure.md)): owns
layout, navigation, sign-in/sign-out, the active delivery location, error boundaries and one
placeholder per team. It reads `config.json` (per stage) and loads the right team's UI for each
customer route (`/`, `/c/*`, `/p/*` → Catalog; `/cart`, `/checkout`, `/orders/*` → Ordering;
`/account/*` → Identity; `/help` → the shell in R1 (static page), Support from R2; full list in [UX design §2](../ux-design.md#2-urls-and-owners)).
Where staff screens live is decided in the staff-side design.

**Hosting** (chosen 2026-11-21): each team builds **one ES-module bundle** in its own repo and
pipeline and uploads it to **its own S3 bucket**. The one web CloudFront distribution serves it at
`/mfe/<team>/*` through origin access control. Bundles come from the same origin as the shell, so
the Content-Security-Policy stays `script-src 'self'` and no CORS is needed. `common` adds one
origin and behaviour per team, once.

**Content-Security-Policy** (sent by the `common` edge stack): `default-src 'self'; script-src
'self'; style-src 'self'; img-src 'self' <Catalog images URL from SSM /shop/<stage>/catalog/images-url>
https://tile.openstreetmap.org data:; connect-src 'self'; font-src 'self'; form-action 'self'
<Cognito managed-login domain>; frame-ancestors 'none'; base-uri 'none'; object-src 'none'`. Sign-in
and sign-out leave through same-origin `/api/auth/*`, which redirect to Cognito (hence its domain in
`form-action`). A new external origin needs a PR that changes this list.

**Deep links** (opening `/p/P-1001` directly, or refreshing any page): a **CloudFront Function**
(viewer request) on the shell's default behaviour rewrites any path without a file extension to
`/index.html`; the shell's router then renders the page, or its own "Page not found". `/api/*` and
`/mfe/*` are separate behaviours and are never rewritten, so an API 404 stays a JSON 404. Custom
error responses are **not** used: they apply to the whole distribution and would turn API 403/404
into the shell page. Unknown routes return HTTP 200 with the "Page not found" screen (acceptable: no
SEO requirement in R1). CloudFront Functions are allowed in the new AWS experience (checked
2026-11-22: the project's SCP allows CloudFront in us-east-1, and only Lambda@Edge is excluded).
Fallback if that ever changes: hash routing (`/#/p/P-1001`); team UIs are unaffected because they
only navigate through `ctx.navigate` and `Link`.

**Contract** (`contractVersion: 1`; additive changes only; a breaking change needs version 2 and a
period in which the shell supports both):
```
mount(element, ctx) -> unmount()
ctx = {
  contractVersion: 1,
  storeId, city, cityName,          // from the active location (serviceability answer)
  apiBase: "/api/<team>",           // same origin; the BFF adds tokens (ADR-0018)
  auth:  { user: {signedIn, userId, name} | null, signIn(returnTo) },
  cart:  Ordering's cart module (below),
  api:   fetch wrapper: correlation ID, JSON, AbortSignal, 409 STORE_* -> location re-check,
         429 -> "Busy right now" (one retry for GET after 1 s),
         x-amz-content-sha256 (SHA-256 of the body) on POST/PUT, required by OAC (ADR-0018),
         timeout per call: 8 s by default, 15 s for checkout, 22 s for chat messages
         (each just above the BFF's own limit of 5 / 12 / 20 s, so the BFF's 504 arrives first),
  route: { path, params, query },   // the current route, parsed by the shell
  onRouteChange(listener) -> unsubscribe,
  navigate(path, {replace?}),       // the only way to change the URL; the shell owns history
  notify(message, {kind: "info" | "error"}),   // shell toast in a live region
  setTitle(title),                  // document title + focus moved to the page heading
  reportError(error, {where})       // to the shell's error reporting (below)
}
```
Team UIs **never handle tokens**: they call same-origin `/api/<team>/...` paths and the browser
sends the session cookie to the BFF ([ADR-0018](0018-customer-sign-in-with-managed-login-and-bff.md)).

**Navigation:** only the shell owns the router and `window.history`. Team UIs change the URL with
`ctx.navigate` or the `Link` component from `common/ui`, which renders a real `<a href>` (open in a
new tab, copy link and screen readers work) and calls `navigate` on a plain click. A link to another
team's page uses its URL from [UX design §2](../ux-design.md#2-urls-and-owners), never that team's
code; the shell unmounts the current team UI and mounts the other. Within its own pages a team reads
`ctx.route` and listens to `onRouteChange` instead of running a second router.

**Cart module** (owned by Ordering, built and versioned in Ordering's repo, loaded by the shell):
the only code that reads or writes the cart (`localStorage` key `shop.cart.v1`). API: `get()`,
`lines()`, `setQty(productId, qty, {maxPerOrder, stock})`, `clear()` (after an order is placed, and
on sign-out), `subscribe(listener)` (also fires when another tab changes the cart, through the
`storage` event, so every tab shows the same cart and badge). `setQty` applies
the cap rule from [ADR-0017](0017-stock-badge-ownership.md) and the 35-line limit, so Catalog's
"Add" button, the header badge and Ordering's cart page always agree.
- **Own entry and version:** it has its own manifest (`/mfe/ordering/cart/manifest.json`, listed
  in `config.json`), so Ordering can release it separately from the cart page. The shell loads it
  **in parallel** with the route's team bundle and mounts the team UI when both are ready (or with
  the stand-in below if the cart module fails), so it adds no round trip before the first render. It exposes `version` (semver). API changes are additive; a new storage format
  gets a new key (`shop.cart.v2`) plus a one-time migration from `v1`.
- **If it fails to load** (10 s timeout or error): the shell passes a stand-in with
  `unavailable: true`, an empty `lines()` and a `setQty` that rejects. Catalog shows "Cart
  unavailable. Retry" and disables "Add"; the header hides the count. The saved cart in
  `localStorage` is untouched, so nothing is lost.
- **Consumer contract test:** Catalog and the shell test against each published cart module version
  (types + a small behaviour suite from Ordering's repo); a breaking change fails their pipelines
  before it reaches customers.

**Failure isolation:** the shell loads each bundle with `import()` and a 10 s timeout and wraps
`mount` in an error boundary. On failure it shows "This section didn't load. Retry" in that team's
placeholder, keeps the header, cart badge and other sections working, and reports the error
(`ui.mount.failed` with team and version).

**Error reporting (R1):** the shell catches uncaught errors and unhandled promise rejections, plus
everything sent to `ctx.reportError`, and sends them to `POST /api/telemetry/errors` (BFF, [Identity
HLD](../features/identity/hld.md#5-architecture)), which writes one structured log line; a metric
filter counts them per team and alarms on a spike. Payload: team, bundle version, route path (no
query string), message, stack (first 2 KB), correlation ID. Never personal data, form values or
tokens. At most 10 reports per page view, body ≤ 8 KB. CloudWatch RUM is in the
[parking lot](../parking-lot.md).

**Caching and deploys:** each team publishes `/mfe/<team>/manifest.json` (`Cache-Control:
no-cache`) pointing to content-hashed files (`Cache-Control: public, max-age=31536000, immutable`).
The shell reads the manifest, then imports the entry file. A deploy uploads the new hashed files
first and the manifest last; old files are kept 7 days (S3 lifecycle) so open tabs keep working.
Rollback = put back the previous manifest.

**Shared runtime (R1): none. Each team bundles its own React and React DOM** (about 45 KB gzip per
team, downloaded once and cached by hash). A shared copy through an import map was dropped: an import
map must be written inline in `index.html`, which a strict CSP allows only through a hash that changes
with every config change, and React publishes no official ES-module build to map to. So `ctx` holds
only plain objects and functions, never React elements or context; `common/ui` declares React as a
peer dependency, so each team's bundle uses its own copy; teams may upgrade React on their own
schedule. Heavy widgets (the map) are lazy-loaded. A shared runtime is in the
[parking lot](../parking-lot.md) for when bundle size matters.

**Styles stay inside their section:** team styles use CSS Modules (class names scoped at build time);
no global selectors (`body`, `h1`, `*`) and no CSS reset in team bundles: the shell owns the reset
and the design tokens (CSS custom properties on `:root`). CSS is built into hashed `.css` files
listed in the manifest, added by the shell as `<link>` on mount and removed on unmount (no injected
`<style>` tags, which `style-src 'self'` blocks). `z-index` values come from the token scale; the
shell owns the top layers (header, dialogs, toasts). A stylelint rule in each UI pipeline rejects
global selectors. Shadow DOM was rejected: it breaks `common/ui` dialogs and portals, and
inherited fonts and tokens.

**Location changes:** when the active store changes, the shell unmounts and remounts the team UI
with the new `ctx`. Team UIs key cached data by `storeId` and abort in-flight requests on unmount
(`AbortController`). The shell re-checks serviceability when the result is older than 15 min, when
the tab regains focus, and on any 409 `STORE_*`, sending its active store as `keepStoreId`, so the
store changes only when it stops serving ([Store Network HLD §5](../features/store-network/hld.md#5-architecture));
tabs stay in step through the `storage` event; sign-out clears `addressId`.

**Shared look and accessibility:** `common/ui` (design tokens; accessible primitives such as
Button, Dialog, QuantityStepper, Toast; the error-message list) is used by every team, version
pinned. Rules in [UX design](../ux-design.md).

**Standalone mode:** each team UI runs alone (`npm run dev` with a small fake shell providing `ctx`).

**Tests:** each team runs a contract test (mount → render → unmount with a fake `ctx`, nothing left
behind: no listeners, timers, styles or history entries); Catalog and the shell run the cart module
consumer test; `common` runs one Playwright journey across all bundles (deep link → browse → cart →
checkout, then refresh on the order page) with axe accessibility checks.

## Consequences
Independent UI releases and clear ownership; one broken team UI no longer breaks the page; the cart
has one owner. Costs: a shared contract and a cart module to version; `common` changes once per new
team (origin + behaviour); each team ships its own React (a larger first download, no coordinated
upgrades); a consistent look depends on teams using `common/ui` and keeping their styles scoped.

## Revisions
| Date | Change |
|---|---|
| 2026-11-21 | With the BFF, team UIs get `apiBase` + `auth` instead of API URLs and tokens |
| 2026-11-21 | Design review fixes ([log §12](../design-review-log.md#12-design-review-fixes)): bundles served at `/mfe/<team>/*` by the web distribution (was: each team's own CloudFront URL; removes CORS); `ctx` gains `contractVersion`, `cart`, `api`, `notify`, `setTitle`; Ordering's cart module; error boundaries; manifest + hashed files; React import map; location-change rules; `common/ui`; contract and journey tests; staff screens decided in the staff-side design (`/admin/stores/*` route dropped) |
| 2026-11-21 | Round-2 fixes ([log §13](../design-review-log.md#13-design-review-fixes-round-2), FE-7 to FE-11, FE-13, FE-14, BE-8, decision D7): `ctx` gains `route`, `onRouteChange`, `navigate`, `reportError`; `Link` in `common/ui`; `ctx.api` adds the OAC body hash and per-route timeouts; cart module with its own manifest, version, fallback and consumer test; error reporting to the BFF; **no shared React in R1** (import map dropped); scoped CSS rules; deep links through a CloudFront Function (fallback: hash routing) |
| 2026-11-22 | Round-3 fixes ([log §14](../design-review-log.md#14-design-review-fixes-round-3), M-1, M-12, M-22, L-21, L-22, L-26): `ctx.city` and `ctx.cityName` come from the serviceability answer; `ctx.api` handles 429; the cart module loads in parallel with the team bundle; full Content-Security-Policy written down; the cart syncs across tabs; `/help` belongs to the shell in R1 |
| 2026-11-22 | AWS checks ([log §15](../design-review-log.md#15-aws-checks)): CloudFront Functions confirmed for deep links |
