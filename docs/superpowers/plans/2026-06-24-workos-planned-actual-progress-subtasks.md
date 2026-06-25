# WorkOS Planned vs Actual Progress and Subtasks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional task start dates and subtasks, then show planned progress, actual progress, and schedule health without replacing the manual workflow status or kanban drag/drop behavior.

**Architecture:** Keep `Task.status` as the user-controlled workflow state used by kanban columns. Keep the existing `Task.progress` column as the manual actual-progress fallback when a task has no subtasks. Add `Task.start_date`, a new `workos_subtask` table, computed `subtask_total` / `subtask_completed` counts on task API responses, frontend progress helper functions, and a real subtasks tab in the task detail dialog.

**Tech Stack:** SQLAlchemy async + Pydantic + FastAPI, Alembic migrations, pytest/pytest-asyncio + httpx, Svelte 5 + TypeScript + Tailwind, Vitest.

## Global Constraints

- **Status remains manual:** `status` is still edited by users and by kanban drag/drop. Planned/actual progress never moves a task between columns.
- **Kanban remains workflow-first:** board columns continue to represent `Task.status`, not schedule health.
- **Actual progress source:** if `subtask_total > 0`, actual progress is `round(subtask_completed / subtask_total * 100)`; otherwise actual progress is the existing `progress` field.
- **Planned progress source:** only calculate planned progress when both `start_date` and `due_date` exist.
- **Health labels:** use `on_track`, `at_risk`, `behind`, and `overdue`; do not store health in the database.
- **Date storage:** store `start_date` and `due_date` as epoch milliseconds, matching the existing `due_date` field.
- **No dependency changes:** use existing Svelte, Tailwind, FastAPI, SQLAlchemy, Alembic, and Vitest tooling.
- **Realtime:** subtask changes must update the open task detail and the board card counts through the existing WorkOS workstream socket room.
- **No hidden automation:** setting status to `done` must not silently mark subtasks complete in this version. If a done task has incomplete subtasks, show the mismatch as health/progress information.

---

## File Map

- `backend/open_webui/models/workos.py` - add `start_date`, `WorkosSubtask`, `SubtaskModel`, `SubtasksDao`, subtask count enrichment, and activity field mapping.
- `backend/open_webui/routers/workos.py` - accept `start_date`, validate schedule dates, add subtask CRUD endpoints, emit task/subtask/activity events.
- `backend/open_webui/migrations/versions/b4c5d6e7f8a9_add_workos_task_schedule_and_subtasks.py` - add task start date and subtask table.
- `backend/open_webui/test/workos/test_models_task.py` - add DAO coverage for start dates and subtask counts.
- `backend/open_webui/test/workos/test_router_task.py` - add API coverage for schedule validation and subtask CRUD.
- `src/lib/components/workos/lib/types.ts` - add `start_date`, computed subtask counts, `Subtask`, and subtask activity event types.
- `src/lib/components/workos/lib/api.ts` - add `start_date` to task payloads and add subtask API wrappers.
- `src/lib/components/workos/lib/store.ts` - add `subtasks` state, subtask actions, load/reset behavior, and realtime reconciliation.
- `src/lib/components/workos/lib/progress.ts` - pure planned/actual/health helpers.
- `src/lib/components/workos/lib/progress.test.ts` - Vitest coverage for progress and health math.
- `src/lib/components/workos/views/detail/SubtasksPanel.svelte` - real subtasks tab UI.
- `src/lib/components/workos/views/TaskDetail.svelte` - add start date row, actual/planned progress display, health badge, and `SubtasksPanel`.
- `src/lib/components/workos/views/TaskCard.svelte` - show compact subtask count and health summary.

---

### Task 1: Backend Task Schedule and Subtask Data Model

**Files:**
- Modify: `backend/open_webui/models/workos.py`
- Modify: `backend/open_webui/test/workos/test_models_task.py`
- Create: `backend/open_webui/migrations/versions/b4c5d6e7f8a9_add_workos_task_schedule_and_subtasks.py`

**Interfaces:**
- Produces: `TaskModel.start_date: Optional[int] = None`
- Produces: `TaskModel.subtask_total: int = 0`
- Produces: `TaskModel.subtask_completed: int = 0`
- Produces: `SubtaskModel`
- Produces: `Subtasks.insert(task_id, title, created_by_id, sort_key=None, db=None)`
- Produces: `Subtasks.list_for_task(task_id, db=None)`
- Produces: `Subtasks.update_fields(id, fields, db=None)`
- Produces: `Subtasks.delete(id, db=None)`

- [ ] **Step 1: Write failing model tests**

Append to `backend/open_webui/test/workos/test_models_task.py`:

```python
@pytest.mark.asyncio
async def test_task_start_date_round_trips():
    team, s = await _stream()
    t = await Tasks.insert(
        s.id, team.id, team.key, 'Scheduled task', 'u1',
        start_date=1_788_120_000_000,
        due_date=1_788_465_600_000,
    )
    assert t.start_date == 1_788_120_000_000
    assert t.due_date == 1_788_465_600_000

    updated = await Tasks.update_fields(t.id, {'start_date': 1_788_206_400_000})
    assert updated.start_date == 1_788_206_400_000


@pytest.mark.asyncio
async def test_subtask_counts_enrich_task_models():
    from open_webui.models.workos import Subtasks

    team, s = await _stream()
    task = await Tasks.insert(s.id, team.id, team.key, 'Parent', 'u1')
    first = await Subtasks.insert(task.id, 'Draft', 'u1')
    await Subtasks.insert(task.id, 'Review', 'u1')
    await Subtasks.update_fields(first.id, {'completed': True})

    reloaded = await Tasks.get_by_id(task.id)
    assert reloaded.subtask_total == 2
    assert reloaded.subtask_completed == 1

    listed = await Tasks.list_for_workstream(s.id)
    parent = next(t for t in listed if t.id == task.id)
    assert parent.subtask_total == 2
    assert parent.subtask_completed == 1
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/test_models_task.py -k "start_date or subtask_counts" -v`

Expected: fail because `start_date` and `Subtasks` do not exist.

- [ ] **Step 3: Add model fields, subtask table, and DAO**

In `backend/open_webui/models/workos.py`, add `func` to the existing SQLAlchemy imports if it is not present:

```python
from sqlalchemy import Boolean, Column, Float, Integer, BigInteger, JSON, Text, select, delete, func
```

Add `start_date` to `WorkosTask` before `due_date`:

```python
    start_date = Column(BigInteger, nullable=True)
```

Add `start_date`, `subtask_total`, and `subtask_completed` to `TaskModel`:

```python
    start_date: Optional[int] = None
    due_date: Optional[int] = None
    progress: int
    subtask_total: int = 0
    subtask_completed: int = 0
```

Add `start_date` to `TasksDao.insert` parameters and row creation:

```python
        assignee_id: Optional[str] = None, start_date: Optional[int] = None,
        due_date: Optional[int] = None, labels: Optional[list] = None,
```

```python
                priority=priority, assignee_id=assignee_id, start_date=start_date,
                due_date=due_date, progress=0,
```

Append after `WorkosTask`:

```python
class WorkosSubtask(Base):
    __tablename__ = 'workos_subtask'

    id = Column(Text, primary_key=True, unique=True)
    task_id = Column(Text)
    title = Column(Text)
    completed = Column(Boolean, default=False)
    sort_key = Column(Float, default=0.0)
    created_by_id = Column(Text, nullable=True)
    completed_at = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)
```

Append after `TaskModel`:

```python
class SubtaskModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_id: str
    title: str
    completed: bool = False
    sort_key: float
    created_by_id: Optional[str] = None
    completed_at: Optional[int] = None
    created_at: int
    updated_at: int
```

Add this helper inside `TasksDao`:

```python
    async def _with_counts(self, rows: list[WorkosTask], db: AsyncSession) -> list[TaskModel]:
        if not rows:
            return []
        ids = [r.id for r in rows]
        res = await db.execute(
            select(
                WorkosSubtask.task_id,
                func.count(WorkosSubtask.id),
                func.sum(WorkosSubtask.completed.cast(Integer)),
            )
            .where(WorkosSubtask.task_id.in_(ids))
            .group_by(WorkosSubtask.task_id)
        )
        counts = {task_id: (total or 0, completed or 0) for task_id, total, completed in res.all()}
        out = []
        for row in rows:
            model = TaskModel.model_validate(row)
            total, completed = counts.get(row.id, (0, 0))
            model.subtask_total = int(total)
            model.subtask_completed = int(completed)
            out.append(model)
        return out
```

Update `TasksDao.insert` after `await db.refresh(row)`:

```python
            return (await self._with_counts([row], db))[0]
```

Update `TasksDao.get_by_id`:

```python
            if not row:
                return None
            return (await self._with_counts([row], db))[0]
```

Update `TasksDao.list_for_workstream`:

```python
            rows = res.scalars().all()
            return await self._with_counts(rows, db)
```

Update `TasksDao.update_fields` after `await db.refresh(row)`:

```python
            return (await self._with_counts([row], db))[0]
```

Append before `Labels = LabelsDao()` or near `TasksDao`:

```python
class SubtasksDao:
    async def insert(
        self, task_id: str, title: str, created_by_id: Optional[str],
        *, sort_key: Optional[float] = None, db: Optional[AsyncSession] = None,
    ) -> SubtaskModel:
        async with get_async_db_context(db) as db:
            now = _now()
            row = WorkosSubtask(
                id=_id(), task_id=task_id, title=title, completed=False,
                sort_key=sort_key if sort_key is not None else float(now),
                created_by_id=created_by_id, completed_at=None, created_at=now, updated_at=now,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return SubtaskModel.model_validate(row)

    async def get_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[SubtaskModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosSubtask).filter_by(id=id))
            row = res.scalars().first()
            return SubtaskModel.model_validate(row) if row else None

    async def list_for_task(self, task_id: str, db: Optional[AsyncSession] = None) -> list[SubtaskModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosSubtask).filter_by(task_id=task_id).order_by(WorkosSubtask.sort_key.asc())
            )
            return [SubtaskModel.model_validate(r) for r in res.scalars().all()]

    async def update_fields(self, id: str, fields: dict, db: Optional[AsyncSession] = None) -> Optional[SubtaskModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosSubtask).filter_by(id=id))
            row = res.scalars().first()
            if not row:
                return None
            if 'completed' in fields:
                row.completed_at = _now() if fields['completed'] else None
            for k, v in fields.items():
                setattr(row, k, v)
            row.updated_at = _now()
            await db.commit()
            await db.refresh(row)
            return SubtaskModel.model_validate(row)

    async def delete(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosSubtask).filter_by(id=id))
            if not res.scalars().first():
                return False
            await db.execute(delete(WorkosSubtask).filter_by(id=id))
            await db.commit()
            return True
```

Instantiate it near `Tasks = TasksDao()`:

```python
Subtasks = SubtasksDao()
```

- [ ] **Step 4: Add the migration**

Create `backend/open_webui/migrations/versions/b4c5d6e7f8a9_add_workos_task_schedule_and_subtasks.py`:

```python
"""add workos task schedule and subtasks

Revision ID: b4c5d6e7f8a9
Revises: a2b3c4d5e6f7
Create Date: 2026-06-24 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b4c5d6e7f8a9'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workos_task', sa.Column('start_date', sa.BigInteger(), nullable=True))
    op.create_table(
        'workos_subtask',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('task_id', sa.Text(), nullable=True),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('completed', sa.Boolean(), nullable=True),
        sa.Column('sort_key', sa.Float(), nullable=True),
        sa.Column('created_by_id', sa.Text(), nullable=True),
        sa.Column('completed_at', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_workos_subtask_task_id', 'workos_subtask', ['task_id'])


def downgrade() -> None:
    op.drop_index('ix_workos_subtask_task_id', table_name='workos_subtask')
    op.drop_table('workos_subtask')
    op.drop_column('workos_task', 'start_date')
```

- [ ] **Step 5: Run model tests**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/test_models_task.py -v`

Expected: all task model tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/models/workos.py backend/open_webui/test/workos/test_models_task.py backend/open_webui/migrations/versions/b4c5d6e7f8a9_add_workos_task_schedule_and_subtasks.py
git commit -m "feat(workos): add task start date and subtask model"
```

---

### Task 2: Backend Task Schedule Validation and Subtask API

**Files:**
- Modify: `backend/open_webui/routers/workos.py`
- Modify: `backend/open_webui/test/workos/test_router_task.py`

**Interfaces:**
- Produces: task create/update payloads with `start_date`
- Produces: `GET /tasks/{task_id}/subtasks`
- Produces: `POST /tasks/{task_id}/subtasks`
- Produces: `PATCH /subtasks/{subtask_id}`
- Produces: `DELETE /subtasks/{subtask_id}`

- [ ] **Step 1: Write failing router tests**

Append to `backend/open_webui/test/workos/test_router_task.py`:

```python
@pytest.mark.asyncio
async def test_task_schedule_fields_and_validation(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        r = await c.post(
            f"/api/v1/workos/workstreams/{s['id']}/tasks",
            json={'title': 'Scheduled', 'start_date': 1000, 'due_date': 2000},
        )
        assert r.status_code == 200, r.text
        t = r.json()
        assert t['start_date'] == 1000
        assert t['due_date'] == 2000

        bad = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'start_date': 3000, 'due_date': 2000})
        assert bad.status_code == 400
        assert 'Start date must be before due date' in bad.text


@pytest.mark.asyncio
async def test_subtask_crud_updates_parent_counts(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        task = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'Parent'})).json()

        created = (await c.post(f"/api/v1/workos/tasks/{task['id']}/subtasks", json={'title': 'Draft'})).json()
        assert created['title'] == 'Draft'
        assert created['completed'] is False

        listed = (await c.get(f"/api/v1/workos/tasks/{task['id']}/subtasks")).json()
        assert [s['id'] for s in listed] == [created['id']]

        updated = (await c.patch(f"/api/v1/workos/subtasks/{created['id']}", json={'completed': True})).json()
        assert updated['completed'] is True
        assert updated['completed_at'] is not None

        parent = (await c.get(f"/api/v1/workos/tasks/{task['id']}")).json()
        assert parent['subtask_total'] == 1
        assert parent['subtask_completed'] == 1

        deleted = (await c.delete(f"/api/v1/workos/subtasks/{created['id']}")).json()
        assert deleted['deleted'] is True
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/test_router_task.py -k "schedule_fields or subtask_crud" -v`

Expected: fail because `start_date` and subtask routes are not wired.

- [ ] **Step 3: Add router schemas and validation**

In `backend/open_webui/routers/workos.py`, extend the model import with:

```python
    Subtasks,
```

Add `start_date` to `TaskCreateForm` and `TaskUpdateForm`:

```python
    start_date: Optional[int] = None
```

Add subtask forms near task forms:

```python
class SubtaskCreateForm(BaseModel):
    title: str
    sort_key: Optional[float] = None


class SubtaskUpdateForm(BaseModel):
    title: Optional[str] = None
    completed: Optional[bool] = None
    sort_key: Optional[float] = None
```

Replace `_validate_task_fields` with:

```python
def _validate_task_fields(fields: dict, *, current: Optional[dict] = None) -> None:
    if fields.get('status') is not None and fields['status'] not in STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid status.')
    if fields.get('priority') is not None and fields['priority'] not in PRIORITIES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid priority.')
    if fields.get('progress') is not None and not (0 <= fields['progress'] <= 100):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Progress out of range.')
    start = fields.get('start_date', (current or {}).get('start_date'))
    due = fields.get('due_date', (current or {}).get('due_date'))
    if start is not None and due is not None and start > due:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Start date must be before due date.')
```

In `create_task`, pass `start_date=form.start_date` to `Tasks.insert`.

In `update_task`, call:

```python
    _validate_task_fields(fields, current=task.model_dump())
```

Add `'start_date': 'start_changed'` to `_ACTIVITY_FIELDS` in `models/workos.py`.

- [ ] **Step 4: Add subtask visibility helper and endpoints**

Append to `backend/open_webui/routers/workos.py` near task endpoints:

```python
async def require_subtask_visible(user, subtask_id: str, db: AsyncSession):
    subtask = await Subtasks.get_by_id(subtask_id, db=db)
    if not subtask:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Subtask not found.')
    task, stream = await require_task_visible(user, subtask.task_id, db)
    return subtask, task, stream


async def _emit_parent_after_subtask(task_id: str, db: AsyncSession):
    task = await Tasks.get_by_id(task_id, db=db)
    if task:
        await emit_event('workos:task.updated', f'workos:workstream:{task.workstream_id}', task.model_dump())
    return task


@router.get('/tasks/{task_id}/subtasks')
async def list_subtasks(
    request: Request, task_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    await require_task_visible(user, task_id, db)
    return await Subtasks.list_for_task(task_id, db=db)


@router.post('/tasks/{task_id}/subtasks')
async def create_subtask(
    request: Request, task_id: str, form: SubtaskCreateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    task, _ = await require_task_visible(user, task_id, db)
    if not form.title.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Subtask title is required.')
    subtask = await Subtasks.insert(task_id, form.title.strip(), user.id, sort_key=form.sort_key, db=db)
    payload = {**subtask.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id}
    await emit_event('workos:subtask.created', f'workos:workstream:{task.workstream_id}', payload)
    await _emit_parent_after_subtask(task_id, db)
    row = await Activity.insert(task_id, task.team_id, user.id, 'subtask_created', {'title': subtask.title}, db=db)
    await _emit_task_room('workos:activity.created', task, {**row.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id})
    return subtask


@router.patch('/subtasks/{subtask_id}')
async def update_subtask(
    request: Request, subtask_id: str, form: SubtaskUpdateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    subtask, task, _ = await require_subtask_visible(user, subtask_id, db)
    fields = form.model_dump(exclude_none=True)
    if 'title' in fields:
        fields['title'] = fields['title'].strip()
        if not fields['title']:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Subtask title is required.')
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
    return updated


@router.delete('/subtasks/{subtask_id}')
async def delete_subtask(
    request: Request, subtask_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    subtask, task, _ = await require_subtask_visible(user, subtask_id, db)
    deleted = await Subtasks.delete(subtask_id, db=db)
    await emit_event(
        'workos:subtask.deleted',
        f'workos:workstream:{task.workstream_id}',
        {'id': subtask_id, 'task_id': task.id, 'workstream_id': task.workstream_id, 'actor_id': user.id},
    )
    await _emit_parent_after_subtask(task.id, db)
    return {'deleted': deleted}
```

- [ ] **Step 5: Run router tests**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/test_router_task.py -v`

Expected: all task router tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/models/workos.py backend/open_webui/test/workos/test_router_task.py
git commit -m "feat(workos): expose task schedule and subtask API"
```

---

### Task 3: Frontend Types, API, Store, and Realtime

**Files:**
- Modify: `src/lib/components/workos/lib/types.ts`
- Modify: `src/lib/components/workos/lib/api.ts`
- Modify: `src/lib/components/workos/lib/store.ts`
- Modify: `src/lib/components/workos/lib/store.test.ts`

**Interfaces:**
- Produces: `Subtask` frontend type.
- Produces: `subtasks: Writable<Subtask[]>`.
- Produces: `addSubtask(taskId, title)`, `editSubtask(id, fields)`, `removeSubtask(id)`.
- Produces: realtime support for `workos:subtask.created`, `workos:subtask.updated`, `workos:subtask.deleted`.

- [ ] **Step 1: Write failing store tests**

In `src/lib/components/workos/lib/store.test.ts`, extend the existing lower import from `./store` so it includes `subtasks`:

```ts
import {
	selectedTaskId, comments, activity, unreadCount, notifications,
	applyCollabEvent, applyNotificationEvent, subtasks
} from './store';
```

Then append:

```ts
describe('subtask realtime', () => {
	it('applies subtask events only for the open task', () => {
		selectedTaskId.set('task-1');
		subtasks.set([]);
		applyCollabEvent('workos:subtask.created', {
			id: 's1', task_id: 'task-1', title: 'Draft', completed: false,
			sort_key: 1, created_by_id: 'u1', completed_at: null, created_at: 1, updated_at: 1
		});
		expect(get(subtasks).map((s) => s.id)).toEqual(['s1']);

		applyCollabEvent('workos:subtask.updated', {
			id: 's1', task_id: 'task-1', title: 'Draft', completed: true,
			sort_key: 1, created_by_id: 'u1', completed_at: 2, created_at: 1, updated_at: 2
		});
		expect(get(subtasks)[0].completed).toBe(true);

		applyCollabEvent('workos:subtask.deleted', { id: 's1', task_id: 'task-1' });
		expect(get(subtasks)).toEqual([]);
	});
});
```

Extend the existing `vi.mock('./api'...)` object with:

```ts
	listSubtasks: vi.fn(async () => []),
	createSubtask: vi.fn(async (t, taskId, body) => ({
		id: 'sub-1', task_id: taskId, title: body.title, completed: false,
		sort_key: 1, created_by_id: 'u1', completed_at: null, created_at: 1, updated_at: 1
	})),
	updateSubtask: vi.fn(async (t, id, body) => ({ id, task_id: 'task-1', title: 'Sub', completed: !!body.completed, sort_key: 1, created_at: 1, updated_at: 2 })),
	deleteSubtask: vi.fn(async () => ({ deleted: true })),
```

- [ ] **Step 2: Run tests to verify failure**

Run: `npm run test:frontend -- src/lib/components/workos/lib/store.test.ts`

Expected: fail because `subtasks` and subtask event handling do not exist.

- [ ] **Step 3: Update frontend types**

In `src/lib/components/workos/lib/types.ts`, update `Task`:

```ts
	start_date?: number | null;
	due_date?: number | null;
	progress: number;
	subtask_total?: number;
	subtask_completed?: number;
```

Add:

```ts
export interface Subtask {
	id: string;
	task_id: string;
	title: string;
	completed: boolean;
	sort_key: number;
	created_by_id?: string | null;
	completed_at?: number | null;
	created_at: number;
	updated_at: number;
}
```

Extend `ActivityType` with:

```ts
	| 'start_changed' | 'subtask_created' | 'subtask_completed' | 'subtask_reopened'
```

- [ ] **Step 4: Update API wrappers**

In `src/lib/components/workos/lib/api.ts`, add `Subtask` to the type import list.

Add `start_date?: number | null` to `createTask` and `updateTask` payload types.

Append:

```ts
export const listSubtasks = (token: string, taskId: string) =>
	request<Subtask[]>(token, `/tasks/${taskId}/subtasks`);
export const createSubtask = (token: string, taskId: string, body: { title: string; sort_key?: number }) =>
	request<Subtask>(token, `/tasks/${taskId}/subtasks`, 'POST', body);
export const updateSubtask = (
	token: string, id: string, body: Partial<Pick<Subtask, 'title' | 'completed' | 'sort_key'>>
) => request<Subtask>(token, `/subtasks/${id}`, 'PATCH', body);
export const deleteSubtask = (token: string, id: string) =>
	request<{ deleted: boolean }>(token, `/subtasks/${id}`, 'DELETE');
```

- [ ] **Step 5: Update store state and actions**

In `src/lib/components/workos/lib/store.ts`, add `type Subtask` to the type import list.

Add near the existing detail stores:

```ts
export const subtasks: Writable<Subtask[]> = writable([]);
```

Update `closeTask()`:

```ts
	subtasks.set([]);
```

Update `loadTaskDetail()`:

```ts
	const [c, a, at, st] = await Promise.all([
		api.listComments(token(), taskId).catch(() => []),
		api.listActivity(token(), taskId).catch(() => []),
		api.listAttachments(token(), taskId).catch(() => []),
		api.listSubtasks(token(), taskId).catch(() => [])
	]);
```

Set the loaded subtasks after the selected-task guard:

```ts
	subtasks.set(st);
```

Append actions near the attachment actions:

```ts
export async function addSubtask(taskId: string, title: string): Promise<void> {
	const saved = await api.createSubtask(token(), taskId, { title });
	subtasks.update((list) => (list.some((s) => s.id === saved.id) ? list : [...list, saved]));
	const refreshed = await api.getTask(token(), taskId).catch(() => null);
	if (refreshed) tasks.update((list) => list.map((t) => (t.id === taskId ? refreshed : t)));
}

export async function editSubtask(id: string, fields: Partial<Pick<Subtask, 'title' | 'completed' | 'sort_key'>>): Promise<void> {
	const before = get(subtasks);
	subtasks.update((list) => list.map((s) => (s.id === id ? { ...s, ...fields } : s)));
	try {
		const saved = await api.updateSubtask(token(), id, fields);
		subtasks.update((list) => list.map((s) => (s.id === id ? saved : s)));
		const refreshed = await api.getTask(token(), saved.task_id).catch(() => null);
		if (refreshed) tasks.update((list) => list.map((t) => (t.id === saved.task_id ? refreshed : t)));
	} catch (e) {
		subtasks.set(before);
		throw e;
	}
}

export async function removeSubtask(id: string): Promise<void> {
	const existing = get(subtasks).find((s) => s.id === id);
	const before = get(subtasks);
	subtasks.update((list) => list.filter((s) => s.id !== id));
	try {
		await api.deleteSubtask(token(), id);
		if (existing) {
			const refreshed = await api.getTask(token(), existing.task_id).catch(() => null);
			if (refreshed) tasks.update((list) => list.map((t) => (t.id === existing.task_id ? refreshed : t)));
		}
	} catch (e) {
		subtasks.set(before);
		throw e;
	}
}
```

Extend `applyCollabEvent`:

```ts
	} else if (event === 'workos:subtask.created') {
		subtasks.update((l) => (l.some((s) => s.id === payload.id) ? l : [...l, payload]));
	} else if (event === 'workos:subtask.updated') {
		subtasks.update((l) => l.map((s) => (s.id === payload.id ? { ...s, ...payload } : s)));
	} else if (event === 'workos:subtask.deleted') {
		subtasks.update((l) => l.filter((s) => s.id !== payload.id));
```

Extend `COLLAB_EVENTS`:

```ts
	'workos:subtask.created', 'workos:subtask.updated', 'workos:subtask.deleted'
```

- [ ] **Step 6: Run store tests**

Run: `npm run test:frontend -- src/lib/components/workos/lib/store.test.ts`

Expected: store tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/lib/components/workos/lib/types.ts src/lib/components/workos/lib/api.ts src/lib/components/workos/lib/store.ts src/lib/components/workos/lib/store.test.ts
git commit -m "feat(workos): wire subtask frontend state and realtime"
```

---

### Task 4: Planned, Actual, and Health Helpers

**Files:**
- Create: `src/lib/components/workos/lib/progress.ts`
- Create: `src/lib/components/workos/lib/progress.test.ts`

**Interfaces:**
- Produces: `plannedProgress(startDate, dueDate, now): number | null`
- Produces: `actualProgress(task): number`
- Produces: `taskHealth(task, now): TaskHealth | null`
- Produces: `TaskHealth = 'on_track' | 'at_risk' | 'behind' | 'overdue'`

- [ ] **Step 1: Write failing helper tests**

Create `src/lib/components/workos/lib/progress.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { actualProgress, plannedProgress, taskHealth } from './progress';
import type { Task } from './types';

const baseTask: Task = {
	id: 't1', workstream_id: 'w1', team_id: 'team', number: 1, key: 'OSL-1',
	title: 'Task', status: 'in_progress', progress: 20, labels: [], sort_key: 1,
	created_at: 0, updated_at: 0
};

describe('plannedProgress', () => {
	it('returns null without both dates', () => {
		expect(plannedProgress(null, 100, 50)).toBeNull();
		expect(plannedProgress(0, null, 50)).toBeNull();
	});

	it('clamps before start and after due date', () => {
		expect(plannedProgress(100, 200, 50)).toBe(0);
		expect(plannedProgress(100, 200, 250)).toBe(100);
	});

	it('calculates percent elapsed between start and due', () => {
		expect(plannedProgress(100, 200, 150)).toBe(50);
	});
});

describe('actualProgress', () => {
	it('uses manual task progress when there are no subtasks', () => {
		expect(actualProgress({ ...baseTask, progress: 35, subtask_total: 0, subtask_completed: 0 })).toBe(35);
	});

	it('uses completed subtask ratio when subtasks exist', () => {
		expect(actualProgress({ ...baseTask, progress: 10, subtask_total: 4, subtask_completed: 3 })).toBe(75);
	});
});

describe('taskHealth', () => {
	it('returns null when schedule dates are missing', () => {
		expect(taskHealth({ ...baseTask, start_date: null, due_date: null }, 150)).toBeNull();
	});

	it('marks overdue when past due and actual is below complete', () => {
		expect(taskHealth({ ...baseTask, start_date: 0, due_date: 100, progress: 90 }, 101)).toBe('overdue');
	});

	it('marks at risk and behind from planned minus actual gap', () => {
		expect(taskHealth({ ...baseTask, start_date: 0, due_date: 100, progress: 40 }, 50)).toBe('at_risk');
		expect(taskHealth({ ...baseTask, start_date: 0, due_date: 100, progress: 20 }, 50)).toBe('behind');
	});

	it('marks on track when actual is close enough to planned', () => {
		expect(taskHealth({ ...baseTask, start_date: 0, due_date: 100, progress: 45 }, 50)).toBe('on_track');
	});
});
```

- [ ] **Step 2: Run tests to verify failure**

Run: `npm run test:frontend -- src/lib/components/workos/lib/progress.test.ts`

Expected: fail because `progress.ts` does not exist.

- [ ] **Step 3: Implement helpers**

Create `src/lib/components/workos/lib/progress.ts`:

```ts
import type { Task } from './types';

export type TaskHealth = 'on_track' | 'at_risk' | 'behind' | 'overdue';

function clampPercent(value: number): number {
	return Math.max(0, Math.min(100, Math.round(value)));
}

export function plannedProgress(
	startDate: number | null | undefined,
	dueDate: number | null | undefined,
	now: number
): number | null {
	if (startDate == null || dueDate == null) return null;
	if (dueDate <= startDate) return now >= dueDate ? 100 : 0;
	if (now <= startDate) return 0;
	if (now >= dueDate) return 100;
	return clampPercent(((now - startDate) / (dueDate - startDate)) * 100);
}

export function actualProgress(task: Pick<Task, 'progress' | 'subtask_total' | 'subtask_completed'>): number {
	const total = task.subtask_total ?? 0;
	const completed = task.subtask_completed ?? 0;
	if (total > 0) return clampPercent((completed / total) * 100);
	return clampPercent(task.progress ?? 0);
}

export function taskHealth(task: Task, now: number): TaskHealth | null {
	if (task.status === 'done' || task.status === 'canceled') return null;
	const planned = plannedProgress(task.start_date, task.due_date, now);
	if (planned == null) return null;
	const actual = actualProgress(task);
	if (task.due_date != null && now > task.due_date && actual < 100) return 'overdue';
	const gap = planned - actual;
	if (gap >= 25) return 'behind';
	if (gap >= 10) return 'at_risk';
	return 'on_track';
}

export const HEALTH_LABEL: Record<TaskHealth, string> = {
	on_track: 'On track',
	at_risk: 'At risk',
	behind: 'Behind',
	overdue: 'Overdue'
};
```

- [ ] **Step 4: Run helper tests**

Run: `npm run test:frontend -- src/lib/components/workos/lib/progress.test.ts`

Expected: progress tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/progress.ts src/lib/components/workos/lib/progress.test.ts
git commit -m "feat(workos): add planned and actual progress helpers"
```

---

### Task 5: Task Detail Scheduling, Progress, and Subtasks UI

**Files:**
- Create: `src/lib/components/workos/views/detail/SubtasksPanel.svelte`
- Modify: `src/lib/components/workos/views/TaskDetail.svelte`

**Interfaces:**
- Consumes: `subtasks`, `addSubtask`, `editSubtask`, `removeSubtask`.
- Consumes: `plannedProgress`, `actualProgress`, `taskHealth`, `HEALTH_LABEL`.
- Produces: editable start date row.
- Produces: actual vs planned progress display.
- Produces: real subtasks tab.

- [ ] **Step 1: Create `SubtasksPanel.svelte`**

Create `src/lib/components/workos/views/detail/SubtasksPanel.svelte`:

```svelte
<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import { subtasks, addSubtask, editSubtask, removeSubtask } from '../../lib/store';

	export let taskId: string;

	let title = '';
	let creating = false;

	async function submit() {
		if (!title.trim()) return;
		await addSubtask(taskId, title.trim());
		title = '';
		creating = false;
	}
</script>

<div class="pt-4 space-y-2">
	{#each $subtasks as subtask (subtask.id)}
		<div class="flex items-center gap-2 rounded-lg border border-gray-200 dark:border-gray-800 px-3 py-2">
			<input
				type="checkbox"
				checked={subtask.completed}
				onchange={(e) => editSubtask(subtask.id, { completed: (e.target as HTMLInputElement).checked })}
				class="h-4 w-4"
				aria-label="Toggle subtask completion"
			/>
			<span class="flex-1 min-w-0 text-sm {subtask.completed ? 'line-through text-gray-400' : ''}">
				{subtask.title}
			</span>
			<button class="text-gray-400 hover:text-red-500" title="Delete subtask" onclick={() => removeSubtask(subtask.id)}>
				<Icon name="trash" size={14} />
			</button>
		</div>
	{/each}

	{#if creating}
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
		<button
			class="inline-flex items-center gap-1.5 text-sm text-teal-600 dark:text-teal-400 hover:underline"
			onclick={() => (creating = true)}
		>
			<Icon name="plus" size={14} /> Add subtask
		</button>
	{/if}

	{#if !$subtasks.length && !creating}
		<div class="text-xs text-gray-400 dark:text-gray-500 py-6 text-center">
			Break this task into smaller steps.
		</div>
	{/if}
</div>
```

- [ ] **Step 2: Wire start date and progress helpers in `TaskDetail.svelte`**

In `src/lib/components/workos/views/TaskDetail.svelte`, import:

```ts
	import SubtasksPanel from './detail/SubtasksPanel.svelte';
	import { plannedProgress, actualProgress, taskHealth, HEALTH_LABEL } from '../lib/progress';
```

Add state:

```ts
	let editingStart = false;
	$: now = Date.now();
	$: actual = t ? actualProgress(t) : 0;
	$: planned = t ? plannedProgress(t.start_date, t.due_date, now) : null;
	$: health = t ? taskHealth(t, now) : null;
```

Add a `Start date` property row before the existing due date row:

```svelte
<PropertyRow icon="calendar" label="Start date">
	{#if editingStart}
		<input
			type="date"
			class="text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded px-2 py-1"
			value={t.start_date ? new Date(t.start_date).toISOString().slice(0, 10) : ''}
			onchange={(e) => {
				const v = (e.target as HTMLInputElement).value;
				editTask(t.id, { start_date: v ? new Date(v).getTime() : null });
				editingStart = false;
			}}
			onblur={() => (editingStart = false)}
			autofocus
		/>
	{:else}
		<button
			class="rounded-md px-1 -mx-1 py-0.5 hover:bg-gray-100 dark:hover:bg-gray-900 {t.start_date ? '' : 'text-gray-400'}"
			onclick={() => (editingStart = true)}
		>
			{t.start_date ? formatDateLong(t.start_date) : 'Add start date'}
		</button>
	{/if}
</PropertyRow>
```

Replace the existing `Progress` property row value with:

```svelte
<div class="w-full space-y-2">
	<div class="flex items-center gap-2">
		<span class="flex-1 h-1.5 rounded-full bg-gray-200 dark:bg-gray-800 overflow-hidden">
			<span class="block h-full bg-teal-500 rounded-full" style="width:{actual}%"></span>
		</span>
		<span class="text-sm text-gray-500 w-10 text-right">{actual}%</span>
	</div>
	{#if planned !== null}
		<div class="flex items-center gap-2">
			<span class="flex-1 h-1.5 rounded-full bg-gray-100 dark:bg-gray-900 overflow-hidden">
				<span class="block h-full bg-gray-400 dark:bg-gray-600 rounded-full" style="width:{planned}%"></span>
			</span>
			<span class="text-xs text-gray-400 w-20 text-right">Planned {planned}%</span>
		</div>
	{/if}
	{#if health}
		<span class="inline-flex text-xs rounded-full px-2 py-0.5 bg-gray-100 dark:bg-gray-900 text-gray-600 dark:text-gray-300">
			{HEALTH_LABEL[health]}
		</span>
	{/if}
	{#if (t.subtask_total ?? 0) === 0 && editingProgress}
		<div class="flex items-center gap-2">
			<input
				type="range" min="0" max="100" step="5" value={t.progress}
				onchange={(e) => editTask(t.id, { progress: parseInt((e.target as HTMLInputElement).value, 10) })}
			/>
			<button class="text-xs text-teal-600 dark:text-teal-400" onclick={() => (editingProgress = false)}>Done</button>
		</div>
	{:else if (t.subtask_total ?? 0) === 0}
		<button class="text-xs text-gray-400 hover:text-teal-600" onclick={() => (editingProgress = true)}>Edit manual progress</button>
	{:else}
		<div class="text-xs text-gray-400">{t.subtask_completed ?? 0}/{t.subtask_total ?? 0} subtasks complete</div>
	{/if}
</div>
```

- [ ] **Step 3: Replace the subtasks placeholder tab content**

In `TaskDetail.svelte`, replace:

```svelte
<Tabs.Content value="subtasks"><SubtasksPlaceholder /></Tabs.Content>
```

with:

```svelte
<Tabs.Content value="subtasks"><SubtasksPanel taskId={t.id} /></Tabs.Content>
```

Remove the unused `SubtasksPlaceholder` import.

- [ ] **Step 4: Type-check**

Run: `npm run check`

Expected: no new errors in `src/lib/components/workos/views/TaskDetail.svelte` or `SubtasksPanel.svelte`.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/views/TaskDetail.svelte src/lib/components/workos/views/detail/SubtasksPanel.svelte
git commit -m "feat(workos): show planned actual progress and subtasks in task detail"
```

---

### Task 6: Board Card Schedule Health Summary

**Files:**
- Modify: `src/lib/components/workos/views/TaskCard.svelte`

**Interfaces:**
- Consumes: `actualProgress`, `taskHealth`, `HEALTH_LABEL`.
- Produces: compact card summary for subtask count and health.

- [ ] **Step 1: Update imports and reactive values**

In `TaskCard.svelte`, add:

```ts
	import { actualProgress, taskHealth, HEALTH_LABEL } from '../lib/progress';
```

Add reactive values:

```ts
	$: actual = actualProgress(task);
	$: health = taskHealth(task, Date.now());
```

- [ ] **Step 2: Add compact summary below priority**

Add after the priority row:

```svelte
{#if (task.subtask_total ?? 0) > 0 || health}
	<div class="flex items-center gap-2 mt-2 text-[12px] text-gray-500 dark:text-gray-400">
		{#if (task.subtask_total ?? 0) > 0}
			<span>{task.subtask_completed ?? 0}/{task.subtask_total ?? 0} subtasks</span>
			<span>{actual}%</span>
		{/if}
		{#if health}
			<span class="rounded-full px-1.5 py-0.5 bg-gray-100 dark:bg-gray-800">{HEALTH_LABEL[health]}</span>
		{/if}
	</div>
{/if}
```

- [ ] **Step 3: Type-check**

Run: `npm run check`

Expected: no new errors in `TaskCard.svelte`.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/views/TaskCard.svelte
git commit -m "feat(workos): show subtask progress and health on task cards"
```

---

### Task 7: Full Verification

**Files:**
- No required file changes.

**Interfaces:**
- Produces: verified backend, frontend helper, and Svelte type-check coverage.

- [ ] **Step 1: Run backend WorkOS tests**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/ -v`

Expected: all WorkOS backend tests pass.

- [ ] **Step 2: Run frontend unit tests**

Run: `npm run test:frontend -- src/lib/components/workos/lib/`

Expected: all WorkOS frontend lib tests pass.

- [ ] **Step 3: Run Svelte check**

Run: `npm run check`

Expected: no new errors in `src/lib/components/workos/`.

- [ ] **Step 4: Manual browser smoke**

Run the app, open `/workos`, and verify:

- Create a task with no dates: no health badge appears.
- Add start date and due date: planned progress appears.
- Move the card across kanban columns: status changes, health does not move the card automatically.
- Add two subtasks and complete one: actual progress becomes `50%`.
- Set manual progress on a task with no subtasks: actual progress follows the slider.
- Add a subtask to that same task: actual progress switches to subtask ratio.
- Mark a task `done` with incomplete subtasks: the task stays in Done, and subtasks remain unchanged.

- [ ] **Step 5: Confirm the working tree state**

```bash
git status --short
```

Expected: either no output, or only files intentionally changed by Tasks 1-6. If there are changes, review each diff before staging it in the task where the fix belongs.

---

## Self-Review

- Spec coverage: start date, optional subtasks, planned progress, actual progress, health, manual status, and kanban drag/drop are covered.
- Placeholder scan: no task is delegated to an unspecified later implementation.
- Type consistency: backend uses `start_date`, `subtask_total`, `subtask_completed`; frontend uses the same names.
- Scope check: this is one cohesive WorkOS task-progress feature. It touches backend schema/API plus frontend task detail/board, but each task produces testable software independently.
