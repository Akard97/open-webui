<!--
  WorkOS — My Work command-center redesign: design spec.
  Branch: osool. Created 2026-06-27.
  Brainstormed interactively; locked decisions in §2.
  Builds directly on Phase 3a ([2026-06-27-workos-phase3a-mywork-filters-design.md]).
  NOT access-control-sensitive: reuses the already visibility-filtered /me/tasks and
  /notifications endpoints unchanged and adds no new data access. No need to touch
  docs/superpowers/specs/2026-06-26-workos-access-control.md.
-->

# WorkOS — My Work command center (Design)

## 1. Context

Phase 3a shipped **My Work** as the cross-workstream landing view: a segmented
toggle (All / Assigned / Created), the shared filter/search bar, and a flat list of
the caller's tasks grouped into due-date buckets (Overdue / Today / This week / Later /
No date). It is backed by the read-only `GET /api/v1/workos/me/tasks` endpoint, which
returns the visibility-filtered union of tasks assigned to **or** created by the caller.

A separate fix in this branch suppressed the workstream **Topbar** on global views
(My Work / Inbox / Admin), so My Work now owns its full content area — `WorkOSApp.svelte`
only renders `<Topbar />` for `board`/`list`.

The user wants My Work to be a **command center**: more than a task list — an at-a-glance
surface that answers "what needs me now, how am I doing, and what just happened," while
still being a place to actually work through tasks. This spec redesigns the My Work view
into a **focus cockpit**: a workable task list as the spine, framed by KPI stats, a
progress/insights panel, an activity rail, and quick-launch shortcuts.

Everything is derived from data the page already loads. **No backend, migration, or
access-control change is required.**

## 2. Locked decisions

Captured during brainstorming (2026-06-27):

| # | Decision | Choice |
|---|---|---|
| D1 | Jobs the page must do | All four: daily focus/triage, at-a-glance status, activity & mentions, launchpad. |
| D2 | Scope | **Frontend-only.** Reuse `/me/tasks` (already loaded) + `/notifications` (existing). No new endpoint, no migration. |
| D3 | Centerpiece | A **workable task list** — a "Needs attention" hero block above the existing due-date buckets. The list stays the spine; click a row to open the task. |
| D4 | Framing extras | All of: KPI **stat strip**, **completion ring/progress**, **status & priority breakdown**, **activity feed + quick-launch rail**. |
| D5 | Layout | Two columns `~2fr / 1fr` (list + right rail), collapsing to a single column below a width breakpoint. KPI strip spans full width on top; FilterBar sits between strip and columns. |
| D6 | Activity feed source | The existing **notifications** list (assigned / mentioned / commented / status-changed), summarized like the Inbox. Capped at 50 server-side; show the top ~8 with "See all" → Inbox. |
| D7 | Backend follow-up | A raw cross-task `/me/activity` feed (beyond notifications) is **deferred** — flagged, not built. |

## 3. Goals / non-goals

**Goals**
- Opening My Work gives an immediate read on workload (counts, completion, status mix)
  without scrolling.
- The most urgent work (overdue, due-today, urgent/high priority) is surfaced first in a
  dedicated "Needs attention" block, above the full bucketed list.
- Recent activity relevant to the user (@mentions, assignments, comments, status changes)
  is visible without leaving for the Inbox.
- The page remains a place to **work**: every task row still opens the task; segment
  toggle and the shared FilterBar behave exactly as today.
- The redesign decomposes the current single `MyWorkView.svelte` into small,
  single-purpose components plus a pure, unit-tested stats module.

**Non-goals**
- No new backend endpoint, DB migration, or persisted state.
- No change to the access-control model or to what `/me/tasks` / `/notifications` return.
- No Timeline/Gantt, Saved Views, global search, or URL deep-linking (separate slices).
- No change to board/list/inbox/admin views beyond the already-landed Topbar suppression.

## 4. Layout & responsive structure

The content area (no Topbar here) is laid out as:

```
Header:   "My Work"           [All · Assigned · Created]      [+ New task]
Strip:    [Overdue n] [Due today n] [In progress n] [Done this week n]
FilterBar (existing, showAssignee=false)
────────────────────────────── grid (2fr / 1fr) ──────────────────────────────
LEFT (list spine)                         │ RIGHT RAIL
  NEEDS ATTENTION                         │   InsightsPanel
    overdue ∪ due-today ∪ urgent/high     │     ◔ completion ring
  TODAY · n                               │     ▰▰▱ by status (segmented bar)
  THIS WEEK · n                           │     ▰▰▱ by priority (segmented bar)
  LATER · n                               │   ActivityRail (top ~8 + See all)
  NO DATE · n                             │   QuickLaunch (workstreams + new task)
```

- Grid: `grid-template-columns: minmax(0, 2fr) minmax(0, 1fr)` with `gap`. Below a
  breakpoint (Tailwind `lg`), collapse to one column; the rail stacks **below** the list.
- The list column scrolls within the page as today; the rail is not independently scrolled
  (no nested scroll) — it stacks naturally.
- KPI strip: 4 tiles, `grid-cols-2` on narrow, `grid-cols-4` at width. Overdue tile uses
  the danger tint when count > 0; others neutral.

## 5. Components & files

Decompose `views/MyWorkView.svelte` (orchestrator) + new `views/commandcenter/*`:

| File | Responsibility | Key props / inputs |
|---|---|---|
| `views/MyWorkView.svelte` | Loads My Work + notifications; owns `segment`; computes derived stats from `$myTasks`/`$myWorkFilter`; lays out header + strip + grid. | — |
| `views/commandcenter/StatStrip.svelte` | 4 KPI tiles; emits a "quick filter / scroll-to" intent on click. | `stats: MyWorkStats`, `active: StatKey \| null`, `on:pick` |
| `views/commandcenter/InsightsPanel.svelte` | Completion ring + status bar + priority bar. Pure presentational. | `stats: MyWorkStats` |
| `views/commandcenter/ActivityRail.svelte` | Renders top ~8 notifications, summarized; "See all" switches to Inbox view. | uses `notifications` store |
| `views/commandcenter/QuickLaunch.svelte` | Distinct workstreams present in the user's tasks → workspace·workstream label; click selects workstream + `view='board'`. New-task entry (workstream picker). | `tasks: Task[]` |
| `views/commandcenter/FocusList.svelte` | "Needs attention" hero + the due-date bucket list (extracted from today's MyWorkView body). Opens tasks on click. | `tasks: Task[]` (already filtered/segmented) |
| `lib/stats.ts` | **Pure functions** computing all counts/breakdowns from `Task[]`. No Svelte/DOM. Unit-tested. | see §6 |

Reuse existing: `lib/buckets.ts` (`bucketByDueDate`, `BUCKET_ORDER`, `BUCKET_LABEL`),
`lib/filters.ts` (`applyFilters`), `chrome/FilterBar.svelte`, the shadcn-svelte kit
(`card`, `badge`, `avatar`, `tooltip`, `scroll-area`) and `ui/Icon.svelte`.

## 6. Data & computation — `lib/stats.ts`

All inputs are the already-loaded `myTasks` (post-segment, pre/post-filter as noted). Pure
functions, given `now: number` for testability (mirrors `bucketByDueDate(tasks, now)`).

```ts
export interface MyWorkStats {
  overdue: number;        // bucketByDueDate(...).overdue.length
  dueToday: number;       // .today.length
  inProgress: number;     // status === 'in_progress'
  doneThisWeek: number;   // status === 'done' && completed_at >= now - 7d
  completionRate: number; // done / (total non-canceled); 0 when denominator 0
  byStatus: Record<TaskStatus, number>;
  byPriority: Record<'urgent'|'high'|'medium'|'low'|'none', number>; // 'none' = null priority
}
export function computeStats(tasks: Task[], now: number): MyWorkStats;

// "Needs attention" = overdue ∪ due-today ∪ (urgent|high priority, status not done/canceled),
// de-duplicated by id, stable order (overdue first, then by due date, then priority).
export function needsAttention(tasks: Task[], now: number): Task[];
```

**Two input sets (this disambiguation is the crux):**
- `segmentSet` = `myTasks` filtered by the **segment toggle only** (All/Assigned/Created).
  It does **not** apply `myWorkFilter` and does **not** apply the list's
  done/canceled-hiding rule.
- `visible` = `applyFilters(segmentSet-with-done/canceled-hidden, myWorkFilter)` — exactly
  today's list set.

**Computation notes**
- Stat strip + ring + breakdowns are computed via `computeStats(segmentSet, now)` —
  i.e. over the segment set **before** the FilterBar (`myWorkFilter`) is applied. This is
  deliberate: the tiles are stable reference counts that *act as filters into the list*, so
  they must not recompute to near-zero when a facet is active. It also lets "Done this week"
  and completion rate count `done` tasks that the list hides by default.
- The list (FocusList) receives `visible`; its hero uses `needsAttention(visible, now)` and
  its buckets use `bucketByDueDate(visible, now)` — so the worked list tracks the FilterBar
  as today, while the stats above it stay whole.
- `byStatus`/`byPriority` render as segmented bars using the board's existing status/
  priority color conventions (reuse `StatusDot`/Pills palette where possible).
- Completion ring is a single SVG arc (no chart lib): `completionRate` → stroke-dashoffset.

## 7. Interactions & states

- **KPI tiles (soft filter / scroll):** clicking "In progress" or "Done this week" toggles
  the corresponding **status** facet on `myWorkFilter` (click again clears). "Overdue" and
  "Due today" have no status equivalent → they scroll the list to that bucket and briefly
  highlight its header. The active tile shows a selected state.
- **Segment toggle & FilterBar:** unchanged from Phase 3a.
- **New task (cross-workstream):** the header `+ New task` opens a small inline form with a
  **workstream picker** (default = the workstream of the user's most recently updated task;
  fall back to first available). On submit, calls existing `addTask(workstreamId, {title})`.
  My Work realtime already folds the new task in.
- **Quick launch:** clicking a workstream calls `selectWorkstream(id)` then `view.set('board')`.
- **Activity "See all":** `view.set('inbox')`.
- **States:**
  - Loading: strip/ring render zeros (no layout shift); list shows nothing until loaded.
  - Empty list: keep today's "Nothing on your plate yet" empty state in the list column;
    rail still renders insights (zeros) + activity ("You're all caught up.") + quick launch.
  - Activity empty: "You're all caught up." (matches Inbox copy).

## 8. Backend

**None.** `MyWorkView` already calls `loadMyWork()` (→ `/me/tasks`). Add a
`loadNotifications()` call on mount so the Activity rail has data (the Inbox view already
defines and uses it; My Work simply also loads it). No new routes, schemas, or migrations.

Deferred follow-up (own spec if pursued): `GET /api/v1/workos/me/activity` returning raw
`Activity` rows across the caller's visible tasks, for a richer feed than notifications.

## 9. Testing

- **Unit (TDD):** `lib/stats.test.ts` covering `computeStats` and `needsAttention` —
  bucket boundaries (overdue vs today vs week), `doneThisWeek` window edge, completion-rate
  zero-denominator, priority `none` grouping, de-dup in `needsAttention`.
- **Reuse:** existing `buckets`/`filters` tests remain valid.
- **Manual browser smoke** (per the no-Vite-without-asking rule, only on request): strip
  counts match the list; tiles filter/scroll; ring + bars reflect the segment; activity
  shows recent notifications and "See all" → Inbox; new-task picker creates into the chosen
  workstream and the task appears live; responsive collapse to one column.

## 10. Out of scope / follow-ups

- Raw cross-task activity endpoint (`/me/activity`) — deferred (§7/D7).
- Timeline/Gantt, Saved Views, global jump-to search, URL deep-linking — separate slices.
- Any access-control change — none; this spec consumes existing visibility-filtered data.
