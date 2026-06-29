# WorkOS Calendar View — Design

**Date:** 2026-06-29
**Status:** Approved (design), pending implementation plan
**Scope:** Frontend-only. No backend, DB, or migration changes.

## Summary

A due-date calendar for the current workstream, mounted as the 4th Topbar tab
(currently a greyed-out stub). Tasks render on their `due_date` as colored
chips. A Month/Week toggle switches granularity. A right rail lists tasks with
no due date; dragging one onto a day schedules it. Dragging a chip between days
reschedules it. Clicking an empty day quick-adds a task due that day. Clicking a
chip opens the existing task-detail drawer.

The view reuses the existing task store, the shared board/list filter
(`boardFilter`), `editTask`/`addTask`, SortableJS, and the realtime workstream
room. `createTask` and the task PATCH already accept `due_date`, so **no backend
work is required.**

## Decisions (from brainstorming)

| # | Decision | Choice |
|---|----------|--------|
| Q1 | What date positions a task | **Due date** only. No-due-date tasks go to the rail. |
| Q2 | Granularity | **Month + Week toggle** (default Month). |
| Q3 | Interactions | All of: click→open, drag→reschedule, click-empty-day→quick-add, unscheduled rail. |
| Q4 | Unscheduled tray placement | **Right rail** (vertical, beside the grid). |
| Q5 | Week start | **Sunday**. |

## Visual language

Matches the existing WorkOS design system (Tailwind utilities, gray surfaces,
status-colored accents, shadcn-svelte primitives scoped to `.workos-root`).

- **Task chip:** status dot (`STATUS_COLOR`) + tinted background (`{color}` at
  ~12% alpha, mirroring the board's `{color}24` pill) + title in primary text.
  - `done` → check glyph + strikethrough, muted title.
  - **Overdue** (`due_date` < today AND status not `done`/`canceled`) → red tint,
    red title, warning glyph.
  - **Urgent** priority → leading red flag glyph.
- **Today:** teal (`#00a5ba`) date badge + faintly tinted cell.
- **Overflow:** when a day holds more chips than fit, show `+N more`; clicking it
  expands the day (popover listing that day's chips). Overflow threshold is a
  fixed cap per cell (e.g. 3 in month view).
- **Out-of-month days:** dimmed date number, still droppable (sets the real date).
- **Unscheduled rail:** header (`Unscheduled · N`), one-line hint, draggable rows
  (grip + status dot + title), each a SortableJS source.

## Architecture

### Edits to existing files

1. **`lib/store.ts`**
   - `ViewKey` (line 18): add `'calendar'`.
   - Add derived `filteredTasks` (reuses `applyFilters` over `tasks` +
     `boardFilter`, mirroring `tasksByStatus`) — the single source for the grid
     and the rail. Updates live via the existing workstream room.
   - `addTask` (line ~182): accept an optional `due_date` (and `start_date` for
     symmetry) in `fields`; set it on the optimistic task and pass it to
     `api.createTask` (which already accepts both).

2. **`chrome/Topbar.svelte`** (line 15): flip the `calendar` tab to `live: true`;
   widen `selectTab`'s cast to include `'calendar'`.

3. **`WorkOSApp.svelte`**
   - Show `<Topbar />` for `calendar` (extend the `board`/`list` guard, line 34).
   - Render `<CalendarView />` in the view switch (line ~51).

### New files

- **`lib/calendar.ts`** — pure date helpers (no Svelte, no store):
  - `monthGrid(cursor: Date): Date[]` → leading days from the prior month so the
    grid starts on Sunday, the full month, trailing days to complete the last
    week (6×7 or 5×7).
  - `weekDays(cursor: Date): Date[]` → the 7 days of the cursor's week.
  - `sameDay(a, b)`, `isToday(d, now)`, `isOverdue(task, now)`.
  - `startOfDay(ms)` / day-key helper for grouping tasks by due day.
- **`lib/calendar.test.ts`** — the one runnable check: month-boundary padding
  (leading/trailing days land on the right weekday), Sunday-start, overdue logic
  (done/canceled excluded), week slicing.
- **`views/CalendarView.svelte`** — owns ephemeral `cursor` (visible period) and
  `mode` (`'month' | 'week'`). Renders the toolbar, the shared
  `<FilterBar filter={boardFilter}>`, the grid, and the rail. Groups
  `$filteredTasks` by due-day into a `Map<dayKey, Task[]>`; rail = tasks with
  `due_date == null`.
- **`views/calendar/DayCell.svelte`** — one cell: date badge, chips (capped with
  `+N more`), empty-day quick-add input, SortableJS drop target
  (`data-day={ms}`).
- **`views/calendar/CalChip.svelte`** — a task chip (status/overdue/done/urgent
  styling). Click → `openTask(task.id)`.
- **`views/calendar/UnscheduledRail.svelte`** — the right rail; SortableJS source
  in the same group as the day cells.

## Data flow

- **Read:** `CalendarView` subscribes to `filteredTasks` + `currentWorkstream`.
  Realtime task changes flow through the existing room into `tasks` →
  `filteredTasks` → grid/rail, with no extra wiring.
- **Reschedule (drag chip → day):** SortableJS `onEnd` reads the destination
  cell's `data-day`; calls `editTask(id, { due_date: <day ms> })`. Day cells +
  rail share one SortableJS group (`'workos-calendar'`). As with the board, the
  store's optimistic write is the source of truth; after the move, re-render from
  the store rather than trusting SortableJS's DOM mutation.
- **Schedule (drag rail row → day):** same `onEnd` path → `editTask` sets
  `due_date`; the row leaves the rail reactively (it no longer matches
  `due_date == null`).
- **Quick-add (click empty day):** inline input (Enter to submit, Esc to cancel,
  mirroring the board/list quick-add) → `addTask(ws.id, { title, due_date })`.
- **Open:** click a chip → `openTask(id)` → existing `TaskDetail` drawer.

## Interactions & edge cases

- Dropping onto an out-of-month trailing/leading day sets that real calendar date.
- Reschedule to the same day is a no-op (no `editTask` call if `due_date`
  unchanged).
- Filter that hides a task removes it from both grid and rail (shared source).
- `done`/`canceled` tasks never render the overdue (red) treatment.
- Month view caps chips per cell at 3 with `+N more`. Week-view cells are tall, so
  they render all chips uncapped (no `+N more`).
- Toggle/cursor state is ephemeral (not persisted); switching workstreams or
  leaving the tab resets to the current month. (Persisting `mode` like
  `listColumns` is a trivial later add if wanted — out of scope now.)

## Testing

- `lib/calendar.test.ts` (Vitest, matches existing `*.test.ts` convention):
  grid padding, Sunday-start, week slicing, `isOverdue` exclusions.
- Manual browser smoke (hot-reload, no Docker rebuild): tab switches in; chips
  land on correct days; drag chip→day reschedules; drag rail→day schedules;
  empty-day quick-add; chip→detail drawer; overdue/today/done styling; Month↔Week
  toggle; filter hides across grid + rail; live update from another session.

## Not doing (YAGNI)

Start→due span bars, multi-day events, recurring tasks, drag-to-resize duration,
cross-workstream/aggregate calendar, saved views, persisted view state. Span bars
are the natural next slice; this design (due-day placement, one SortableJS group)
leaves room for them without rework.
