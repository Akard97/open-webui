# WorkOS — Workstream Overview page (design)

> Approved direction: **"Ink + Studio"** (2026-07-02) — ink-dark KPI hero band + reference-style white
> analytics cards (user-supplied dashboard reference, re-skinned in Osool teal). Mockup:
> `workos_overview_mockup_v4_ink_studio` (session artifact). Scope decision: Overview is
> **workstream-level** (the existing `overview` Topbar tab goes live). A separate **team-level
> workload page across all teams** is explicitly deferred to a later phase.
>
> Governing principle (user feedback): **no redundant information** — every fact appears exactly
> once, in the one visual that explains it. "Overdue" is the sanctioned exception: it appears as a
> *number* (KPI), as *items* (attention list), and *per person* (team table) — three lenses, never
> the same rendering twice.
>
> Second governing principle (user feedback): **all calculations must be accurate and correct** —
> every metric below has a precise definition and a unit test. No metric ships without one.

## 1. Page structure

A new `OverviewView` rendered when `view == 'overview'` for the current workstream, as the 4th
workstream tab (Topbar `TABS`: `overview.live` → `true`). Layout top-to-bottom:

1. **Ink hero band** (dark `#101623` panel in BOTH themes): breadcrumb `Workspace / Workstream`,
   title "Overview", a time-range selector (applies to §3.2 Momentum only), and 5 KPI tiles.
2. **Row**: Weekly momentum chart card (LayerChart) | Distribution card.
3. **Team performance** table card (full width).
4. **Row**: Needs attention list | Pulse (activity feed).

All data except §3.6 Pulse/activity-strip derives client-side from the already-loaded `tasks`
store (`GET /workstreams/{id}/tasks`), so Overview stays consistent with Board/List and updates
live through the existing task socket handlers. Activity data comes from one new endpoint (§4).

## 2. Canonical definitions (single source of truth)

Implemented as pure functions in `src/lib/components/workos/lib/overview.ts`, all taking
`(tasks, now)` (or explicit windows) so they are deterministic and unit-testable.

- **Task universe `W`**: all tasks of the current workstream with `status != 'canceled'`.
  Canceled tasks are excluded from every metric on this page.
- **OPEN**: `status ∉ {done, canceled}`.
- **`now`**: a `nowTick` store refreshed every 60 s while Overview is mounted (day rollovers
  happen without a reload — deliberate improvement over My Work's page-load-static `now`).
- **Due day** (timezone rule): `due_date`/`start_date` are stored as **UTC-midnight timestamps**
  of the picked calendar date (`DueDateCell` parses `YYYY-MM-DD` → UTC). The calendar date is
  therefore the timestamp's **UTC** Y/M/D fields; deadlines are experienced **locally**:
  - `dueDayStartLocal(ts)` = local 00:00.000 of the UTC-date of `ts`.
  - `dueDayEndLocal(ts)` = local 23:59:59.999 of the UTC-date of `ts`.
- **Overdue**: `OPEN && due_date != null && dueDayEndLocal(due_date) < now`. A task is *not*
  overdue during its due day. **Days late** = `ceil((now − dueDayEndLocal) / 86 400 000)`.
- **Health**: `taskHealth()` from `lib/progress.ts` (on_track / at_risk / behind / overdue),
  with its overdue boundary **fixed** to the rule above (§5.1).
- **Completed in window `(a, b]`**: `status == 'done' && a < completed_at ≤ b`. This is exact
  because the DAO clears `completed_at` on any transition out of `done`
  (`models/workos.py` `update_fields`), with the §5.2 hardening for idempotent re-saves.
- **Rolling weeks** (KPIs): `(now − 7d, now]` vs `(now − 14d, now − 7d]`.
- **Calendar weeks** (Momentum chart): local weeks starting **Monday**; the newest bin is the
  current partial week and is labeled as such. KPIs use rolling windows, the chart uses calendar
  bins — a deliberate, documented mismatch (each is the natural frame for its visual).

## 3. Blocks and their metrics

### 3.1 KPI tiles (ink hero)

| # | Tile | Value | Caption | Notes |
|---|------|-------|---------|-------|
| 1 | Open tasks | `\|OPEN\|` | "`n` in progress · `m` in review" | counts over OPEN |
| 2 | Due this week | OPEN, not overdue, due day ∈ [today … today+6] (7 local days incl. today) | "`k` due tomorrow" (due day == tomorrow); "none tomorrow" when 0 | |
| 3 | Overdue | overdue count (§2) | "oldest `X`d late" = max days-late; "all clear" when 0 | |
| 4 | Completed | completed in `(now−7d, now]` | "last 7 days vs prior 7" | delta pill vs prior window: ↑ green when higher, ↓ red when lower, hidden when equal |
| 5 | New tasks | `created_at ∈ (now−7d, now]` over `W` (any status) | "added in last 7 days" | |

### 3.2 Weekly momentum (LayerChart card)

- Grouped bars per calendar week over the selected range (**4 / 6 / 12 weeks**, default 6):
  light-teal `created[w]` (`created_at ∈ w` over `W`) next to saturated-teal `completed[w]` (§2).
- Hover tooltip (LayerChart): week label + both values; current bin labeled "(this week)".
- Footnote: **avg completion time** = mean(`completed_at − created_at`) over tasks completed in
  the selected range, in days, 1 decimal; delta vs the preceding equal-length window —
  ▾ green (faster), ▴ red (slower), hidden when either window is empty. Label it
  **"avg completion time"** (created→done lead time), NOT "cycle time" — we do not measure
  in_progress→done. Empty range → "—".

### 3.3 Distribution card

- **Priority pairs** over OPEN: urgent / high / medium / low, plus "None" only when > 0.
  Invariant (tested): pairs sum to `|OPEN|`.
- **Status bar** over `W`: segments backlog / todo / in_progress / in_review / done, widths
  `n/|W|`, labels show counts, colors from `lib/colors.ts`. The ONLY place the full status mix
  appears.
- **Activity strip**: activity events per local calendar day, last 14 days incl. today, from the
  §4 histogram. Bar intensity = linear vs the max day (3 teal steps + light base). Today's bucket
  increments live on `workos:activity.created`.

### 3.4 Team performance table

Rows: every user id in `assignee_ids` of any **OPEN** task (so each row has `Open_i ≥ 1`;
people whose work is all done/canceled don't linger as zero rows), sorted by Open desc, then
name; plus an **Unassigned** row (OPEN with empty `assignee_ids`) when non-empty, always last,
with "Backlog pool" pill.

- **Multi-assignee rule (documented in a header tooltip):** a task counts fully for EACH of its
  assignees, so columns may sum to more than the global totals. No fractional attribution.
- Columns: `Open_i`, `InProgress_i`, `InReview_i`, `Overdue_i` (rule §2), **Load**, **Health**.
- **Load** = `Open_i / max_j(Open_j)` — relative to the busiest member (never > 100 %); tooltip
  "relative to the busiest member". Unassigned row same scale, gray.
- **Health pill** (tooltip states the rule verbatim): with `riskHigh_i = Overdue_i + Behind_i`
  (behind via `taskHealth`): **Needs support** `riskHigh ≥ 2` · **Watch** `riskHigh == 1` or
  `AtRisk_i ≥ 2` · **On track** otherwise. (Rows always have `Open_i ≥ 1`, so no zero-open pill
  is needed.)
- Avatars + names via the `directory` store.

### 3.5 Needs attention list

Qualifying OPEN tasks: overdue, health `behind`, health `at_risk`, or **due soon** (due day is
today or tomorrow). Each task appears once under its most severe class
(overdue > behind > at_risk > due_soon).

Ranking: severity class, then within class — overdue: `dueDayEndLocal` asc (most late first);
behind / at_risk: `plannedProgress − actualProgress` gap desc; due_soon: due asc.
Right-hand label: "`X`d late" / "behind plan" (tooltip "`a`% done vs `p`% planned") / "at risk" /
"due today"·"due tomorrow". Rows show severity dot, title, key, assignee avatars; click →
`openTask(id)`. Show 6, "Show all `N`" expands in place. Empty state: "Nothing needs attention."

### 3.6 Pulse

Latest 8 items from §4, template per `ActivityType` ("moved `KEY` to In review", "completed
`KEY`", "commented on `KEY`", "added a subtask to `KEY`", …), actor name via `directory`,
relative time via a shared `ago()`. Live-prepends on `workos:activity.created` for the current
workstream (room already joined by the store). Click → `openTask`.

## 4. Backend: one new endpoint

`GET /workstreams/{workstream_id}/activity?limit=30&days=14&tz_offset_minutes=0`

- **Gates**: `_require_workos` + `require_workstream_visible` — 404 posture, identical to
  `GET /workstreams/{id}/tasks`. No new visibility semantics.
- **Response**: `{ items: [...], daily: [{day: 'YYYY-MM-DD', n}] }` where `items` = newest
  `limit` activities of tasks in the workstream **joined with** `task_key`, `task_title`
  (pulse must not N+1); `daily` = per-day counts over the last `days` days computed with the
  client-supplied `tz_offset_minutes` so buckets match the viewer's local midnight.
- **Clamps**: `limit ≤ 100` (default 30), `1 ≤ days ≤ 31` (default 14),
  `|tz_offset_minutes| ≤ 840`. Invalid values clamp, never 500.
- **DAO**: `Activities.list_for_workstream(...)` + `Activities.daily_counts_for_workstream(...)`
  via join `workos_activity.task_id → workos_task.id` filtered on `workstream_id` (grouping done
  in Python over the window's rows; workstream volumes are modest).
- **Access doc**: add the route to §4 of
  `docs/superpowers/specs/2026-06-26-workos-access-control.md` (standing rule).

## 5. Shared correctness fixes (small, in-scope)

1. **`taskHealth` overdue boundary** (`lib/progress.ts`): change `now > due_date` →
   `now > dueDayEndLocal(due_date)`. Today, a task due *today* shows "Overdue" on
   Board/My Work from the morning (UTC midnight) — wrong, and inconsistent with
   `bucketByDueDate`. Affects TaskCard / MyWork / hover card; update `progress` unit tests.
2. **`completed_at` idempotence** (`models/workos.py` `update_fields`): stamp `completed_at`
   only on a **transition into** `done` (capture prior status before the setattr loop);
   re-saving an already-done task currently re-stamps it, silently shifting §3.2 history.
   Keep the existing clear-on-reopen behavior. Add a DAO test.

## 6. Frontend architecture

```
src/lib/components/workos/
  views/OverviewView.svelte          orchestrator: layout, nowTick, loadWorkstreamActivity
  views/overview/KpiBand.svelte      ink hero + 5 tiles + range selector
  views/overview/MomentumCard.svelte LayerChart grouped bars + tooltip + completion-time footnote
  views/overview/DistributionCard.svelte
  views/overview/TeamTable.svelte
  views/overview/AttentionList.svelte
  views/overview/PulseCard.svelte
  lib/overview.ts                    ALL metric functions (pure) — the accuracy layer
  lib/overview.test.ts               vitest
```

The due-day helpers (`dueDayStartLocal` / `dueDayEndLocal`, §2) live in `lib/progress.ts` (which
`taskHealth` needs for §5.1) and are imported by `overview.ts` — one implementation, no circular
imports.

- **Wiring**: `ViewKey` union + `'overview'`; Topbar `TABS` overview `live: true`;
  `WorkOSApp.svelte` renders `OverviewView`. Store additions: `wsActivity` (`{items, daily}`),
  `loadWorkstreamActivity(id)`, socket handler for `workos:activity.created` (append + bump
  today's bucket when it matches the current workstream).
- **Charts**: install via `npx shadcn-svelte add chart` (chart wrapper + `layerchart`; repo is
  Svelte ^5.53 / Tailwind 4 / bits-ui 2 — compatible). LayerChart renders the Momentum chart
  (tooltips/animation earn it); status bar, load bars, and activity strip are plain
  CSS/SVG — LayerChart only where it adds value.
- **Styling**: hero stays ink (`#101623` family) in both themes with its own dark-tile palette;
  cards/page follow the app idiom (white / `dark:` grays, hairline borders, `rounded-xl`);
  status & priority colors ONLY from `lib/colors.ts`; numbers `tabular-nums`. Do NOT reference
  the My Work page for styling. Do not run prettier on workos files (repo convention).
- **States**: per-card empty states; activity cards show a skeleton while the endpoint loads and
  a quiet error state ("Couldn't load activity") on failure — task-derived cards never block on
  it. 0-task workstream → full-page friendly empty state.
- **A11y**: KPI tiles and chart carry `aria-label`s with the computed values; attention/pulse
  rows are buttons; the range selector is a real listbox; contrast on ink tiles ≥ AA.

## 7. Testing

- **`lib/overview.test.ts`** (vitest): every §2/§3 function — window edges (Monday boundary,
  partial week, rolling vs calendar), due-day tz mapping (UTC-midnight → local day; test with
  simulated offsets), overdue/days-late boundaries, multi-assignee counting, load-bar max rule,
  health-pill thresholds, attention ranking order, priority-pairs sum invariant, delta signs
  (completed ↑ good, completion-time ▾ good), reopened-task exclusion, empty sets.
- **Backend pytest** (`.venv` python): endpoint visibility (team member OK, non-member 404,
  restricted-workspace non-member 404, app-admin OK), clamps, histogram tz correctness across a
  midnight boundary, join fields present; DAO test for §5.2.
- **Static**: `svelte-check` clean.
- **Manual smoke** (user's Vite hot-reload + Docker backend; do not start a Vite server without
  asking): tab renders, tooltips, live task update recomputes KPIs, activity prepends via socket.

## 8. Out of scope (explicit)

- Team-level workload page across all teams (next phase — the user's workload-monitor ask).
- `Files` Topbar tab; saved time-range preference; workstream target/end dates; per-status
  time-in-state analytics (needs status-transition history aggregation).
