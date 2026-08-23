# Usage Dashboard Expansion — Design Spec

**Date:** 2026-08-23
**Status:** Approved design, pending implementation plan
**Owner:** Ahmad Alsawarieh
**Builds on:** `2026-08-19-usage-analytics-design.md` (the base usage-analytics pipeline; this spec extends its dashboard and query API only — collection, taxonomy, retention, and privacy rules are unchanged)

## 1. Goal

Make the admin Usage dashboard genuinely insightful at three levels — everyone, admin Groups, and individual users — and add visit/presence numbers (currently online, active today/this week/this month with previous-period comparison).

Confirmed scope decisions:

- "User groups" means the admin-managed permission **Groups** (Admin Panel → Groups), not WorkOS teams.
- Presence is a **snapshot on load** with a manual refresh button — no polling, no socket push (keeps the base spec's no-realtime rule).
- No per-page presence breakdown — only a total currently-online count (plus who).
- All four insight clusters are in: activity rhythm, adoption & trends, model usage, deeper user profiles.
- UI structure: one Usage tab with a **scope selector** (Everyone / any Group); no new tabs or routes.

## 2. UI design

Admin styling throughout (plain admin look, matching the existing Analytics area — not the bold WorkOS look).

### 2.1 Header

Existing header row gains a **scope selector** (`Everyone` / each admin Group, fetched from the existing groups API) next to the period selector (7/30/90 days), plus a manual **refresh** button that reloads everything including presence.

### 2.2 Everyone scope, top to bottom

1. **Presence & reach strip** — five compact cards:
   - **Online now** — count of distinct users with a live websocket session (`SESSION_POOL`); clicking the card opens a popover listing the online users' names.
   - **Active today (DAU)**, **Active 7d (WAU)**, **Active 30d (MAU)** — distinct users with at least one usage event in the window; each card shows a delta arrow vs the previous equal-length window. These use fixed 1/7/30-day windows independent of the period selector.
   - **New users** — users whose first-ever usage event falls inside the selected period, with delta arrow.
2. **Per-tool cards** (existing) — each gains a small trend arrow: active users vs the previous equal-length period.
3. **Charts row** — the existing daily-active-per-tool `ChartLine`, plus a new **Sessions per day** line chart with an average-session-length stat beside it.
4. **Activity heatmap** — new component: hour-of-day × weekday grid, cell shade proportional to event volume. Plain CSS grid cells, no chart library.
5. **Top models** — horizontal HTML bars: model name, message count, unique users. Sourced from `chat.message.sent` events.
6. **Groups comparison table** (Everyone scope only) — one row per admin Group: members, active users, adoption % (active ÷ members), events, top tool. Clicking a row sets the scope selector to that group.
7. **Events table + Users table** (existing, unchanged layout; now scope-aware).

### 2.3 Group scope

Identical layout minus the groups comparison table. Every number is filtered to the group's current members. "Online now" is the intersection of online users and group members. The users table lists members only.

### 2.4 User level (modal upgrade)

The existing per-user activity modal gains, above the activity timeline:

- Stats header: first seen (all-time), last seen, sessions, average session length, busiest hour.
- Daily-activity sparkline over the selected period.
- Tool-split mini bars.
- Top models used.

## 3. Backend API

All endpoints live in the existing `analytics.py` router (admin-only, registered only when `ENABLE_ADMIN_ANALYTICS` is true). All aggregation happens in SQL inside the DAO (`models/usage.py`), matching the existing style — no in-Python crunching.

### 3.1 Group filtering

Every existing usage endpoint (`overview`, `daily`, `events`, `users`, `users/{id}/activity`) and every new aggregate endpoint gains an optional `group_id` query param. When set, the DAO adds `WHERE user_id IN (<member ids>)`; member ids are fetched once per request via `Groups.get_group_user_ids_by_id`. A `group_id` referencing a deleted group returns 404; the frontend resets scope to Everyone.

### 3.2 New endpoints

| endpoint | returns |
|---|---|
| `GET /usage/presence?group_id=` | `{online: n, users: [{id, name}]}` — reads `SESSION_POOL` (websocket heartbeat pool in `socket/main.py`), dedupes multi-tab entries by user id, intersects with group members when scoped. No DB events involved. |
| `GET /usage/active?days=&group_id=` | `{dau: {current, previous}, wau: {…}, mau: {…}, new_users: {…}}` — DAU/WAU/MAU use fixed 1/7/30-day windows; `new_users` uses the `days` param (the dashboard's selected period). Previous = equal-length window immediately before each. |
| `GET /usage/heatmap?days=&group_id=` | 7×24 matrix of event counts bucketed in **UTC** by SQL. The frontend rotates the 168-hour week vector by the browser's timezone offset (whole-hour offsets only — fine for our region, which has no DST). |
| `GET /usage/models?days=&group_id=` | Top 10 `{model, messages, unique_users}` from `chat.message.sent`. Model id extracted from the JSON `properties` column via SQLAlchemy `properties['model'].as_string()`, which compiles per-dialect (SQLite `json_extract`, Postgres `->>`). |
| `GET /usage/sessions/daily?days=&group_id=` | Per-day distinct `session_id` count, plus overall average session length (`max(created_at) − min(created_at)` per session, averaged). |
| `GET /usage/groups?days=` | Per-group rollup: `{group_id, name, members, active_users, events, top_tool}`. Adoption % is computed client-side. |
| `GET /usage/users/{id}/summary?days=` | The whole user-modal stats payload in one call: first_seen (all-time), last_seen, sessions, avg_session_ms, busiest_hour, per-day counts (sparkline), tool split, top models. |

### 3.3 Changed endpoints

`GET /usage/overview` additionally returns the previous-period `active_users` per tool (one extra aggregate over the prior window) to power the per-tool delta arrows.

### 3.4 Metric definitions

- **Previous period** — the equal-length window immediately before the selected one. Two aggregates per metric; no schema change, no pre-aggregation.
- **New user** — `MIN(created_at)` over the user's entire event history falls inside the window (subquery over `usage_event`, not the user table's `created_at`) — measures first *activity*, so pre-existing accounts that only now start using the platform count as new.
- **Session length** — `max(created_at) − min(created_at)` per `session_id`. Single-event sessions (length 0) are excluded from the average so they do not drag it toward zero.
- **Online now** — distinct user ids in `SESSION_POOL`. Entries carry a `last_seen_at` heartbeat and a reaper already evicts stale ones, so the count is trustworthy as-is.

No new tables and no migration. Everything reads off the existing `usage_event` and `group_member` tables plus the in-memory/Redis `SESSION_POOL`.

## 4. Error handling

- Frontend keeps the existing pattern: request-generation counters drop stale responses; a single `loadError` retry banner covers all fetches. New endpoints join the same `Promise.all` load; one failed call does not blank the page — sections render whatever arrived.
- A failed presence fetch shows `—` on the Online-now card without escalating to the banner (least-critical number).
- Deleted `group_id` → 404 → frontend resets scope to Everyone.

## 5. Edge cases

- Empty group (0 members): all zeros; adoption % renders `—` (no divide-by-zero).
- Group membership is **current** membership — events by ex-members drop out of the group view retroactively. Documented caveat (§7), not a bug.
- Deleted users appearing in the online list render as "removed user" (same convention as the users table).
- Heatmap with fewer than 7 days of data still renders the full grid, empty cells zero-shaded.
- `chat.message.sent` rows missing the `model` property bucket as `unknown`.
- Timezone rotation is a single browser-offset rotation of the 168-hour vector; DST-mid-period drift is accepted (target region has no DST).

## 6. Testing

- **Backend (pytest, `.venv` python, existing usage test suite):**
  - Each new DAO aggregate against seeded fixture events with known expected counts.
  - `group_id` filtering on both old and new endpoints.
  - Presence endpoint with a monkeypatched `SESSION_POOL`: multi-tab same-user dedupe, group intersection.
  - New-user boundary: first event just inside vs just outside the window.
  - Single-event-session exclusion from the session-length average.
  - Admin-only enforcement (403 for non-admins) on every new endpoint.
- **Frontend (vitest):** heatmap rotation math (UTC vector → local, including negative offsets), delta-arrow direction, adoption-% formatting.
- **Browser smoke** at the end — the base dashboard smoke is still pending, so one combined checklist; ask before starting any Vite dev server (standing rule).

## 7. Metric caveats

Additions to the base spec's §11:

- Group-scoped numbers reflect **current** group membership, applied retroactively over historical events. Moving a user between groups moves their whole history in group views.
- DAU/WAU/MAU count *usage-event activity*, not logins. A user who logs in but triggers no tracked event does not count.
- "Online now" counts live websocket connections; a user with the tab open but the socket dropped is not counted, and the number is a point-in-time snapshot (manual refresh only).
- Session length inherits the base spec's caveat: `session_id` and timestamps are client-reported for client events — indicative, not authoritative.

## 8. Out of scope

- Polling or realtime presence updates; per-page presence breakdown.
- WorkOS teams as a grouping dimension.
- Funnels, retention curves, cohort analysis (unchanged from base spec).
- Any change to collection, event taxonomy, retention, or privacy rules.
