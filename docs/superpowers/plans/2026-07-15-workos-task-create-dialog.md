# WorkOS Task Create Dialog + Attachment-Required Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every "add task" entry point opens one create dialog where only title + ≥1 assignee are mandatory, and creators can flag a task as requiring an attachment before it can be moved to `done` (hard server-side block).

**Architecture:** Backend first — new `workos_task.attachment_required` boolean (migration `e7f8a9b0c1d2`), min-1-assignee rule on POST/PATCH, a new `task.flag.attachment_required` capability (app-admin → creator), and a done-transition guard returning `400 ATTACHMENT_REQUIRED`. Frontend second — a shared `TaskCreateDialog.svelte` (shadcn Dialog, opened via the existing `openModal` store with a new `'task'` kind) replaces all five quick-add inputs; the store handles the `ATTACHMENT_REQUIRED` rejection with rollback + toast; detail/card affordances surface the flag.

**Tech Stack:** FastAPI + SQLAlchemy async + Alembic, pytest-asyncio; Svelte 4-style components (`export let`, `$:`) with shadcn-svelte primitives, vitest.

**Spec:** `docs/superpowers/specs/2026-07-15-workos-task-create-dialog-design.md`

## Global Constraints

- Branch: `osool`, work directly (no worktree unless executor chooses one).
- **NEVER use a haiku-model subagent for Svelte file edits** (cp1252 corruption risk — standing project rule).
- Backend tests: `cd C:\Projects\open-webui` then `.venv\Scripts\python.exe -m pytest backend\open_webui\test\workos -q` (must use the repo `.venv` python).
- Frontend tests: `npm run test:frontend -- --run src/lib/components/workos`.
- Type check: `npm run check` (run in Tasks 6 and 8; slow).
- Do NOT start a Vite dev server (standing rule: ask the user first). No Docker rebuild for frontend changes.
- Pinned strings (tests assert byte-for-byte):
  - `'Task needs at least one assignee.'` (400)
  - `'Only the task creator or an admin may change the attachment requirement.'` (403)
  - `'ATTACHMENT_REQUIRED'` (400 detail on blocked done-transition)
- The access-control reference doc `docs/superpowers/specs/2026-06-26-workos-access-control.md` MUST be updated in the same task that changes the capability table (Task 3).
- Task 5 (dialog UI) may only start after the user has approved the static HTML mockup (gate handled outside this plan — mockup already presented during planning).
- Commit after every task; commit messages end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: `attachment_required` column, migration, DAO plumbing

**Files:**
- Modify: `backend/open_webui/models/workos.py` (WorkosTask ~:486, TaskModel ~:535, TasksDao.insert ~:651)
- Create: `backend/open_webui/migrations/versions/e7f8a9b0c1d2_workos_attachment_required.py`
- Test: `backend/open_webui/test/workos/test_models_task.py` (append)

**Interfaces:**
- Produces: `WorkosTask.attachment_required` (Boolean, default False), `TaskModel.attachment_required: bool = False`, `Tasks.insert(..., attachment_required: bool = False)`. Every task payload the API returns now carries `attachment_required`.

- [ ] **Step 1: Write the failing test** — append to `test_models_task.py`:

```python
@pytest.mark.asyncio
async def test_attachment_required_round_trips():
    team, s = await _stream()
    flagged = await Tasks.insert(s.id, team.id, team.key, 'Needs proof', 'u1', attachment_required=True)
    assert flagged.attachment_required is True
    plain = await Tasks.insert(s.id, team.id, team.key, 'No proof', 'u1')
    assert plain.attachment_required is False
    toggled = await Tasks.update_fields(flagged.id, {'attachment_required': False})
    assert toggled.attachment_required is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python.exe -m pytest backend\open_webui\test\workos\test_models_task.py::test_attachment_required_round_trips -q`
Expected: FAIL — `TypeError: ... unexpected keyword argument 'attachment_required'`

- [ ] **Step 3: Implement**

In `WorkosTask`, after `progress = Column(Integer, default=0)`:

```python
    attachment_required = Column(Boolean, default=False)
```

In `TaskModel`, after `progress: int`:

```python
    attachment_required: bool = False
```

In `TasksDao.insert`, add the kwarg and pass it through:

```python
    async def insert(
        self, workstream_id: str, team_id: str, team_key: str, title: str, created_by_id: Optional[str],
        *, description: Optional[str] = None, status: str = 'backlog', priority: Optional[str] = None,
        assignee_ids: Optional[list] = None, start_date: Optional[int] = None,
        due_date: Optional[int] = None, labels: Optional[list] = None,
        attachment_required: bool = False,
        db: Optional[AsyncSession] = None,
    ) -> TaskModel:
```

and in the `WorkosTask(...)` constructor call, after `progress=0,`:

```python
                attachment_required=attachment_required,
```

Create the migration file:

```python
"""workos task attachment_required flag

Adds ``workos_task.attachment_required`` — a per-task boolean set by the
creator; when true the task cannot move to ``done`` until it has at least
one attachment (task-level or comment-level).

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-07-15 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, None] = 'd6e7f8a9b0c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'workos_task',
        # sa.false() compiles to the right literal per dialect (0 on SQLite, false on Postgres).
        sa.Column('attachment_required', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    with op.batch_alter_table('workos_task') as batch:
        batch.drop_column('attachment_required')
```

- [ ] **Step 4: Run tests**

Run: `.venv\Scripts\python.exe -m pytest backend\open_webui\test\workos\test_models_task.py -q`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/models/workos.py backend/open_webui/migrations/versions/e7f8a9b0c1d2_workos_attachment_required.py backend/open_webui/test/workos/test_models_task.py
git commit -m "feat(workos): attachment_required column on tasks + migration"
```

---

### Task 2: server-side min-1-assignee rule + flag in create/update forms

**Files:**
- Modify: `backend/open_webui/routers/workos.py` (TaskCreateForm :569, TaskUpdateForm :580, create_task :657, update_task :687)
- Create: `backend/open_webui/test/workos/test_router_task_rules.py`
- Modify (sweep): every existing test that POSTs `/workstreams/{id}/tasks` — see Step 5.

**Interfaces:**
- Consumes: `Tasks.insert(..., attachment_required=...)` from Task 1.
- Produces: `POST /workstreams/{id}/tasks` rejects missing/empty `assignee_ids` with `400 'Task needs at least one assignee.'` and accepts `attachment_required: bool`; `PATCH /tasks/{id}` rejects `assignee_ids: []` with the same detail. `TaskUpdateForm.attachment_required: Optional[bool]` exists (gating added in Task 3).

- [ ] **Step 1: Write the failing tests** — create `test_router_task_rules.py`:

```python
"""Create/patch assignee rules: every task needs at least one assignee."""
import pytest

from open_webui.test.workos.test_router_teams import _client, U1
from open_webui.test.workos.test_router_task import _stream


@pytest.mark.asyncio
async def test_create_without_assignees_rejected(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'X'})
        assert r.status_code == 400
        assert r.json()['detail'] == 'Task needs at least one assignee.'
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                         json={'title': 'X', 'assignee_ids': []})
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_create_with_assignee_succeeds(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                         json={'title': 'X', 'assignee_ids': ['u1']})
        assert r.status_code == 200, r.text
        assert r.json()['assignee_ids'] == ['u1']


@pytest.mark.asyncio
async def test_patch_cannot_clear_assignees(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                          json={'title': 'X', 'assignee_ids': ['u1']})).json()
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_ids': []})
        assert r.status_code == 400
        assert r.json()['detail'] == 'Task needs at least one assignee.'
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_ids': ['u1']})
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_create_carries_attachment_required(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                         json={'title': 'X', 'assignee_ids': ['u1'], 'attachment_required': True})
        assert r.status_code == 200, r.text
        assert r.json()['attachment_required'] is True
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                         json={'title': 'Y', 'assignee_ids': ['u1']})
        assert r.json()['attachment_required'] is False
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv\Scripts\python.exe -m pytest backend\open_webui\test\workos\test_router_task_rules.py -q`
Expected: FAIL (creates succeed without assignees / `attachment_required` missing)

- [ ] **Step 3: Implement router changes**

`TaskCreateForm` — add after `labels`:

```python
    attachment_required: bool = False
```

`TaskUpdateForm` — add after `sort_key`:

```python
    attachment_required: Optional[bool] = None
```

In `create_task`, after `_validate_task_fields(form.model_dump())` (line ~664) insert:

```python
    if not form.assignee_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Task needs at least one assignee.')
```

and extend the `Tasks.insert(...)` call with `attachment_required=form.attachment_required` (keyword args, before `db=db`).

In `update_task`, replace the existing assignee block:

```python
    if 'assignee_ids' in fields:
        await validate_assignees(fields['assignee_ids'], task.workstream_id, db)
```

with:

```python
    if 'assignee_ids' in fields:
        if not fields['assignee_ids']:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Task needs at least one assignee.')
        await validate_assignees(fields['assignee_ids'], task.workstream_id, db)
```

(Note: `fields = form.model_dump(exclude_none=True)` means `attachment_required=False` survives — `False is not None`.)

- [ ] **Step 4: Run new tests**

Run: `.venv\Scripts\python.exe -m pytest backend\open_webui\test\workos\test_router_task_rules.py -q`
Expected: PASS

- [ ] **Step 5: Sweep existing tests (suite must stay green)**

Run the full suite to enumerate breakage: `.venv\Scripts\python.exe -m pytest backend\open_webui\test\workos -q`
Every failing test posts `/workstreams/{...}/tasks` without assignees (~31 sites across 12 files, found via `grep -rn "workstreams/.*}/tasks" backend/open_webui/test/workos`). Fix pattern — add the **creating user's own id** as assignee:

- `test_router_task.py::_stream` callers: change each `json={'title': ...}` to `json={'title': ..., 'assignee_ids': ['u1']}` (creator in those tests is U1). In `test_non_member_cannot_create_task` the U2 request must keep failing with **404** — add `'assignee_ids': ['u2']` so the assertion still tests visibility, not the new rule.
- `test_router_multi_assignee.py::_task`: change to `json={'title': 'T', 'assignee_ids': ['u1'], **body}` so explicit bodies still override. Rewrite `test_create_task_without_assignees_defaults_empty` → the create now fails:

```python
@pytest.mark.asyncio
async def test_create_task_without_assignees_rejected(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'T'})
        assert r.status_code == 400
```

- `test_capability_matrix.py::_team_ws_task`, `test_router_write_gates.py`, `test_router_access_leaks.py`, `test_router_my_tasks.py`, `test_router_comments.py`, `test_router_attachments.py`, `test_router_activity_notifications.py`, `test_router_workstream_activity.py`, `test_router_workstream_attachments.py`, `test_realtime.py`: same mechanical fix — assignee = the id of the user whose client performs the POST (check each `_client(monkeypatch, user=...)`).
- Notification-counting tests: assigning the **actor** to their own task fires no notification (actor excluded), so counts are unchanged — verify, don't assume.
- `test_seeder.py`: seeder writes through the DAO, not the router — should be untouched; if it fails, the failure is elsewhere.

Run: `.venv\Scripts\python.exe -m pytest backend\open_webui\test\workos -q`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/
git commit -m "feat(workos): tasks require at least one assignee (create + patch)"
```

---

### Task 3: flag-toggle capability + done-transition guard + doc sync

**Files:**
- Modify: `backend/open_webui/utils/workos_access.py` (CAPABILITIES :209)
- Modify: `backend/open_webui/routers/workos.py` (update_task :687)
- Create: `backend/open_webui/test/workos/test_router_attachment_required.py`
- Modify: `docs/superpowers/specs/2026-06-26-workos-access-control.md`

**Interfaces:**
- Consumes: `TaskUpdateForm.attachment_required` (Task 2), `Attachments.list_for_task(task_id, db=db)` (existing DAO), `require_capability` (existing).
- Produces: capability key `'task.flag.attachment_required'`; `PATCH /tasks/{id}` behavior: 403 for non-creator/non-app-admin flag changes, `400 'ATTACHMENT_REQUIRED'` on blocked done-transitions. Frontend (Task 4) matches the literal `'ATTACHMENT_REQUIRED'`.

- [ ] **Step 1: Write the failing tests** — create `test_router_attachment_required.py`:

```python
"""Attachment-required-to-complete: toggle permission matrix + done-block guard."""
import pytest
from types import SimpleNamespace

from open_webui.models.workos import Attachments
from open_webui.test.workos.test_router_teams import _client, U1, U2

ADMIN = SimpleNamespace(id='adm', name='Root', role='admin')


async def _setup(c, creator_id='u1', flag=True):
    team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
    await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                       json={'name': 'Eng', 'visibility': 'team'})).json()
    s = (await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'P'})).json()
    task = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                         json={'title': 'T', 'assignee_ids': [creator_id, 'u2'],
                               'attachment_required': flag})).json()
    return team, ws, s, task


@pytest.mark.asyncio
async def test_done_blocked_without_attachment(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _setup(c)
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'status': 'done'})
        assert r.status_code == 400
        assert r.json()['detail'] == 'ATTACHMENT_REQUIRED'
        # nothing persisted
        assert (await c.get(f"/api/v1/workos/tasks/{t['id']}")).json()['status'] == 'backlog'


@pytest.mark.asyncio
async def test_done_allowed_with_task_attachment(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _setup(c)
        await Attachments.insert(t['id'], None, 'k1', 'proof.txt', 3, 'text/plain', 'u1')
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'status': 'done'})
        assert r.status_code == 200, r.text
        assert r.json()['status'] == 'done'


@pytest.mark.asyncio
async def test_done_allowed_with_comment_attachment(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _setup(c)
        comment = (await c.post(f"/api/v1/workos/tasks/{t['id']}/comments", json={'body': 'proof below'})).json()
        await Attachments.insert(t['id'], comment['id'], 'k2', 'proof.png', 3, 'image/png', 'u1')
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'status': 'done'})
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_flag_off_and_non_done_transitions_unaffected(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, plain = await _setup(c, flag=False)
        assert (await c.patch(f"/api/v1/workos/tasks/{plain['id']}", json={'status': 'done'})).status_code == 200
        _, _, _, flagged = await _setup(c)
        assert (await c.patch(f"/api/v1/workos/tasks/{flagged['id']}",
                              json={'status': 'in_progress'})).status_code == 200


@pytest.mark.asyncio
async def test_resave_of_done_task_not_blocked(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _setup(c, flag=False)
        assert (await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'status': 'done'})).status_code == 200
        assert (await c.patch(f"/api/v1/workos/tasks/{t['id']}",
                              json={'attachment_required': True})).status_code == 200
        # already done: a resave that still says 'done' is not a transition
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'status': 'done', 'title': 'Renamed'})
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_toggle_creator_and_app_admin_allowed(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _setup(c)
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'attachment_required': False})
        assert r.status_code == 200 and r.json()['attachment_required'] is False
    async with _client(monkeypatch, user=ADMIN) as c:
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'attachment_required': True})
        assert r.status_code == 200 and r.json()['attachment_required'] is True


@pytest.mark.asyncio
async def test_toggle_assignee_forbidden(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _setup(c)
    async with _client(monkeypatch, user=U2) as c:  # assignee, task-writable, NOT creator
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'attachment_required': False})
        assert r.status_code == 403
        assert r.json()['detail'] == 'Only the task creator or an admin may change the attachment requirement.'
        # flag unchanged
        assert (await c.get(f"/api/v1/workos/tasks/{t['id']}")).json()['attachment_required'] is True


@pytest.mark.asyncio
async def test_toggle_team_owner_forbidden_when_not_creator(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:  # U1 = team owner
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                           json={'name': 'Eng', 'visibility': 'team'})).json()
        s = (await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'P'})).json()
    async with _client(monkeypatch, user=U2) as c:  # u2 creates the task
        t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                          json={'title': 'T', 'assignee_ids': ['u2'], 'attachment_required': True})).json()
    async with _client(monkeypatch, user=U1) as c:  # owner but not creator → 403
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'attachment_required': False})
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_resending_same_flag_value_is_not_gated(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _setup(c)
    async with _client(monkeypatch, user=U2) as c:  # assignee resends unchanged value
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}",
                          json={'attachment_required': True, 'priority': 'high'})
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_mixed_patch_fails_atomically(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _setup(c, flag=False)
        # turning the flag ON and completing in the same patch, with no attachment → blocked, nothing saved
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}",
                          json={'status': 'done', 'attachment_required': True})
        assert r.status_code == 400 and r.json()['detail'] == 'ATTACHMENT_REQUIRED'
        after = (await c.get(f"/api/v1/workos/tasks/{t['id']}")).json()
        assert after['status'] == 'backlog' and after['attachment_required'] is False
        # turning it OFF and completing in one patch is the creator's prerogative → allowed
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}",
                          json={'status': 'done', 'attachment_required': False})
        assert r.status_code == 200, r.text
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv\Scripts\python.exe -m pytest backend\open_webui\test\workos\test_router_attachment_required.py -q`
Expected: FAIL (toggles succeed for everyone, done never blocked)

- [ ] **Step 3: Implement**

`workos_access.py` — add to `CAPABILITIES` after the `'task.delete'` entry:

```python
    'task.flag.attachment_required': ((_app_admin, _owner('creator_id')),
                          'Only the task creator or an admin may change the attachment requirement.'),
```

`routers/workos.py` `update_task` — after the assignee block from Task 2, before `before = task.model_dump()`, insert:

```python
    if 'attachment_required' in fields and fields['attachment_required'] != task.attachment_required:
        await require_capability('task.flag.attachment_required', user, db,
                                 task=task, creator_id=task.created_by_id)
    # Hard gate: a flagged task cannot TRANSITION to done without at least one
    # attachment (task-level or comment-level both count). Runs before any field
    # is persisted so a mixed patch fails atomically.
    if fields.get('status') == 'done' and task.status != 'done':
        effective_flag = fields.get('attachment_required', task.attachment_required)
        if effective_flag and not await Attachments.list_for_task(task_id, db=db):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='ATTACHMENT_REQUIRED')
```

(`require_capability` and `Attachments` are already imported by the router — verify, add to the import list if missing.)

- [ ] **Step 4: Run tests**

Run: `.venv\Scripts\python.exe -m pytest backend\open_webui\test\workos -q`
Expected: ALL PASS

- [ ] **Step 5: Sync the access-control reference doc**

In `docs/superpowers/specs/2026-06-26-workos-access-control.md`:
1. Append to the HTML comment changelog at the top: `2026-07-15: task.flag.attachment_required capability added (app-admin → creator; assignees/managers may edit tasks but not this flag). PATCH /tasks/{id} additionally blocks status→done with 400 ATTACHMENT_REQUIRED when the flag is set and the task has zero attachment rows. Tasks now require ≥1 assignee at create, and a patch may not clear assignees to [].`
2. Add a row to the `CAPABILITIES` table in §3: `| task.flag.attachment_required | app-admin → creator | PATCH /tasks/{id} when the patch changes attachment_required |`
3. In §4 Tasks table, `PATCH /tasks/{id}` row: append `; attachment_required changes gated by require_capability('task.flag.attachment_required'); status→done blocked (400 ATTACHMENT_REQUIRED) when flagged with no attachments` and on `POST .../tasks` append `; assignee_ids must be non-empty (400)`.

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/utils/workos_access.py backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_attachment_required.py docs/superpowers/specs/2026-06-26-workos-access-control.md
git commit -m "feat(workos): attachment-required flag capability + done-transition guard"
```

---

### Task 4: frontend lib layer — types, api, store (+ vitest)

**Files:**
- Modify: `src/lib/components/workos/lib/types.ts` (Task :50, ModalRequest consumers see store)
- Modify: `src/lib/components/workos/lib/api.ts` (createTask :89, updateTask :95)
- Modify: `src/lib/components/workos/lib/store.ts` (ModalRequest :22, addTask :237, editTask :263)
- Test: `src/lib/components/workos/lib/store.test.ts`

**Interfaces:**
- Consumes: server behavior from Tasks 2–3 (`attachment_required` field, `'ATTACHMENT_REQUIRED'` detail).
- Produces (used by Tasks 5–7):
  - `Task.attachment_required?: boolean`
  - `ModalRequest` union gains `{ kind: 'task'; workstreamId: string; prefill?: { status?: TaskStatus; start_date?: number | null; due_date?: number | null } }`
  - `openTaskCreate(workstreamId: string, prefill?: { status?: TaskStatus; start_date?: number | null; due_date?: number | null }): void`
  - `addTask(workstreamId, fields)` where `fields` adds `description?: string; labels?: string[]; attachment_required?: boolean`
  - `editTask` swallows `'ATTACHMENT_REQUIRED'` (rollback + toast, resolves).

- [ ] **Step 1: Write the failing tests** — append to `store.test.ts` (inside a new describe at the end; `tasks`, `mk`, `get` already imported):

```ts
describe('create dialog store plumbing', () => {
	it('addTask forwards assignees + attachment flag to the API', async () => {
		const api = await import('./api');
		const { addTask } = await import('./store');
		await addTask('w1', { title: 'New', assignee_ids: ['u2'], attachment_required: true });
		expect(api.createTask).toHaveBeenLastCalledWith(
			expect.anything(), 'w1',
			expect.objectContaining({ assignee_ids: ['u2'], attachment_required: true })
		);
	});

	it('editTask rolls back and swallows ATTACHMENT_REQUIRED', async () => {
		const api = await import('./api');
		const { editTask } = await import('./store');
		tasks.set([mk({ id: 'a', status: 'todo', attachment_required: true })]);
		(api.updateTask as any).mockRejectedValueOnce('ATTACHMENT_REQUIRED');
		await editTask('a', { status: 'done' }); // must not throw
		expect(get(tasks)[0].status).toBe('todo'); // rolled back
	});

	it('openTaskCreate opens the task modal with prefill', async () => {
		const { openTaskCreate, openModal } = await import('./store');
		openTaskCreate('w1', { status: 'todo' });
		expect(get(openModal)).toEqual({ kind: 'task', workstreamId: 'w1', prefill: { status: 'todo' } });
	});
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npm run test:frontend -- --run src/lib/components/workos/lib/store.test.ts`
Expected: FAIL — `openTaskCreate` not exported; `editTask` rejects; `attachment_required` type error is fine at runtime but fails `expect`.

- [ ] **Step 3: Implement**

`types.ts` — in `Task`, after `progress: number;`:

```ts
	attachment_required?: boolean;
```

`api.ts` — extend both bodies:

```ts
export const createTask = (
	token: string, workstreamId: string,
	body: { title: string; description?: string; status?: TaskStatus; priority?: TaskPriority | null;
		assignee_ids?: string[]; start_date?: number | null; due_date?: number | null; labels?: string[];
		attachment_required?: boolean }
) => request<Task>(token, `/workstreams/${workstreamId}/tasks`, 'POST', body);
```

and in `updateTask`'s `Pick<...>` add `| 'attachment_required'` to the key union.

`store.ts`:

1. `ModalRequest` union — add:

```ts
	| { kind: 'task'; workstreamId: string; prefill?: { status?: TaskStatus; start_date?: number | null; due_date?: number | null } }
```

2. Next to `openModal`, export the opener:

```ts
export function openTaskCreate(
	workstreamId: string,
	prefill?: { status?: TaskStatus; start_date?: number | null; due_date?: number | null }
): void {
	openModal.set({ kind: 'task', workstreamId, ...(prefill ? { prefill } : {}) });
}
```

3. `addTask` — widen the fields type and thread the new fields through the optimistic task:

```ts
export async function addTask(
	workstreamId: string,
	fields: {
		title: string; description?: string; status?: TaskStatus; priority?: TaskPriority | null;
		assignee_ids?: string[]; start_date?: number | null; due_date?: number | null;
		labels?: string[]; attachment_required?: boolean;
	}
): Promise<void> {
```

and in the `optimistic` literal change `labels: [],` to `labels: fields.labels ?? [],`, add `description: fields.description ?? null,` after `title`, and add `attachment_required: fields.attachment_required ?? false,` after `progress: 0,`.

4. `editTask` — in the catch block, after the rollback line:

```ts
	} catch (e) {
		if (before) tasks.update((list) => list.map((t) => (t.id === id ? before : t)));
		if (e === 'ATTACHMENT_REQUIRED') {
			toast.error('Attach a file before completing this task');
			return; // handled: rolled back + user informed
		}
		throw e;
	}
```

- [ ] **Step 4: Run tests**

Run: `npm run test:frontend -- --run src/lib/components/workos`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/types.ts src/lib/components/workos/lib/api.ts src/lib/components/workos/lib/store.ts src/lib/components/workos/lib/store.test.ts
git commit -m "feat(workos): task-create modal plumbing + ATTACHMENT_REQUIRED handling in store"
```

---

### Task 5: TaskCreateDialog component + mount

**Precondition:** user has approved the dialog mockup (gate outside this plan).

**Files:**
- Create: `src/lib/components/workos/views/TaskCreateDialog.svelte`
- Modify: `src/lib/components/workos/WorkOSApp.svelte` (import + mount next to `<ModalHost />` at :90)

**Interfaces:**
- Consumes: `openModal` (kind `'task'`), `addTask`, `directory`, `labels` stores (Task 4); `toggleAssignee` from `lib/assignees`; shadcn `Dialog/Select/DropdownMenu/Checkbox/Button/Input`; WorkOS `Icon`, `AssigneeAvatars`, `StatusDot`, `Pills`.
- Produces: the dialog every entry point opens in Task 6. No new exports beyond the component.

- [ ] **Step 1: Create the component**

```svelte
<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog';
	import * as Select from '$lib/components/ui/select';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import Icon from '../ui/Icon.svelte';
	import StatusDot from '../ui/StatusDot.svelte';
	import Pills from '../ui/Pills.svelte';
	import AssigneeAvatars from './AssigneeAvatars.svelte';
	import { STATUS_ORDER, STATUS_LABEL, PRIORITY_ORDER, type TaskStatus, type TaskPriority } from '../lib/types';
	import { STATUS_COLOR, statusShape } from '../lib/colors';
	import { toggleAssignee } from '../lib/assignees';
	import { openModal, addTask, directory, labels } from '../lib/store';

	$: req = $openModal?.kind === 'task' ? $openModal : null;

	let title = '';
	let assigneeIds: string[] = [];
	let description = '';
	let status: TaskStatus = 'backlog';
	let priority: TaskPriority | '' = '';
	let start = ''; // yyyy-mm-dd
	let due = '';
	let labelIds: string[] = [];
	let requireAttachment = false;
	let busy = false;
	let err = '';

	// Reset + apply prefill each time the dialog opens.
	let lastReq: typeof req = null;
	$: if (req !== lastReq) {
		lastReq = req;
		if (req) {
			title = '';
			assigneeIds = [];
			description = '';
			status = req.prefill?.status ?? 'backlog';
			priority = '';
			start = req.prefill?.start_date ? toDateInput(req.prefill.start_date) : '';
			due = req.prefill?.due_date ? toDateInput(req.prefill.due_date) : '';
			labelIds = [];
			requireAttachment = false;
			busy = false;
			err = '';
		}
	}

	function toDateInput(ts: number): string {
		return new Date(ts).toISOString().slice(0, 10);
	}

	$: members = Object.entries($directory).map(([id, u]) => ({ id, name: u.name }));
	$: labelById = Object.fromEntries($labels.map((l) => [l.id, l]));
	$: assigneeSummary =
		assigneeIds.length === 0 ? '' :
		assigneeIds.length === 1 ? ($directory[assigneeIds[0]]?.name ?? '1 assignee') :
		`${assigneeIds.length} assignees`;
	$: canSubmit = !!title.trim() && assigneeIds.length > 0 && !busy;

	function close() {
		openModal.set(null);
	}

	async function submit() {
		if (!req || !canSubmit) return;
		busy = true;
		err = '';
		try {
			await addTask(req.workstreamId, {
				title: title.trim(),
				assignee_ids: assigneeIds,
				description: description.trim() || undefined,
				status,
				priority: priority || null,
				start_date: start ? new Date(start).getTime() : null,
				due_date: due ? new Date(due).getTime() : null,
				labels: labelIds.length ? labelIds : undefined,
				attachment_required: requireAttachment
			});
			close();
		} catch (e: any) {
			err = typeof e === 'string' ? e : (e?.detail ?? 'Could not create the task.');
		} finally {
			busy = false;
		}
	}
</script>

<Dialog.Root open={req != null} onOpenChange={(o) => { if (!o) close(); }}>
	<Dialog.Content class="sm:max-w-lg rounded-2xl">
		<Dialog.Header>
			<Dialog.Title>New task</Dialog.Title>
			<Dialog.Description class="sr-only">Create a task — title and at least one assignee are required.</Dialog.Description>
		</Dialog.Header>

		{#if err}<div class="text-sm text-red-600">{err}</div>{/if}

		<div class="space-y-4">
			<!-- Title (required) -->
			<Input
				placeholder="Task title"
				bind:value={title}
				autofocus
				onkeydown={(e) => { if (e.key === 'Enter' && canSubmit) submit(); }}
			/>

			<!-- Assignees (required, multi-select) -->
			<div class="space-y-1">
				<DropdownMenu.Root>
					<DropdownMenu.Trigger
						class="w-full inline-flex items-center gap-2 rounded-md border border-gray-200 dark:border-gray-800 px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-900"
					>
						{#if assigneeIds.length}
							<AssigneeAvatars ids={assigneeIds} size={22} max={4} />
							<span>{assigneeSummary}</span>
						{:else}
							<span class="inline-flex items-center gap-1.5 text-gray-400">
								<Icon name="user" size={15} /> Assign to…
							</span>
						{/if}
						<span class="flex-1"></span>
						<Icon name="chevron-down" size={13} />
					</DropdownMenu.Trigger>
					<DropdownMenu.Content class="w-64 max-h-64 overflow-y-auto">
						{#each members as m (m.id)}
							<DropdownMenu.CheckboxItem
								checked={assigneeIds.includes(m.id)}
								closeOnSelect={false}
								onCheckedChange={() => (assigneeIds = toggleAssignee(assigneeIds, m.id))}
							>
								<span class="inline-flex items-center gap-2">
									<AssigneeAvatars ids={[m.id]} max={1} size={20} />
									{m.name}
								</span>
							</DropdownMenu.CheckboxItem>
						{/each}
						{#if !members.length}<DropdownMenu.Item disabled>No members</DropdownMenu.Item>{/if}
					</DropdownMenu.Content>
				</DropdownMenu.Root>
				{#if !assigneeIds.length}
					<p class="text-xs text-amber-600 dark:text-amber-500">At least one assignee is required.</p>
				{/if}
			</div>

			<!-- Description (optional) -->
			<textarea
				class="w-full min-h-[72px] text-sm rounded-md border border-gray-200 dark:border-gray-800 bg-transparent px-3 py-2 focus:outline-none focus:ring-1 focus:ring-primary"
				placeholder="Description (optional)"
				bind:value={description}
			></textarea>

			<!-- Status + Priority -->
			<div class="grid grid-cols-2 gap-3">
				<Select.Root type="single" bind:value={status}>
					<Select.Trigger class="w-full">
						<span class="inline-flex items-center gap-2">
							<StatusDot shape={statusShape(status)} color={STATUS_COLOR[status]} /> {STATUS_LABEL[status]}
						</span>
					</Select.Trigger>
					<Select.Content>
						{#each STATUS_ORDER as s (s)}
							<Select.Item value={s} label={STATUS_LABEL[s]} />
						{/each}
					</Select.Content>
				</Select.Root>
				<Select.Root type="single" bind:value={priority}>
					<Select.Trigger class="w-full">
						{#if priority}<Pills priority={priority} />{:else}<span class="text-gray-400">No priority</span>{/if}
					</Select.Trigger>
					<Select.Content>
						<Select.Item value="" label="No priority" />
						{#each PRIORITY_ORDER as p (p)}
							<Select.Item value={p} label={p} />
						{/each}
					</Select.Content>
				</Select.Root>
			</div>

			<!-- Dates -->
			<div class="grid grid-cols-2 gap-3">
				<div class="space-y-1">
					<Label class="text-xs text-gray-500">Start date</Label>
					<input type="date" class="w-full text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded-md px-2 py-1.5" bind:value={start} />
				</div>
				<div class="space-y-1">
					<Label class="text-xs text-gray-500">Due date</Label>
					<input type="date" class="w-full text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded-md px-2 py-1.5" bind:value={due} />
				</div>
			</div>

			<!-- Labels (optional) -->
			{#if $labels.length}
				<DropdownMenu.Root>
					<DropdownMenu.Trigger
						class="w-full inline-flex items-center gap-2 rounded-md border border-gray-200 dark:border-gray-800 px-3 py-2 text-sm hover:bg-gray-50 dark:hover:bg-gray-900"
					>
						<Icon name="tag" size={14} />
						{#if labelIds.length}
							<span>{labelIds.map((id) => labelById[id]?.name).filter(Boolean).join(', ')}</span>
						{:else}
							<span class="text-gray-400">Labels (optional)</span>
						{/if}
						<span class="flex-1"></span>
						<Icon name="chevron-down" size={13} />
					</DropdownMenu.Trigger>
					<DropdownMenu.Content class="w-64 max-h-64 overflow-y-auto">
						{#each $labels as l (l.id)}
							<DropdownMenu.CheckboxItem
								checked={labelIds.includes(l.id)}
								closeOnSelect={false}
								onCheckedChange={(v) => (labelIds = v ? [...labelIds, l.id] : labelIds.filter((x) => x !== l.id))}
							>
								<span class="inline-flex items-center gap-2">
									<span class="w-2 h-2 rounded-full" style="background:{l.color}"></span>{l.name}
								</span>
							</DropdownMenu.CheckboxItem>
						{/each}
					</DropdownMenu.Content>
				</DropdownMenu.Root>
			{/if}

			<!-- Require attachment to complete -->
			<label class="flex items-start gap-2.5 rounded-lg border border-gray-200 dark:border-gray-800 px-3 py-2.5 cursor-pointer">
				<Checkbox bind:checked={requireAttachment} class="mt-0.5" />
				<span class="text-sm">
					<span class="inline-flex items-center gap-1.5 font-medium"><Icon name="paperclip" size={14} /> Require attachment to complete</span>
					<span class="block text-xs text-gray-500 dark:text-gray-400 mt-0.5">The task can't be marked Done until a file is attached.</span>
				</span>
			</label>
		</div>

		<Dialog.Footer>
			<Button variant="outline" size="sm" onclick={close}>Cancel</Button>
			<Button size="sm" onclick={submit} disabled={!canSubmit}>Create task</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
```

Adaptation notes for the implementer (verify against the actual codebase, these are known risk spots):
- If `Checkbox` doesn't support `bind:checked` in this shadcn-svelte version, use `checked={requireAttachment} onCheckedChange={(v) => (requireAttachment = !!v)}`.
- If `Icon` has no `tag` glyph, use `sliders` or add the glyph to `ui/Icon.svelte` following its existing string-path pattern.
- `Select.Item value=""` for "No priority": if the Select component treats `''` as unselectable, use value `'none'` and map it to `null` in `submit()`.

- [ ] **Step 2: Mount it** — in `WorkOSApp.svelte`, next to the ModalHost import:

```ts
	import TaskCreateDialog from './views/TaskCreateDialog.svelte';
```

and next to `<ModalHost />`:

```svelte
	<TaskCreateDialog />
```

- [ ] **Step 3: Static check**

Run: `npm run check`
Expected: no NEW errors vs. the pre-task baseline (run it before editing if unsure).

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/views/TaskCreateDialog.svelte src/lib/components/workos/WorkOSApp.svelte
git commit -m "feat(workos): TaskCreateDialog — title + assignee required, attachment flag"
```

---

### Task 6: rewire all entry points to the dialog

**Files:**
- Modify: `src/lib/components/workos/views/BoardView.svelte` (:99-136 handlers, :144-151 top add, :183-191 column add)
- Modify: `src/lib/components/workos/views/ListView.svelte` (:47-82 handlers, :103-115 toolbar add, :233-248 group add)
- Modify: `src/lib/components/workos/views/TimelineView.svelte` (:66-85 submitNew, :150-169 submitRow, :190-203 toolbar UI, plus the bottom-row quick-add markup that uses `addingRow`)
- Modify: `src/lib/components/workos/views/calendar/DayCell.svelte` (:17-28 submit, :58-77 input/button)

**Interfaces:**
- Consumes: `openTaskCreate` (Task 4). After this task `addTask` has NO view callers left (only the dialog calls it); the removed local state (`adding`, `newTitle`, `creatingTop`, `topTitle`, `creatingNew`, `newGlobalTitle`, `addingRow`, `rowTitle`, DayCell `adding`/`title`) and their submit functions must be deleted, along with now-unused imports (`addTask`, `Input` where it was only used for quick-add).

- [ ] **Step 1: BoardView** — delete `submitAdd`, `submitTop`, and the `adding/newTitle/creatingTop/topTitle` state. Top button becomes:

```svelte
	<Button size="sm" onclick={() => { const ws = $currentWorkstream; if (ws) openTaskCreate(ws.id); }}>
		<Icon name="plus" size={15} /> Add New
	</Button>
```

(remove the `{#if creatingTop}` Input branch entirely). Column "+" button becomes:

```svelte
	<Button variant="ghost" size="icon-xs" class="text-gray-400 hover:text-gray-600"
		onclick={() => { const ws = $currentWorkstream; if (ws) openTaskCreate(ws.id, { status }); }}
		title="Add task"><Icon name="plus" size={16} /></Button>
```

Delete the `{#if adding === status}` Input block at the bottom of each column and the `adding !== status` condition in the empty-column hint (becomes just `{#if !(byStatus[status]?.length)}`). Import `openTaskCreate` from `../lib/store` (drop `addTask`; keep `Input` only if still used — it isn't, drop it; `toast` stays only if still used — it isn't after removing the handlers, drop it). New cards arriving via the dialog follow the same path as realtime `task.created` events, which the board already renders without re-initializing SortableJS — no `initSortables()` call is needed.

- [ ] **Step 2: ListView** — delete `submitAdd`, `submitNew`, `adding/newTitle/creatingNew/newGlobalTitle`. Toolbar button:

```svelte
	<Button size="sm" onclick={() => { const ws = $currentWorkstream; if (ws) openTaskCreate(ws.id); }}>
		<Icon name="plus" size={15} /> Add new
	</Button>
```

Group-footer button:

```svelte
	<Button variant="ghost" size="sm" class="text-primary"
		onclick={() => { const ws = $currentWorkstream; if (ws) openTaskCreate(ws.id, { status }); }}>
		<Icon name="plus" size={15} /> Add task
	</Button>
```

Remove both `{#if creatingNew}` / `{#if adding === status}` Input branches. Swap `addTask` → `openTaskCreate` in the store import; drop `Input` and `toast` if now unused (`toast` — check remaining usages first).

- [ ] **Step 3: TimelineView** — delete `submitNew`, `submitRow`, `creatingNew/newTitle/addingRow/rowTitle`. Both add affordances call:

```ts
	const ts = dayToTs(todayDay(Date.now()));
	openTaskCreate(ws.id, { start_date: ts, due_date: ts });
```

i.e. toolbar button:

```svelte
	<Button size="sm" onclick={() => { const ws = $currentWorkstream; if (!ws) return; const ts = dayToTs(todayDay(Date.now())); openTaskCreate(ws.id, { start_date: ts, due_date: ts }); }}>
		<Icon name="plus" size={15} /> Add new
	</Button>
```

and the bottom-row quick-add (find the markup using `addingRow`) becomes a plain button with the same handler. Swap store import `addTask` → `openTaskCreate`.

- [ ] **Step 4: DayCell** — delete `adding/title/submit`. The plus button:

```svelte
	onclick={() => { const ws = $currentWorkstream; if (ws) openTaskCreate(ws.id, { due_date: dayKey(date.getTime()) }); }}
```

Remove the `{#if adding}` input branch (button no longer conditional). Swap import `addTask` → `openTaskCreate`.

- [ ] **Step 5: Verify**

Run: `npm run check` — expect no new errors (in particular: no unused-import warnings for the files touched).
Run: `npm run test:frontend -- --run src/lib/components/workos` — expect ALL PASS.
Grep: `grep -rn "addTask" src/lib/components/workos --include=*.svelte` — expect ZERO hits (store + tests only).

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/workos/views/
git commit -m "feat(workos): all task-add entry points open the create dialog"
```

---

### Task 7: flag affordances — detail toggle, done hint, card/list badges

**Files:**
- Modify: `src/lib/components/workos/lib/roles.ts` (append predicate)
- Test: `src/lib/components/workos/lib/roles.test.ts` (append)
- Modify: `src/lib/components/workos/views/TaskDetail.svelte` (status dropdown :266-287, new PropertyRow after the Assignee row ~:359; add `attachments` + `user` imports)
- Modify: `src/lib/components/workos/views/TaskCard.svelte` (footer :129-145)
- Modify: `src/lib/components/workos/views/ListView.svelte` (desktop row title :151-154, mobile card meta :218-224)

**Interfaces:**
- Consumes: `Task.attachment_required`, `attachments` store (already holds ALL attachment rows for the open task, comment-level included — matches the server's count), `editTask` (Task 4 handles the 400).
- Produces: `canToggleAttachmentRequired(task, user)` in `roles.ts`.

- [ ] **Step 1: Failing predicate test** — append to `roles.test.ts` (match its existing import style):

```ts
describe('canToggleAttachmentRequired', () => {
	const task = { created_by_id: 'u1' } as Task;
	it('creator may toggle', () => {
		expect(canToggleAttachmentRequired(task, { id: 'u1', role: 'user' })).toBe(true);
	});
	it('app admin may toggle', () => {
		expect(canToggleAttachmentRequired(task, { id: 'zz', role: 'admin' })).toBe(true);
	});
	it('assignee / other members may not', () => {
		expect(canToggleAttachmentRequired(task, { id: 'u2', role: 'user' })).toBe(false);
	});
	it('legacy task without creator: admin only', () => {
		const legacy = { created_by_id: null } as Task;
		expect(canToggleAttachmentRequired(legacy, { id: 'u1', role: 'user' })).toBe(false);
		expect(canToggleAttachmentRequired(legacy, { id: 'u1', role: 'admin' })).toBe(true);
	});
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npm run test:frontend -- --run src/lib/components/workos/lib/roles.test.ts`
Expected: FAIL — not exported.

- [ ] **Step 3: Implement predicate** — append to `roles.ts`:

```ts
// Mirrors the server capability 'task.flag.attachment_required': app-admin → creator.
export function canToggleAttachmentRequired(
	task: Task,
	user: { id?: string; role?: string } | null | undefined
): boolean {
	if (!user) return false;
	return user.role === 'admin' || (task.created_by_id != null && task.created_by_id === user.id);
}
```

- [ ] **Step 4: Run predicate tests** — expect PASS.

- [ ] **Step 5: TaskDetail** — add imports: `attachments` to the store import list, `user` from `$lib/stores`, `canToggleAttachmentRequired` from `../lib/roles`. Add reactive state near the top:

```ts
	$: needsAttachment = !!t?.attachment_required && $attachments.length === 0;
	$: canToggleRequired = !!t && canToggleAttachmentRequired(t, $user);
```

In the status dropdown, mark the Done item (inside the `{#each STATUS_ORDER as s}` loop):

```svelte
	<DropdownMenu.Item onSelect={() => editTask(t.id, { status: s })}>
		<span class="inline-flex items-center gap-2">
			<StatusDot shape={statusShape(s)} color={STATUS_COLOR[s]} /> {STATUS_LABEL[s]}
			{#if s === 'done' && needsAttachment}
				<span class="inline-flex items-center gap-1 text-[11px] text-amber-600 dark:text-amber-500">
					<Icon name="paperclip" size={12} /> attachment required
				</span>
			{/if}
		</span>
	</DropdownMenu.Item>
```

(Selecting Done with no attachment still fires `editTask`; the server rejects and the store toasts — the hint is advisory.) After the Assignee `PropertyRow`, add:

```svelte
	<!-- Attachment requirement (creator/app-admin may toggle; others see state) -->
	<PropertyRow icon="paperclip" label="Attachment">
		{#if canToggleRequired}
			<button
				class="inline-flex items-center gap-2 rounded-md px-1 -mx-1 py-0.5 hover:bg-gray-100 dark:hover:bg-gray-900"
				onclick={() => editTask(t.id, { attachment_required: !t.attachment_required })}
			>
				{#if t.attachment_required}
					<Badge variant="secondary" class="text-amber-700 dark:text-amber-400">Required to complete</Badge>
				{:else}
					<span class="text-gray-400">Not required</span>
				{/if}
			</button>
		{:else if t.attachment_required}
			<Badge variant="secondary" class="text-amber-700 dark:text-amber-400">Required to complete</Badge>
		{:else}
			<span class="text-gray-400">Not required</span>
		{/if}
	</PropertyRow>
```

(`Badge` is already imported in TaskDetail.)

- [ ] **Step 6: TaskCard badge** — in the footer div (:129), before the subtask counter:

```svelte
	{#if task.attachment_required}
		<span class="flex-none text-amber-600 dark:text-amber-500" title="Attachment required to complete">
			<Icon name="paperclip" size={13} />
		</span>
	{/if}
```

- [ ] **Step 7: ListView badges** — desktop row, after the title button inside the name span:

```svelte
	{#if task.attachment_required}
		<span class="flex-none text-amber-600 dark:text-amber-500" title="Attachment required to complete"><Icon name="paperclip" size={13} /></span>
	{/if}
```

Mobile card: same snippet inside the meta row (`task.key` / due-date line).

- [ ] **Step 8: Verify + commit**

Run: `npm run test:frontend -- --run src/lib/components/workos` and `npm run check` — expect PASS / no new errors.

```bash
git add src/lib/components/workos/lib/roles.ts src/lib/components/workos/lib/roles.test.ts src/lib/components/workos/views/TaskDetail.svelte src/lib/components/workos/views/TaskCard.svelte src/lib/components/workos/views/ListView.svelte
git commit -m "feat(workos): attachment-required affordances — detail toggle, done hint, badges"
```

---

### Task 8: full verification sweep

**Files:** none new (fixes only if something fails).

- [ ] **Step 1: Backend suite**

Run: `.venv\Scripts\python.exe -m pytest backend\open_webui\test\workos -q`
Expected: ALL PASS.

- [ ] **Step 2: Frontend suite + types**

Run: `npm run test:frontend -- --run src/lib/components/workos`
Run: `npm run check`
Expected: ALL PASS / no new errors.

- [ ] **Step 3: Consistency greps**

- `grep -rn "attachment_required" backend/open_webui | grep -v test` → model column, TaskModel, DAO insert, both forms, create_task pass-through, capability entry, guard. Nothing else.
- `grep -rn "ATTACHMENT_REQUIRED" src backend` → router guard, store handler, backend tests, store test. Nothing else.
- `grep -rn "addTask" src/lib/components/workos --include=*.svelte` → only `TaskCreateDialog.svelte`.

- [ ] **Step 4: Commit any stragglers; report**

Report to the operator: suite counts, and that browser smoke (all entry points + prefills, drag-to-done rejection toast, detail toggle permissions, migration against the Docker container DB) remains a manual follow-up — do NOT start a dev server for it.
