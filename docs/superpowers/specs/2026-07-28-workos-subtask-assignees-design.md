# WorkOS — Subtask Assignees (Design)

> Brainstormed + approved 2026-07-28 on branch `osool`. Subtasks gain their own
> assignees, defaulted from the parent task, with a two-way subset invariant
> against the parent's assignee list.

## Goal

Every subtask can carry assignees. On creation it defaults to the parent task's
first assignee. Assigning someone who is not on the parent task automatically
adds them to the parent — subject to a permission gate (§4) — and removing
someone from the parent cascades their removal from all its subtasks.

## Decisions (locked with user)

| # | Decision | Choice |
|---|---|---|
| 1 | Cardinality | **Multiple assignees** per subtask (mirrors parent `assignee_ids`) |
| 2 | Parent removal edge | **Cascade-remove** from all subtasks of that task |
| 3 | Minimum | **Zero allowed** on subtasks (parent keeps its min-1 rule) |
| 4 | Existing rows | **No backfill** — pre-feature subtasks stay unassigned |
| 5 | Architecture | **JSON column + router orchestration** (approach A) |
| 6 | Auto-add gate | Expanding the parent list requires `task.write` on the parent (§4) |
| 7 | Notification | New type `subtask_assigned`, gated by the existing `assigned` admin toggle |

**Invariant: subtask assignees ⊆ parent `assignee_ids`.** Enforced in both
directions — auto-add on grow (subtask side), cascade-remove on shrink (parent
side). The only rows that may violate it are pre-migration rows left at `[]`
(vacuously fine) — the invariant is maintained from first write onward.

## 1. Data model + migration

- `WorkosSubtask` ([models/workos.py:496](../../backend/open_webui/models/workos.py))
  gains `assignee_ids = Column(JSON, default=list)` — same shape as
  `WorkosTask.assignee_ids`.
- `SubtaskModel` gains `assignee_ids: list = []`.
- One Alembic migration: add the nullable JSON column, no data backfill.
  (Server code treats `NULL` and `[]` identically, matching the task model.)
- `SubtasksDao.insert` accepts `assignee_ids`; `update_fields` passes it
  through like any other field. No invariant logic in the DAO (approach A).

## 2. Backend endpoints ([routers/workos.py](../../backend/open_webui/routers/workos.py))

### `POST /tasks/{task_id}/subtasks`
- `SubtaskCreateForm` gains `assignee_ids: Optional[list] = None`.
- Absent or empty → server defaults to `[parent.assignee_ids[0]]`.
- Present → dedupe (preserve order), `validate_assignees` (same
  workstream-visibility rule as tasks, G1), then the auto-add step (§3).

### `PATCH /subtasks/{subtask_id}`
- `SubtaskUpdateForm` gains `assignee_ids: Optional[list] = None`.
- `None` = untouched; `[]` = explicit clear (allowed). Pydantic keeps the
  distinction; the handler must use `exclude_unset`-style handling for this
  field rather than `exclude_none` blindly dropping `[]` — mirror how the
  parent form treats lists.
- Same dedupe → validate → auto-add pipeline as create.

### `PATCH /tasks/{task_id}` (cascade)
- After a successful parent update where `assignee_ids` shrank: for every
  subtask of the task whose list intersects the removed ids, strip those ids,
  persist, and emit `workos:subtask.updated` per changed row.
- No notifications on removal (matches current parent behavior).
- Runs after the existing update/emit/activity/notify block so parent events
  keep their current order.

## 3. Auto-add to parent

When a subtask create/patch introduces assignees not on the parent:

1. Gate: caller must pass `require_task_writable` on the parent (§4). 403
   detail: `'Only task editors can add new people to the task.'`
2. Append missing ids to the **end** of the parent's `assignee_ids` (the
   parent's first assignee — the default source — never shifts).
3. Reuse the parent-update side-effect pieces exactly as `update_task` does:
   `Tasks.update_fields`, `workos:task.updated` emit, and
   [`task_change_activities`](../../backend/open_webui/models/workos.py) (its
   `assignee_ids` branch already produces the added/removed activity row).
4. Do **not** send the parent-level `assigned` notification for auto-added
   users — they receive `subtask_assigned` instead (§5). No double-notify.

## 4. Permissions

- Subtask create is open to any task-visible user (existing posture,
  unchanged). Unconditional auto-add would therefore let any task-visible
  user self-assign into the parent's assignee list — and parent assignment
  grants `task.write` — a privilege-escalation path. Hence:
  - **Choosing assignees from the parent's existing list** → current subtask
    gates only (`require_task_visible` on create, `require_subtask_writable`
    on patch).
  - **Expanding the parent list (auto-add)** → additionally requires
    `require_task_writable` on the parent. Creators, assignees, and workspace
    managers keep the seamless flow; others get the 403 above.
- `subtask.write` capability chain is **unchanged**: the subset invariant
  means a subtask assignee is always a parent assignee, which the chain
  already covers.
- Assignment still confers **no visibility** (assignment ≠ access).
- Doc-sync obligation: update
  [2026-06-26-workos-access-control.md](2026-06-26-workos-access-control.md)
  (§4 subtask rows + a data-model note on the invariant and the auto-add
  gate) as part of implementation.

## 5. Notifications

- New type `subtask_assigned`, sent only to **newly added** subtask
  assignees (diff vs the subtask's previous list; never re-sent on unrelated
  edits). Recipients pass through the existing `notify()` visibility filter.
- Copy: `"{actor} assigned you a subtask on {task_key}"`; `data` carries the
  subtask title for richer inbox rows.
- Admin rules: `_notif_enabled` maps `subtask_assigned` → the existing
  `assigned` toggle (category map; no new admin knob, no RulesTab change).
- Inbox treatment: counts as "Needs you" (`inbox.ts` predicate), same teal
  glyph family as `assigned` (`TypeGlyph`), verb wiring in
  `notifications.ts`, `FeedRow`, `NeedsYouCard`, and the MyWork activity
  mapping (~6 small frontend touchpoints).

## 6. Frontend

- `SubtasksPanel.svelte` row (approved mockup, 2026-07-28):
  - Right-aligned avatar stack (reuse the existing avatar-group component
    from the multi-assignee work) before the delete button.
  - Unassigned → dashed ghost `user-plus` button.
  - Click → assignee popover (same multi-select picker pattern as task
    detail, sourced from the `directory` store) with two groups:
    **"On this task"** (parent assignees) and **"Everyone else"** (rest of
    directory). Picking from "Everyone else" shows a `+ added to task` pill
    and a footer hint ("Picking someone new also adds them to the task").
  - Users without `task.write` on the parent see only the "On this task"
    group — the auto-add path is hidden, not disabled.
- New-subtask input unchanged; the server default (parent's first assignee)
  shows up on the created row via the store/realtime update.
- Plumbing: `types.ts` Subtask gains `assignee_ids: string[]`; `api.ts`
  create/update pass it; `store.ts` needs no new event types — cascade and
  auto-add arrive over existing `workos:subtask.updated` /
  `workos:task.updated` events.

## 7. Testing

Backend (pytest, `.venv` python):
- create defaults to parent's first assignee; explicit list respected.
- create/patch auto-add: parent grows (appended at end), activity row
  written, `subtask_assigned` sent to new ids only, no parent `assigned`.
- auto-add without `task.write` → 403; within-parent assignment without
  `task.write` → allowed.
- cascade: parent shrink strips ids from subtasks + emits per-row updates.
- `[]` clear allowed; invisible id → 400 via `validate_assignees`;
  `subtask_assigned` respects the `assigned` rules toggle.

Frontend (vitest):
- `notifications.ts` summary + `inbox.ts` needs-you for `subtask_assigned`.
- store handling of subtask update events carrying `assignee_ids`.

## Non-goals (YAGNI)

- Subtasks in My Work / cross-task "my subtasks" queries.
- Subtask assignee filters in board/list views.
- Per-subtask assignment activity rows (parent-level activity only).
- Backfill of pre-feature subtasks.
