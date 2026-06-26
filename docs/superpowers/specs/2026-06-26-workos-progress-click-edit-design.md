# WorkOS — Click-to-edit task progress (detail view)

**Date:** 2026-06-26
**Status:** Approved design, pending implementation plan

## Summary

Replace the current "Edit progress" button + range slider in the WorkOS task
detail view with two parallel, direct interactions:

1. **The progress bar** — click it (or a small pencil affordance) to *arm* it,
   then click or click-and-drag to set the value.
2. **The percentage text** — click the `%` number to turn it into an input and
   type an exact value.

This is a frontend-only change. No backend, API, store, or data-model changes.

## Scope

- **In scope:** the Progress row of
  `src/lib/components/workos/views/TaskDetail.svelte`
  (currently lines ~237–286).
- **Out of scope:**
  - Card/board editing — task cards remain read-only.
  - Editing when a task has subtasks — progress stays derived and read-only.
  - Drag without an explicit arm step.
  - Snap-to-5 (old slider behavior).
  - Any change to how subtask-derived progress is calculated.

### Editability rule (unchanged)

Progress is editable **only when the task has no subtasks**
(`(t.subtask_total ?? 0) === 0`). When subtasks exist, the row shows
"X/Y subtasks complete" and neither the bar nor the `%` text is interactive —
identical to today.

## Behavior

### 1. The bar: arm → click / drag

- **Not armed (editable):** the combined planned+actual bar looks editable
  (pointer cursor + subtle hover hint). A small pencil affordance sits beside
  it. Clicking the **bar** *or* the **pencil** *arms* the bar.
  - The first (arming) click does **not** change the value — it only enters the
    armed state.
- **Armed:** a draggable handle appears at the current `%`.
  - **Click** anywhere on the bar sets progress to that position.
  - **Click-and-drag** scrubs the value live.
  - Position → value: `round((pointerX − barLeft) / barWidth × 100)`, clamped to
    `0–100`.
- **Live vs. save:** while dragging, the displayed value updates from local state
  only (no network call per pixel). On pointer release, the value is saved once.
  A plain click (no drag) saves on release as well.
- **Exit armed state:** clicking outside the bar, pressing `Escape`, or pressing
  `Enter`. Exiting only removes the handle/armed styling — the value is already
  persisted from the last click/drag.

### 2. The percentage text: click → type

- Available **whenever progress is editable**, independent of whether the bar is
  armed (a parallel quick path to an exact number).
- Click the `%` number → it becomes a focused, pre-selected
  `<input type="number">` pre-filled with the current value.
- **Commit:** `Enter` or blur — value clamped to `0–100`, then saved.
- **Cancel:** `Escape` — revert, no save.
- **Invalid/empty:** revert to the last value, no save.

## State (local to `TaskDetail.svelte`)

| State | Type | Purpose |
|-------|------|---------|
| `barArmed` | `boolean` | Replaces today's `editingProgress`. True while the bar is armed. |
| `dragValue` | `number \| null` | Live value during a drag; `null` when not dragging (display falls back to `t.progress`). |
| `editingPercent` | `boolean` | True while the `%` text is in input mode. |
| `percentDraft` | `string` | Current text-input draft value. |

## Interaction details

- **Computing value from pointer:** read the bar element's bounding rect on
  pointerdown/move; clamp the fraction to `[0, 1]` before scaling to `0–100` and
  rounding to the nearest integer.
- **Drag handling:** pointerdown on an armed bar starts a drag; pointermove
  updates `dragValue` (local display only); pointerup ends the drag and saves
  via the existing store function. Use pointer events and capture so drags that
  leave the bar still track. Prevent text selection during drag.
- **Outside-click / key handling:** while armed, a window-level listener handles
  click-outside to exit; `Escape`/`Enter` exit the armed state.
- **Displayed value:** the bar's actual fill and the `%` text show
  `dragValue ?? t.progress` so the number and fill move together during a drag.

## Save path (unchanged)

Both interactions call the existing store function:

```ts
editTask(t.id, { progress }) // → PATCH /tasks/{id}
```

- Optimistic update + rollback is already implemented in
  `src/lib/components/workos/lib/store.ts`.
- The backend (`backend/open_webui/routers/workos.py`) already validates
  `0 <= progress <= 100`.
- **No backend, API (`api.ts`), or store changes are required.**

## Accessibility

- When editable, the bar is keyboard-focusable and exposed as
  `role="slider"` with `aria-valuenow` / `aria-valuemin="0"` /
  `aria-valuemax="100"`.
- While armed, `←` / `→` adjust the value by 1 and save.
- The `%` text path uses a native `<input type="number">`.

## Files touched

- `src/lib/components/workos/views/TaskDetail.svelte` — the only file expected to
  change. The current edit block (button + range slider, ~lines 265–284) is
  removed; the bar markup (~lines 238–264) gains the armed/click/drag interaction
  and the clickable `%` input.

## Risks / notes

- **Accidental edits:** mitigated by the explicit arm-first step.
- **Drag save spam:** mitigated by saving only on pointer release.
- **Coexistence of the two paths:** the `%` input and the armed bar both write
  the same `progress` field via the same store function, so they cannot diverge;
  the displayed value derives from a single source.
