# Sites Analytics — real view tracking, merged into Overview

Date: 2026-08-29
Status: approved (brainstorming), ready for implementation plan
Supersedes: the mock `Analytics` tab introduced in `2026-08-28-sites-redesign-design.md`

## Problem

The Site Publisher's `Analytics` tab renders entirely fabricated numbers — a hardcoded
sparkline, invented totals, and a `topPages` table listing files that may not exist in the
site. It is labelled `PREVIEW`, but a tab that only ever shows fiction is worse than no tab:
it occupies prime navigation space and teaches users to distrust the numbers.

Separately, the `Overview` tab carries a fake `Views · 7d` stat card alongside three real
ones, mixing truth and fiction inside a single row.

## Goals

1. Record real pageviews for published sites, privacy-first (no cookies, no stored PII).
2. Surface those numbers inside `Overview`. Delete the separate `Analytics` tab.
3. Never let analytics failures degrade site serving or the Overview tab.

## Non-goals

- Referrer, geography, device, or time-on-page metrics.
- Retention/pruning of view rows (accepted risk, see Decisions).
- Real-time updates. The card fetches on mount and on range change.
- Any charting library dependency.

## Decisions

Recorded here because several were live options during design.

| Decision | Choice | Rationale |
|---|---|---|
| Build depth | Real tracking, not a mock merge | The tab stops lying |
| Visitor identity | Daily-salted HMAC of IP + UA | No cookies, no stored PII, unlinkable across days |
| What counts as a view | HTML documents only | "Views" means pageviews, not server hits |
| Storage shape | Raw rows, retention off by default | User's explicit call; `SITES_ANALYTICS_RETENTION_DAYS` is the opt-in lever |
| Owner's own visits | Recorded, shown separately | Honest headline, no lost data |
| Overview layout | Chart-led hero (option B) | One insight card, no duplicated stat tiles |
| Analytics read access | Site owner or app admin | Mirrors existing `_get_owned_site` |

### Growth: an adversarially reachable write path

This is not merely organic growth. Recording is an **unauthenticated, unmetered INSERT**:
the write is reachable by anyone who can load a public site URL, there is no rate limit,
and the bot filter is a User-Agent substring match that is bypassed by sending a normal
browser User-Agent. A single caller in a loop can add rows as fast as the app will serve
pages. The `(site_id, created_at)` composite index keeps read performance flat regardless
of table size, so the cost lands on storage rather than latency — but nothing in the
feature bounds it.

`SITES_ANALYTICS_RETENTION_DAYS` is the lever:

- **Unset, `0`, negative, or unparseable → keep every row forever.** This is the default
  and is exactly the behaviour before the setting existed; a misconfigured value can never
  silently start deleting data.
- A **positive integer** deletes `site_view` rows older than that many days.
- Declared in `backend/open_webui/env.py` with the repo's existing int-with-fallback idiom
  (cf. `REDIS_SENTINEL_MAX_RETRY_COUNT`, `UVICORN_WORKERS`).
- Implemented as `SiteViews.prune_older_than(days, now_ms=None, db=None) -> int`, returning
  the number of rows deleted.
- Wired as a daily loop in `main.py`'s `lifespan`, alongside the existing
  `periodic_usage_events_cleanup` and following the same shape: the task is created only
  when retention is on, its body is wrapped in `try/except` with `log.exception`, and a
  failure neither breaks startup nor stops the loop.

Retention is a size bound on a hostile write path, not a reporting window, so its cutoff is
a plain millisecond timestamp and deliberately does not align with the analytics day
buckets. It does not defend against a burst — only against unbounded accumulation.

### Deliberate omission: `user_id`

The table stores `is_owner` but **not** the viewer's user id. `is_owner` is the only
identity signal the feature needs, and storing viewer ids would make `site_view` a
per-employee browsing log of internal pages — a materially different privacy artifact
from an aggregate view counter.

**This protects public sites, not small-audience private ones.** For a private site shared
with one or two named grantees, the owner already knows the audience by name from the
access-grant list. The owner-visible `top_pages` is then that person's reading history, and
`unique_visitors: 1` confirms which of them it was. Omitting `user_id` changes nothing
about what the owner learns in that case — the identification comes from the grant list
plus the visitor count, not from the table.

So the honest scope of the omission: it prevents the *database* from becoming a
cross-site, cross-user browsing log, and it prevents anyone with database access from
reconstructing one. It does not give a grantee of a narrowly-shared private site any
meaningful anonymity from that site's owner. Anyone relying on this trade-off for a
small-audience private site should be told that their reading is visible to the owner,
rather than assuming the omission delivers a privacy property it does not.

## Data model

New table, migration `b1c2d3e4f5a6`, `down_revision = 'e4f5a6b7c8d9'` (the current single
head, `e4f5a6b7c8d9_site_publisher`).

```
site_view
  id           Text        PK, uuid4
  site_id      Text        NOT NULL
  path         Text        NOT NULL   served filename, e.g. "index.html"
  visitor_key  Text        NOT NULL   32 hex chars
  is_owner     Boolean     NOT NULL   default False
  created_at   BigInteger  NOT NULL   epoch ms, matching sites.py::_now()

  index ix_site_view_site_created on (site_id, created_at)
```

`created_at` is milliseconds, consistent with `Site.created_at` / `Site.updated_at`.

### visitor_key derivation

```
msg  = f"{utc_date_iso}|{site_id}|{client_ip}|{user_agent}"
key  = hmac.new(WEBUI_SECRET_KEY.encode(), msg.encode(), sha256).digest()[:16].hex()
```

Three properties, each load-bearing:

- **`utc_date_iso` in the message** rotates the salt daily. Two visits by the same person
  on different days produce unrelated keys, so the table cannot reconstruct a visit history.
- **`site_id` in the message** scopes the key per site. The same visitor across two sites
  produces unrelated keys, preventing cross-site correlation.
- **`WEBUI_SECRET_KEY` as the HMAC key** means an attacker holding the database still
  cannot brute-force the (small) IP+UA space back to a raw IP.

Client IP comes from `request.client.host` — never from a forwarded header read directly in
application code.

That is not the same as "the real client address". `backend/start.sh`, `backend/dev.sh` and
`start_windows.bat` all launch uvicorn with `--forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-*}"`,
and `*` trusts **every** peer. Uvicorn's proxy-headers middleware then rewrites
`scope["client"]` from whatever `X-Forwarded-For` the caller sent, so on a default
deployment anything that can reach the app can choose its own apparent IP.

**Deployment note:** set `FORWARDED_ALLOW_IPS` to the reverse proxy's address in
production. With the default `*`, `client.host` is caller-controlled.

### DAO

`SiteViewsTable` is added to the existing `backend/open_webui/models/sites.py`, next to
`SitesTable`. It exposes:

- `record_view(site_id, path, visitor_key, is_owner, db=None)`
- `get_analytics(site_id, days, db=None)` — returns totals, daily series, top pages
- `prune_older_than(days, now_ms=None, db=None) -> int` — retention; `days <= 0` is a no-op
  returning `0`

No new module: the file stays small and the two tables are one cohesive concern.

Day bucketing groups on `SiteView.created_at.op('/')(day_ms)` — the literal SQL `/`
operator between two integer operands — rather than a SQL date function, so the same query
runs on both SQLite and Postgres. This is deliberately not Python's `/` on the column:
SQLAlchemy compiles that to true division (`CAST(... AS NUMERIC)` on Postgres), which gives
every row its own fractional key, so `GROUP BY` fails to merge two views recorded on the
same day at different times. Casting that true-division result to `Integer` is not a valid
alternative either — Postgres rounds numeric-to-integer casts rather than truncating.
`.op('/')` truncates (floors) directly in SQL. Buckets are converted back to ISO dates in
Python.

The analytics window is bounded at **both** ends: `created_at >= window_start` and
`created_at < (today_idx + 1) * day_ms`. The upper bound is not redundant. A row stamped in
the future — a server clock rolled back, or a bad import — would otherwise be counted in
`totals['views']` while its day index fell past the last `series` bucket, so it would
appear in no day at all and `sum(series) != totals['views']` **within a single response**.
The bound is the end of today rather than `now`, so a view recorded later today still
counts.

`SitesTable.delete_site_by_id` is extended to delete the site's `site_view` rows inside its
existing single transaction, alongside the access-grant cleanup it already does. With
retention off by default, orphaned view rows would otherwise persist forever.

## Recording path

Hooked into `serve_site_entry` and `serve_site_file` in
`backend/open_webui/routers/sites.py`, after access resolution succeeds.

Rules, in evaluation order:

1. **Access first.** `_resolve_site_for_view` resolves the site and the viewer together,
   returning `(site, viewer)` rather than discarding the viewer it already resolved. When it
   returns `(RedirectResponse, None)` (anonymous visitor bounced to `/auth`), nothing is
   recorded — a bounced visitor did not view the page.
2. **HTML only.** The entry route always qualifies. The file route qualifies only when the
   filename ends in `.html` or `.htm`. Assets (css, js, images) are never recorded.
3. **Bot filter.** Skip when the User-Agent is empty or matches
   `bot|crawl|spider|slurp|headless|curl|wget|python-requests` (case-insensitive).
   This is a substring match on a caller-supplied string, so it filters *polite* automation
   only; anything sending a browser User-Agent is counted as a human.
4. **GET only.** A `HEAD` renders no page, so it is a request, not a pageview — and link
   preview fetchers and uptime monitors, which routinely send browser-shaped User-Agents
   the bot filter will not catch, are exactly who sends one. These routes are FastAPI
   `APIRoute`s, which (unlike Starlette's plain `Route`) do **not** auto-add `HEAD` to a
   `GET` route, so such a request is already rejected with `405` before reaching recording.
   The method guard in `_record_view` is what keeps that true if the routes are ever
   declared with `methods=['GET', 'HEAD']` or mounted as Starlette routes; it is a
   deliberate backstop, not dead code.
5. **Owner detection.** The `viewer` `_resolve_site_for_view` resolved is threaded straight
   through to the recorder, so a private site's pageview does not repeat the JWT decode, up
   to two Redis GETs, and the user lookup access resolution already performed. A public
   site's `_resolve_site_for_view` returns `viewer=None` unconditionally — public sites are
   readable without credentials, so nothing is resolved there — and the recorder resolves
   the viewer itself via `_get_optional_user`, but only when an `authorization` header or
   `token` cookie is actually present. Anonymous public traffic pays no token-decode or
   user-lookup cost at all; a logged-in owner browsing their own public site is still
   recognised.
6. **Serve first, record second — and record entirely off the response path.** The route
   handler calls `_serve_file` — which raises a 404 for a document the site does not have —
   before it calls `_queue_view`. Only a document that was actually served reaches this
   checklist, by construction: recording depends on `_serve_file`'s prior success through
   explicit sequencing, not on FastAPI discarding background tasks that were queued before
   a later exception.

   The split is deliberate. `_queue_view` is **synchronous** and does nothing but read the
   scalars the recorder needs off the already-parsed request — method, User-Agent,
   `request.client.host`, and whether credentials are present — and append one FastAPI
   `BackgroundTasks` entry. Every filter, the visitor-key HMAC, the viewer resolution in
   rule 5 and the INSERT itself run in `_record_view` **after the response has been sent**.
   Nothing analytics-related, including the JWT decode a credentialed visit to a public
   site needs, is on the response path.

   Passing the `Request` through to the background task is sound: Starlette runs background
   tasks inside the still-open ASGI scope, so its headers and cookies remain readable, and
   the values the filters depend on were captured before the response anyway. The recorder
   needs it only because `_get_optional_user` reaches `app.state.redis` to check token
   revocation, and it touches the request only when credentials were actually present.

   `_record_view` is wrapped in `try/except Exception` with `log.warning`; a failing
   analytics write must never delay or 500 a published page.

### Known imprecision

**Every reload counts.** Served pages carry `Cache-Control: no-cache`, which forces the
browser to revalidate on each visit, and the route re-serves the file every time — so a
visitor who reloads five times produces five rows. "Views" therefore means pageviews, not
distinct reading sessions; `unique_visitors` is the number to read for audience size.

There are no `304 Not Modified` responses to reason about here. These routes return
Starlette's `FileResponse`, which sets an `etag` header but never reads `If-None-Match` or
`If-Modified-Since` — conditional-request handling lives in `StaticFiles`, which these
routes do not use. Every served request is a `200`.

## API

```
GET /api/v1/sites/{id}/analytics?days=7|30|90
```

Auth: `_require_publisher` then `_get_owned_site`, matching every other detail endpoint.
Non-owners receive `404`, not `403`, so the endpoint does not confirm that a site exists.

`days` is validated against `{7, 30, 90}`; any other value returns `400`.

Response:

```json
{
  "days": 30,
  "totals": { "views": 2847, "unique_visitors": 391, "owner_views": 52 },
  "series": [{ "day": "2026-08-01", "views": 12 }],
  "top_pages": [{ "path": "index.html", "views": 1904 }]
}
```

- `views`, `series`, `unique_visitors`, and `top_pages` all **exclude** owner visits.
  `owner_views` is the separate owner count. The headline number is therefore real traffic.
- `unique_visitors` is `COUNT(DISTINCT visitor_key)` over the window — a real count, not a
  sketch or an estimate, and so **exact against honest clients**. It is not a guarantee
  against a hostile one: `visitor_key` is derived from the client IP, and with the default
  `FORWARDED_ALLOW_IPS=*` a caller picks its own apparent IP (see *visitor_key derivation*),
  so every spoofed `X-Forwarded-For` value mints a fresh key and inflates the count.
- `series` is zero-filled across every UTC day in the window, so the chart draws a real
  gap as zero rather than interpolating a straight line between distant points.
- `top_pages` returns the top 5 paths by view count.

Three indexed queries, all filtered on `(site_id, created_at)`.

Client function `getSiteAnalytics(token, id, days)` is added to
`src/lib/apis/sites/index.ts`, following the existing `jsonHeaders` / `handle` pattern.

## UI

### Tab shell

`src/lib/components/sites/tabs/AnalyticsTab.svelte` is deleted and the `analytics` entry is
removed from the `tabs` array in `SiteDetail.svelte`. Tabs become
Overview · Files · Settings · Versions. The `PREVIEW` badge survives only on Versions, which
remains a mockup.

### `OverviewTab.svelte`: the analytics data owner

The tab, not the card, owns the fetch — so both `InsightsCard` and the new `TopPagesCard`
can render from one load while the tab keeps control of where they sit. `OverviewTab` holds:

- `days`, defaulting to `30`, and the `loadSeq` request-generation counter: a response is
  only applied if no newer request — for either a different range or a different site — has
  started since, so a slow stale response can never paint another range's, or another
  site's, numbers under the current header.
- The `$derived` `siteId` primitive (`site.id`, not the whole `site` object) that the load
  `$effect` depends on. `SitesPage` recomputes `selected` via `sites.find(...)` on every list
  refresh (e.g. after a settings save), producing a new object with the same id; a
  `$derived` primitive doesn't notify subscribers when its value is unchanged, so keying the
  effect off `siteId` instead of `site` avoids a spurious reload — and the skeleton flash
  that comes with it — on every save.
- `ownerVisible`, sticky across reloads so a loading/failed window never yanks the "Yours"
  stat in or out, but reset to `false` whenever `siteId` changes so it doesn't stay sticky
  across sites.
- `dataUnknown` (`loading || failed`), one definition of "the current range's numbers are
  not known yet", reused by the KPI numerals passed to `InsightsCard` and by the Top pages
  gate below.

### `InsightsCard.svelte`: presentational KPI row + chart

Purely presentational: it renders from props and calls `onRangeChange` on a click, but does
not fetch and does not own the range state. Lives in `src/lib/components/sites/`, rendered
by `OverviewTab`.

- KPI row: Views, Unique visitors, Yours. `Yours` is hidden when `owner_views` is 0 rather
  than rendering a zero.
- Range toggle 7d · 30d · 90d. Clicking a range calls `onRangeChange`, which `OverviewTab`
  applies to its `days` state, retriggering the load effect.
- Area chart: the hand-rolled SVG from the deleted `AnalyticsTab`, now driven by `series`.
  No charting dependency. Colors from the existing `--st-chart` / `--st-chart-fill` tokens
  in `sites.css`.
- Hover readout showing day and view count for the nearest point. A sparkline with no
  readable values is decoration, not information.
- Three non-happy states: skeleton while loading, an empty state at zero views
  ("No views yet — share the link to start seeing traffic"), and an inline muted error on
  fetch failure. `OverviewTab` renders fully in all three; analytics never takes the tab down.

### New component: `TopPagesCard.svelte`

Also purely presentational, taking `loading` and the `top_pages` rows `OverviewTab` already
fetched: each row shows its path, a bar sized proportionally to the top row's view count,
and the formatted count. While loading it renders a skeleton rather than the previous
site's or range's rows still sitting in state. `OverviewTab` keeps the card mounted through
a loading window (gated on `dataUnknown`, not just `loading`) so the two-column row doesn't
collapse and reflow on every range switch.

### Overview structure

Top to bottom:

1. URL bar with copy / open actions (unchanged)
2. `InsightsCard`
3. Two columns at the `lg` breakpoint (stacked below it): `TopPagesCard` | `Details`.
   `TopPagesCard` is omitted while there are no rows to show, and `Details` then spans both
   columns instead of leaving one empty.
4. Slim quick-actions row (Replace files → Files, Change viewers → Settings,
   Restore version → Versions)

The current four stat tiles are removed. Files, Visibility, and Updated move into `Details`
instead of duplicating what the hero already shows.

### Pure helpers

Series-to-SVG-path conversion, nearest-point lookup for the hover readout, and number
formatting are extracted to
`src/lib/components/sites/lib/analytics.ts` so they are unit-testable without mounting a
component, matching the existing `form.ts` / `access.ts` / `selection.ts` convention.
`formatCount` takes a `locale` parameter rather than hardcoding `'en-US'`: the module stays
pure and unit-testable, and callers (`InsightsCard`, `TopPagesCard`) pass `$i18n.language`
so counts format in the active UI language instead of always US English.

## Testing

### Backend — `backend/open_webui/test/sites/test_analytics.py`

Following the existing suite's conftest and style.

- `visitor_key` is stable within a UTC day, differs across days, and differs across sites
  for identical IP + UA.
- Empty and bot User-Agents record nothing.
- An asset request (`.png`, `.css`) records nothing; an `.html` request records a row.
- An anonymous request to a private site (redirected to `/auth`) records nothing.
- Owner visits set `is_owner`, are excluded from `views`, and appear in `owner_views`.
- `series` is zero-filled and covers exactly `days` entries.
- `days` outside `{7, 30, 90}` returns 400.
- A non-owner, non-admin user requesting the analytics endpoint receives 404.
- A failing insert does not break the serve response.
- Deleting a site removes its `site_view` rows.
- A `HEAD` request records nothing, and `_record_view`'s method guard rejects a non-`GET`
  method directly.
- `_queue_view` resolves no user and writes no row; both happen only once the queued
  background task is awaited.
- A future-dated row is excluded from the window, and `sum(series) == totals['views']`.
  A row in the last millisecond of today still counts.
- `prune_older_than` deletes rows past the retention window, keeps rows inside it, and is a
  no-op returning `0` for `days` of `0` or negative.
- `SITES_ANALYTICS_RETENTION_DAYS` parses to `0` when unset, unparseable, or negative, and
  to the integer when valid — anything that is not a positive integer must mean "keep
  forever", never "delete everything".

### Frontend — `src/lib/components/sites/lib/analytics.test.ts`

Vitest, alongside the existing `form.test.ts` / `access.test.ts`.

- Series-to-path handles the all-zero series and the single-point series without producing
  `NaN` in the path data. (Zero-filling is the API's job, not the client's — the client
  never reconstructs missing days.)
- Nearest-point lookup maps an x offset to the correct series index, including at both edges.
- Number formatting adds thousands separators.

## Files touched

New:
- `backend/open_webui/migrations/versions/b1c2d3e4f5a6_site_view.py`
- `backend/open_webui/test/sites/test_analytics.py`
- `src/lib/components/sites/InsightsCard.svelte`
- `src/lib/components/sites/TopPagesCard.svelte`
- `src/lib/components/sites/lib/analytics.ts`
- `src/lib/components/sites/lib/analytics.test.ts`

Modified:
- `backend/open_webui/models/sites.py` — `SiteView` model, `SiteViewsTable` DAO
  (`record_view`, `get_analytics`, `prune_older_than`), view-row cleanup in
  `delete_site_by_id`
- `backend/open_webui/routers/sites.py` — recording hooks (`_queue_view` / `_record_view`),
  analytics endpoint
- `backend/open_webui/env.py` — `SITES_ANALYTICS_RETENTION_DAYS`
- `backend/open_webui/main.py` — daily `periodic_site_views_cleanup` task in `lifespan`,
  created only when retention is on
- `src/lib/apis/sites/index.ts` — `getSiteAnalytics`
- `src/lib/components/sites/SiteDetail.svelte` — drop the analytics tab
- `src/lib/components/sites/tabs/OverviewTab.svelte` — restructure

Deleted:
- `src/lib/components/sites/tabs/AnalyticsTab.svelte`
