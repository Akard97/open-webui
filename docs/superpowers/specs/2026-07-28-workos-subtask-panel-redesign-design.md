# WorkOS Subtask Panel Redesign — Design

**Date:** 2026-07-28
**Status:** Approved (direction B — "Teal checklist" mockup)
**Component:** `src/lib/components/workos/views/detail/SubtasksPanel.svelte`

## Goal

Enhance the subtask list UI/UX inside the task detail drawer. The grouped assignee
dropdown (On this task / Everyone else, auto-add hint) is explicitly liked and moves
over **verbatim** — no changes to its markup, logic, or permissions gating.

## Scope

- Rework `SubtasksPanel.svelte` internals only. No backend changes.
- No store/API changes: `editSubtask` already accepts `title`, `completed`,
  `sort_key`; `addSubtask` / `removeSubtask` unchanged. All mutations stay
  optimistic-with-rollback; failures surface via the existing
  `notifyFailed` toast ("Couldn't update — try again").
- One new pure helper module: `src/lib/components/workos/lib/subtaskPanel.ts`
  exporting:
  - `computeSortKey(list, fromIndex, toIndex)` → `Array<{ id, sort_key }>` —
    single-element in the normal midpoint case, full-list plan when
    renumbering, empty array when `fromIndex === toIndex`.
  - `resolveRename(current, draft)` → `{ action: 'commit', title } | { action: 'revert' }`.
- Panel renders a **derived list sorted by `sort_key` ascending**. Today the store
  appends realtime/created subtasks at the end and never re-sorts; sorting in the
  panel fixes ordering drift and makes reorder purely data-driven (a realtime
  `subtask.updated` carrying a new `sort_key` re-sorts automatically).

## Visual design (direction B)

### Progress header
- Hidden when there are 0 subtasks.
- Segmented bar: one flex block per subtask, 3px gaps, 6px tall, rounded.
  `completed_count` segments fill teal left→right; the rest are neutral gray.
  The fill is count-based (leftmost N segments), not per-row status.
- Fallback: when subtask count > 24, render a single continuous bar
  (completed/total width) instead of segments.
- Right side: rectangle badge (badge=rectangle rule) reading `1/3 done` —
  teal text on teal tint, dark-mode equivalent.
- The segmented form is deliberately distinct from the three existing WorkOS
  progress bars (never-unify rule); it is a new, visually different species.

### Rows
- Borderless; soft neutral fill (light: gray-50-ish, dark: gray-900-ish),
  hover one step darker; rounded-lg; comfortable padding (~10px 12px).
- Custom round checkbox, 18px: unchecked = 2px neutral ring; checked = teal fill,
  white check, ~150ms scale "pop" animation. Implemented as a button with
  `role="checkbox"`, `aria-checked`, and an aria-label (the shadcn square
  Checkbox is intentionally not used here — checklist look approved in mockup).
- Completed rows: title strikethrough + gray; row **stays in place** (no
  sinking/regrouping). Row fill slightly faded.
- Row right side: assignee dropdown (unchanged), then delete.
- Hover-reveal: drag handle (left edge) and trash (right edge) are
  opacity-0 until row hover or focus-within; on touch devices
  (`@media (hover: none)`) both are always visible.

### Quick-add
- Persistent input row pinned after the list (replaces the "Add subtask"
  toggle button). Plus icon, borderless input, 1.5px border on the row;
  border turns teal on focus-within.
- Enter: create (trimmed; empty = no-op), clear input, **keep focus** so the
  user can chain entries. Esc: clear + blur. While a create is in flight the
  input stays enabled (optimistic store append handles ordering).

### Empty state
- When 0 subtasks: centered icon + "Break this task into smaller steps." +
  hint line ("Type below — Enter adds the next one."). Quick-add remains visible.

### Theming
- Light + dark via existing workos tokens / Tailwind dark: variants.
- Teal = existing Osool primary teal tokens; no new palette entries.

## Interactions

### Inline rename
- Click on the title (completed or not) swaps it to an in-place text input,
  pre-filled with the current title.
- Enter or blur commits via `editSubtask(id, { title })` with trimmed value;
  empty or unchanged value reverts silently. Esc reverts.
- Optimistic; failure rolls back in store and toasts.

### Toggle complete
- Unchanged semantics: `editSubtask(id, { completed })`. Row stays in place.

### Drag reorder (desktop only)
- Pointer-event-based drag on the handle only (same approach family as the
  Timeline bar drag; HTML5 DnD deliberately avoided).
- Visuals during drag: dragged row at 50% opacity; 2px teal drop-indicator
  line between rows at the current target position.
- On drop, compute the new key with `computeSortKey`:
  - between neighbors → midpoint `(prev + next) / 2`
  - dropped first → `first − 1000`
  - dropped last → `last + 1000`
  - degenerate midpoint (float precision: result not strictly between
    neighbors) → renumber the whole list to `(index + 1) * 1000` via one
    `editSubtask` per row, dragged row included at its new position.
- Persist via `editSubtask(id, { sort_key })`; the sorted derived view makes
  the move appear instantly (optimistic) and reconciles on realtime echo.
- Mobile: no drag handle rendered; order is read-only there.
- Keyboard: when the drag handle has focus, ArrowUp/ArrowDown moves the row
  one position (same `computeSortKey` path).

### Delete
- Unchanged: per-row trash, no confirmation dialog (parity with current panel).

### Permissions
- UI does not pre-gate actions by role (parity with current panel); the server
  remains authoritative and failures roll back + toast. The assignee dropdown
  keeps its existing `canExpand` gating untouched.

## Error handling

- All mutations: optimistic store update → rollback on rejection → `notifyFailed`
  toast. This is the existing pattern; the redesign adds no new error paths
  except the renumber fan-out, where each row PATCH failing independently
  rolls back that row and toasts once (guard against toast spam: fire at most
  one toast per renumber batch).

## Testing (TDD)

- `subtaskPanel.test.ts` (vitest, pure):
  - midpoint between neighbors
  - move to top / bottom
  - single-item and two-item lists
  - degenerate midpoint triggers renumber output (`(i+1)*1000` full-list plan)
  - no-op when `fromIndex === toIndex`
- Rename commit/revert logic: `resolveRename` unit-tested (trim, empty,
  unchanged, whitespace-only).
- Component-level behavior verified by browser smoke after build (checkbox
  pop, hover reveals, quick-add chaining, drag, dark mode, mobile).

## Out of scope

- Assignee dropdown changes of any kind.
- Backend/router/model changes.
- Completed-group collapsing or auto-sinking (explicitly rejected — C chosen
  for placement: completed stays in place).
- Subtask due dates, descriptions, or nesting.
