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
| Storage shape | Raw rows, kept forever | User's explicit call; pruning deferred |
| Owner's own visits | Recorded, shown separately | Honest headline, no lost data |
| Overview layout | Chart-led hero (option B) | One insight card, no duplicated stat tiles |
| Analytics read access | Site owner or app admin | Mirrors existing `_get_owned_site` |

### Accepted risk: unbounded growth

`site_view` has no retention policy. Row count grows linearly with traffic forever. The
`(site_id, created_at)` composite index keeps read performance flat regardless of table
size, so the cost is storage, not latency. A retention job is a small, isolated addition
if the table ever becomes a problem.

### Deliberate omission: `user_id`

The table stores `is_owner` but **not** the viewer's user id. `is_owner` is the only
identity signal the feature needs, and storing viewer ids would make `site_view` a
per-employee browsing log of internal pages — a materially different privacy artifact
from an aggregate view counter.

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

Client IP comes from `request.client.host`. Deployments behind a proxy already run uvicorn
with proxy headers enabled, so `client.host` is the real client address.

### DAO

`SiteViewsTable` is added to the existing `backend/open_webui/models/sites.py`, next to
`SitesTable`. It exposes:

- `record_view(site_id, path, visitor_key, is_owner, db=None)`
- `get_analytics(site_id, days, db=None)` — returns totals, daily series, top pages

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

`SitesTable.delete_site_by_id` is extended to delete the site's `site_view` rows inside its
existing single transaction, alongside the access-grant cleanup it already does. With no
retention policy, orphaned view rows would otherwise persist forever.

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
4. **Owner detection.** The `viewer` `_resolve_site_for_view` resolved is threaded straight
   into `_record_view`, so a private site's pageview does not repeat the JWT decode, up to
   two Redis GETs, and the user lookup access resolution already performed. A public site's
   `_resolve_site_for_view` returns `viewer=None` unconditionally — public sites are
   readable without credentials, so nothing is resolved there — and `_record_view` resolves
   the viewer itself via `_get_optional_user`, but only when an `authorization` header or
   `token` cookie is actually present. Anonymous public traffic still pays no token-decode
   or user-lookup cost; a logged-in owner browsing their own public site is still
   recognised.
5. **Serve first, record second.** The route handler calls `_serve_file` — which raises a
   404 for a document the site does not have — before it calls `_record_view`. Only a
   document that was actually served reaches this checklist, by construction: recording
   depends on `_serve_file`'s prior success through explicit sequencing, not on FastAPI
   discarding background tasks that were queued before a later exception. From there, the
   insert is scheduled through FastAPI `BackgroundTasks` and wrapped in `try/except
   Exception` with `log.warning`; a failing analytics write must never delay or 500 a
   published page.

### Known imprecision

Requests answered `304 Not Modified` are still recorded: `_record_view` runs whenever
`_serve_file` has already succeeded, and it does not distinguish a fresh 200 from a
revalidated 304. This over-counts refreshes of cached pages slightly. Accepted: served
pages carry `Cache-Control: no-cache`, so revalidation implies the page was displayed.

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
- `unique_visitors` is `COUNT(DISTINCT visitor_key)` over the window — exact, not estimated.
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

### New component: `InsightsCard.svelte`

Layout option B, the chart-led hero. Lives in `src/lib/components/sites/`, rendered by
`OverviewTab`.

- KPI row: Views, Unique visitors, Yours. `Yours` is hidden when `owner_views` is 0 rather
  than rendering a zero.
- Range toggle 7d · 30d · 90d, defaulting to 30d, refetching on change.
- Area chart: the hand-rolled SVG from the deleted `AnalyticsTab`, now driven by `series`.
  No charting dependency. Colors from the existing `--st-chart` / `--st-chart-fill` tokens
  in `sites.css`.
- Hover readout showing day and view count for the nearest point. A sparkline with no
  readable values is decoration, not information.
- Three non-happy states: skeleton while loading, an empty state at zero views
  ("No views yet — share the link to start seeing traffic"), and an inline muted error on
  fetch failure. `OverviewTab` renders fully in all three; analytics never takes the tab down.

### Overview structure

Top to bottom:

1. URL bar with copy / open actions (unchanged)
2. `InsightsCard`
3. Two columns: `Top pages` | `Details`
4. Slim quick-actions row (Replace files → Files, Change viewers → Settings,
   Restore version → Versions)

The current four stat tiles are removed. Files, Visibility, and Updated move into `Details`
instead of duplicating what the hero already shows.

### Pure helpers

Series-to-SVG-path conversion, nearest-point lookup for the hover readout, and number
formatting are extracted to
`src/lib/components/sites/lib/analytics.ts` so they are unit-testable without mounting a
component, matching the existing `form.ts` / `access.ts` / `selection.ts` convention.

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
- `src/lib/components/sites/lib/analytics.ts`
- `src/lib/components/sites/lib/analytics.test.ts`

Modified:
- `backend/open_webui/models/sites.py` — `SiteView` model, `SiteViewsTable` DAO, view-row
  cleanup in `delete_site_by_id`
- `backend/open_webui/routers/sites.py` — recording hooks, analytics endpoint
- `src/lib/apis/sites/index.ts` — `getSiteAnalytics`
- `src/lib/components/sites/SiteDetail.svelte` — drop the analytics tab
- `src/lib/components/sites/tabs/OverviewTab.svelte` — restructure

Deleted:
- `src/lib/components/sites/tabs/AnalyticsTab.svelte`
