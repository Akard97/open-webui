# WorkOS — Multiple Assignees per Task

**Date:** 2026-06-26
**Status:** Approved design, ready for implementation plan
**Scope:** Extend WorkOS tasks from a single assignee to a flat list of equal assignees, across DB, API, activity log, notifications, and frontend UI.

## Goal

A WorkOS task currently has at most one assignee (`assignee_id`). Users need to assign **multiple** people to a task. Assignees are a flat set of equals — there is no "primary" or "owner" among them.

## Locked Decisions

- **Model:** Flat list, all assignees equal. No "primary" concept.
- **Cap:** No hard limit on the number of assignees.
- **Notifications:** On any change to a task's assignee set (and on create with assignees), send the `assigned` notification to **all current assignees** (excluding the actor). This intentionally re-notifies people already on the task when the set is edited.
- **Old column:** Drop `assignee_id` entirely. The feature is not externally released, so no dead column is kept.
- **Filtering:** Assignee filtering stays client-side, as today. No new server-side assignee filter endpoint.

## Storage Choice

The `workos_task` table already has `labels = Column(JSON, default=list)`. We reuse that exact pattern for assignees: a JSON list column directly on the row. This serializes for free through `TaskModel`'s `from_attributes` config and adds **no joins** to any task-listing endpoint. A junction table was considered and rejected as higher blast-radius (extra query/assembly on every task read) for no benefit given flat, uncapped, client-side-filtered assignees.

## Design by Layer

### 1. Backend DB model — `backend/open_webui/models/workos.py`

`WorkosTask` (~line 470):
```python
# was: assignee_id = Column(Text, nullable=True)
assignee_ids = Column(JSON, default=list)
```

`TaskModel` (~line 519):
```python
# was: assignee_id: Optional[str] = None
assignee_ids: list = []
```

`_participants()` helper (~line 822-832):
```python
# was: if task.assignee_id: out.add(task.assignee_id)
out.update(task.assignee_ids or [])
```

`_ACTIVITY_FIELDS` (~line 828-836): map `'assignee_ids': 'assignee_changed'` (was `'assignee_id'`).

### 2. Migration — `c?d?e?f?_add_workos_multi_assignee.py`

`down_revision = 'b4c5d6e7f8a9'`.

`upgrade()`:
1. `op.add_column('workos_task', sa.Column('assignee_ids', sa.JSON(), nullable=True))`.
2. Backfill via a data migration: for each row, set `assignee_ids = [assignee_id]` when `assignee_id` is not null, else `[]`. (Use a lightweight `op.get_bind()` + `SELECT id, assignee_id` / `UPDATE`, encoding the list as JSON text for SQLite.)
3. Drop the index and the old column with SQLite-safe batch ops:
   ```python
   op.drop_index('ix_workos_task_assignee_id', table_name='workos_task')
   with op.batch_alter_table('workos_task') as batch:
       batch.drop_column('assignee_id')
   ```

`downgrade()`: re-add `assignee_id` (Text, nullable), backfill from the first element of `assignee_ids` (or null when empty), re-create `ix_workos_task_assignee_id`, then drop `assignee_ids`.

### 3. Backend API — `backend/open_webui/routers/workos.py`

- `TaskCreateForm`: `assignee_id: Optional[str] = None` → `assignee_ids: Optional[list[str]] = None`.
- `TaskUpdateForm`: same swap.
- `TasksDao.insert`: parameter `assignee_ids: list[str] = None` → normalize to `[]`, pass to `WorkosTask`.
- Create endpoint: pass `assignee_ids=form.assignee_ids or []`. If non-empty, notify those users (`type='assigned'`, recipients = `set(assignee_ids) - {actor}`).
- Update endpoint:
  - When `'assignee_ids' in fields` and the set changed → notify all **current** assignees: `recipients = set(updated.assignee_ids) - {user.id}`, `type='assigned'`.
  - `status_changed` recipients become `{updated.created_by_id} | set(updated.assignee_ids)`.

### 4. Activity log

When writing the `assignee_changed` activity, compute **added** and **removed** sets (diff of before/after lists) and store them in the activity `data` (e.g. `{'added': [...], 'removed': [...]}`) instead of `{from, to}` scalars. This lets the UI render a readable diff.

`ActivityItem.svelte` (`assignee_changed` branch): render `"{who} assigned {names(added)}"` and/or `"removed {names(removed)}"` from `d.added` / `d.removed`, instead of the single `displayName(d.to)`.

### 5. Frontend — `src/lib/components/workos/`

- **lib/types.ts**: `Task.assignee_id?: string | null` → `assignee_ids: string[]`.
- **lib/api.ts**: `createTask` body and `updateTask` allowed-fields swap `assignee_id` → `assignee_ids`.
- **lib/store.ts**: `addTask` field, `editTask` passthrough swap to `assignee_ids`. `displayName('Unassigned')` helper stays for empty-list rendering.
- **views/detail/AssigneeField.svelte**: convert the single-select dropdown to a **multi-select** — each member row is a toggle (checkmark when selected); toggling builds the new array and calls `editTask(task.id, { assignee_ids: [...] })`. Header shows stacked avatars of current assignees, or "Unassigned" when empty.
- **views/TaskCard.svelte**: footer renders a **stacked/overlapping avatar group** with wrap or "+N" overflow, instead of one avatar + name. "Unassigned" when empty.
- Any client-side assignee filter (e.g. "my tasks"): `task.assignee_id === id` → `task.assignee_ids.includes(id)`.

### 6. Testing

Follow the existing WorkOS TDD pattern.

- **Backend:** DAO insert/update with assignee lists; create + update notification fan-out to all current assignees (actor excluded); `assignee_changed` activity carries correct `added`/`removed`; `_participants()` includes all assignees. Run with the `.venv` python per the existing WorkOS test setup.
- **Frontend:** AssigneeField multi-select toggle adds/removes ids and calls `editTask` with the right array; store update; TaskCard renders an avatar group / overflow / "Unassigned".

No live Vite dev server for smoke testing without explicit user approval (per project hard rule). Manual browser smoke is a follow-up the user runs or approves.

## Out of Scope (YAGNI)

- No "primary" assignee or ordering semantics.
- No per-task assignee cap.
- No new server-side assignee filter endpoint.
- No bulk re-assignment UI.
