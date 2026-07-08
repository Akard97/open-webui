# WorkOS Timeline View (Gantt)

**Date:** 2026-07-09
**Branch base:** `osool`
**Status:** Approved design — ready for implementation plan

## Goal

Add a **Timeline view** to WorkOS: an interactive, planning-first Gantt for the
current workstream. Users drag bars to set and move `start_date`/`due_date`,
see overlaps and gaps, and pull unscheduled work onto the calendar. The visual
direction is **bold blocks** — chunky solid status-color bars with progress,
avatars, and state text rendered on the bar — validated against mockups in the
brainstorming session (visual companion, 2026-07-08/09).

Frontend-only: no backend, API, or migration changes. `Task.start_date` and
`Task.due_date` already exist (ms timestamps), and `editTask` already logs
`start_changed`/`due_changed` activities.

## Decisions (from brainstorming)

1. **Purpose: schedule planning.** Interactive editing (drag move/resize) is
   first-class, not an afterthought.
2. **Rows: flat, sorted by date.** One row per task ordered by effective start
   (`start_date ?? due_date`), tie-break by due date, then title. No swimlane
   grouping.
3. **Unscheduled tasks: right-side rail with drag-to-schedule**, mirroring the
   Calendar view's `UnscheduledRail` pattern.
4. **Zoom: three presets — Week / Month / Quarter**, segmented control,
   persisted per user in `localStorage`.
5. **Mobile: view-only, simplified.** Chart renders and pans; editing happens
   via the detail drawer. No touch drag/resize.
6. **Visual direction: Bold blocks (option B)** — solid status-color bars,
   progress as a color split, avatar chip and state text on the bar, hatched
   weekends, badged today marker.
7. **Left rail: planning rail (option B)** — ~260px, two-line rows
   (status dot + name / date range + priority flag).
8. **Overdue treatment: slip tail (option A)** — the bar keeps its status color
   up to the due date, then a hatched red tail extends to today, growing daily.
9. **Implementation: hand-rolled Svelte** — no gantt library. Custom component
   plus a pure, unit-tested date-math module.

## Placement

- New view value `'timeline'`; `WorkOSApp.svelte` renders `TimelineView` for it.
- Topbar tab order becomes `Overview · List · Board · Timeline · Calendar ·
  Files`; the tab is live on desktop and mobile.
- New gantt-chart glyph added to `ui/Icon.svelte` (Lucide path data, matching
  the existing fixed-glyph pattern).

## Layout (desktop, top → bottom / left → right)

1. **Toolbar** — the shared `FilterBar` bound to `boardFilter` (Status /
   Priority / Label / Assignee chips + search), with trailing slot controls:
   - **Zoom segmented control** (Week / Month / Quarter).
   - **Today button** — scrolls the today line to ~30% of the viewport.
   - **Add new** (teal primary) — inline title input, same pattern as List.
2. **Chart region** (horizontal native scroll):
   - **Header** — month band above day columns. Week zoom shows weekday names +
     day numbers; Month shows day numbers; Quarter shows week gridlines with
     the month band dominant. Today's number is badged (teal pill).
   - **Rows** — left planning rail cell + bar lane per task:
     - **Rail cell** (~260px, two lines): status dot + semibold name (click →
       `openTask`); second line `Jul 6 → Jul 15 · ⚑ High` (red + "Nd overdue"
       when late).
     - **Bar lane**: day gridlines, hatched weekend columns, teal today line
       with a TODAY badge, and the task's bar/milestone.
   - **+ Add task** row at the bottom of the rail — inline title input.
3. **Unscheduled rail** (right, ~200px, collapsible; collapse state ephemeral):
   cards with status dot + name + priority; drag onto the chart to schedule.

## Bar anatomy

- **Bar**: 24px tall, 6px radius, solid `STATUS_COLOR[status]`; subtle status-
  tinted shadow. Progress renders as a color split — solid up to the progress
  fraction, ~25% tint after (fraction from the same `actualProgress` helper
  `ProgressCell` uses, so subtask completion counts).
- **On-bar content** (shown only when the bar is wide enough, in priority
  order): state text (`✓ Done`, `55%`, `Todo`…) at the left; assignee avatar
  chip (white circle, initials) at the right. Narrow bars show nothing —
  details live in the rail and hover card.
- **Overdue (slip tail)**: for non-done, non-canceled tasks with
  `due_date < today` (existing `isOverdue`), the bar keeps its status color to
  the due date, then a hatched red tail (`repeating-linear-gradient`) extends
  to the today line with a `⚠ Nd` label when it fits. Rail meta line turns red.
- **Milestone** (due-only task): a status-colored diamond (rotated square) at
  the due date.
- **Start-only task**: a 1-day bar at `start_date`; dragging its right handle
  sets a due date.
- **Done**: full green (`#769a4a`), ✓ glyph, no slip tail.
- **Hover**: row highlight, resize handles appear (teal-outlined white grips at
  bar edges), and the existing `TaskHoverCard` shows after its usual delay.
- **Dark mode**: `dark:` variants for all surfaces (canvas, gridlines, weekend
  hatch, rail, header); bar colors are shared between themes like the Board.

## Time model & math (`lib/timeline.ts`)

Pure functions, no DOM. All-day semantics on ms timestamps (Calendar parity):
a bar spans `start_date` at 00:00 through `due_date` end-of-day inclusive.

- **Classification**: start+due → `bar`; due-only → `milestone`; start-only →
  1-day `bar`; neither → `unscheduled`. Canceled tasks are excluded entirely
  (Board/List parity).
- **Window**: `[min task date − 7d, max task date + 14d]`, expanded to at least
  ~6 weeks and always containing today.
- **Scale**: `dayWidth` per zoom — Week ≈ 48px, Month ≈ 24px (default),
  Quarter ≈ 8px. Helpers: `dateToX`, `xToDate` (day-snapped), `barGeometry`
  (left/width incl. slip-tail segment), `sortTimeline`.
- **Edit helpers**: `applyMove(task, dayDelta)` and
  `applyResize(task, edge, dayDelta)` return new `{start_date, due_date}`
  pairs, clamped to a 1-day minimum. The component calls
  `editTask(id, pair)` with the result.

## Interactions

All drags are pointer-event based, day-snapped, with a live dark tooltip above
the bar showing the pending range (`Jul 9 → Jul 14`).

- **Move**: drag the bar body — both dates shift; drop → optimistic
  `editTask({start_date, due_date})`.
- **Resize**: drag an edge handle — start or due changes alone; min 1 day.
  The left handle on a milestone creates a `start_date`.
- **Milestone drag**: moves `due_date`.
- **Click vs drag**: pointer movement ≤ 4px is a click → `openTask(id)`.
- **Drag-in from the unscheduled rail** (HTML5 DnD, Calendar-rail pattern):
  the drop day becomes `start_date = due_date` (a 1-day bar to resize).
- **Add task**: toolbar "Add new" and the rail's "+ Add task" create via
  `addTask(workstreamId, { title, start_date: today, due_date: today })` so
  the new task appears on the chart immediately (status defaults to backlog).
- **Cancel/scroll**: Esc cancels an in-flight drag; dragging near the viewport
  edge auto-scrolls the chart.
- **Write gating**: when `!canEditTask(task, userId, role)` (existing
  `lib/roles` predicate) the bar shows no handles or grab cursor and drags are
  inert — cosmetic only; the server re-checks `PATCH /tasks/{id}` regardless.

## Data flow

- Tasks come from the `filteredTasks` derived store; the shared `FilterBar`
  drives `boardFilter`, so facet filters and search work with no extra wiring.
- Realtime is free: bars re-derive from the store on task events.
- Reused helpers: `isOverdue` (`lib/calendar`), `actualProgress`
  (`lib/progress`), `STATUS_COLOR`/`PRIORITY_COLOR` (`lib/colors`),
  `formatDateShort` (`lib/format`), `AssigneeAvatars`, `TaskHoverCard`,
  `StatusDot` (rail dots), shadcn `DropdownMenu`/`buttonVariants` where menus
  or buttons are needed.
- **New persisted state**: `timelineZoom` writable in `lib/store.ts`, saved to
  `localStorage` under `workos:timeline-zoom` (mirrors `listColumns`).

## Mobile (view-only)

- The Timeline tab renders on mobile: horizontal pan via native scroll,
  narrower single-line rail (~150px, dot + name only).
- No drag, resize, or rail drag-in; handles never render. Tapping a bar or
  rail row opens the full-screen detail drawer (existing mobile pattern).
- Unscheduled tasks appear as a collapsible section above the chart (the
  Calendar view's mobile unscheduled pattern).
- Zoom presets remain available.

## Component / file structure

**New**
- `views/TimelineView.svelte` — shell: toolbar, scroll container, window/scale
  wiring, drag orchestration; composes the parts below.
- `views/timeline/TimelineHeader.svelte` — month band + day/week columns +
  today badge.
- `views/timeline/TimelineRail.svelte` — planning-rail rows + "+ Add task".
- `views/timeline/TimelineBar.svelte` — bar/milestone rendering: progress
  split, slip tail, avatar, state text, handles, drag/click handling.
- `views/timeline/UnscheduledPanel.svelte` — right rail with draggable cards.
- `lib/timeline.ts` + `lib/timeline.test.ts` — the pure math above.

**Modified**
- `chrome/Topbar.svelte` — Timeline tab.
- `WorkOSApp.svelte` — route the `timeline` view.
- `lib/store.ts` — `'timeline'` in the view union + `timelineZoom`.
- `ui/Icon.svelte` — gantt glyph.

## Testing & verification

- **Unit (vitest)** — `lib/timeline.test.ts`: window computation (padding,
  6-week minimum, contains today), `dateToX`/`xToDate` round-trips per zoom,
  day snapping, `barGeometry` incl. slip-tail segment and milestone position,
  classification of the four task shapes, `sortTimeline` ordering,
  `applyMove`/`applyResize` clamping (1-day minimum, milestone start
  creation).
- `svelte-check` clean; existing suites stay green.
- **Browser smoke (manual follow-up; never auto-start Vite — standing rule):**
  tab appears and routes; bars render per status incl. progress split, slip
  tail, milestone; drag move/resize persists and survives reload; rail drag-in
  schedules a task; filters/search narrow rows; zoom presets re-scale and the
  choice survives reload; Today button scrolls; drawer opens from title/bar
  click; dark mode; mobile pan + tap.

## Out of scope

- Dependency arrows, baselines, critical path.
- Swimlane grouping (status/assignee), saved views.
- Row virtualization (workstream task counts are modest; revisit if needed).
- Export/print, backend/API changes, new realtime events.
- Touch drag-editing on mobile.
