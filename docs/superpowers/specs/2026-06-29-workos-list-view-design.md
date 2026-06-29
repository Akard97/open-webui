# WorkOS List View Redesign

**Date:** 2026-06-29
**Branch base:** `osool`
**Status:** Approved design — ready for implementation plan

## Goal

Rebuild the WorkOS **List view** (`src/lib/components/workos/views/ListView.svelte`)
into a polished, status-grouped, **inline-editable table** modeled on the
provided ClickUp-style reference image — but **without any Kanban feel** (no
cards-in-columns, no drag-between-columns). Accents use the Osool **teal**
brand (`--primary` / `brand-*`), not the image's indigo/purple.

All editing reuses existing store actions (`editTask`, `addTask`, `removeTask`).
The only new persistent state is a per-user **column-visibility preference**
saved to `localStorage`.

## Context

- **Current List view** (`views/ListView.svelte`) is bare: groups by status via
  `tasksByStatus`, sticky group headers (status `Pills` dot + label + count), and
  flat rows in a fixed grid `[dot · key · title · priority · due · avatars]`.
  The whole row calls `openTask(id)`. No column headers, no per-group add, no
  row menu, no collapse, no inline editing, no column config.
- **The detail drawer** (`views/TaskDetail.svelte`) already implements every
  inline editor we need, as inline markup:
  - **Status** — `DropdownMenu` of the 6 `StatusDot` glyphs → `editTask({status})`
    (plus a separate `Canceled` item).
  - **Priority** — `DropdownMenu` of `Pills` → `editTask({priority})` (incl. "No
    priority").
  - **Due date** — native `<input type="date">` → `editTask({due_date})`.
  - **Assignee** — already a standalone component, `views/detail/AssigneeField.svelte`,
    which takes a `task` prop and calls `editTask({assignee_ids})`.
- **Design-system primitives** (reused): `Pills`, `StatusDot`, `Icon`,
  `AssigneeAvatars`, the shared `FilterBar`, shadcn `DropdownMenu`. Status colors
  live in `lib/colors.ts` (`STATUS_COLOR`); priority colors in `PRIORITY_COLOR`.
- **Status set:** `STATUS_ORDER = [backlog, todo, in_progress, in_review, done]`
  (excludes `canceled`). `tasksByStatus` buckets by status and is already
  filter-applied + sort-keyed. The Board and current List both iterate
  `STATUS_ORDER`, so `canceled` tasks are not shown in either view today — the new
  List preserves that parity.
- **Persistence pattern:** the store already persists `navCollapsed` to
  `localStorage` under `workos:nav-collapsed` (write on subscribe, read on init).
  The column preference mirrors this exactly.
- **Hard rule:** do not start a Vite dev server for smoke testing without asking.
  Browser smoke is a manual follow-up.

## Decisions (from brainstorming)

1. **Interaction model: fully inline-editable** for the reference image's cells
   (status circle, assignee, due date, priority). Clicking the **name** still
   opens the detail drawer for full editing.
2. **Columns: richer than the image, no task key, and user-configurable.**
   Available columns: **Name** (always on), **Assignee**, **Due date**,
   **Priority**, **Labels**, **Progress**. The task `key` (WORK-123) is dropped.
   A **Columns** dropdown toggles the optional five; the choice is persisted to
   `localStorage` per browser.
3. **Labels & Progress are display-only in the list** (they are our additions,
   not in the reference image): Labels render as chips; Progress renders a
   read-only mini-bar + percent for in-progress tasks (and `—` otherwise).
   Both are edited in the drawer (click the name). Inline editing is limited to
   the four image cells, keeping scope tight and avoiding duplication of the
   drawer's complex tag-create picker and drag-slider.
4. **Grouping: by status, collapsible.** Only non-empty status groups are shown
   (matches the image and current behavior). Each group has a collapsible header
   (chevron + status pill + count) and a `+ Add task` footer. Collapse state is
   ephemeral component state (not persisted — YAGNI).
5. **Group-header "…" menu: dropped.** It has no real action for us (collapse is
   the chevron). Not rendered.
6. **No row drag-reorder / drag-between-groups.** Keeps it list-not-board; order
   stays by `sort_key`.

## Layout (top → bottom)

1. **Toolbar** — the shared `FilterBar` (Status / Priority / Label / Assignee
   chips + search), unchanged, followed by a thin list-local row holding a
   right-aligned **Columns** `DropdownMenu`. The top-level "New task" entry point
   stays where it is today (the `Topbar`, shown for the List view) — no second
   global add button is added to the list body.
2. **Status groups** (iterate `STATUS_ORDER`, skip empty buckets) — each a white
   rounded card (`border` + `12px` radius), containing:
   - **Group header:** chevron (collapse toggle) + status pill (`StatusDot` glyph
     + `STATUS_LABEL`, on a tint of the status color, matching the Board chip) +
     task count.
   - **Column-header row:** muted labels for each *visible* column
     (`Name · Assignee · Due date · Priority · Labels · Progress`).
   - **Task rows** (when expanded): a CSS grid whose `grid-template-columns` is
     built from the visible columns. Per row:
     - **Status circle** (left of Name) — `StatusCell`: a `StatusDot`-glyph
       `DropdownMenu` trigger; selecting a status calls `editTask({status})`.
     - **Name** — a button; click (or Enter/Space) opens the drawer via
       `openTask(task.id)`.
     - **Assignee** — `AssigneeField` (avatars, or "Assign" placeholder).
     - **Due date** — `DueDateCell`: formatted short date, or "Add date"
       placeholder; click reveals a native date input → `editTask({due_date})`.
     - **Priority** — `PriorityCell`: flag + label `DropdownMenu`, or an empty
       flag placeholder → `editTask({priority})`.
     - **Labels** — chips (reusing `Pills label=` / a small chip), display-only.
     - **Progress** — `ProgressCell`: read-only mini-bar + `{n}` for
       `in_progress` tasks, else `—`.
     - **Row "…" menu** (hover/focus, far right) — `DropdownMenu`: Edit
       (`openTask`) and Delete (`removeTask`, gated by `canDeleteTask`), matching
       `TaskCard`.
   - **`+ Add task` footer** — reveals an inline title input (like the Board's
     per-column add); Enter calls `addTask(workstreamId, { title, status })` with
     the group's status; Escape cancels.

## Component / file structure

**Rewrite**
- `views/ListView.svelte` — toolbar (FilterBar + Columns dropdown), grouped
  collapsible sections, dynamic column-header + rows grid, per-group inline add,
  collapse state, row menu. Composes the cells below.

**New** (`views/cells/`)
- `StatusCell.svelte` — props: `task`. The leading status-glyph `DropdownMenu`
  (6 statuses + Canceled) → `editTask({status})`.
- `PriorityCell.svelte` — props: `task`. Flag + priority `DropdownMenu`
  (incl. "No priority") or empty-flag placeholder → `editTask({priority})`.
- `DueDateCell.svelte` — props: `task`. Short-date display / "Add date"
  placeholder toggling a native `<input type="date">` → `editTask({due_date})`.
- `ProgressCell.svelte` — props: `task`. Read-only mini progress bar + percent
  for `in_progress` (reuses `actualProgress`/`taskHealth` from `lib/progress`),
  `—` otherwise.

**Reused unchanged**
- `views/detail/AssigneeField.svelte` (assignee cell — already `task`-prop based),
  `Pills`, `StatusDot`, `Icon`, `AssigneeAvatars`, `FilterBar`,
  `lib/store`, `lib/types`, `lib/colors`, `lib/format`, `lib/progress`,
  `lib/roles` (`canDeleteTask`), shadcn `DropdownMenu`.

**New store / lib additions**
- `lib/store.ts` — a `listColumns` writable persisted to `localStorage` under
  `workos:list-columns`, mirroring the existing `navCollapsed` pattern (read on
  init, write on subscribe). Shape: a record of the 5 optional columns →
  `boolean`, all defaulting to `true`. Plus a small `LIST_COLUMNS` metadata
  array (`{ key, label }`) for rendering the Columns menu and building the grid
  template, and a `gridTemplate(visible)` helper that maps visible columns to
  fixed widths (Name = `1fr`).
- `lib/colors.ts` (or a tiny `lib/status.ts`) — a `statusShape(status)` helper
  returning the `StatusDot` glyph shape, so `StatusCell` doesn't re-duplicate the
  status→shape map. (Board/TaskDetail keep their existing copies; adopting the
  shared helper there is out of scope.)

The new cells are list-tuned (compact, dense-table sizing). They intentionally
do **not** refactor the drawer's inline editors — `TaskDetail` deliberately keeps
those inline (per the task-detail spec), and a 10-line dropdown duplicated in a
focused cell is cheaper and lower-risk than refactoring the 550-line drawer.

## Color & theming

- Accents (active affordances, `+ Add task`, Columns button) use the Osool teal
  `--primary` / `brand-*`, not indigo.
- Status pill/glyph tints from `STATUS_COLOR`; priority flag colors from
  `PRIORITY_COLOR`; both unchanged.
- Dark mode preserved throughout (`dark:` variants; `.workos-root` already
  themed).

## Behavior / data notes

- **Event handling:** editable cells (status / assignee / due / priority) and the
  row "…" menu must `stopPropagation` so they don't trigger the row/name's
  `openTask`. Only the Name button (and Enter/Space on it) opens the drawer.
- **Canceled tasks:** setting a task to `Canceled` from `StatusCell` moves it into
  the `canceled` bucket, which is not rendered (no `canceled` group) — the row
  disappears from the List, consistent with the Board and the current List.
- **Add task:** inline add uses the current workstream id
  (`currentWorkstream.id`) and the group's status. Empty/whitespace titles are
  ignored. Reuses the existing optimistic `addTask`.
- **Date format:** short month + day for the cell (e.g. `Mar 17`), matching the
  current List's `toLocaleDateString('en-US', { month: 'short', day: 'numeric' })`.
- **Labels:** `task.labels` is an array of label **ids**; the List builds a
  `labelById` map from the `labels` store (as `TaskCard`/`BoardView` do) to render
  chips (name + color dot), capped with an overflow indicator.
- **Realtime:** rows are driven by `tasksByStatus` (the filtered/sorted derived
  store), so existing realtime task events update the List with no extra wiring.
- No new backend/API changes; no new realtime events.

## Testing & verification

- Editing/add/delete reuse existing store actions, so the logic risk is small and
  concentrated in the **new** code:
  - **Column preference:** unit-test the `listColumns` default (all `true`),
    the `localStorage` round-trip (read existing pref on init), and the
    `gridTemplate(visible)` builder (correct template for a representative
    visible/hidden set, Name always `1fr`).
  - Avoid testing pure markup.
- Keep the frontend test suite green (project vitest command). Update any test
  that references the old `ListView` markup/grid.
- **Browser smoke (manual follow-up; do not auto-start Vite):** switch to List →
  verify grouped collapsible sections, the Columns dropdown toggles columns and
  the choice survives reload, inline-edit each of status/assignee/due/priority,
  `+ Add task` per group, row "…" delete (gated), name opens the drawer, and dark
  mode.

## Out of scope

- Inline editing of Labels and Progress (edit via the drawer).
- Group-by other than status; saved views; the group-header "…" menu.
- Row drag-reorder / drag-between-groups.
- Showing `canceled` tasks in the List (preserves current Board/List parity).
- Any backend/API or realtime-event changes.
- Refactoring the drawer's inline editors or the Board to share the new cells.
