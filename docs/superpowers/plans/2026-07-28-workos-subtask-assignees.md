# WorkOS Subtask Assignees Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Subtasks carry their own `assignee_ids` list, defaulted from the parent task's first assignee, with a two-way subset invariant against the parent (auto-add on grow gated by `task.write`, cascade-remove on parent shrink) and a new `subtask_assigned` notification.

**Architecture:** JSON column on `workos_subtask` mirroring the parent task's `assignee_ids`; all invariant logic lives in router endpoints (`backend/open_webui/routers/workos.py`) where emit/activity/notify already live. Frontend reuses `AssigneeAvatars` + the `DropdownMenu` picker pattern from `AssigneeField`.

**Tech Stack:** FastAPI + SQLAlchemy async + Alembic (backend), Svelte 5 + shadcn-svelte (frontend), pytest + vitest.

**Spec:** `docs/superpowers/specs/2026-07-28-workos-subtask-assignees-design.md`

## Global Constraints

- Invariant: subtask assignees ⊆ parent `assignee_ids` from first write onward (pre-migration rows may stay `[]`).
- Auto-add 403 detail string, exact: `'Only task editors can add new people to the task.'`
- `subtask_assigned` maps to the existing `assigned` toggle in `WORKOS_RULES.notifications` — no new admin knob, no RulesTab change.
- Auto-added users get `subtask_assigned` only — never a parent-level `assigned` notification from the auto-add path.
- Parent's first assignee never shifts: auto-add appends missing ids at the END of the parent list.
- Zero assignees allowed on subtasks (`[]` valid); parent keeps its min-1 rule.
- Backend tests run with `backend/.venv/Scripts/python.exe` (NOT system python — torch DLL issue on this machine).
- NEVER dispatch haiku-model subagents for Svelte edits (cp1252 corruption history).
- All work on branch `osool`. No Docker rebuild for frontend changes (user runs Vite hot-reload). Do NOT start a Vite dev server.

---

### Task 1: Model layer + migration

**Files:**
- Modify: `backend/open_webui/models/workos.py` (WorkosSubtask table ~line 496, SubtaskModel ~line 548, SubtasksDao.insert ~line 752)
- Create: `backend/open_webui/migrations/versions/b0c1d2e3f4a5_workos_subtask_assignees.py`
- Test: `backend/open_webui/test/workos/test_models_task.py` (append)

**Interfaces:**
- Produces: `WorkosSubtask.assignee_ids` (JSON column, default list); `SubtaskModel.assignee_ids: list = []`; `SubtasksDao.insert(..., assignee_ids: Optional[list] = None, ...)` keyword arg.

- [ ] **Step 1: Write the failing test**

Append to `backend/open_webui/test/workos/test_models_task.py`:

```python
@pytest.mark.asyncio
async def test_subtask_assignee_ids_roundtrip():
    team, s = await _stream()
    task = await Tasks.insert(s.id, team.id, team.key, 'Parent', 'u1', assignee_ids=['u1', 'u2'])

    st = await Subtasks.insert(task.id, 'Child', 'u1', assignee_ids=['u2'])
    assert st.assignee_ids == ['u2']

    # default: no assignees passed -> empty list, not None
    st2 = await Subtasks.insert(task.id, 'Child 2', 'u1')
    assert st2.assignee_ids == []

    updated = await Subtasks.update_fields(st.id, {'assignee_ids': ['u1', 'u2']})
    assert updated.assignee_ids == ['u1', 'u2']

    cleared = await Subtasks.update_fields(st.id, {'assignee_ids': []})
    assert cleared.assignee_ids == []
```

The file already has an async `_stream()` helper (line 12) returning `(team, workstream)`; reuse it. Extend the existing import (line 3) to `from open_webui.models.workos import Teams, Workspaces, Workstreams, Labels, Tasks, Subtasks`.

- [ ] **Step 2: Run test to verify it fails**

Run (from `C:\Projects\open-webui\backend`):
```bash
.venv/Scripts/python.exe -m pytest open_webui/test/workos/test_models_task.py::test_subtask_assignee_ids_roundtrip -v
```
Expected: FAIL — `TypeError: SubtasksDao.insert() got an unexpected keyword argument 'assignee_ids'`

- [ ] **Step 3: Add column + model field + DAO param**

In `backend/open_webui/models/workos.py`:

WorkosSubtask table (after the `completed` column, ~line 502):
```python
class WorkosSubtask(Base):
    __tablename__ = 'workos_subtask'

    id = Column(Text, primary_key=True, unique=True)
    task_id = Column(Text)
    title = Column(Text)
    completed = Column(Boolean, default=False)
    assignee_ids = Column(JSON, default=list)
    sort_key = Column(Float, default=0.0)
    created_by_id = Column(Text, nullable=True)
    completed_at = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)
```
(`JSON` is already imported — `WorkosTask.assignee_ids` uses it.)

SubtaskModel (~line 548):
```python
class SubtaskModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_id: str
    title: str
    completed: bool = False
    assignee_ids: list = []
    sort_key: float
    created_by_id: Optional[str] = None
    completed_at: Optional[int] = None
    created_at: int
    updated_at: int
```

SubtasksDao.insert (~line 752):
```python
    async def insert(
        self, task_id: str, title: str, created_by_id: Optional[str],
        *, assignee_ids: Optional[list] = None, sort_key: Optional[float] = None,
        db: Optional[AsyncSession] = None,
    ) -> SubtaskModel:
        async with get_async_db_context(db) as db:
            now = _now()
            row = WorkosSubtask(
                id=_id(), task_id=task_id, title=title, completed=False,
                assignee_ids=assignee_ids or [],
                sort_key=sort_key if sort_key is not None else float(now),
                created_by_id=created_by_id, completed_at=None, created_at=now, updated_at=now,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return SubtaskModel.model_validate(row)
```

`update_fields` needs no change — it already sets arbitrary fields via `setattr`.

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/Scripts/python.exe -m pytest open_webui/test/workos/test_models_task.py -v
```
Expected: PASS (all tests in file — the schema comes from `Base.metadata.create_all` in conftest, so no migration needed for tests)

- [ ] **Step 5: Write the migration**

Create `backend/open_webui/migrations/versions/b0c1d2e3f4a5_workos_subtask_assignees.py`:

```python
"""workos subtask assignees

Adds ``workos_subtask.assignee_ids`` as a JSON list (mirroring
``workos_task.assignee_ids``). No backfill by design — pre-feature
subtasks stay unassigned (spec 2026-07-28, decision 4).

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-07-28 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b0c1d2e3f4a5'
down_revision: Union[str, None] = 'a9b0c1d2e3f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workos_subtask', sa.Column('assignee_ids', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('workos_subtask') as batch:
        batch.drop_column('assignee_ids')
```

(Head verified 2026-07-28: `a9b0c1d2e3f4` is the current tip — nothing revises it.)

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/models/workos.py backend/open_webui/migrations/versions/b0c1d2e3f4a5_workos_subtask_assignees.py backend/open_webui/test/workos/test_models_task.py
git commit -m "feat(workos): subtask assignee_ids column, model field, DAO support"
```

---

### Task 2: Create-subtask — default, explicit assignees, auto-add gate, notification

**Files:**
- Modify: `backend/open_webui/routers/workos.py` (SubtaskCreateForm ~line 617, `_notif_enabled` ~line 928, `create_subtask` ~line 1315, new helper above the subtask endpoints ~line 1299)
- Test: `backend/open_webui/test/workos/test_router_subtask_assignees.py` (create)

**Interfaces:**
- Consumes: `SubtasksDao.insert(..., assignee_ids=...)` from Task 1; existing `validate_assignees(assignee_ids, workstream_id, db)`, `require_task_writable(user, task, stream, db)`, `task_change_activities(actor_id, before, after)`, `notify(request, db, *, recipients, actor, type, task, extra=...)`.
- Produces: `_expand_parent_assignees(request, user, task, stream, assignee_ids, db) -> TaskModel` (router-local helper, reused verbatim by Task 3); `_NOTIF_CATEGORY` dict; notification type string `'subtask_assigned'` with `data.subtask_title`; POST body field `assignee_ids`.

- [ ] **Step 1: Write the failing tests**

Create `backend/open_webui/test/workos/test_router_subtask_assignees.py`:

```python
import pytest

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_teams import _client, U1, U2
from open_webui.test.workos.test_router_task import _stream


async def _task(c, **body):
    """Team with members u1(owner)/u2/u3, one workstream, one task created by u1."""
    team, ws, s = await _stream(c)
    for uid in ('u2', 'u3'):
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': uid, 'role': 'member'})
    t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                      json={'title': 'T', 'assignee_ids': ['u1'], **body})).json()
    return team, ws, s, t


def _capture(monkeypatch, types):
    """Collect (type, user_ids) pairs emitted via notify()'s emit_users call."""
    sent = []

    async def _eu(event, payload, user_ids):
        if payload.get('type') in types:
            sent.append((payload['type'], tuple(sorted(user_ids)), payload.get('data', {})))

    monkeypatch.setattr(wr, 'emit_users', _eu)
    return sent


@pytest.mark.asyncio
async def test_create_defaults_to_parents_first_assignee(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c, assignee_ids=['u2', 'u3'])
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks", json={'title': 'A'})).json()
        assert st['assignee_ids'] == ['u2']


@pytest.mark.asyncio
async def test_create_empty_list_also_defaults(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                           json={'title': 'A', 'assignee_ids': []})).json()
        assert st['assignee_ids'] == ['u1']


@pytest.mark.asyncio
async def test_create_explicit_within_parent_kept_and_deduped(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c, assignee_ids=['u1', 'u2'])
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                           json={'title': 'A', 'assignee_ids': ['u2', 'u2']})).json()
        assert st['assignee_ids'] == ['u2']
        parent = (await c.get(f"/api/v1/workos/tasks/{t['id']}")).json()
        assert parent['assignee_ids'] == ['u1', 'u2']  # unchanged


@pytest.mark.asyncio
async def test_create_auto_adds_missing_assignee_to_parent_end(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)  # parent assignees ['u1']
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                           json={'title': 'A', 'assignee_ids': ['u3']})).json()
        assert st['assignee_ids'] == ['u3']
        parent = (await c.get(f"/api/v1/workos/tasks/{t['id']}")).json()
        assert parent['assignee_ids'] == ['u1', 'u3']  # appended at end, first stays first
        acts = (await c.get(f"/api/v1/workos/tasks/{t['id']}/activity")).json()
        changed = [a for a in acts if a['type'] == 'assignee_changed']
        assert changed and changed[0]['data'].get('added') == ['u3']


@pytest.mark.asyncio
async def test_create_notifies_subtask_assigned_not_parent_assigned(monkeypatch):
    sent = _capture(monkeypatch, {'subtask_assigned', 'assigned'})
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                     json={'title': 'Wire it', 'assignee_ids': ['u2']})
    types = [x[0] for x in sent]
    assert types == ['subtask_assigned']
    assert sent[0][1] == ('u2',)
    assert sent[0][2].get('subtask_title') == 'Wire it'


@pytest.mark.asyncio
async def test_default_assignee_is_actor_no_notification(monkeypatch):
    sent = _capture(monkeypatch, {'subtask_assigned'})
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)  # parent first assignee == u1 == actor
        await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks", json={'title': 'A'})
    assert sent == []


@pytest.mark.asyncio
async def test_non_task_writer_cannot_auto_add_on_create(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s, t = await _task(c)  # creator u1, assignees ['u1']; u2 plain member
    async with _client(monkeypatch, user=U2) as c:
        # u2 is task-visible so may create a subtask, but expanding the parent
        # list requires task.write -> 403 (blocks self-assign escalation).
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                         json={'title': 'sneak', 'assignee_ids': ['u2']})
        assert r.status_code == 403, r.text
        assert 'Only task editors' in r.text
        # within the parent's existing list: allowed
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                         json={'title': 'ok', 'assignee_ids': ['u1']})
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_create_invisible_assignee_rejected(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                         json={'title': 'A', 'assignee_ids': ['u9']})
        assert r.status_code == 400
        assert 'cannot access this workstream' in r.text


@pytest.mark.asyncio
async def test_subtask_assigned_respects_assigned_rules_toggle(monkeypatch):
    sent = _capture(monkeypatch, {'subtask_assigned'})
    rules = {'team_creation': 'all_users', 'default_workspace_visibility': 'team',
             'notifications': {'assigned': False}}
    async with _client(monkeypatch, user=U1, rules=rules) as c:
        _, _, _, t = await _task(c)
        await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                     json={'title': 'A', 'assignee_ids': ['u2']})
    assert sent == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python.exe -m pytest open_webui/test/workos/test_router_subtask_assignees.py -v
```
Expected: FAIL — defaults tests get `assignee_ids == []` (field ignored by the form), auto-add tests find parent unchanged / no 403.

- [ ] **Step 3: Implement**

In `backend/open_webui/routers/workos.py`:

**(a)** SubtaskCreateForm (~line 617):
```python
class SubtaskCreateForm(BaseModel):
    title: str
    assignee_ids: Optional[list] = None
    sort_key: Optional[float] = None
```

**(b)** `_notif_enabled` (~line 928) — category map so `subtask_assigned` rides the `assigned` admin toggle:
```python
# Notification types that share another type's WORKOS_RULES.notifications toggle.
_NOTIF_CATEGORY = {'subtask_assigned': 'assigned'}


def _notif_enabled(request: Request, type: str) -> bool:
    rules = request.app.state.config.WORKOS_RULES or {}
    cfg = rules.get('notifications') or {}
    return cfg.get(_NOTIF_CATEGORY.get(type, type), True)
```

**(c)** New helper, placed right after `_emit_parent_after_subtask` (~line 1304). The spec pins the 403 detail to `'Only task editors can add new people to the task.'` — the raw `task.write` capability string is different, so the gate is wrapped rather than called bare:
```python
async def _expand_parent_assignees(request: Request, user, task, stream, assignee_ids: list, db: AsyncSession):
    """Auto-add subtask assignees missing from the parent task (subset invariant).

    Expanding the parent list requires task.write: subtask creation is open to
    any task-visible user, and parent assignment itself grants task.write, so an
    ungated auto-add would let any visible user self-assign into edit rights.
    Returns the (possibly updated) parent task.
    """
    missing = [uid for uid in assignee_ids if uid not in (task.assignee_ids or [])]
    if not missing:
        return task
    try:
        await require_task_writable(user, task, stream, db)
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail='Only task editors can add new people to the task.')
    before = task.model_dump()
    updated = await Tasks.update_fields(
        task.id, {'assignee_ids': [*(task.assignee_ids or []), *missing]}, db=db
    )
    await emit_event('workos:task.updated', f'workos:workstream:{updated.workstream_id}', updated.model_dump())
    for act in task_change_activities(user.id, before, updated.model_dump()):
        row = await Activity.insert(task.id, updated.team_id, user.id, act['type'], act['data'], db=db)
        await _emit_task_room('workos:activity.created', updated,
                              {**row.model_dump(), 'workstream_id': updated.workstream_id, 'actor_id': user.id})
    return updated
```

**(d)** `create_subtask` (~line 1315) becomes:
```python
@router.post('/tasks/{task_id}/subtasks')
async def create_subtask(
    request: Request, task_id: str, form: SubtaskCreateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    task, stream = await require_task_visible(user, task_id, db)
    if not form.title.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Subtask title is required.')
    assignee_ids = list(dict.fromkeys(form.assignee_ids or []))
    if assignee_ids:
        await validate_assignees(assignee_ids, task.workstream_id, db)
        task = await _expand_parent_assignees(request, user, task, stream, assignee_ids, db)
    elif task.assignee_ids:
        assignee_ids = [task.assignee_ids[0]]
    subtask = await Subtasks.insert(
        task_id, form.title.strip(), user.id, assignee_ids=assignee_ids, sort_key=form.sort_key, db=db
    )
    payload = {**subtask.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id}
    await emit_event('workos:subtask.created', f'workos:workstream:{task.workstream_id}', payload)
    await _emit_parent_after_subtask(task_id, db)
    row = await Activity.insert(task_id, task.team_id, user.id, 'subtask_created', {'title': subtask.title}, db=db)
    await _emit_task_room('workos:activity.created', task, {**row.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id})
    if assignee_ids:
        await notify(request, db, recipients=set(assignee_ids), actor=user,
                     type='subtask_assigned', task=task, extra={'subtask_title': subtask.title})
    return subtask
```
Note the existing `task, _ =` unpack changes to `task, stream =` (the helper needs the stream). `notify()` already excludes the actor and filters recipients through `can_see_workstream`, so the default-assignee-is-actor case sends nothing.

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/python.exe -m pytest open_webui/test/workos/test_router_subtask_assignees.py -v
```
Expected: 9 PASS (Task 3's patch tests are not written yet).

Also run the untouched neighbors to catch regressions:
```bash
.venv/Scripts/python.exe -m pytest open_webui/test/workos/test_router_task.py open_webui/test/workos/test_router_write_gates.py open_webui/test/workos/test_router_multi_assignee.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_subtask_assignees.py
git commit -m "feat(workos): subtask create defaults + gated auto-add to parent + subtask_assigned notify"
```

---

### Task 3: Patch-subtask — assignee edits, auto-add, notify new only, clear-to-empty

**Files:**
- Modify: `backend/open_webui/routers/workos.py` (SubtaskUpdateForm ~line 622, `update_subtask` ~line 1333)
- Test: `backend/open_webui/test/workos/test_router_subtask_assignees.py` (append)

**Interfaces:**
- Consumes: `_expand_parent_assignees(...)` from Task 2 (exact signature above); PATCH body field `assignee_ids` (list; `[]` = clear).

- [ ] **Step 1: Write the failing tests**

Append to `test_router_subtask_assignees.py`:

```python
@pytest.mark.asyncio
async def test_patch_auto_adds_and_notifies_only_new_ids(monkeypatch):
    sent = _capture(monkeypatch, {'subtask_assigned', 'assigned'})
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c, assignee_ids=['u1', 'u2'])
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                           json={'title': 'A', 'assignee_ids': ['u2']})).json()
        sent.clear()
        r = await c.patch(f"/api/v1/workos/subtasks/{st['id']}",
                          json={'assignee_ids': ['u2', 'u3']})
        assert r.status_code == 200, r.text
        assert r.json()['assignee_ids'] == ['u2', 'u3']
    parent = None
    async with _client(monkeypatch, user=U1) as c:
        parent = (await c.get(f"/api/v1/workos/tasks/{t['id']}")).json()
    assert parent['assignee_ids'] == ['u1', 'u2', 'u3']
    # only the NEW subtask assignee is notified, and only subtask_assigned
    assert [x[0] for x in sent] == ['subtask_assigned']
    assert sent[0][1] == ('u3',)


@pytest.mark.asyncio
async def test_patch_clear_to_empty_allowed(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks", json={'title': 'A'})).json()
        assert st['assignee_ids'] == ['u1']
        r = await c.patch(f"/api/v1/workos/subtasks/{st['id']}", json={'assignee_ids': []})
        assert r.status_code == 200, r.text
        assert r.json()['assignee_ids'] == []


@pytest.mark.asyncio
async def test_patch_unrelated_edit_does_not_renotify(monkeypatch):
    sent = _capture(monkeypatch, {'subtask_assigned'})
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c, assignee_ids=['u1', 'u2'])
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                           json={'title': 'A', 'assignee_ids': ['u2']})).json()
        sent.clear()
        await c.patch(f"/api/v1/workos/subtasks/{st['id']}", json={'completed': True})
        # resending the same assignee list is also not a new assignment
        await c.patch(f"/api/v1/workos/subtasks/{st['id']}", json={'assignee_ids': ['u2']})
    assert sent == []


@pytest.mark.asyncio
async def test_subtask_creator_without_task_write_cannot_expand_parent(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s, t = await _task(c)  # u2 is a plain member, task-visible
    async with _client(monkeypatch, user=U2) as c:
        # u2 creates a subtask (open posture) without touching assignees
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks", json={'title': 'mine'})).json()
        # u2 IS the subtask creator -> passes subtask.write, but self-assign
        # would expand the parent -> 403
        r = await c.patch(f"/api/v1/workos/subtasks/{st['id']}", json={'assignee_ids': ['u2']})
        assert r.status_code == 403, r.text
        assert 'Only task editors' in r.text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python.exe -m pytest open_webui/test/workos/test_router_subtask_assignees.py -v
```
Expected: the 4 new tests FAIL (PATCH ignores `assignee_ids` — form has no such field), earlier 9 still PASS.

- [ ] **Step 3: Implement**

**(a)** SubtaskUpdateForm (~line 622):
```python
class SubtaskUpdateForm(BaseModel):
    title: Optional[str] = None
    completed: Optional[bool] = None
    assignee_ids: Optional[list] = None
    sort_key: Optional[float] = None
```
(`model_dump(exclude_none=True)` drops `None` but keeps `[]`, so "absent = untouched, `[]` = clear" works with the existing dump call.)

**(b)** `update_subtask` (~line 1333) becomes:
```python
@router.patch('/subtasks/{subtask_id}')
async def update_subtask(
    request: Request, subtask_id: str, form: SubtaskUpdateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    subtask, task, stream = await require_subtask_visible(user, subtask_id, db)
    await require_subtask_writable(user, subtask, task, stream, db)
    fields = form.model_dump(exclude_none=True)
    if 'title' in fields:
        fields['title'] = fields['title'].strip()
        if not fields['title']:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Subtask title is required.')
    newly_assigned: list = []
    if 'assignee_ids' in fields:
        fields['assignee_ids'] = list(dict.fromkeys(fields['assignee_ids']))
        await validate_assignees(fields['assignee_ids'], task.workstream_id, db)
        task = await _expand_parent_assignees(request, user, task, stream, fields['assignee_ids'], db)
        newly_assigned = [uid for uid in fields['assignee_ids'] if uid not in (subtask.assignee_ids or [])]
    updated = await Subtasks.update_fields(subtask_id, fields, db=db)
    payload = {**updated.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id}
    await emit_event('workos:subtask.updated', f'workos:workstream:{task.workstream_id}', payload)
    await _emit_parent_after_subtask(task.id, db)
    if 'completed' in fields and fields['completed'] != subtask.completed:
        row = await Activity.insert(
            task.id, task.team_id, user.id,
            'subtask_completed' if fields['completed'] else 'subtask_reopened',
            {'title': updated.title},
            db=db,
        )
        await _emit_task_room('workos:activity.created', task, {**row.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id})
    if newly_assigned:
        await notify(request, db, recipients=set(newly_assigned), actor=user,
                     type='subtask_assigned', task=task, extra={'subtask_title': updated.title})
    return updated
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/python.exe -m pytest open_webui/test/workos/test_router_subtask_assignees.py open_webui/test/workos/test_router_write_gates.py -v
```
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_subtask_assignees.py
git commit -m "feat(workos): subtask assignee patching with gated parent auto-add"
```

---

### Task 4: Cascade removal on parent patch

**Files:**
- Modify: `backend/open_webui/routers/workos.py` (`update_task`, insert before the `return` at ~line 753)
- Test: `backend/open_webui/test/workos/test_router_subtask_assignees.py` (append)

**Interfaces:**
- Consumes: `before` dict + `updated` TaskModel already in scope in `update_task`; `Subtasks.list_for_task` / `Subtasks.update_fields` from Task 1.

- [ ] **Step 1: Write the failing tests**

Append to `test_router_subtask_assignees.py`:

```python
@pytest.mark.asyncio
async def test_parent_removal_cascades_to_subtasks(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c, assignee_ids=['u1', 'u2', 'u3'])
        a = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                          json={'title': 'A', 'assignee_ids': ['u2', 'u3']})).json()
        b = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                          json={'title': 'B', 'assignee_ids': ['u1']})).json()
        # drop u2 from the parent
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_ids': ['u1', 'u3']})
        assert r.status_code == 200, r.text
        listed = {s['title']: s['assignee_ids'] for s in
                  (await c.get(f"/api/v1/workos/tasks/{t['id']}/subtasks")).json()}
        assert listed['A'] == ['u3']   # u2 stripped
        assert listed['B'] == ['u1']   # untouched


@pytest.mark.asyncio
async def test_cascade_can_empty_a_subtask(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c, assignee_ids=['u1', 'u2'])
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                           json={'title': 'A', 'assignee_ids': ['u2']})).json()
        await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_ids': ['u1']})
        listed = (await c.get(f"/api/v1/workos/tasks/{t['id']}/subtasks")).json()
        assert listed[0]['assignee_ids'] == []


@pytest.mark.asyncio
async def test_cascade_emits_subtask_updated_events(monkeypatch):
    events = []
    real_emit = wr.emit_event

    async def _ee(event, room, payload):
        if event == 'workos:subtask.updated':
            events.append(payload['id'])
        return await real_emit(event, room, payload)

    monkeypatch.setattr(wr, 'emit_event', _ee)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c, assignee_ids=['u1', 'u2'])
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                           json={'title': 'A', 'assignee_ids': ['u2']})).json()
        events.clear()
        await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_ids': ['u1']})
    assert events == [st['id']]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python.exe -m pytest open_webui/test/workos/test_router_subtask_assignees.py -v
```
Expected: 3 new tests FAIL (subtask assignees keep the removed id; no events).

- [ ] **Step 3: Implement**

In `update_task`, immediately before `return {**updated.model_dump(), 'deleted_label_ids': deleted_label_ids}` (~line 753), add:

```python
    # Cascade: dropping a parent assignee strips them from every subtask, keeping
    # the invariant "subtask assignees are a subset of parent assignees".
    if 'assignee_ids' in fields:
        removed = [uid for uid in (before.get('assignee_ids') or []) if uid not in (updated.assignee_ids or [])]
        if removed:
            for st in await Subtasks.list_for_task(task_id, db=db):
                kept = [uid for uid in (st.assignee_ids or []) if uid not in removed]
                if kept != (st.assignee_ids or []):
                    changed = await Subtasks.update_fields(st.id, {'assignee_ids': kept}, db=db)
                    await emit_event(
                        'workos:subtask.updated', f'workos:workstream:{updated.workstream_id}',
                        {**changed.model_dump(), 'workstream_id': updated.workstream_id, 'actor_id': user.id},
                    )
```

- [ ] **Step 4: Run the full workos backend suite**

```bash
.venv/Scripts/python.exe -m pytest open_webui/test/workos/ -v
```
Expected: all PASS (this is the last backend change — run everything).

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_subtask_assignees.py
git commit -m "feat(workos): cascade parent assignee removal onto subtasks"
```

---

### Task 5: Frontend lib plumbing + notification logic

**Files:**
- Modify: `src/lib/components/workos/lib/types.ts` (Subtask ~line 122, NotificationType ~line 151)
- Modify: `src/lib/components/workos/lib/api.ts` (~lines 187–191)
- Modify: `src/lib/components/workos/lib/store.ts` (`editSubtask` ~line 455)
- Modify: `src/lib/components/workos/lib/notifications.ts`
- Modify: `src/lib/components/workos/lib/inbox.ts` (`isNeedsYou` ~line 20)
- Test: `src/lib/components/workos/lib/notifications.test.ts`, `src/lib/components/workos/lib/inbox.test.ts` (append)

**Interfaces:**
- Produces: `Subtask.assignee_ids: string[]`; `NotificationType` includes `'subtask_assigned'`; `api.createSubtask`/`api.updateSubtask` accept `assignee_ids`; `editSubtask(id, fields)` accepts `assignee_ids` (Task 6 calls it).

- [ ] **Step 1: Write the failing tests**

Append to `src/lib/components/workos/lib/notifications.test.ts` (match the file's existing `mk` helper usage — it builds a Notification with a type and optional data; follow the pattern of the `assigned` cases visible at the top of the file):

```ts
it('summarizes subtask_assigned', () => {
	expect(summarizeNotification(mk('subtask_assigned', d))).toBe('Mia assigned you a subtask on OSL-7');
	expect(summarizeNotification(mk('subtask_assigned'))).toBe('Mia assigned you a subtask on');
});
```
(If the file's bare `mk('assigned')` case expects `'Someone assigned you'`, mirror that actor-less pattern instead — copy whatever `mk` produces; adjust the expected string to `Someone assigned you a subtask on` accordingly.)

Append to `src/lib/components/workos/lib/inbox.test.ts` inside the `isNeedsYou` describe block:

```ts
it('treats unread subtask_assigned as needs-you', () => {
	expect(isNeedsYou(mk({ type: 'subtask_assigned' }))).toBe(true);
	expect(isNeedsYou(mk({ type: 'subtask_assigned', read: true }))).toBe(false);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `C:\Projects\open-webui`):
```bash
npm run test:frontend -- --run src/lib/components/workos/lib/notifications.test.ts src/lib/components/workos/lib/inbox.test.ts
```
Expected: FAIL — type error on `'subtask_assigned'` and/or wrong summary/needs-you result.

- [ ] **Step 3: Implement**

`types.ts` — Subtask (~line 122):
```ts
export interface Subtask {
	id: string;
	task_id: string;
	title: string;
	completed: boolean;
	assignee_ids: string[];
	sort_key: number;
	created_by_id?: string | null;
	completed_at?: number | null;
	created_at: number;
	updated_at: number;
}
```
NotificationType (~line 151):
```ts
export type NotificationType = 'assigned' | 'subtask_assigned' | 'mentioned' | 'commented' | 'status_changed';
```

`api.ts` (~lines 187–191):
```ts
export const createSubtask = (
	token: string, taskId: string, body: { title: string; sort_key?: number; assignee_ids?: string[] }
) => request<Subtask>(token, `/tasks/${taskId}/subtasks`, 'POST', body);
export const updateSubtask = (
	token: string, id: string, body: Partial<Pick<Subtask, 'title' | 'completed' | 'sort_key' | 'assignee_ids'>>
) => request<Subtask>(token, `/subtasks/${id}`, 'PATCH', body);
```

`store.ts` — `editSubtask` signature (~line 455), body unchanged:
```ts
export async function editSubtask(id: string, fields: Partial<Pick<Subtask, 'title' | 'completed' | 'sort_key' | 'assignee_ids'>>): Promise<void> {
```

`notifications.ts` — add the case after `'assigned'`:
```ts
		case 'subtask_assigned': return `${who} assigned you a subtask on ${key}`.trim();
```

`inbox.ts` — `isNeedsYou`:
```ts
export function isNeedsYou(n: Notification): boolean {
	return !n.read && (n.type === 'mentioned' || n.type === 'assigned' || n.type === 'subtask_assigned');
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
npm run test:frontend -- --run src/lib/components/workos/lib
```
Expected: all lib tests PASS (including pre-existing store/roles/urlSync suites).

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/types.ts src/lib/components/workos/lib/api.ts src/lib/components/workos/lib/store.ts src/lib/components/workos/lib/notifications.ts src/lib/components/workos/lib/inbox.ts src/lib/components/workos/lib/notifications.test.ts src/lib/components/workos/lib/inbox.test.ts
git commit -m "feat(workos): subtask assignee_ids + subtask_assigned type in frontend lib"
```

---

### Task 6: Inbox + MyWork rendering for subtask_assigned

**Files:**
- Modify: `src/lib/components/workos/ui/Icon.svelte` (add `list-checks` path)
- Modify: `src/lib/components/workos/views/inbox/TypeGlyph.svelte`
- Modify: `src/lib/components/workos/views/inbox/FeedRow.svelte` (~lines 22–25, 62–70)
- Modify: `src/lib/components/workos/views/inbox/NeedsYouCard.svelte` (~line 19)
- Modify: `src/lib/components/workos/views/MyWorkView.svelte` (~line 153)

**Interfaces:**
- Consumes: `NotificationType` incl. `'subtask_assigned'` (Task 5); notification `data.subtask_title` (Task 2).

- [ ] **Step 1: Add the icon**

`Icon.svelte` — add to the `LUCIDE` record (alphabetical placement not required; drop it next to `list`):
```ts
		'list-checks': '<path d="m3 17 2 2 4-4"/><path d="m3 7 2 2 4-4"/><path d="M13 6h8"/><path d="M13 12h8"/><path d="M13 18h8"/>',
```

- [ ] **Step 2: TypeGlyph**

`TypeGlyph.svelte` — extend both records (`subtask_assigned` shares the assigned teal family per the design system's one-meaning-per-hue rule):
```ts
	const ICON: Record<NotificationType, string> = {
		mentioned: 'at-sign',
		assigned: 'user-plus',
		subtask_assigned: 'list-checks',
		commented: 'message-square',
		status_changed: 'arrow-right-left'
	};
	// Colored types carry an inline style; neutral ones use theme classes.
	const STYLE: Partial<Record<NotificationType, string>> = {
		mentioned: `color:var(--primary);background:${tint('var(--primary)')}`,
		assigned: `color:${STATUS_COLOR.in_progress};background:${tint(STATUS_COLOR.in_progress)}`,
		subtask_assigned: `color:${STATUS_COLOR.in_progress};background:${tint(STATUS_COLOR.in_progress)}`
	};
```
(`Record<NotificationType, string>` makes the ICON addition mandatory — svelte-check fails without it.)

- [ ] **Step 3: FeedRow**

`FeedRow.svelte` — VERB map (~line 22):
```ts
	const VERB: Record<string, string> = {
		assigned: 'assigned you', subtask_assigned: 'assigned you a subtask on',
		mentioned: 'mentioned you in',
		commented: 'commented on', status_changed: 'moved'
	};
```
Second line under the row (~line 62): show the subtask title the same way comment snippets render. Change the trailing branch from:
```svelte
				{:else if item.data?.snippet}
					<div class="wos-meta mt-1 line-clamp-2 border-l-2 border-gray-200 pl-2.5 text-gray-500 dark:border-gray-800 dark:text-gray-400">{item.data.snippet}</div>
				{/if}
```
to:
```svelte
				{:else if item.data?.snippet}
					<div class="wos-meta mt-1 line-clamp-2 border-l-2 border-gray-200 pl-2.5 text-gray-500 dark:border-gray-800 dark:text-gray-400">{item.data.snippet}</div>
				{:else if item.type === 'subtask_assigned' && item.data?.subtask_title}
					<div class="wos-meta mt-1 line-clamp-1 border-l-2 border-gray-200 pl-2.5 text-gray-500 dark:border-gray-800 dark:text-gray-400">{item.data.subtask_title}</div>
				{/if}
```

- [ ] **Step 4: NeedsYouCard**

`NeedsYouCard.svelte` (~line 19):
```ts
	$: verb =
		n.type === 'assigned' ? 'assigned you' :
		n.type === 'subtask_assigned' ? 'assigned you a subtask on' :
		'mentioned you in';
```

- [ ] **Step 5: MyWorkView**

`MyWorkView.svelte` — in `toAct` (~line 153), add a branch:
```ts
		if (n.type === 'assigned') { action = 'assigned'; detail = 'to you'; }
		else if (n.type === 'subtask_assigned') { action = 'assigned you a subtask on'; }
		else if (n.type === 'mentioned') action = 'mentioned you in';
		else if (n.type === 'commented') action = 'commented on';
```

- [ ] **Step 6: Type-check**

```bash
npm run check
```
Expected: 0 errors (warnings at the pre-existing baseline are fine).

- [ ] **Step 7: Commit**

```bash
git add src/lib/components/workos/ui/Icon.svelte src/lib/components/workos/views/inbox/TypeGlyph.svelte src/lib/components/workos/views/inbox/FeedRow.svelte src/lib/components/workos/views/inbox/NeedsYouCard.svelte src/lib/components/workos/views/MyWorkView.svelte
git commit -m "feat(workos): render subtask_assigned notifications in inbox and My Work"
```

---

### Task 7: SubtasksPanel — avatar stacks + grouped assignee picker

**Files:**
- Modify: `src/lib/components/workos/views/detail/SubtasksPanel.svelte` (full rework below)
- Modify: `src/lib/components/workos/views/detail/TaskDetailBody.svelte` (~line 533: pass the task, not just the id)

**Interfaces:**
- Consumes: `editSubtask(id, { assignee_ids })` (Task 5); `AssigneeAvatars` (`ids`, `max`, `size` props); `toggleAssignee(ids, id): string[]` from `lib/assignees`; `canEditTask(task, userId, teamRole, workspaceRole)` from `lib/roles`; `directory`, `roles`, `displayName` stores from `lib/store`; OWUI `user` store from `$lib/stores`.
- Produces: `SubtasksPanel` prop change: `export let task: Task` (replaces `taskId`).

**Approved mockup (2026-07-28):** row = checkbox + title + avatar stack (or dashed ghost `user-plus` button when unassigned) + trash; picker = dropdown grouped **"On this task"** (parent assignees) then **"Everyone else"** (rest of directory, only when the viewer can edit the parent task) with an amber `+ added to task` pill on selected non-parent members and the footer hint "Picking someone new also adds them to the task".

- [ ] **Step 1: Update the call site**

`TaskDetailBody.svelte` line ~533:
```svelte
						<Tabs.Content value="subtasks"><SubtasksPanel task={t} /></Tabs.Content>
```

- [ ] **Step 2: Rework SubtasksPanel**

Replace `src/lib/components/workos/views/detail/SubtasksPanel.svelte` with:

```svelte
<script lang="ts">
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import Icon from '../../ui/Icon.svelte';
	import { Button } from '$lib/components/ui/button';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import AssigneeAvatars from '../AssigneeAvatars.svelte';
	import { subtasks, addSubtask, editSubtask, removeSubtask, directory, roles } from '../../lib/store';
	import { toggleAssignee } from '../../lib/assignees';
	import { canEditTask } from '../../lib/roles';
	import { user } from '$lib/stores';
	import type { Task, Subtask } from '../../lib/types';

	export let task: Task;

	let title = '';
	let creating = false;

	$: parentIds = task.assignee_ids ?? [];
	$: members = Object.entries($directory).map(([id, u]) => ({ id, name: u.name }));
	$: onTask = members.filter((m) => parentIds.includes(m.id));
	$: everyoneElse = members.filter((m) => !parentIds.includes(m.id));
	// Whether the viewer may expand the parent's assignee list (mirrors the
	// server's task.write gate on auto-add; workspace-admin edge under-shown,
	// server remains authoritative).
	$: canExpand =
		$user?.role === 'admin' || canEditTask(task, $user?.id ?? '', $roles[task.team_id], undefined);

	async function submit() {
		if (!title.trim()) return;
		await addSubtask(task.id, title.trim());
		title = '';
		creating = false;
	}

	function toggle(subtask: Subtask, id: string) {
		editSubtask(subtask.id, { assignee_ids: toggleAssignee(subtask.assignee_ids, id) });
	}
</script>

<div class="pt-4 space-y-2">
	{#each $subtasks as subtask (subtask.id)}
		<div class="flex items-center gap-2 rounded-lg border border-gray-200 dark:border-gray-800 px-3 py-2">
			<Checkbox
				checked={subtask.completed}
				onCheckedChange={(v) => editSubtask(subtask.id, { completed: !!v })}
				class="size-4"
				aria-label="Toggle subtask completion"
			/>
			<span class="flex-1 min-w-0 text-sm {subtask.completed ? 'line-through text-gray-400' : ''}">
				{subtask.title}
			</span>
			<DropdownMenu.Root>
				<DropdownMenu.Trigger
					class="inline-flex items-center rounded-md p-0.5 hover:bg-gray-100 dark:hover:bg-gray-900"
					aria-label="Edit subtask assignees"
				>
					{#if (subtask.assignee_ids ?? []).length}
						<AssigneeAvatars ids={subtask.assignee_ids} size={20} max={3} />
					{:else}
						<span
							class="flex size-6 items-center justify-center rounded-full border-[1.5px] border-dashed border-gray-300 text-gray-400 dark:border-gray-700 dark:text-gray-500"
						>
							<Icon name="user-plus" size={13} />
						</span>
					{/if}
				</DropdownMenu.Trigger>
				<DropdownMenu.Content class="w-72 max-h-72 overflow-y-auto">
					<DropdownMenu.Label class="wos-caption text-gray-400">On this task</DropdownMenu.Label>
					{#each onTask as m (m.id)}
						<DropdownMenu.CheckboxItem
							checked={(subtask.assignee_ids ?? []).includes(m.id)}
							closeOnSelect={false}
							onCheckedChange={() => toggle(subtask, m.id)}
						>
							<span class="inline-flex items-center gap-2">
								<AssigneeAvatars ids={[m.id]} max={1} size={20} />
								{m.name}
							</span>
						</DropdownMenu.CheckboxItem>
					{/each}
					{#if !onTask.length}
						<DropdownMenu.Item disabled>No assignees on this task</DropdownMenu.Item>
					{/if}
					{#if canExpand && everyoneElse.length}
						<DropdownMenu.Separator />
						<DropdownMenu.Label class="wos-caption text-gray-400">Everyone else</DropdownMenu.Label>
						{#each everyoneElse as m (m.id)}
							<DropdownMenu.CheckboxItem
								checked={(subtask.assignee_ids ?? []).includes(m.id)}
								closeOnSelect={false}
								onCheckedChange={() => toggle(subtask, m.id)}
							>
								<span class="inline-flex min-w-0 flex-1 items-center gap-2">
									<AssigneeAvatars ids={[m.id]} max={1} size={20} />
									<span class="truncate">{m.name}</span>
									{#if (subtask.assignee_ids ?? []).includes(m.id)}
										<span
											class="wos-micro ml-auto rounded-full bg-amber-100 px-2 py-px text-amber-700 dark:bg-amber-950 dark:text-amber-400"
										>+ added to task</span>
									{/if}
								</span>
							</DropdownMenu.CheckboxItem>
						{/each}
						<DropdownMenu.Separator />
						<div class="flex items-center gap-1.5 px-2 py-1.5 text-[11px] text-gray-400 dark:text-gray-500">
							<Icon name="user-plus" size={12} /> Picking someone new also adds them to the task
						</div>
					{/if}
				</DropdownMenu.Content>
			</DropdownMenu.Root>
			<Button variant="ghost" size="icon-xs" class="text-gray-400 hover:text-red-500" title="Delete subtask" onclick={() => removeSubtask(subtask.id)}>
				<Icon name="trash" size={14} />
			</Button>
		</div>
	{/each}

	{#if creating}
		<!-- svelte-ignore a11y_autofocus -->
		<input
			class="w-full text-sm rounded-lg border border-gray-300 dark:border-gray-700 bg-transparent px-3 py-2"
			placeholder="Subtask title..."
			bind:value={title}
			onkeydown={(e) => {
				if (e.key === 'Enter') submit();
				if (e.key === 'Escape') {
					creating = false;
					title = '';
				}
			}}
			autofocus
		/>
	{:else}
		<Button variant="ghost" size="sm" class="text-primary" onclick={() => (creating = true)}>
			<Icon name="plus" size={14} /> Add subtask
		</Button>
	{/if}

	{#if !$subtasks.length && !creating}
		<div class="text-xs text-gray-400 dark:text-gray-500 py-6 text-center">
			Break this task into smaller steps.
		</div>
	{/if}
</div>
```

Notes for the implementer:
- If `DropdownMenu.Label` or `DropdownMenu.Separator` are not exported by `$lib/components/ui/dropdown-menu`, check its `index.ts` for the actual export names (shadcn-svelte usually exports `DropdownMenuLabel`/`DropdownMenuSeparator` re-mapped as `Label`/`Separator`); adjust rather than removing the grouping.
- The "picked from Everyone else" pill shows on already-checked non-parent members. That state only exists transiently (auto-add moves them into the parent list on save + realtime refresh moves them into "On this task"), which matches the mockup's intent: the pill is feedback at pick time.
- UI copy: sentence case, no terminal punctuation on labels.

- [ ] **Step 3: Type-check + full frontend tests**

```bash
npm run check
npm run test:frontend -- --run src/lib/components/workos
```
Expected: 0 new check errors; all vitest suites PASS.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/views/detail/SubtasksPanel.svelte src/lib/components/workos/views/detail/TaskDetailBody.svelte
git commit -m "feat(workos): subtask row assignee avatars and grouped picker"
```

---

### Task 8: Access-control doc sync + memory

**Files:**
- Modify: `docs/superpowers/specs/2026-06-26-workos-access-control.md` (header changelog + §4 Subtasks table + §1 data-model note)
- Modify: `C:\Users\aalsawarieh\.claude\projects\C--Projects-open-webui\memory\workos-subtask-assignees.md` (status flip)

**Interfaces:** none (documentation).

- [ ] **Step 1: Update the access-control reference**

In `docs/superpowers/specs/2026-06-26-workos-access-control.md`:

**(a)** Append to the HTML comment changelog at the top of the file:
```
  2026-07-28: subtasks gained assignee_ids (JSON list) with a subset invariant
  against the parent task's list. POST /tasks/{id}/subtasks and PATCH
  /subtasks/{id} accept assignee_ids (validated via validate_assignees);
  assigning someone NOT already on the parent requires task.write on the parent
  (403 'Only task editors can add new people to the task.') — without this
  gate, any task-visible user could self-assign via a subtask and thereby gain
  task.write. Parent-side removal cascades off all subtasks (PATCH /tasks).
  New notification type 'subtask_assigned' shares the 'assigned' rules toggle
  and is visibility-filtered by notify() like every other type. subtask.write
  chain unchanged (subset invariant ⇒ subtask assignee is always a parent
  assignee). Assignment still confers no visibility.
```

**(b)** In §4 "Subtasks" table, update the two changed rows:

| Route | change |
|---|---|
| `POST /tasks/{id}/subtasks` | append: "; `assignee_ids` validated via `validate_assignees`, defaults to parent's first assignee; ids not on the parent additionally require `require_task_writable` (auto-add)" |
| `PATCH /subtasks/{id}` | append: "; `assignee_ids` edits validated via `validate_assignees`; expanding the parent list additionally requires `require_task_writable`" |

**(c)** In §1, after the assignment-vs-membership table, add one line:
```
Subtasks carry their own `assignee_ids` (JSON list on `workos_subtask`), constrained to a **subset of the parent task's list** (auto-add on grow — gated by `task.write` — and cascade on parent shrink). Like task assignment, subtask assignment grants **no visibility**.
```

- [ ] **Step 2: Update memory**

In `C:\Users\aalsawarieh\.claude\projects\C--Projects-open-webui\memory\workos-subtask-assignees.md`, replace the `Status:` line with:
```
Status: BUILT on osool (all 8 plan tasks; backend suite + vitest + svelte-check green). Migration b0c1d2e3f4a5 must be applied in the container (restart osool-ai-open-webui-1). Browser smoke pending.
```
Also update the one-liner in `MEMORY.md` to say "BUILT, smoke pending".

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-06-26-workos-access-control.md
git commit -m "docs(workos): record subtask assignee invariant in access-control reference"
```

---

## Final verification (after all tasks)

- [ ] `cd backend && .venv/Scripts/python.exe -m pytest open_webui/test/workos/ -q` → all pass
- [ ] `npm run test:frontend -- --run src/lib/components/workos` → all pass
- [ ] `npm run check` → no new errors
- [ ] Remind the user: restart the `osool-ai-open-webui-1` container so Alembic applies `b0c1d2e3f4a5`, then browser-smoke (create subtask → default avatar appears; assign non-parent member → pill + parent grows; remove parent assignee → subtask loses them; inbox shows "assigned you a subtask on").
