# WorkOS — Workstream Board Redesign (TaskBoard look)

**Date:** 2026-06-23
**Status:** Approved (design); pending spec review
**Tool route:** `/workos` (board view)
**Reference:** TaskBoard mockup provided by the user (kanban with colored column headers, row-based cards)
**Builds on:** [WorkOS Phase 1](2026-06-22-workos-phase1-design.md)

---

## 1. Overview

A **visual redesign** of the WorkOS workstream (board) page to match the TaskBoard
mockup. This is a presentation-layer change only: no backend, no status-enum, and no
data-model changes. All existing functionality — drag-and-drop, task CRUD, realtime,
Board/List switching — is preserved.

Scope (confirmed with user): **Board + topbar**. The sidebar, the List view's own
styling, and any new *features* (Calendar, Files, Overview, Automation, real filtering)
are out of scope. Controls that appear in the mockup but have no backing feature are
rendered as **decorative stubs** — present for the visual match, inert on click.

## 2. Goals & non-goals

### Goals
- Restyle the board cards to the mockup's row-based layout (assignee / date / priority rows).
- Restyle column headers as colored, rounded status-header chips with count + add button.
- Rebuild the topbar into a title row + a tab row (`Overview · List · Board · Calendar · Files`).
- Add a board-local filter bar (`Due Date / Assignee / Priority / Advance Filters`) + primary `+ Add New`.
- Keep all current behavior working: drag-and-drop, add task, open task, realtime, view switching.

### Non-goals
- No status-enum / data-model / backend changes. The 5 existing statuses stay.
- No functional filtering, Calendar/Files/Overview tabs, Share, or Automation (decorative).
- No sidebar redesign. No List view restyle.

## 3. Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Scope | Board + topbar |
| Columns | Keep the 5 existing statuses + drag-drop; apply the mockup's colored-header style |
| Card content | Mockup row layout; **keep** label chips; **drop** mono key and progress % |
| Filters / extra tabs | Decorative for now (visual only); Board + List tabs stay functional |
| Primary add action | Move into the board filter row's `+ Add New` (remove the Topbar "New task") |

## 4. Components & responsibilities

```
WorkOSApp.svelte (unchanged shell)
  ├── Topbar.svelte        (rebuilt: title row + tab row)
  └── BoardView.svelte     (filter bar + restyled column headers; composes TaskCard)
        └── TaskCard.svelte (NEW: one card, mockup layout)
  Icon.svelte              (extended glyph set)
  styles.css               (spinner keyframe)
```

### 4.1 `Topbar.svelte` (rebuilt)
- **Title row**: layers icon + breadcrumb (`Workspace · Workstream` falling back to team/`WorkOS`)
  + decorative edit-pencil; right side = assignee avatar stack derived from the current
  board's tasks (decorative) + **Share** and **Automation** outline buttons (decorative stubs).
- **Tab row**: `Overview · List · Board · Calendar · Files` with the mockup's underline-active
  style. **Board** and **List** call `view.set(...)` (functional). **Overview / Calendar /
  Files** are inert (no view exists) — rendered, no-op on click.
- The Topbar is shared chrome rendered for all views; it must keep behaving sensibly when no
  workstream is selected (tabs hidden, as today).

### 4.2 `BoardView.svelte` (restyled, behavior preserved)
- **Filter bar** (new, top of the board): `Due Date`, `Assignee`, `Priority` pill-dropdowns
  + `Advance Filters` (sliders icon) — all decorative — and a functional `+ Add New` primary
  button that calls the existing `addTask(currentWorkstream.id, { title })` flow (inline title
  entry, same pattern the current Topbar uses).
- **Column headers**: colored rounded chip per status = status dot/icon + `STATUS_LABEL` +
  count, with a decorative `…` menu and the functional `+` (per-column add, existing flow).
  Colors reuse `Pills`' `STATUS_COLOR` (backlog gray, todo slate, in_progress blue,
  in_review purple, done green), tinted background + solid text/dot.
- **Drag-and-drop preserved exactly**: same Sortable wiring, `data-status` on the column drop
  target, `data-task-id` / `data-sort-key` on each card, same `handleEnd` / `moveTask` logic,
  same re-init on workstream change.

### 4.3 `TaskCard.svelte` (new)
Props: `task: Task`, `labelById: Record<string, Label>`. Emits/handles click → `openTask(task.id)`.
Renders the drag attributes on its root (`data-task-id`, `data-sort-key`) so Sortable still works.

Layout (top to bottom):
- **Title row**: semibold title; decorative `…` top-right; an animated **spinner** icon shown
  only when `task.status === 'in_progress'`.
- **Assignee row**: muted `user` icon + initials avatar (`initials(task.assignee_id)`), or a
  `–` placeholder avatar when unassigned.
- **Date row**: `calendar` icon + formatted `due_date` (date; include time when the timestamp
  carries one). Append a red **Overdue** badge when `due_date < now` and `status !== 'done'`.
  Row hidden when there is no due date.
- **Priority row**: colored `flag` icon + `"{Priority} Priority"` (capitalized), color-mapped
  from `urgent/high/medium/low`; `"No Priority"` (muted) when null.
- **Label chips**: render when `task.labels` is non-empty, using each label's color (reuse the
  `Pills` label style).

### 4.4 `Icon.svelte` (extended)
Add Lucide path data for: `flag`, `user`, `loader` (spinner), `sliders`, `pencil`, `share-2`,
`zap`. No API change to the component.

### 4.5 `styles.css`
Add a `@keyframes` spin + a `.workos-spin` helper for the in-progress loader. All other styling
stays inline Tailwind to match the existing code.

## 5. Data mapping

All fields already exist on `Task` (Phase 1). No new data.

| Card element | Source |
|---|---|
| Title | `task.title` |
| Spinner | `task.status === 'in_progress'` |
| Assignee | `task.assignee_id` → `initials()` / `displayName()` / `directory` |
| Date + Overdue | `task.due_date` vs `Date.now()`, `task.status` |
| Priority | `task.priority` (`urgent/high/medium/low`) |
| Labels | `task.labels` → `labelById` |
| Column color | status → `STATUS_COLOR` |

## 6. Theming & accessibility

- Light + dark variants for every new surface (cards, header chips, topbar, filter bar),
  following the existing `dark:` utility pattern.
- Decorative buttons remain real `<button>`s but are inert; give them `aria-disabled`/`title`
  hints where helpful so they don't read as broken to assistive tech.
- Color is never the only signal: priority/overdue also carry text; status headers carry labels.

## 7. Testing & verification

- Type-check: `svelte-check` clean (no new TS errors).
- Unit (where logic warrants): a small pure helper for date/overdue formatting is unit-testable;
  extract it so `TaskCard` stays thin. Existing store/roles tests must stay green.
- Manual browser smoke on the running Osool instance: board renders in the new style, drag-drop
  still moves/persists a card, `+ Add New` and per-column `+` create tasks, Board/List tabs
  switch, decorative controls are inert, dark mode looks right.

## 8. Risks

- **Drag-drop regression** from restructuring card markup — mitigated by keeping the exact
  data attributes and Sortable wiring, and smoke-testing a move.
- **Topbar shared across views** — must not break the List view or the no-workstream state.
- **Decorative-looks-broken** — inert controls styled to match the mockup; acceptable per the
  user's "decorative for now" choice, revisited when those features land.

## 9. Files touched

- `src/lib/components/workos/chrome/Topbar.svelte` (rebuilt)
- `src/lib/components/workos/views/BoardView.svelte` (restyled; filter bar; column headers)
- `src/lib/components/workos/views/TaskCard.svelte` (new)
- `src/lib/components/workos/ui/Icon.svelte` (glyphs)
- `src/lib/components/workos/styles.css` (spin keyframe)
- (optional) a tiny date/overdue helper module + its test
