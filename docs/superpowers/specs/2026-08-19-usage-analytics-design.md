# Usage Analytics — Design Spec

**Date:** 2026-08-19
**Status:** Approved design, pending implementation plan
**Owner:** Ahmad Alsawarieh

## 1. Goal

Give admins visibility into user behavior across all pages and tools of the Osool platform (chat, WorkOS, Policy Review, hub/home, admin, settings). The data serves four purposes at once:

1. **Adoption tracking** — which tools get used, by whom, how often.
2. **Product improvement** — which views/features get used inside each tool.
3. **Compliance trail** — who did what, when, for sensitive actions.
4. **Per-user activity view** — an admin-visible activity timeline per user.

**Access rule:** collection covers every logged-in user; viewing is restricted to app admins only (`role == "admin"`), behind the existing `ENABLE_ADMIN_ANALYTICS` gate.

**Approach chosen:** in-house event pipeline (event table + batch ingest endpoint + frontend tracker + admin dashboard tabs). Self-hosted PostHog/Umami rejected (heavy extra infrastructure on a single internal VM, separate access story). Inferring behavior from audit middleware rejected (API traffic is a weak proxy for user intent; no page-view or duration signal).

## 2. Data model

One new table, `usage_event`, created via Alembic migration (same pattern as existing WorkOS tables):

| column | type | notes |
|---|---|---|
| `id` | text (uuid) | primary key |
| `user_id` | text | who did it; from auth token, never from payload |
| `event_name` | text | dot-namespaced, e.g. `workos.task.create`, `page.view` |
| `tool` | text | top-level bucket: `chat`, `workos`, `policy`, `home`, `admin`, `settings` |
| `properties` | JSON | view name, entity id, duration_ms, model id, etc. Ids only — never content. |
| `session_id` | text | client-generated per browser session; groups one visit |
| `source` | text | `client` or `server` |
| `created_at` | bigint | epoch **milliseconds** |

Indexes: `(created_at)`, `(user_id, created_at)`, `(event_name, created_at)`.

## 3. Event taxonomy

A curated allowlist of roughly 35 named events, maintained in one backend module and mirrored to the frontend tracker. Two kinds, split by trust level:

- **Client-emitted** (frontend tracker, best-effort; loss acceptable):
  - `page.view` — properties: `tool`, `view`, `path`; `duration_ms` delivered on leave.
  - `workos.view.switch` — board / list / timeline / calendar / files / my-work / inbox.
  - `chat.new`, `search.used`, and similar behavior-only signals.
- **Server-emitted** (inside backend routers; spoof-proof; doubles as the compliance trail. Best-effort by design: the insert runs in its own transaction and failures are logged and swallowed so telemetry can never break or roll back the real action — a rare emit failure loses that one event):
  - `workos.task.create` / `workos.task.complete` / `workos.task.delete`
  - `workos.comment.create`
  - `policy.review.submit` / `policy.review.approve` / `policy.review.reject`
  - `policy.doc.upload`
  - `chat.message.sent` (model id in properties)
  - team/workspace membership changes

**Rule:** compliance-grade action → server event. Behavior-only signal → client event. An action is emitted from exactly one side, so counts never double.

## 4. Collection

### 4.1 Frontend tracker

New app-wide module `src/lib/utils/usage.ts`:

- `track(event_name, properties?)` pushes into an in-memory queue.
- Auto page-views: subscribes to SvelteKit `afterNavigate` plus the native `popstate` pattern (shallow pushState is invisible to `$app/stores` — see the WorkOS URL-sync lesson); maps route → `tool`/`view` and emits `page.view`. On leave, `duration_ms` goes out via `navigator.sendBeacon` so tab-close does not lose it.
- Batching: flush every 10 s or at 20 queued events, whichever first — one `POST /api/v1/usage/events` with an array. `sendBeacon` on `visibilitychange: hidden` catches the tail.
- Session id: `crypto.randomUUID()` stored in `sessionStorage`.
- Fire-and-forget: failures are dropped silently; no retries, no console spam, never blocks UI.
- Tracker reads the `ENABLE_USAGE_TRACKING` flag from the existing config endpoint and is fully inert when the flag is off.

### 4.2 Server-side emission

Helper `UsageEvents.emit(user_id, event_name, tool, properties)` called inline (not middleware) at ~12 spots in existing routers (`workos.py`, policy router, chats router). Synchronous insert in its own DB session (never the caller's), wrapped in try/except so a telemetry failure can never break or roll back the real action.

Emission points that live in access-control code paths (membership changes) must follow the access-control reference doc (`docs/superpowers/specs/2026-06-26-workos-access-control.md`); emission observes those actions, it must not alter their logic.

### 4.3 Ingest endpoint

`POST /api/v1/usage/events`:

- Auth: any logged-in user. `user_id` always taken from the auth token — a payload-supplied user id is ignored.
- `event_name` validated against the allowlist; unknown names rejected.
- `source` forced to `client`; only the backend helper writes `source='server'`.
- Caps: max 50 events per batch; each `properties` JSON ≤ 2 KB. Per-user rate limit of 1,000 ingest **requests** per hour (far above normal use — the tracker flushes at most every 10 s ≈ 360 req/hr); excess requests rejected with 429. Deliberately counts requests, not events, so the theoretical ceiling is 50k events/hr — acceptable for an internal tool where the cap exists to stop runaway loops, not abuse (see the implementation plan).
- Invalid items in a batch are skipped individually; valid ones are stored. Response reports accepted/rejected counts.

### 4.4 Configuration

`ENABLE_USAGE_TRACKING` persistent-config flag (default **on**), same style as `WORKOS_RULES` config. Off = ingest endpoint refuses client events and the frontend tracker is inert. Server-side compliance events keep flowing regardless (they are the audit trail).

## 5. Admin query API

Extends the existing `analytics.py` router (already registered only when `ENABLE_ADMIN_ANALYTICS` is true; all endpoints admin-only):

| endpoint | returns |
|---|---|
| `GET /analytics/usage/overview?days=30` | per-tool totals: active users, sessions, events, avg time from page durations |
| `GET /analytics/usage/daily?days=30&tool=` | daily active users + event counts (trend lines) |
| `GET /analytics/usage/events?days=&tool=` | event-name leaderboard: counts + unique users |
| `GET /analytics/usage/users?days=&sort=` | per-user rollup: last seen, sessions, events by tool; paginated |
| `GET /analytics/usage/users/{id}/activity?days=&page=` | one user's event stream, newest first, filterable by tool |

All aggregation happens in SQL inside the DAO (`models/usage.py`) — no in-Python crunching — matching the existing analytics DAO style.

## 6. Admin dashboard UI

New **"Usage"** tab inside the existing admin Analytics page (`src/lib/components/admin/Analytics/`), reusing its chart primitives:

1. **Overview strip** — per-tool adoption cards (chat / WorkOS / policy / home): active users, trend arrow.
2. **Trends** — daily-active line chart with tool filter (reuses existing `ChartLine`).
3. **Feature table** — event leaderboard: event name, count, unique users.
4. **Users table** — per-user rollup; clicking a row opens a drawer with that user's activity timeline.

Styling matches the existing admin Analytics area (not the bold WorkOS look — this is an admin surface).

## 7. Retention and privacy

- Raw events kept **365 days**; a daily cleanup task (same pattern as existing periodic cleanups in `main.py` lifespan) deletes older rows.
- No pre-aggregation tables initially. Estimated volume (~50 users × ~200 events/day ≈ 3–4 M rows/year) is trivial under the chosen indexes; aggregation is a later optimization if queries slow down.
- No content captured — events record that a task was created, never its title or body. Properties hold ids only.
- No IP address or user-agent stored.
- Deleted users: events are retained (compliance) but rendered as "removed user" in the UI.

## 8. Error handling

- Client tracker: silent drop on any failure; no retry storms.
- Server emit: try/except-wrapped; telemetry can never fail the underlying action.
- Ingest: per-item validation; bad items skipped, good items stored.

## 9. Testing

- **Backend (pytest, `.venv` python):** ingest auth, allowlist enforcement, spoofed `user_id` rejection, batch caps, DAO aggregate correctness, retention cleanup, and server-emit firing on task create / policy approve.
- **Frontend (vitest):** tracker batching, flush triggers, route → tool/view mapping.
- **Browser smoke** at the end (ask before starting any Vite dev server, per standing rule).

## 10. Out of scope

- Funnels, retention curves, cohort analysis (would motivate PostHog later).
- Non-admin visibility (team leads, self-view).
- Auto-capture of arbitrary clicks.
- Real-time dashboard updates; dashboards query on load.

## 11. Metric caveats

- `workos.task.complete` fires only on the transition into the done state. A task created directly as done (e.g. via an API/import path that skips the normal create-then-complete flow) counts only as a `workos.task.create`, not as a completion.
- Per-tool `sessions` counts must not be summed across tools to get a "total sessions" figure — a single browser session generates a distinct `session_id`-per-tool grouping in the DAO's aggregate queries, so one real user session can legitimately count once per tool the user visited in it. Summing overstates session volume.
- `duration_ms` and `session_id` are client-reported (from `src/lib/utils/usage.ts`). They are bounds-checked and shape-validated server-side (`_validate_client_event` in `backend/open_webui/models/usage.py`) to reject obviously bad values, but a hostile or modified client can still submit misleading-but-in-range numbers. Treat these fields as indicative, not authoritative, for anything adversarial (e.g. abuse investigations).

The dashboard expansion (`2026-08-23-usage-dashboard-expansion-design.md`) adds:

- Group-scoped numbers reflect **current** group membership, applied retroactively over historical events — moving a user between groups moves their whole event history into the group's view, including events recorded before the move.
- DAU/WAU/MAU count *usage-event activity*, not logins. A user who logs in but triggers no tracked event does not count toward any of the three.
- "Online now" counts live `SESSION_POOL` websocket connections, not open tabs — a tab left open after the socket drops is not counted — and it is a point-in-time snapshot taken on load/refresh, not a live figure.
- The dashboard's session-length metrics (`/usage/sessions/daily`, per-user average session length) reuse `session_id` and timestamps and so inherit the caveat above: client-reported, indicative rather than authoritative.
