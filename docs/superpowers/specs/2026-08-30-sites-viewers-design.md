# Sites Viewers — naming who viewed a published site

Date: 2026-08-30
Status: approved (brainstorming), ready for implementation plan
Builds on: `2026-08-29-sites-analytics-design.md`

## Problem

The Sites Overview tab reports how many people viewed a site, but not who. For an internal
publisher, "who has actually read this" is often the more useful question — and the data to
answer it is already flowing past the recording path and being discarded.

## Goals

1. Show the site owner a roster of named viewers, with anonymous views aggregated honestly.
2. Fix the unique-visitor overcount described below, which is a defect in the shipped feature.
3. Change nothing about when a viewer is resolved, so anonymous traffic stays free and stays
   anonymous.

## Non-goals

- Per-person page-by-page reading history. The roster reports totals and a last-seen time.
- A chronological activity feed.
- Notifying viewers that they are being attributed.
- Making anonymous visitors identifiable across days. The daily salt rotation stays.

## Reversal of a prior decision

The analytics spec contains a section titled "Deliberate omission: `user_id`", which argued
that storing the viewer's user id would make `site_view` "a per-employee browsing log of
internal pages — a materially different privacy artifact from an aggregate view counter."

**That decision is reversed here, deliberately and with the same reasoning acknowledged.** The
user asked for named viewers, which cannot be delivered without storing the identity. The
consequence is exactly what the original section described: `site_view` becomes a record of
which named people read which site and when.

What follows from that, and is part of this design rather than an afterthought:

- The roster is visible only to the site owner and app admins — the same audience as the rest
  of the analytics endpoint, which returns 404 rather than 403 to everyone else.
- `SITES_ANALYTICS_RETENTION_DAYS` (already shipped, default off) is the control that bounds
  how long this record persists.

  **The user was asked directly and chose to keep it off: named viewer records are retained
  indefinitely.** This is recorded as an explicit decision, not an inherited default — the
  merge-gate review's objection was precisely that leaning on a mitigation nobody had turned
  on undercuts the argument for the reversal. The lever is documented in `.env.example` and
  can be set later without a code change; until then, the access control below is the only
  bound on this record.
- The prior spec's section will be rewritten in place to record the reversal, not deleted.
  A spec that silently drops a decision it once argued for is worse than one that never made
  the argument.

### Attribution scope

Signed-in viewers are named on **all** sites, including public ones. A signed-in visitor to a
public site is resolved today anyway (their session cookie is present), so this adds no
resolution that was not already happening — only retention of the result.

Anonymous visitors remain anonymous **because they are never resolved**, not because the
result is discarded. Recording still skips the token decode and user lookup entirely when a
request carries no credentials, so the privacy property and the performance property are the
same property.

## The unique-visitor defect

`unique_visitors` is currently `COUNT(DISTINCT visitor_key)` over the whole window. But
`visitor_key` deliberately embeds the UTC date so it rotates daily. Someone who visits every
day for a month therefore contributes **thirty** distinct keys and is counted as thirty unique
visitors. The metric is really "sum of daily uniques", and it overstates on every window
longer than a day.

Storing `user_id` makes a correct count possible for the attributable half:

```
unique_visitors = COUNT(DISTINCT COALESCE(user_id, visitor_key))
```

Signed-in viewers dedupe correctly across the whole window. Anonymous visitors still cannot —
that is inherent to the daily rotation, which is not being weakened — so that portion remains
sum-of-daily-uniques. The UI states this rather than presenting a number that is exact for one
half of its inputs and inflated for the other.

The fix is not retroactive, and that is a transient worth naming: rows written before migration
`c1d2e3f4a5b7` have `user_id IS NULL` and fall back to `visitor_key`, so for as long as the
retention window still holds pre-migration rows, a signed-in daily visitor is counted once per
pre-migration day *plus* once for all their post-migration rows. There is no backfill — an
unattributed past view is the honest record, and the attribution was never captured to restore —
so the residual overcount simply ages out as those rows leave the window.

## Data model

Migration `c1d2e3f4a5b7`, `down_revision = 'b1c2d3e4f5a6'` (the current head).

One column added to `site_view`:

| column | type | note |
|---|---|---|
| `user_id` | Text, **nullable** | the signed-in viewer; NULL means anonymous |

NULL carries two meanings that are indistinguishable and do not need distinguishing: a genuinely
anonymous view, and a row recorded before this migration. Rows predating the change simply have
no attribution.

No new index. The roster query filters on `(site_id, created_at)` — already covered by
`ix_site_view_site_created` — and groups the (small) filtered set by `user_id`.

## Recording

`_record_view` already resolves `viewer` for exactly the cases that need it. It gains one
argument to `SiteViews.record_view`: `viewer.id if viewer is not None else None`.

Nothing else about the recording path changes. In particular the resolution gate

```python
if viewer is None and has_credentials:
    viewer = await _get_optional_user(request)
```

is untouched, so anonymous traffic to a public site continues to pay neither a token decode nor
a user lookup — the property pinned by the existing `auth_calls` tests.

## Aggregation

New `SiteViewsTable.get_viewers(site_id, days, limit=8, now_ms=None, db=None) -> dict`:

```json
{
  "people": [
    { "user_id": "...", "name": "Sara Al-Mutairi", "profile_image_url": "...",
      "views": 14, "last_viewed_at": 1756500000000 }
  ],
  "anonymous_views": 203,
  "more": 3
}
```

- `people` is the top `limit` named viewers ranked by view count, tie-broken by
  `last_viewed_at` descending then `user_id` ascending so the ordering is deterministic.
- Owner visits are **excluded**, consistent with every other visitor-facing number; the KPI
  row's `Yours` already reports them.
- `anonymous_views` counts rows where `user_id IS NULL`, owner rows excluded.
- `more` is the number of named viewers beyond `limit`, so the card can say "+3 more" without
  returning the full list.
- Names and avatars come from `Users.get_users_by_user_ids(...)` in one batch call. A viewer
  whose account has since been deleted resolves to no row; those views fall back to a
  `Deleted user` label rather than vanishing, so the counts still reconcile with `views`.
  (Since the post-review hardening below, account deletion detaches the id from its rows,
  so this label is a backstop for rows that predate the fix or bypassed the delete flow,
  not the normal outcome.)

Two queries: one `GROUP BY user_id` over the window, one batch user lookup.

## API

The existing `GET /api/v1/sites/{id}/analytics?days=7|30|90` gains a `viewers` block, rather
than a second endpoint, so Overview still makes one request:

```json
{
  "days": 30,
  "totals": { "views": 2847, "unique_visitors": 391, "owner_views": 52 },
  "series": [ ... ],
  "top_pages": [ ... ],
  "viewers": { "people": [ ... ], "anonymous_views": 203, "more": 3 }
}
```

Auth is unchanged — `_require_publisher` then `_get_owned_site`, 404 for anyone else.

## UI

New `src/lib/components/sites/ViewersCard.svelte`, presentational, receiving props from
`OverviewTab` (which owns the fetch, the range state, and the `loadSeq` guard).

Overview's structure becomes:

```
URL bar
InsightsCard                       (KPI row + range toggle + chart)
[ Viewers | Top pages ]            two columns at lg
Details                            full width
quick actions
```

Details moves to full width; it is five key-value rows and reads fine that way.

Each roster row: avatar, name, view count, relative last-seen. The anonymous row uses a muted
avatar, is labelled `Anonymous`, and shows only a view count — no last-seen, because the
aggregate has no single subject. It sorts last regardless of count, since it is a different
kind of row from the named ones.

States: skeleton while loading (shared with the rest of the tab), hidden on failure, and a
`No viewers yet` empty state when the window has no views at all.

The `Unique visitors` KPI gains a short note that anonymous visitors are counted per day, so
the number is not read as an exact headcount.

## Testing

### Backend — extending `backend/open_webui/test/sites/test_analytics.py`

- A signed-in viewer's `user_id` is recorded; an anonymous view records `NULL`.
- Anonymous traffic to a public site still triggers zero user resolutions (the existing
  `auth_calls` assertion must continue to hold — this is the regression guard for the privacy
  and performance property).
- Roster ranks by view count, applies the cap, and reports the correct `more` remainder.
- Owner views appear in neither `people` nor `anonymous_views`.
- `anonymous_views` counts only NULL-attributed rows.
- A viewer with a deleted account still appears, labelled, and the counts reconcile.
- `unique_visitors` counts one signed-in viewer as **one** across a multi-day window (the
  regression test for the defect above), while two anonymous days still count as two.
- Roster respects the time window and site scoping.
- Auth unchanged: a non-owner still gets 404.

### Frontend

`ViewersCard` is presentational, so any pure formatting it needs (relative last-seen, the
"+N more" phrasing) goes in `src/lib/components/sites/lib/analytics.ts` beside the existing
helpers and is unit-tested there.

## Files touched

New:
- `backend/open_webui/migrations/versions/c1d2e3f4a5b7_site_view_user_id.py`
- `src/lib/components/sites/ViewersCard.svelte`

Modified:
- `backend/open_webui/models/sites.py` — `user_id` column, `record_view` argument,
  `get_viewers`, corrected `unique_visitors`
- `backend/open_webui/routers/sites.py` — pass the viewer id; include `viewers` in the response
- `backend/open_webui/test/sites/test_analytics.py`
- `src/lib/components/sites/tabs/OverviewTab.svelte` — two-column row, Details full width
- `src/lib/components/sites/lib/analytics.ts` (+ its test)
- `docs/superpowers/specs/2026-08-29-sites-analytics-design.md` — rewrite the
  "Deliberate omission: `user_id`" section as a recorded reversal

## Post-review hardening (2026-08-30)

An adversarial review after the build surfaced three gaps; all three are fixed in code, and
none reopens the retention decision above (still deliberately off).

1. **Account deletion now detaches identity.** `Users.delete_user_by_id` calls
   `SiteViews.detach_user`, which sets `user_id` back to NULL on that account's view rows.
   The rows stay — the views happened and totals must keep reconciling — but the record
   stops naming the deleted account. Before this, deletion left the id linked to sites and
   timestamps indefinitely, which the retention decision never meant to cover: that decision
   was about live accounts, not about surviving deletion.
2. **Recording is rate-limited per (site, client IP).** Public sites are an unauthenticated
   write path; a browser-shaped User-Agent was the only gate. `_view_rate_ok` in the sites
   router now enforces a fixed-window cap (60 views/min per site per IP, in-process, bounded
   key map that fails open under address rotation — the bound protected there is this
   process's memory, since per-IP limiting cannot stop a rotating attacker anyway). Honest
   traffic never approaches the cap.
3. **`record_view` refuses to insert for a deleted site.** Recording runs after the
   response, so it races site deletion; the insert is now `INSERT … SELECT … WHERE EXISTS
   site` — one statement, not check-then-act — so a site deleted before the background task
   runs gains no orphan rows. The residual window is a single statement's execution racing
   the delete transaction's snapshot; without foreign keys (this codebase uses none, and
   SQLite would not enforce them as configured) that microsecond window is accepted and the
   delete's own same-transaction sweep of view rows covers the other ordering.
