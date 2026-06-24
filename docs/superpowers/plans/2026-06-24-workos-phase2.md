# WorkOS Phase 2 — Collaboration & Notifications — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add task comments (markdown), file attachments, an automatic activity log, @mentions, and a notification system with an in-tool inbox to WorkOS, built on the Phase 1 spine.

**Architecture:** Four new WorkOS-owned tables (`workos_comment`, `workos_attachment`, `workos_activity`, `workos_notification`) with DAOs in `models/workos.py`; new endpoints in `routers/workos.py` reusing the Phase 1 auth helpers and the `emit_event` room broadcaster; per-user notification delivery via the existing `emit_to_users` helper. Frontend extends `lib/store.ts` + `lib/api.ts`, replaces the TaskDetail stub with a combined comment/activity timeline, and adds an Inbox view with a live unread badge.

**Tech Stack:** SQLAlchemy async + Pydantic + FastAPI (backend), pytest/pytest-asyncio + httpx (backend tests), Svelte 5 runes + TypeScript + Tailwind (frontend), vitest (frontend tests), Socket.IO (realtime), OWUI `Storage` provider (attachment bytes).

## Global Constraints

- **Spec:** `docs/superpowers/specs/2026-06-24-workos-phase2-design.md`. Every task implements part of it.
- **No "Open WebUI" shown to users** — this is the Osool rebrand; user-facing copy says WorkOS/Osool, never Open WebUI.
- **Backend tests REQUIRE** `backend/.venv/Scripts/python` (bare `python` lacks deps). Run from `backend/`.
- **Test DB isolation:** the workos conftest creates/drops only `workos_*` tables; never touch `Base.sorted_tables`.
- **Convention (match Phase 1):** ids are `Text` UUIDs via `_id()`; timestamps are `int(time.time_ns())` via `_now()`; user refs are `Text` (no DB FK). Python is 4-space indent; Svelte/TS files use **tabs**.
- **Realtime emits are best-effort** — go through the `emit_event(event, room, payload)` and `emit_users(event, payload, user_ids)` wrappers in `routers/workos.py` so tests can monkeypatch them.
- **Config:** notification settings + max attachment size live as keys **inside the existing `WORKOS_RULES` dict** (already registered on `app.state.config` in `main.py`). Do **not** add a new `PersistentConfig` — that avoids the Phase 1 "unregistered config key 500s" footgun.
- **Mention token format (canonical):** a mention is encoded in a comment/description body as `@[Display Name](mention:USER_ID)`. Both backend and frontend parse it with the regex `\(mention:([^)\s]+)\)`.
- **Frontend check:** `npm run check` must stay clean for `src/lib/components/workos/` (the pre-existing sortablejs baseline error in BoardView is the only allowed exception).

---

## File Structure

**Backend (modify):**
- `backend/open_webui/models/workos.py` — add 4 tables, 4 Pydantic models, 4 DAOs, and the pure helpers `parse_mentions()` + `task_change_activities()`.
- `backend/open_webui/routers/workos.py` — add the `emit_users` wrapper, comment/attachment/activity/notification endpoints, fan-out on task update + comment create, bootstrap unread count, admin settings extension.

**Backend (create):**
- `backend/open_webui/migrations/versions/a2b3c4d5e6f7_add_workos_phase2_tables.py`
- `backend/open_webui/test/workos/test_models_collab.py`
- `backend/open_webui/test/workos/test_router_comments.py`
- `backend/open_webui/test/workos/test_router_activity_notifications.py`
- `backend/open_webui/test/workos/test_router_attachments.py`

**Frontend (modify):**
- `src/lib/components/workos/lib/types.ts` — add Comment/Attachment/Activity/Notification/FeedItem types; extend Bootstrap + WorkosRules.
- `src/lib/components/workos/lib/api.ts` — add wrappers.
- `src/lib/components/workos/lib/store.ts` — feed stores, notification store, unread count, realtime handlers.
- `src/lib/components/workos/lib/roles.ts` — `canDeleteComment` / `canDeleteAttachment`.
- `src/lib/components/workos/views/TaskDetail.svelte` — replace the Phase 2 stub with the feed + composer + files.
- `src/lib/components/workos/WorkOSApp.svelte` — render the Inbox view.
- `src/lib/components/workos/chrome/Sidebar.svelte` — Inbox entry + badge.
- `src/lib/components/workos/views/admin/RulesTab.svelte` — notification toggles + max attachment size.

**Frontend (create):**
- `src/lib/components/workos/lib/mentions.ts` (+ `mentions.test.ts`)
- `src/lib/components/workos/views/detail/Feed.svelte`
- `src/lib/components/workos/views/detail/CommentItem.svelte`
- `src/lib/components/workos/views/detail/ActivityItem.svelte`
- `src/lib/components/workos/views/detail/CommentComposer.svelte`
- `src/lib/components/workos/views/detail/AttachmentList.svelte`
- `src/lib/components/workos/views/InboxView.svelte`

---

## Task 1: Comment + Activity models, DAOs, and pure helpers

**Files:**
- Modify: `backend/open_webui/models/workos.py` (append after the existing `Labels`/`Tasks` section, before `can_see_team`)
- Test: `backend/open_webui/test/workos/test_models_collab.py`

**Interfaces:**
- Consumes: `Base`, `get_async_db_context`, `_id`, `_now`, `select`, `delete` (already imported in `models/workos.py`); `re` (add `import re` at top).
- Produces:
  - `CommentModel(id, task_id, user_id, body, mentions: list, edited_at: Optional[int], created_at, updated_at)`
  - `ActivityModel(id, task_id, team_id, user_id, type, data: dict, created_at)`
  - `Comments` DAO: `insert(task_id, user_id, body, mentions, db=None) -> CommentModel`; `get_by_id(id, db=None)`; `list_for_task(task_id, db=None) -> list[CommentModel]`; `update_body(id, body, mentions, db=None) -> Optional[CommentModel]` (sets `edited_at`/`updated_at`); `delete(id, db=None) -> bool`
  - `Activity` DAO: `insert(task_id, team_id, user_id, type, data, db=None) -> ActivityModel`; `list_for_task(task_id, db=None) -> list[ActivityModel]`
  - `parse_mentions(body: str) -> list[str]` (unique user ids, order-preserving)
  - `task_change_activities(actor_id, before: dict, after: dict) -> list[dict]` (each `{'type': str, 'data': dict}`)

- [ ] **Step 1: Write failing tests**

Create `backend/open_webui/test/workos/test_models_collab.py`:

```python
import pytest

from open_webui.models.workos import (
    Comments, Activity, parse_mentions, task_change_activities,
)


def test_parse_mentions_extracts_unique_ids_in_order():
    body = "hi @[Lara](mention:u1) and @[Yusuf](mention:u2) and again @[Lara](mention:u1)"
    assert parse_mentions(body) == ['u1', 'u2']


def test_parse_mentions_empty_when_none():
    assert parse_mentions("plain text, email a@b.com, code `mention:x`") == []


def test_task_change_activities_diffs_relevant_fields():
    before = {'status': 'todo', 'assignee_id': None, 'priority': None,
              'due_date': None, 'title': 'A', 'description': None}
    after = {'status': 'in_progress', 'assignee_id': 'u2', 'priority': 'high',
             'due_date': 123, 'title': 'A', 'description': None}
    acts = task_change_activities('u1', before, after)
    types = {a['type'] for a in acts}
    assert types == {'status_changed', 'assignee_changed', 'priority_changed', 'due_changed'}
    status = next(a for a in acts if a['type'] == 'status_changed')
    assert status['data'] == {'from': 'todo', 'to': 'in_progress'}


def test_task_change_activities_marks_completed_and_reopened():
    done = task_change_activities('u1', {'status': 'todo'}, {'status': 'done'})
    assert any(a['type'] == 'completed' for a in done)
    reopened = task_change_activities('u1', {'status': 'done'}, {'status': 'todo'})
    assert any(a['type'] == 'reopened' for a in reopened)


@pytest.mark.asyncio
async def test_comments_crud():
    c = await Comments.insert('t1', 'u1', 'hello @[Y](mention:u2)', ['u2'])
    assert c.body == 'hello @[Y](mention:u2)' and c.mentions == ['u2'] and c.edited_at is None
    listed = await Comments.list_for_task('t1')
    assert [x.id for x in listed] == [c.id]
    edited = await Comments.update_body(c.id, 'edited', [])
    assert edited.body == 'edited' and edited.edited_at is not None
    assert await Comments.delete(c.id) is True
    assert await Comments.list_for_task('t1') == []


@pytest.mark.asyncio
async def test_activity_insert_and_list():
    a = await Activity.insert('t1', 'team1', 'u1', 'status_changed', {'from': 'todo', 'to': 'done'})
    assert a.type == 'status_changed' and a.data == {'from': 'todo', 'to': 'done'}
    assert [x.id for x in await Activity.list_for_task('t1')] == [a.id]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/test_models_collab.py -v`
Expected: FAIL with `ImportError: cannot import name 'Comments'` (etc.).

- [ ] **Step 3: Add `import re` to the top of `models/workos.py`**

At the top of `backend/open_webui/models/workos.py`, add `re` to the imports (after `import time`):

```python
import re
import time
import uuid
```

- [ ] **Step 4: Implement the tables, models, DAOs, and pure helpers**

Append to `backend/open_webui/models/workos.py`, **before** the `async def can_see_team` definition:

```python
# ──────────────────────────── Comment + Activity Tables ────────────────────────────


class WorkosComment(Base):
    __tablename__ = 'workos_comment'

    id = Column(Text, primary_key=True, unique=True)
    task_id = Column(Text)
    user_id = Column(Text)
    body = Column(Text)
    mentions = Column(JSON, default=list)
    edited_at = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


class WorkosActivity(Base):
    __tablename__ = 'workos_activity'

    id = Column(Text, primary_key=True, unique=True)
    task_id = Column(Text)
    team_id = Column(Text)
    user_id = Column(Text)
    type = Column(Text)
    data = Column(JSON, default=dict)
    created_at = Column(BigInteger)


class CommentModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_id: str
    user_id: str
    body: str
    mentions: list = []
    edited_at: Optional[int] = None
    created_at: int
    updated_at: int


class ActivityModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_id: str
    team_id: str
    user_id: str
    type: str
    data: dict = {}
    created_at: int


_MENTION_RE = re.compile(r'\(mention:([^)\s]+)\)')


def parse_mentions(body: str) -> list:
    """Extract unique user ids from `@[Name](mention:ID)` tokens, preserving order."""
    out: list = []
    for uid in _MENTION_RE.findall(body or ''):
        if uid not in out:
            out.append(uid)
    return out


_ACTIVITY_FIELDS = {
    'status': 'status_changed',
    'assignee_id': 'assignee_changed',
    'priority': 'priority_changed',
    'due_date': 'due_changed',
    'title': 'title_changed',
    'description': 'description_changed',
}


def task_change_activities(actor_id: str, before: dict, after: dict) -> list:
    """Diff two task field-dicts into activity entries (pure; no DB)."""
    acts: list = []
    for field, atype in _ACTIVITY_FIELDS.items():
        if field in after and after[field] != before.get(field):
            acts.append({'type': atype, 'data': {'from': before.get(field), 'to': after[field]}})
    # Completion transitions get their own entry in addition to status_changed.
    if 'status' in after and after['status'] != before.get('status'):
        if after['status'] == 'done':
            acts.append({'type': 'completed', 'data': {}})
        elif before.get('status') == 'done':
            acts.append({'type': 'reopened', 'data': {}})
    return acts


class CommentsDao:
    async def insert(
        self, task_id: str, user_id: str, body: str, mentions: list,
        db: Optional[AsyncSession] = None,
    ) -> CommentModel:
        async with get_async_db_context(db) as db:
            now = _now()
            row = WorkosComment(
                id=_id(), task_id=task_id, user_id=user_id, body=body,
                mentions=mentions or [], edited_at=None, created_at=now, updated_at=now,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return CommentModel.model_validate(row)

    async def get_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[CommentModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosComment).filter_by(id=id))
            row = res.scalars().first()
            return CommentModel.model_validate(row) if row else None

    async def list_for_task(self, task_id: str, db: Optional[AsyncSession] = None) -> list:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosComment).filter_by(task_id=task_id).order_by(WorkosComment.created_at.asc())
            )
            return [CommentModel.model_validate(r) for r in res.scalars().all()]

    async def update_body(
        self, id: str, body: str, mentions: list, db: Optional[AsyncSession] = None
    ) -> Optional[CommentModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosComment).filter_by(id=id))
            row = res.scalars().first()
            if not row:
                return None
            now = _now()
            row.body = body
            row.mentions = mentions or []
            row.edited_at = now
            row.updated_at = now
            await db.commit()
            await db.refresh(row)
            return CommentModel.model_validate(row)

    async def delete(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosComment).filter_by(id=id))
            if not res.scalars().first():
                return False
            await db.execute(delete(WorkosComment).filter_by(id=id))
            await db.commit()
            return True


class ActivityDao:
    async def insert(
        self, task_id: str, team_id: str, user_id: str, type: str, data: dict,
        db: Optional[AsyncSession] = None,
    ) -> ActivityModel:
        async with get_async_db_context(db) as db:
            row = WorkosActivity(
                id=_id(), task_id=task_id, team_id=team_id, user_id=user_id,
                type=type, data=data or {}, created_at=_now(),
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return ActivityModel.model_validate(row)

    async def list_for_task(self, task_id: str, db: Optional[AsyncSession] = None) -> list:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosActivity).filter_by(task_id=task_id).order_by(WorkosActivity.created_at.asc())
            )
            return [ActivityModel.model_validate(r) for r in res.scalars().all()]


Comments = CommentsDao()
Activity = ActivityDao()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/test_models_collab.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/models/workos.py backend/open_webui/test/workos/test_models_collab.py
git commit -m "feat(workos): comment + activity models, DAOs, mention/diff helpers"
```

---

## Task 2: Attachment + Notification models and DAOs

**Files:**
- Modify: `backend/open_webui/models/workos.py` (append after the `Activity = ActivityDao()` line from Task 1)
- Test: `backend/open_webui/test/workos/test_models_collab.py` (append)

**Interfaces:**
- Produces:
  - `AttachmentModel(id, task_id, comment_id: Optional[str], storage_key, name, size, content_type: Optional[str], created_by_id, created_at)`
  - `NotificationModel(id, user_id, actor_id, task_id: Optional[str], comment_id: Optional[str], type, data: dict, read: bool, created_at)`
  - `Attachments` DAO: `insert(task_id, comment_id, storage_key, name, size, content_type, created_by_id, db=None)`; `get_by_id(id, db=None)`; `list_for_task(task_id, db=None)`; `delete(id, db=None) -> bool`
  - `Notifications` DAO: `insert(user_id, actor_id, type, data, task_id=None, comment_id=None, db=None)`; `list_for_user(user_id, unread_only=False, limit=50, before=None, db=None)`; `unread_count(user_id, db=None) -> int`; `mark_read(user_id, ids=None, all=False, db=None) -> int`; `get_by_id(id, db=None)`

- [ ] **Step 1: Write failing tests**

Append to `backend/open_webui/test/workos/test_models_collab.py`:

```python
@pytest.mark.asyncio
async def test_attachments_crud():
    from open_webui.models.workos import Attachments
    a = await Attachments.insert('t1', None, 'wos/abc_file.pdf', 'file.pdf', 1234, 'application/pdf', 'u1')
    assert a.comment_id is None and a.storage_key == 'wos/abc_file.pdf' and a.size == 1234
    assert [x.id for x in await Attachments.list_for_task('t1')] == [a.id]
    assert (await Attachments.get_by_id(a.id)).name == 'file.pdf'
    assert await Attachments.delete(a.id) is True
    assert await Attachments.list_for_task('t1') == []


@pytest.mark.asyncio
async def test_notifications_list_count_and_mark_read():
    from open_webui.models.workos import Notifications
    n1 = await Notifications.insert('u1', 'u2', 'assigned', {'task_key': 'OSL-1'}, task_id='t1')
    await Notifications.insert('u1', 'u2', 'mentioned', {'task_key': 'OSL-1'}, task_id='t1')
    assert await Notifications.unread_count('u1') == 2
    assert len(await Notifications.list_for_user('u1')) == 2
    assert len(await Notifications.list_for_user('u1', unread_only=True)) == 2
    assert await Notifications.mark_read('u1', ids=[n1.id]) == 1
    assert await Notifications.unread_count('u1') == 1
    assert await Notifications.mark_read('u1', all=True) == 1
    assert await Notifications.unread_count('u1') == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/test_models_collab.py -k "attachments or notifications" -v`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the tables, models, and DAOs**

Append to `backend/open_webui/models/workos.py` (after `Activity = ActivityDao()`):

```python
# ──────────────────────────── Attachment + Notification Tables ────────────────────────────


class WorkosAttachment(Base):
    __tablename__ = 'workos_attachment'

    id = Column(Text, primary_key=True, unique=True)
    task_id = Column(Text)
    comment_id = Column(Text, nullable=True)
    storage_key = Column(Text)
    name = Column(Text)
    size = Column(BigInteger)
    content_type = Column(Text, nullable=True)
    created_by_id = Column(Text, nullable=True)
    created_at = Column(BigInteger)


class WorkosNotification(Base):
    __tablename__ = 'workos_notification'

    id = Column(Text, primary_key=True, unique=True)
    user_id = Column(Text)
    actor_id = Column(Text, nullable=True)
    task_id = Column(Text, nullable=True)
    comment_id = Column(Text, nullable=True)
    type = Column(Text)
    data = Column(JSON, default=dict)
    read = Column(Boolean, default=False)
    created_at = Column(BigInteger)


class AttachmentModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_id: str
    comment_id: Optional[str] = None
    storage_key: str
    name: str
    size: int
    content_type: Optional[str] = None
    created_by_id: Optional[str] = None
    created_at: int


class NotificationModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    actor_id: Optional[str] = None
    task_id: Optional[str] = None
    comment_id: Optional[str] = None
    type: str
    data: dict = {}
    read: bool
    created_at: int


class AttachmentsDao:
    async def insert(
        self, task_id: str, comment_id: Optional[str], storage_key: str, name: str,
        size: int, content_type: Optional[str], created_by_id: Optional[str],
        db: Optional[AsyncSession] = None,
    ) -> AttachmentModel:
        async with get_async_db_context(db) as db:
            row = WorkosAttachment(
                id=_id(), task_id=task_id, comment_id=comment_id, storage_key=storage_key,
                name=name, size=size, content_type=content_type,
                created_by_id=created_by_id, created_at=_now(),
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return AttachmentModel.model_validate(row)

    async def get_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[AttachmentModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosAttachment).filter_by(id=id))
            row = res.scalars().first()
            return AttachmentModel.model_validate(row) if row else None

    async def list_for_task(self, task_id: str, db: Optional[AsyncSession] = None) -> list:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosAttachment).filter_by(task_id=task_id).order_by(WorkosAttachment.created_at.asc())
            )
            return [AttachmentModel.model_validate(r) for r in res.scalars().all()]

    async def delete(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosAttachment).filter_by(id=id))
            if not res.scalars().first():
                return False
            await db.execute(delete(WorkosAttachment).filter_by(id=id))
            await db.commit()
            return True


class NotificationsDao:
    async def insert(
        self, user_id: str, actor_id: Optional[str], type: str, data: dict,
        task_id: Optional[str] = None, comment_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> NotificationModel:
        async with get_async_db_context(db) as db:
            row = WorkosNotification(
                id=_id(), user_id=user_id, actor_id=actor_id, task_id=task_id,
                comment_id=comment_id, type=type, data=data or {}, read=False, created_at=_now(),
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return NotificationModel.model_validate(row)

    async def list_for_user(
        self, user_id: str, unread_only: bool = False, limit: int = 50,
        before: Optional[int] = None, db: Optional[AsyncSession] = None,
    ) -> list:
        async with get_async_db_context(db) as db:
            q = select(WorkosNotification).filter_by(user_id=user_id)
            if unread_only:
                q = q.filter(WorkosNotification.read == False)  # noqa: E712
            if before is not None:
                q = q.filter(WorkosNotification.created_at < before)
            q = q.order_by(WorkosNotification.created_at.desc()).limit(limit)
            res = await db.execute(q)
            return [NotificationModel.model_validate(r) for r in res.scalars().all()]

    async def unread_count(self, user_id: str, db: Optional[AsyncSession] = None) -> int:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosNotification).filter_by(user_id=user_id, read=False)
            )
            return len(res.scalars().all())

    async def mark_read(
        self, user_id: str, ids: Optional[list] = None, all: bool = False,
        db: Optional[AsyncSession] = None,
    ) -> int:
        async with get_async_db_context(db) as db:
            q = select(WorkosNotification).filter_by(user_id=user_id, read=False)
            if not all:
                q = q.filter(WorkosNotification.id.in_(ids or []))
            res = await db.execute(q)
            rows = res.scalars().all()
            for row in rows:
                row.read = True
            await db.commit()
            return len(rows)

    async def get_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[NotificationModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosNotification).filter_by(id=id))
            row = res.scalars().first()
            return NotificationModel.model_validate(row) if row else None


Attachments = AttachmentsDao()
Notifications = NotificationsDao()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/test_models_collab.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/models/workos.py backend/open_webui/test/workos/test_models_collab.py
git commit -m "feat(workos): attachment + notification models and DAOs"
```

---

## Task 3: Alembic migration for the four Phase 2 tables

**Files:**
- Create: `backend/open_webui/migrations/versions/a2b3c4d5e6f7_add_workos_phase2_tables.py`

**Interfaces:**
- Consumes: alembic head `f0a1b2c3d4e5` (the Phase 1 WorkOS migration — verified current head).
- Produces: new head `a2b3c4d5e6f7` creating `workos_comment`, `workos_attachment`, `workos_activity`, `workos_notification`.

- [ ] **Step 1: Write the migration file**

Create `backend/open_webui/migrations/versions/a2b3c4d5e6f7_add_workos_phase2_tables.py`:

```python
"""add workos phase2 tables

Revision ID: a2b3c4d5e6f7
Revises: f0a1b2c3d4e5
Create Date: 2026-06-24 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = 'f0a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'workos_comment',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('task_id', sa.Text(), nullable=True),
        sa.Column('user_id', sa.Text(), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('mentions', sa.JSON(), nullable=True),
        sa.Column('edited_at', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'workos_attachment',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('task_id', sa.Text(), nullable=True),
        sa.Column('comment_id', sa.Text(), nullable=True),
        sa.Column('storage_key', sa.Text(), nullable=True),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('size', sa.BigInteger(), nullable=True),
        sa.Column('content_type', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'workos_activity',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('task_id', sa.Text(), nullable=True),
        sa.Column('team_id', sa.Text(), nullable=True),
        sa.Column('user_id', sa.Text(), nullable=True),
        sa.Column('type', sa.Text(), nullable=True),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'workos_notification',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=True),
        sa.Column('actor_id', sa.Text(), nullable=True),
        sa.Column('task_id', sa.Text(), nullable=True),
        sa.Column('comment_id', sa.Text(), nullable=True),
        sa.Column('type', sa.Text(), nullable=True),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('read', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_workos_notification_user_id', 'workos_notification', ['user_id'])
    op.create_index('ix_workos_comment_task_id', 'workos_comment', ['task_id'])
    op.create_index('ix_workos_activity_task_id', 'workos_activity', ['task_id'])
    op.create_index('ix_workos_attachment_task_id', 'workos_attachment', ['task_id'])


def downgrade() -> None:
    op.drop_index('ix_workos_attachment_task_id', table_name='workos_attachment')
    op.drop_index('ix_workos_activity_task_id', table_name='workos_activity')
    op.drop_index('ix_workos_comment_task_id', table_name='workos_comment')
    op.drop_index('ix_workos_notification_user_id', table_name='workos_notification')
    op.drop_table('workos_notification')
    op.drop_table('workos_activity')
    op.drop_table('workos_attachment')
    op.drop_table('workos_comment')
```

- [ ] **Step 2: Verify the migration applies and reverts cleanly**

Run: `cd backend && .venv/Scripts/python -m alembic upgrade head`
Expected: applies `a2b3c4d5e6f7` with no error.

Run: `cd backend && .venv/Scripts/python -m alembic downgrade -1 && .venv/Scripts/python -m alembic upgrade head`
Expected: drops then re-creates the four tables with no error.

- [ ] **Step 3: Commit**

```bash
git add backend/open_webui/migrations/versions/a2b3c4d5e6f7_add_workos_phase2_tables.py
git commit -m "feat(workos): alembic migration for phase 2 collaboration tables"
```

---

## Task 4: Comment endpoints + activity-on-comment + the `emit_users` wrapper

**Files:**
- Modify: `backend/open_webui/routers/workos.py`
- Test: `backend/open_webui/test/workos/test_router_comments.py`

**Interfaces:**
- Consumes: `require_task_visible`, `team_role`, `emit_event`, `Workspaces`, `Tasks` (existing); `Comments`, `Activity`, `Notifications`, `parse_mentions`, `CommentModel`, `can_see_workstream` (from `models.workos`); `resolve_user_names` (existing, for actor/recipient names).
- Produces:
  - `emit_users(event, payload, user_ids)` wrapper (best-effort, monkeypatchable).
  - `notify(db, *, recipients, actor_id, actor_name, type, task, comment_id=None, snippet=None, extra=None)` helper that filters out the actor, respects `WORKOS_RULES['notifications']`, writes one `WorkosNotification` per recipient, and emits `workos:notification.created` per recipient. Returns the created `NotificationModel` list.
  - Endpoints: `GET /tasks/{task_id}/comments`, `POST /tasks/{task_id}/comments`, `PATCH /comments/{id}`, `DELETE /comments/{id}`.

- [ ] **Step 1: Write failing tests**

Create `backend/open_webui/test/workos/test_router_comments.py`:

```python
import pytest

from open_webui.test.workos.test_router_teams import _client, U1, U2
from open_webui.test.workos.test_router_task import _stream


async def _task(c):
    team, ws, s = await _stream(c)
    t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'T'})).json()
    return team, ws, s, t


@pytest.mark.asyncio
async def test_comment_create_list_edit_delete(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/comments", json={'body': 'first comment'})
        assert r.status_code == 200, r.text
        com = r.json()
        assert com['body'] == 'first comment' and com['edited_at'] is None
        listed = (await c.get(f"/api/v1/workos/tasks/{t['id']}/comments")).json()
        assert [x['id'] for x in listed] == [com['id']]
        edited = (await c.patch(f"/api/v1/workos/comments/{com['id']}", json={'body': 'edited'})).json()
        assert edited['body'] == 'edited' and edited['edited_at'] is not None
        assert (await c.delete(f"/api/v1/workos/comments/{com['id']}")).json()['deleted'] is True


@pytest.mark.asyncio
async def test_comment_create_writes_activity(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        await c.post(f"/api/v1/workos/tasks/{t['id']}/comments", json={'body': 'hi'})
        acts = (await c.get(f"/api/v1/workos/tasks/{t['id']}/activity")).json()
        assert any(a['type'] == 'comment_added' for a in acts)


@pytest.mark.asyncio
async def test_only_author_can_edit_comment(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        await c.post(f"/api/v1/workos/teams/{t['team_id']}/members", json={'user_id': 'u2', 'role': 'member'})
        com = (await c.post(f"/api/v1/workos/tasks/{t['id']}/comments", json={'body': 'mine'})).json()
    async with _client(monkeypatch, user=U2) as c:
        r = await c.patch(f"/api/v1/workos/comments/{com['id']}", json={'body': 'hacked'})
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_non_member_cannot_comment(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
    async with _client(monkeypatch, user=U2) as c:
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/comments", json={'body': 'x'})
        assert r.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/test_router_comments.py -v`
Expected: FAIL with 404 (routes not defined).

- [ ] **Step 3: Add the `emit_users` wrapper and imports**

In `backend/open_webui/routers/workos.py`, extend the model import to add the new names:

```python
from open_webui.models.workos import (
    Teams, TeamMembers, Workspaces, WorkspaceMembers, Workstreams,
    Labels, Tasks, Comments, Activity, Attachments, Notifications,
    TeamModel, WorkspaceModel, WorkstreamModel, TaskModel, LabelModel,
    CommentModel, ActivityModel, AttachmentModel, NotificationModel,
    parse_mentions, task_change_activities, can_see_workstream,
)
```

Add the `emit_users` wrapper directly below the existing `emit_event` function:

```python
async def emit_users(event: str, payload: dict, user_ids: list) -> None:
    try:
        from open_webui.socket.main import emit_to_users

        await emit_to_users(event, payload, user_ids)
    except Exception as e:  # pragma: no cover - emit is best-effort
        log.debug(f'workos emit_to_users failed for {event}: {e}')
```

- [ ] **Step 4: Add comment schemas, the `notify` helper, and the endpoints**

Append to `backend/open_webui/routers/workos.py` (at the end of the file):

```python
# ──────────────────────────────── collaboration: schemas ────────────────────────────────


class CommentForm(BaseModel):
    body: str


# ──────────────────────────────── collaboration: helpers ────────────────────────────────


def _notif_enabled(request: Request, type: str) -> bool:
    rules = request.app.state.config.WORKOS_RULES or {}
    cfg = rules.get('notifications') or {}
    return cfg.get(type, True)


async def _actor_name(user) -> str:
    return getattr(user, 'name', None) or user.id


async def notify(
    request: Request, db, *, recipients: set, actor, type: str, task, comment_id=None, snippet=None, extra=None,
):
    """Create + deliver one notification per recipient (minus the actor)."""
    if not _notif_enabled(request, type):
        return []
    targets = {r for r in recipients if r and r != actor.id}
    if not targets:
        return []
    data = {
        'task_id': task.id, 'task_key': task.key, 'task_title': task.title,
        'workstream_id': task.workstream_id, 'actor_name': await _actor_name(actor),
    }
    if snippet is not None:
        data['snippet'] = snippet[:140]
    if extra:
        data.update(extra)
    created = []
    for uid in targets:
        n = await Notifications.insert(uid, actor.id, type, data, task_id=task.id, comment_id=comment_id, db=db)
        created.append(n)
        await emit_users('workos:notification.created', n.model_dump(), [uid])
    return created


async def _participants(task, db) -> set:
    """Creator + assignee + distinct comment authors + users mentioned on existing comments."""
    out: set = set()
    if task.created_by_id:
        out.add(task.created_by_id)
    if task.assignee_id:
        out.add(task.assignee_id)
    for com in await Comments.list_for_task(task.id, db=db):
        out.add(com.user_id)
        out.update(com.mentions or [])
    return out


async def _emit_task_room(event: str, task, payload: dict) -> None:
    await emit_event(event, f'workos:workstream:{task.workstream_id}', payload)


# ──────────────────────────────── comment endpoints ────────────────────────────────


@router.get('/tasks/{task_id}/comments')
async def list_comments(
    request: Request, task_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    await require_task_visible(user, task_id, db)
    return await Comments.list_for_task(task_id, db=db)


@router.post('/tasks/{task_id}/comments')
async def create_comment(
    request: Request, task_id: str, form: CommentForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    task, _ = await require_task_visible(user, task_id, db)
    body = (form.body or '').strip()
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Comment body required.')
    mentions = parse_mentions(body)
    comment = await Comments.insert(task_id, user.id, body, mentions, db=db)
    activity = await Activity.insert(task_id, task.team_id, user.id, 'comment_added', {}, db=db)
    payload = {**comment.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id}
    await _emit_task_room('workos:comment.created', task, payload)
    await _emit_task_room('workos:activity.created',
                          task, {**activity.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id})
    # Notification fan-out: mentioned first, then commented (minus those mentioned).
    mentioned = {m for m in mentions if await can_see_workstream(m, False, task.workstream_id, db=db)}
    await notify(request, db, recipients=mentioned, actor=user, type='mentioned', task=task,
                 comment_id=comment.id, snippet=body)
    participants = await _participants(task, db) - mentioned
    await notify(request, db, recipients=participants, actor=user, type='commented', task=task,
                 comment_id=comment.id, snippet=body)
    return comment


@router.patch('/comments/{comment_id}')
async def update_comment(
    request: Request, comment_id: str, form: CommentForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    existing = await Comments.get_by_id(comment_id, db=db)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Comment not found.')
    task, _ = await require_task_visible(user, existing.task_id, db)
    if existing.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Only the author may edit.')
    body = (form.body or '').strip()
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Comment body required.')
    new_mentions = parse_mentions(body)
    updated = await Comments.update_body(comment_id, body, new_mentions, db=db)
    payload = {**updated.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id}
    await _emit_task_room('workos:comment.updated', task, payload)
    # Only notify mentions that are newly added on this edit.
    fresh = {m for m in new_mentions if m not in (existing.mentions or [])
             and await can_see_workstream(m, False, task.workstream_id, db=db)}
    await notify(request, db, recipients=fresh, actor=user, type='mentioned', task=task,
                 comment_id=comment_id, snippet=body)
    return updated


@router.delete('/comments/{comment_id}')
async def delete_comment(
    request: Request, comment_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    existing = await Comments.get_by_id(comment_id, db=db)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Comment not found.')
    task, stream = await require_task_visible(user, existing.task_id, db)
    ws = await Workspaces.get_by_id(stream.workspace_id, db=db)
    is_admin = (await team_role(user, ws.team_id, db)) in {'owner', 'admin'}
    if not is_admin and existing.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Only the author or an admin may delete.')
    deleted = await Comments.delete(comment_id, db=db)
    await _emit_task_room('workos:comment.deleted',
                          task, {'id': comment_id, 'task_id': task.id, 'workstream_id': task.workstream_id,
                                 'actor_id': user.id})
    return {'deleted': deleted}


@router.get('/tasks/{task_id}/activity')
async def list_activity(
    request: Request, task_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    await require_task_visible(user, task_id, db)
    return await Activity.list_for_task(task_id, db=db)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/test_router_comments.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_comments.py
git commit -m "feat(workos): comment endpoints, activity-on-comment, notify helper"
```

---

## Task 5: Activity + notifications on task update

**Files:**
- Modify: `backend/open_webui/routers/workos.py` (the existing `update_task` handler, ~line 589)
- Test: `backend/open_webui/test/workos/test_router_activity_notifications.py`

**Interfaces:**
- Consumes: `task_change_activities`, `Activity`, `notify`, `_emit_task_room` (Task 4).
- Produces: `update_task` now records activity for changed fields and fires `assigned` + `status_changed` notifications.

- [ ] **Step 1: Write failing tests**

Create `backend/open_webui/test/workos/test_router_activity_notifications.py`:

```python
import pytest

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_teams import _client, U1
from open_webui.test.workos.test_router_task import _stream


async def _task(c):
    team, ws, s = await _stream(c)
    await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'T'})).json()
    return team, ws, s, t


@pytest.mark.asyncio
async def test_update_task_records_activity(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'status': 'in_progress', 'priority': 'high'})
        acts = (await c.get(f"/api/v1/workos/tasks/{t['id']}/activity")).json()
        types = {a['type'] for a in acts}
        assert 'status_changed' in types and 'priority_changed' in types


@pytest.mark.asyncio
async def test_assigning_user_notifies_assignee(monkeypatch):
    sent = []

    async def _eu(event, payload, user_ids):
        sent.append((event, tuple(user_ids), payload.get('type')))

    monkeypatch.setattr(wr, 'emit_users', _eu)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_id': 'u2'})
    assert ('workos:notification.created', ('u2',), 'assigned') in sent


@pytest.mark.asyncio
async def test_actor_not_notified_for_own_status_change(monkeypatch):
    sent = []

    async def _eu(event, payload, user_ids):
        sent.extend(user_ids)

    monkeypatch.setattr(wr, 'emit_users', _eu)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)  # creator + (no assignee) = U1 only
        await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'status': 'done'})
    assert 'u1' not in sent  # the actor (creator) is filtered out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/test_router_activity_notifications.py -v`
Expected: FAIL (no activity recorded / no notification emitted).

- [ ] **Step 3: Rewrite the `update_task` handler**

Replace the existing `update_task` function in `backend/open_webui/routers/workos.py` (the block starting `@router.patch('/tasks/{task_id}')`) with:

```python
@router.patch('/tasks/{task_id}')
async def update_task(
    request: Request, task_id: str, form: TaskUpdateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    task, _ = await require_task_visible(user, task_id, db)
    fields = form.model_dump(exclude_none=True)
    _validate_task_fields(fields)
    before = task.model_dump()
    updated = await Tasks.update_fields(task_id, fields, db=db)
    await emit_event('workos:task.updated', f'workos:workstream:{updated.workstream_id}', updated.model_dump())
    # Activity log for the changed fields.
    for act in task_change_activities(user.id, before, updated.model_dump()):
        row = await Activity.insert(task_id, updated.team_id, user.id, act['type'], act['data'], db=db)
        await _emit_task_room('workos:activity.created', updated,
                              {**row.model_dump(), 'workstream_id': updated.workstream_id, 'actor_id': user.id})
    # Notifications: assignment + status change.
    if 'assignee_id' in fields and updated.assignee_id and updated.assignee_id != before.get('assignee_id'):
        await notify(request, db, recipients={updated.assignee_id}, actor=user, type='assigned', task=updated)
    if 'status' in fields and updated.status != before.get('status'):
        await notify(request, db, recipients={updated.created_by_id, updated.assignee_id}, actor=user,
                     type='status_changed', task=updated,
                     extra={'from': before.get('status'), 'to': updated.status})
    return updated
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/test_router_activity_notifications.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_activity_notifications.py
git commit -m "feat(workos): activity + notifications on task update"
```

---

## Task 6: Attachment endpoints (upload / list / gated download / delete)

**Files:**
- Modify: `backend/open_webui/routers/workos.py`
- Test: `backend/open_webui/test/workos/test_router_attachments.py`

**Interfaces:**
- Consumes: `Attachments`, `Activity` (DAOs); `require_task_visible`, `team_role`, `Workspaces`, `_emit_task_room`.
- Produces: a module-level `Storage` import (patchable as `wr.Storage`); `_max_attachment_bytes(request)`; endpoints `POST /tasks/{task_id}/attachments`, `GET /tasks/{task_id}/attachments`, `GET /attachments/{id}/content`, `DELETE /attachments/{id}`.

- [ ] **Step 1: Write failing tests**

Create `backend/open_webui/test/workos/test_router_attachments.py`:

```python
import io

import pytest

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_teams import _client, U1, U2
from open_webui.test.workos.test_router_task import _stream


class _FakeStorage:
    store = {}

    @staticmethod
    def upload_file(file_obj, filename, tags):
        data = file_obj.read()
        key = f'wos/{filename}'
        _FakeStorage.store[key] = data
        return data, key

    @staticmethod
    def get_file(key):
        # Return a real temp path with the bytes (download streams from disk).
        import tempfile
        path = tempfile.mktemp()
        with open(path, 'wb') as f:
            f.write(_FakeStorage.store.get(key, b''))
        return path

    @staticmethod
    def delete_file(key):
        _FakeStorage.store.pop(key, None)


async def _task(c):
    team, ws, s = await _stream(c)
    t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'T'})).json()
    return team, ws, s, t


@pytest.mark.asyncio
async def test_attachment_upload_list_download_delete(monkeypatch):
    monkeypatch.setattr(wr, 'Storage', _FakeStorage)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        files = {'file': ('notes.txt', io.BytesIO(b'hello bytes'), 'text/plain')}
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/attachments", files=files)
        assert r.status_code == 200, r.text
        att = r.json()
        assert att['name'] == 'notes.txt' and att['size'] == 11
        listed = (await c.get(f"/api/v1/workos/tasks/{t['id']}/attachments")).json()
        assert [x['id'] for x in listed] == [att['id']]
        dl = await c.get(f"/api/v1/workos/attachments/{att['id']}/content")
        assert dl.status_code == 200 and dl.content == b'hello bytes'
        assert (await c.delete(f"/api/v1/workos/attachments/{att['id']}")).json()['deleted'] is True


@pytest.mark.asyncio
async def test_attachment_download_denied_for_non_member(monkeypatch):
    monkeypatch.setattr(wr, 'Storage', _FakeStorage)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        files = {'file': ('a.txt', io.BytesIO(b'x'), 'text/plain')}
        att = (await c.post(f"/api/v1/workos/tasks/{t['id']}/attachments", files=files)).json()
    async with _client(monkeypatch, user=U2) as c:
        r = await c.get(f"/api/v1/workos/attachments/{att['id']}/content")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_attachment_rejects_oversize(monkeypatch):
    monkeypatch.setattr(wr, 'Storage', _FakeStorage)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        # The test app's WORKOS_RULES has no max set -> default 25MB; force a tiny cap.
        c._transport.app.state.config.WORKOS_RULES['max_attachment_mb'] = 0
        files = {'file': ('big.bin', io.BytesIO(b'0123456789'), 'application/octet-stream')}
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/attachments", files=files)
        assert r.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/test_router_attachments.py -v`
Expected: FAIL (routes not defined).

- [ ] **Step 3: Add imports for upload/download**

In `backend/open_webui/routers/workos.py`, extend the FastAPI import and add Storage + FileResponse near the top imports:

```python
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status
from fastapi.responses import FileResponse
```

Add below the existing `from open_webui.utils.access_control import has_permission` line:

```python
import asyncio
import uuid as _uuid

from open_webui.storage.provider import Storage
```

- [ ] **Step 4: Add the attachment endpoints**

Append to `backend/open_webui/routers/workos.py`:

```python
# ──────────────────────────────── attachment endpoints ────────────────────────────────


def _max_attachment_bytes(request: Request) -> int:
    rules = request.app.state.config.WORKOS_RULES or {}
    mb = rules.get('max_attachment_mb', 25)
    return int(mb) * 1024 * 1024


@router.post('/tasks/{task_id}/attachments')
async def upload_attachment(
    request: Request, task_id: str, file: UploadFile = File(...), comment_id: Optional[str] = None,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    task, _ = await require_task_visible(user, task_id, db)
    contents = await file.read()
    limit = _max_attachment_bytes(request)
    if len(contents) > limit:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Attachment too large.')
    import io as _io

    safe_name = file.filename or 'file'
    storage_name = f'workos/{_uuid.uuid4()}_{safe_name}'
    _data, key = await asyncio.to_thread(
        Storage.upload_file, _io.BytesIO(contents), storage_name,
        {'OpenWebUI-User-Id': user.id, 'WorkOS-Task-Id': task_id},
    )
    att = await Attachments.insert(
        task_id, comment_id, key, safe_name, len(contents), file.content_type, user.id, db=db,
    )
    activity = await Activity.insert(task_id, task.team_id, user.id, 'attachment_added',
                                     {'name': safe_name}, db=db)
    await _emit_task_room('workos:attachment.created',
                          task, {**att.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id})
    await _emit_task_room('workos:activity.created',
                          task, {**activity.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id})
    return att


@router.get('/tasks/{task_id}/attachments')
async def list_attachments(
    request: Request, task_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    await require_task_visible(user, task_id, db)
    return await Attachments.list_for_task(task_id, db=db)


@router.get('/attachments/{attachment_id}/content')
async def download_attachment(
    request: Request, attachment_id: str,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    att = await Attachments.get_by_id(attachment_id, db=db)
    if not att:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Attachment not found.')
    await require_task_visible(user, att.task_id, db)  # 404 if the caller can't see the task
    path = await asyncio.to_thread(Storage.get_file, att.storage_key)
    return FileResponse(path, media_type=att.content_type or 'application/octet-stream', filename=att.name)


@router.delete('/attachments/{attachment_id}')
async def delete_attachment(
    request: Request, attachment_id: str,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    att = await Attachments.get_by_id(attachment_id, db=db)
    if not att:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Attachment not found.')
    task, stream = await require_task_visible(user, att.task_id, db)
    ws = await Workspaces.get_by_id(stream.workspace_id, db=db)
    is_admin = (await team_role(user, ws.team_id, db)) in {'owner', 'admin'}
    if not is_admin and att.created_by_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Only the uploader or an admin may delete.')
    try:
        await asyncio.to_thread(Storage.delete_file, att.storage_key)
    except Exception as e:  # pragma: no cover - best-effort
        log.debug(f'workos attachment storage delete failed: {e}')
    deleted = await Attachments.delete(attachment_id, db=db)
    await _emit_task_room('workos:attachment.deleted',
                          task, {'id': attachment_id, 'task_id': task.id,
                                 'workstream_id': task.workstream_id, 'actor_id': user.id})
    return {'deleted': deleted}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/test_router_attachments.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_attachments.py
git commit -m "feat(workos): attachment upload/list/gated-download/delete endpoints"
```

---

## Task 7: Notification endpoints + bootstrap unread count

**Files:**
- Modify: `backend/open_webui/routers/workos.py` (new endpoints + the existing `bootstrap` handler)
- Test: `backend/open_webui/test/workos/test_router_activity_notifications.py` (append)

**Interfaces:**
- Consumes: `Notifications` DAO.
- Produces: `GET /notifications`, `POST /notifications/read`; `bootstrap` response gains `notifications_unread: int`.

- [ ] **Step 1: Write failing tests**

Append to `backend/open_webui/test/workos/test_router_activity_notifications.py`:

```python
@pytest.mark.asyncio
async def test_notifications_list_and_mark_read(monkeypatch):
    from open_webui.models.workos import Notifications
    async with _client(monkeypatch, user=U1) as c:
        n = await Notifications.insert('u1', 'u2', 'assigned', {'task_key': 'OSL-1'}, task_id='t1')
        await Notifications.insert('u1', 'u2', 'mentioned', {'task_key': 'OSL-1'}, task_id='t1')
        listed = (await c.get('/api/v1/workos/notifications')).json()
        assert len(listed) == 2
        r = (await c.post('/api/v1/workos/notifications/read', json={'ids': [n.id]})).json()
        assert r['unread'] == 1
        r = (await c.post('/api/v1/workos/notifications/read', json={'all': True})).json()
        assert r['unread'] == 0


@pytest.mark.asyncio
async def test_bootstrap_includes_unread_count(monkeypatch):
    from open_webui.models.workos import Notifications
    async with _client(monkeypatch, user=U1) as c:
        await Notifications.insert('u1', 'u2', 'assigned', {}, task_id='t1')
        body = (await c.get('/api/v1/workos/bootstrap')).json()
        assert body['notifications_unread'] == 1


@pytest.mark.asyncio
async def test_notifications_are_per_user(monkeypatch):
    from open_webui.models.workos import Notifications
    await Notifications.insert('u2', 'u1', 'assigned', {}, task_id='t1')
    async with _client(monkeypatch, user=U1) as c:
        assert (await c.get('/api/v1/workos/notifications')).json() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/test_router_activity_notifications.py -k notif -v`
Expected: FAIL (routes/field missing).

- [ ] **Step 3: Add the notification schema + endpoints**

Append to `backend/open_webui/routers/workos.py`:

```python
# ──────────────────────────────── notification endpoints ────────────────────────────────


class MarkReadForm(BaseModel):
    ids: Optional[list] = None
    all: bool = False


@router.get('/notifications')
async def list_notifications(
    request: Request, unread_only: bool = False, limit: int = 50, before: Optional[int] = None,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    return await Notifications.list_for_user(user.id, unread_only=unread_only, limit=limit, before=before, db=db)


@router.post('/notifications/read')
async def mark_notifications_read(
    request: Request, form: MarkReadForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    await Notifications.mark_read(user.id, ids=form.ids, all=form.all, db=db)
    return {'unread': await Notifications.unread_count(user.id, db=db)}
```

- [ ] **Step 4: Add the unread count to `bootstrap`**

In the existing `bootstrap` handler, change the final return to include the count:

```python
    return {
        'teams': teams, 'workspaces': workspaces, 'workstreams': workstreams, 'roles': roles,
        'notifications_unread': await Notifications.unread_count(user.id, db=db),
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/test_router_activity_notifications.py -v`
Expected: PASS (6 tests in this file).

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_activity_notifications.py
git commit -m "feat(workos): notification list/mark-read endpoints + bootstrap unread count"
```

---

## Task 8: Admin settings — notification toggles + max attachment size

**Files:**
- Modify: `backend/open_webui/routers/workos.py` (the `SettingsForm` + `admin_update_settings` handler)
- Test: `backend/open_webui/test/workos/test_router_admin.py` (append)

**Interfaces:**
- Produces: `SettingsForm` gains `notifications: Optional[dict]` and `max_attachment_mb: Optional[int]`; these persist into `WORKOS_RULES`.

- [ ] **Step 1: Write a failing test**

Append to `backend/open_webui/test/workos/test_router_admin.py`:

```python
@pytest.mark.asyncio
async def test_admin_can_set_notification_settings(monkeypatch):
    from open_webui.test.workos.test_router_teams import _client, ADMIN
    async with _client(monkeypatch, user=ADMIN) as c:
        r = await c.patch('/api/v1/workos/admin/settings',
                          json={'notifications': {'commented': False}, 'max_attachment_mb': 50})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body['notifications'] == {'commented': False}
        assert body['max_attachment_mb'] == 50
```

(If `test_router_admin.py` does not already import `pytest`, add `import pytest` at the top.)

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/test_router_admin.py -k notification -v`
Expected: FAIL (fields ignored / not persisted).

- [ ] **Step 3: Extend `SettingsForm` and `admin_update_settings`**

Replace the `SettingsForm` class with:

```python
class SettingsForm(BaseModel):
    team_creation: Optional[str] = None
    default_workspace_visibility: Optional[str] = None
    notifications: Optional[dict] = None
    max_attachment_mb: Optional[int] = None
```

The existing `admin_update_settings` body already does `rules.update(form.model_dump(exclude_none=True))`, so the new keys persist automatically. Add one validation line after the existing visibility check, before `rules = dict(...)`:

```python
    if form.max_attachment_mb is not None and form.max_attachment_mb < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid max_attachment_mb.')
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/test_router_admin.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full backend WorkOS suite**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/ -v`
Expected: all pass (Phase 1 + Phase 2 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_admin.py
git commit -m "feat(workos): admin settings for notification toggles + max attachment size"
```

---

## Task 9: Frontend types + mention parser

**Files:**
- Modify: `src/lib/components/workos/lib/types.ts`
- Create: `src/lib/components/workos/lib/mentions.ts`
- Test: `src/lib/components/workos/lib/mentions.test.ts`

**Interfaces:**
- Produces:
  - Types `Comment`, `Attachment`, `Activity`, `Notification`, `FeedItem`; `Bootstrap.notifications_unread: number`; `WorkosRules.notifications?` + `WorkosRules.max_attachment_mb?`.
  - `mentions.ts`: `parseMentions(body: string): string[]`; `mentionToken(id: string, name: string): string`; `renderMentions(body: string, name: (id: string) => string): string`.

- [ ] **Step 1: Write failing tests**

Create `src/lib/components/workos/lib/mentions.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { parseMentions, mentionToken, renderMentions } from './mentions';

describe('mentions', () => {
	it('parses unique ids in order', () => {
		const body = 'hi @[Lara](mention:u1) and @[Y](mention:u2) and @[Lara](mention:u1)';
		expect(parseMentions(body)).toEqual(['u1', 'u2']);
	});

	it('returns empty for none', () => {
		expect(parseMentions('plain text')).toEqual([]);
	});

	it('builds a token', () => {
		expect(mentionToken('u1', 'Lara')).toBe('@[Lara](mention:u1)');
	});

	it('renders tokens to @name using the resolver', () => {
		const out = renderMentions('hey @[Lara](mention:u1)!', (id) => (id === 'u1' ? 'Lara' : id));
		expect(out).toBe('hey **@Lara**!');
	});
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test:frontend -- src/lib/components/workos/lib/mentions.test.ts`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `mentions.ts`**

Create `src/lib/components/workos/lib/mentions.ts`:

```ts
const MENTION_RE = /@\[[^\]]*\]\(mention:([^)\s]+)\)/g;

export function parseMentions(body: string): string[] {
	const out: string[] = [];
	for (const m of (body ?? '').matchAll(MENTION_RE)) {
		if (!out.includes(m[1])) out.push(m[1]);
	}
	return out;
}

export function mentionToken(id: string, name: string): string {
	return `@[${name}](mention:${id})`;
}

/** Replace mention tokens with bold @name for markdown rendering. */
export function renderMentions(body: string, name: (id: string) => string): string {
	return (body ?? '').replace(MENTION_RE, (_full, id) => `**@${name(id)}**`);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test:frontend -- src/lib/components/workos/lib/mentions.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Add the new types**

Append to `src/lib/components/workos/lib/types.ts`:

```ts
export interface Comment {
	id: string;
	task_id: string;
	user_id: string;
	body: string;
	mentions: string[];
	edited_at?: number | null;
	created_at: number;
	updated_at: number;
}

export interface Attachment {
	id: string;
	task_id: string;
	comment_id?: string | null;
	storage_key: string;
	name: string;
	size: number;
	content_type?: string | null;
	created_by_id?: string | null;
	created_at: number;
}

export type ActivityType =
	| 'created' | 'status_changed' | 'assignee_changed' | 'priority_changed'
	| 'due_changed' | 'completed' | 'reopened' | 'comment_added'
	| 'attachment_added' | 'title_changed' | 'description_changed';

export interface Activity {
	id: string;
	task_id: string;
	team_id: string;
	user_id: string;
	type: ActivityType;
	data: Record<string, unknown>;
	created_at: number;
}

export type NotificationType = 'assigned' | 'mentioned' | 'commented' | 'status_changed';

export interface Notification {
	id: string;
	user_id: string;
	actor_id?: string | null;
	task_id?: string | null;
	comment_id?: string | null;
	type: NotificationType;
	data: Record<string, any>;
	read: boolean;
	created_at: number;
}

export type FeedItem =
	| { kind: 'comment'; at: number; comment: Comment }
	| { kind: 'activity'; at: number; activity: Activity };
```

Update the existing `Bootstrap` and `WorkosRules` interfaces:

```ts
export interface Bootstrap {
	teams: Team[];
	workspaces: Workspace[];
	workstreams: Workstream[];
	roles: Record<string, TeamRole>;
	notifications_unread: number;
}

export interface WorkosRules {
	team_creation: 'all_users' | 'admins_only';
	default_workspace_visibility: Visibility;
	notifications?: Partial<Record<NotificationType, boolean>>;
	max_attachment_mb?: number;
}
```

- [ ] **Step 6: Verify type-check is clean**

Run: `npm run check 2>&1 | grep -i workos` (PowerShell: `npm run check; ` then inspect output)
Expected: no new errors in `src/lib/components/workos/` (the BoardView sortablejs baseline error may remain).

- [ ] **Step 7: Commit**

```bash
git add src/lib/components/workos/lib/types.ts src/lib/components/workos/lib/mentions.ts src/lib/components/workos/lib/mentions.test.ts
git commit -m "feat(workos): phase 2 frontend types + mention parser"
```

---

## Task 10: Frontend API wrappers

**Files:**
- Modify: `src/lib/components/workos/lib/api.ts`

**Interfaces:**
- Consumes: `Comment`, `Attachment`, `Activity`, `Notification` types; the `request` + `BASE` helpers (existing).
- Produces: `listComments`, `createComment`, `updateComment`, `deleteComment`, `listActivity`, `listAttachments`, `uploadAttachment`, `attachmentUrl`, `deleteAttachment`, `listNotifications`, `markNotificationsRead`.

- [ ] **Step 1: Add the type imports**

In `src/lib/components/workos/lib/api.ts`, extend the type import list with: `Comment, Attachment, Activity, Notification`.

- [ ] **Step 2: Append the wrappers**

Append to `src/lib/components/workos/lib/api.ts`:

```ts
// Comments
export const listComments = (token: string, taskId: string) =>
	request<Comment[]>(token, `/tasks/${taskId}/comments`);
export const createComment = (token: string, taskId: string, body: { body: string }) =>
	request<Comment>(token, `/tasks/${taskId}/comments`, 'POST', body);
export const updateComment = (token: string, id: string, body: { body: string }) =>
	request<Comment>(token, `/comments/${id}`, 'PATCH', body);
export const deleteComment = (token: string, id: string) =>
	request<{ deleted: boolean }>(token, `/comments/${id}`, 'DELETE');

// Activity
export const listActivity = (token: string, taskId: string) =>
	request<Activity[]>(token, `/tasks/${taskId}/activity`);

// Attachments
export const listAttachments = (token: string, taskId: string) =>
	request<Attachment[]>(token, `/tasks/${taskId}/attachments`);
export const deleteAttachment = (token: string, id: string) =>
	request<{ deleted: boolean }>(token, `/attachments/${id}`, 'DELETE');
export const attachmentUrl = (id: string) => `${BASE}/attachments/${id}/content`;
export async function uploadAttachment(
	token: string, taskId: string, file: File, commentId?: string
): Promise<Attachment> {
	const fd = new FormData();
	fd.append('file', file);
	const qs = commentId ? `?comment_id=${encodeURIComponent(commentId)}` : '';
	const res = await fetch(`${BASE}/tasks/${taskId}/attachments${qs}`, {
		method: 'POST',
		headers: { authorization: `Bearer ${token}` },
		body: fd
	});
	if (!res.ok) throw await res.json().catch(() => ({ detail: 'Upload failed' }));
	return (await res.json()) as Attachment;
}

// Notifications
export const listNotifications = (token: string, unreadOnly = false) =>
	request<Notification[]>(token, `/notifications?unread_only=${unreadOnly}`);
export const markNotificationsRead = (token: string, body: { ids?: string[]; all?: boolean }) =>
	request<{ unread: number }>(token, '/notifications/read', 'POST', body);
```

- [ ] **Step 3: Verify type-check is clean**

Run: `npm run check`
Expected: no new errors in `src/lib/components/workos/`.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/lib/api.ts
git commit -m "feat(workos): phase 2 api wrappers (comments, attachments, notifications)"
```

---

## Task 11: Store — feed stores, notifications, realtime handlers

**Files:**
- Modify: `src/lib/components/workos/lib/store.ts`
- Modify: `src/lib/components/workos/lib/roles.ts`
- Test: `src/lib/components/workos/lib/store.test.ts` (append)

**Interfaces:**
- Consumes: `api.*` (Task 10); `parseMentions` (not needed here); existing `socket`, `user`, `selectedTaskId`, `currentWorkstreamId`, `loadBootstrap`.
- Produces:
  - Stores: `comments`, `activity`, `attachments` (`Writable<...[]>`), `feed` (derived `FeedItem[]`), `notifications` (`Writable<Notification[]>`), `unreadCount` (`Writable<number>`).
  - Functions: `loadTaskDetail(taskId)`, `postComment(taskId, body)`, `editComment(id, body)`, `deleteComment(id)`, `uploadFiles(taskId, files, commentId?)`, `removeAttachment(id)`, `loadNotifications()`, `markRead(ids)`, `markAllRead()`, `applyCollabEvent(event, payload)`, `applyNotificationEvent(payload)`.
  - `roles.ts`: `canDeleteComment(comment, userId, role)`, `canDeleteAttachment(att, userId, role)`.

- [ ] **Step 1: Write failing tests**

Append to `src/lib/components/workos/lib/store.test.ts` (keep existing imports; add what's needed):

```ts
import {
	selectedTaskId, comments, activity, unreadCount, notifications,
	applyCollabEvent, applyNotificationEvent
} from './store';
import { get } from 'svelte/store';

describe('collab realtime', () => {
	it('applies comment.created only for the open task', () => {
		selectedTaskId.set('task-1');
		comments.set([]);
		applyCollabEvent('workos:comment.created', {
			id: 'c1', task_id: 'task-1', user_id: 'u2', body: 'hi', mentions: [],
			edited_at: null, created_at: 1, updated_at: 1, workstream_id: 'w1', actor_id: 'u2'
		});
		expect(get(comments).map((c) => c.id)).toEqual(['c1']);

		applyCollabEvent('workos:comment.created', {
			id: 'c2', task_id: 'other', user_id: 'u2', body: 'x', mentions: [],
			edited_at: null, created_at: 2, updated_at: 2, workstream_id: 'w1', actor_id: 'u2'
		});
		expect(get(comments).map((c) => c.id)).toEqual(['c1']); // ignored: different task
	});

	it('applies comment.deleted', () => {
		selectedTaskId.set('task-1');
		comments.set([{ id: 'c1', task_id: 'task-1', user_id: 'u2', body: 'hi', mentions: [],
			edited_at: null, created_at: 1, updated_at: 1 }]);
		applyCollabEvent('workos:comment.deleted', { id: 'c1', task_id: 'task-1' });
		expect(get(comments)).toEqual([]);
	});

	it('increments unread on notification.created', () => {
		unreadCount.set(0);
		notifications.set([]);
		applyNotificationEvent({ id: 'n1', user_id: 'u1', type: 'assigned', data: {}, read: false, created_at: 1 });
		expect(get(unreadCount)).toBe(1);
		expect(get(notifications).map((n) => n.id)).toEqual(['n1']);
	});
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test:frontend -- src/lib/components/workos/lib/store.test.ts`
Expected: FAIL (exports missing).

- [ ] **Step 3: Add role helpers**

Append to `src/lib/components/workos/lib/roles.ts` (match the existing helper style — check how `canDeleteTask` is written and mirror it):

```ts
export function canDeleteComment(
	comment: { user_id: string },
	userId: string,
	role: 'owner' | 'admin' | 'member' | undefined
): boolean {
	return comment.user_id === userId || role === 'owner' || role === 'admin';
}

export function canDeleteAttachment(
	att: { created_by_id?: string | null },
	userId: string,
	role: 'owner' | 'admin' | 'member' | undefined
): boolean {
	return att.created_by_id === userId || role === 'owner' || role === 'admin';
}
```

- [ ] **Step 4: Add stores, derived feed, actions, and realtime handlers**

Add to `src/lib/components/workos/lib/store.ts`. First extend the type import at the top:

```ts
import {
	STATUS_ORDER,
	type Team, type Workspace, type Workstream, type Label, type Task, type Member,
	type TeamRole, type TaskStatus, type TaskPriority,
	type Comment, type Activity, type Attachment, type Notification, type FeedItem
} from './types';
```

Add the stores near the other `writable` declarations:

```ts
export const comments: Writable<Comment[]> = writable([]);
export const activity: Writable<Activity[]> = writable([]);
export const attachments: Writable<Attachment[]> = writable([]);
export const notifications: Writable<Notification[]> = writable([]);
export const unreadCount: Writable<number> = writable(0);

export const feed = derived([comments, activity], ([$c, $a]): FeedItem[] => {
	const items: FeedItem[] = [
		...$c.map((comment) => ({ kind: 'comment' as const, at: comment.created_at, comment })),
		...$a.map((act) => ({ kind: 'activity' as const, at: act.created_at, activity: act }))
	];
	return items.sort((x, y) => x.at - y.at);
});
```

In `loadBootstrap`, set the unread count from the bootstrap payload (add after `roles.set(b.roles);`):

```ts
		unreadCount.set(b.notifications_unread ?? 0);
```

In `openTask`, load the detail; replace the existing `openTask` with:

```ts
export function openTask(id: string): void {
	selectedTaskId.set(id);
	void loadTaskDetail(id);
}
```

In `closeTask`, clear the feed; replace with:

```ts
export function closeTask(): void {
	selectedTaskId.set(null);
	comments.set([]);
	activity.set([]);
	attachments.set([]);
}
```

Add the detail loaders + actions (anywhere after `removeTask`):

```ts
export async function loadTaskDetail(taskId: string): Promise<void> {
	const [c, a, at] = await Promise.all([
		api.listComments(token(), taskId).catch(() => []),
		api.listActivity(token(), taskId).catch(() => []),
		api.listAttachments(token(), taskId).catch(() => [])
	]);
	if (get(selectedTaskId) !== taskId) return; // user moved on
	comments.set(c);
	activity.set(a);
	attachments.set(at);
}

export async function postComment(taskId: string, body: string): Promise<void> {
	const saved = await api.createComment(token(), taskId, { body });
	comments.update((list) => (list.some((c) => c.id === saved.id) ? list : [...list, saved]));
	void loadTaskDetail(taskId); // refresh activity (comment_added) too
}

export async function editComment(id: string, body: string): Promise<void> {
	const saved = await api.updateComment(token(), id, { body });
	comments.update((list) => list.map((c) => (c.id === id ? saved : c)));
}

export async function deleteCommentAction(id: string): Promise<void> {
	comments.update((list) => list.filter((c) => c.id !== id));
	await api.deleteComment(token(), id);
}

export async function uploadFiles(taskId: string, files: FileList | File[], commentId?: string): Promise<void> {
	for (const f of Array.from(files)) {
		const saved = await api.uploadAttachment(token(), taskId, f, commentId);
		attachments.update((list) => [...list, saved]);
	}
	void loadTaskDetail(taskId);
}

export async function removeAttachment(id: string): Promise<void> {
	attachments.update((list) => list.filter((a) => a.id !== id));
	await api.deleteAttachment(token(), id);
}

export async function loadNotifications(): Promise<void> {
	notifications.set(await api.listNotifications(token()).catch(() => []));
}

export async function markRead(ids: string[]): Promise<void> {
	notifications.update((list) => list.map((n) => (ids.includes(n.id) ? { ...n, read: true } : n)));
	const r = await api.markNotificationsRead(token(), { ids });
	unreadCount.set(r.unread);
}

export async function markAllRead(): Promise<void> {
	notifications.update((list) => list.map((n) => ({ ...n, read: true })));
	const r = await api.markNotificationsRead(token(), { all: true });
	unreadCount.set(r.unread);
}

/** Reconcile a collaboration room event into the open task's feed. */
export function applyCollabEvent(event: string, payload: any): void {
	const open = get(selectedTaskId);
	if (!payload || payload.task_id !== open) return;
	if (event === 'workos:comment.created') {
		comments.update((l) => (l.some((c) => c.id === payload.id) ? l : [...l, payload]));
	} else if (event === 'workos:comment.updated') {
		comments.update((l) => l.map((c) => (c.id === payload.id ? { ...c, ...payload } : c)));
	} else if (event === 'workos:comment.deleted') {
		comments.update((l) => l.filter((c) => c.id !== payload.id));
	} else if (event === 'workos:activity.created') {
		activity.update((l) => (l.some((a) => a.id === payload.id) ? l : [...l, payload]));
	} else if (event === 'workos:attachment.created') {
		attachments.update((l) => (l.some((a) => a.id === payload.id) ? l : [...l, payload]));
	} else if (event === 'workos:attachment.deleted') {
		attachments.update((l) => l.filter((a) => a.id !== payload.id));
	}
}

export function applyNotificationEvent(payload: any): void {
	if (!payload || !payload.id) return;
	notifications.update((l) => (l.some((n) => n.id === payload.id) ? l : [payload, ...l]));
	if (!payload.read) unreadCount.update((n) => n + 1);
}
```

Wire the handlers into the socket binding. In `connectRealtime`, add the new event constants and the notification handler. Replace the `TASK_EVENTS` constant and the relevant part of `connectRealtime`/`disconnectRealtime`:

```ts
const TASK_EVENTS = ['workos:task.created', 'workos:task.updated', 'workos:task.deleted'];
const COLLAB_EVENTS = [
	'workos:comment.created', 'workos:comment.updated', 'workos:comment.deleted',
	'workos:activity.created', 'workos:attachment.created', 'workos:attachment.deleted'
];
```

In `connectRealtime`, after the `for (const ev of TASK_EVENTS) { ... }` loop, add:

```ts
	for (const ev of COLLAB_EVENTS) {
		handlers[ev] = (payload: any) => applyCollabEvent(ev, payload);
		s.on(ev, handlers[ev]);
	}
	handlers['workos:notification.created'] = (payload: any) => applyNotificationEvent(payload);
	s.on('workos:notification.created', handlers['workos:notification.created']);
```

In `disconnectRealtime`, change the cleanup loop to include the new events:

```ts
	for (const ev of [...TASK_EVENTS, ...COLLAB_EVENTS, 'workos:notification.created', 'connect']) {
		if (handlers[ev]) s.off(ev, handlers[ev]);
	}
```

> Note: comment/activity/attachment events arrive on the existing `workos:workstream:{id}` room the store already subscribes to in `subscribeRoom` — no new subscribe call is needed. Notification events arrive on the user's personal `user:{id}` room, which the app joins on connect (no WorkOS-side subscribe needed).

- [ ] **Step 5: Run tests to verify they pass**

Run: `npm run test:frontend -- src/lib/components/workos/lib/store.test.ts`
Expected: PASS (existing + 3 new tests).

- [ ] **Step 6: Verify type-check is clean**

Run: `npm run check`
Expected: no new errors in `src/lib/components/workos/`.

- [ ] **Step 7: Commit**

```bash
git add src/lib/components/workos/lib/store.ts src/lib/components/workos/lib/roles.ts src/lib/components/workos/lib/store.test.ts
git commit -m "feat(workos): store feed/notification state + collab realtime handlers"
```

---

## Task 12: TaskDetail combined feed + composer + attachments

**Files:**
- Create: `src/lib/components/workos/views/detail/ActivityItem.svelte`
- Create: `src/lib/components/workos/views/detail/CommentItem.svelte`
- Create: `src/lib/components/workos/views/detail/CommentComposer.svelte`
- Create: `src/lib/components/workos/views/detail/AttachmentList.svelte`
- Create: `src/lib/components/workos/views/detail/Feed.svelte`
- Modify: `src/lib/components/workos/views/TaskDetail.svelte`

**Interfaces:**
- Consumes: stores `feed`, `attachments`, `comments`, `selectedTask`, `directory`, `displayName`, `roles`, `currentTeam`, actions `postComment`, `editComment`, `deleteCommentAction`, `uploadFiles`, `removeAttachment`; `renderMentions`, `mentionToken` (mentions.ts); `canDeleteComment`, `canDeleteAttachment` (roles.ts); `api.attachmentUrl`; the existing `Markdown` renderer (`$lib/components/chat/Messages/Markdown.svelte` — confirm props during implementation; pass the rendered string).
- Produces: a rendered combined timeline in the task detail panel.

> The five components are created together because the feed cannot render without its item components, and TaskDetail cannot mount without the feed — a reviewer evaluates them as one deliverable.

- [ ] **Step 1: Create `ActivityItem.svelte`**

Create `src/lib/components/workos/views/detail/ActivityItem.svelte`:

```svelte
<script lang="ts">
	import { displayName } from '../../lib/store';
	import { STATUS_LABEL, type Activity, type TaskStatus } from '../../lib/types';

	export let activity: Activity;

	function label(a: Activity): string {
		const who = displayName(a.user_id);
		const d = a.data as Record<string, any>;
		const st = (v: string) => STATUS_LABEL[v as TaskStatus] ?? v;
		switch (a.type) {
			case 'status_changed': return `${who} changed status ${st(d.from)} → ${st(d.to)}`;
			case 'completed': return `${who} completed this task`;
			case 'reopened': return `${who} reopened this task`;
			case 'assignee_changed': return `${who} ${d.to ? `assigned ${displayName(d.to)}` : 'unassigned this'}`;
			case 'priority_changed': return `${who} set priority to ${d.to ?? 'none'}`;
			case 'due_changed': return `${who} changed the due date`;
			case 'title_changed': return `${who} renamed this task`;
			case 'description_changed': return `${who} edited the description`;
			case 'comment_added': return `${who} commented`;
			case 'attachment_added': return `${who} attached ${d.name ?? 'a file'}`;
			default: return `${who} updated this task`;
		}
	}
</script>

<div class="flex items-center gap-2 text-xs text-gray-400 py-1">
	<span class="w-1.5 h-1.5 rounded-full bg-gray-300 dark:bg-gray-600 flex-none"></span>
	<span>{label(activity)}</span>
</div>
```

- [ ] **Step 2: Create `CommentItem.svelte`**

Create `src/lib/components/workos/views/detail/CommentItem.svelte`:

```svelte
<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import Markdown from '$lib/components/chat/Messages/Markdown.svelte';
	import { user } from '$lib/stores';
	import { displayName, editComment, deleteCommentAction, roles, currentTeam } from '../../lib/store';
	import { renderMentions } from '../../lib/mentions';
	import { canDeleteComment } from '../../lib/roles';
	import type { Comment } from '../../lib/types';

	export let comment: Comment;

	$: myRole = $currentTeam ? $roles[$currentTeam.id] : undefined;
	$: rendered = renderMentions(comment.body, displayName);
	$: mine = comment.user_id === ($user?.id ?? '');

	let editing = false;
	let draft = '';
	function startEdit() { draft = comment.body; editing = true; }
	function save() { editComment(comment.id, draft); editing = false; }
</script>

<div class="py-2 group">
	<div class="flex items-center gap-2 mb-1">
		<span class="text-sm font-medium">{displayName(comment.user_id)}</span>
		{#if comment.edited_at}<span class="text-[11px] text-gray-400">(edited)</span>{/if}
		<div class="flex-1"></div>
		{#if mine}
			<button class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-gray-600" title="Edit" onclick={startEdit}><Icon name="pencil" size={13} /></button>
		{/if}
		{#if canDeleteComment(comment, $user?.id ?? '', myRole)}
			<button class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500" title="Delete" onclick={() => deleteCommentAction(comment.id)}><Icon name="trash" size={13} /></button>
		{/if}
	</div>
	{#if editing}
		<textarea class="w-full text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded p-2 min-h-16" bind:value={draft}></textarea>
		<div class="flex gap-2 mt-1">
			<button class="text-sm px-3 py-1 rounded bg-teal-600 text-white" onclick={save}>Save</button>
			<button class="text-sm px-3 py-1 rounded border border-gray-300 dark:border-gray-700" onclick={() => (editing = false)}>Cancel</button>
		</div>
	{:else}
		<div class="text-sm prose prose-sm dark:prose-invert max-w-none">
			<Markdown id={comment.id} content={rendered} />
		</div>
	{/if}
</div>
```

> During implementation, confirm `Markdown.svelte`'s required props (it expects at least `id` and `content`). If its prop names differ, adapt this one call site; do not change the shared component.

- [ ] **Step 3: Create `CommentComposer.svelte`**

Create `src/lib/components/workos/views/detail/CommentComposer.svelte`:

```svelte
<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import { directory, postComment, uploadFiles } from '../../lib/store';
	import { mentionToken } from '../../lib/mentions';

	export let taskId: string;

	let body = '';
	let showMentions = false;
	let fileInput: HTMLInputElement;

	$: members = Object.entries($directory).map(([id, u]) => ({ id, name: u.name }));

	function insertMention(id: string, name: string) {
		body = `${body}${body.endsWith(' ') || body === '' ? '' : ' '}${mentionToken(id, name)} `;
		showMentions = false;
	}

	async function send() {
		const text = body.trim();
		if (!text) return;
		body = '';
		await postComment(taskId, text);
	}

	async function onFiles(e: Event) {
		const files = (e.target as HTMLInputElement).files;
		if (files && files.length) await uploadFiles(taskId, files);
		(e.target as HTMLInputElement).value = '';
	}
</script>

<div class="border-t border-gray-200 dark:border-gray-800 pt-2 mt-2">
	<textarea
		class="w-full text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded p-2 min-h-16"
		placeholder="Write a comment… use @ to mention"
		bind:value={body}
	></textarea>
	<div class="flex items-center gap-2 mt-1 relative">
		<button class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-900 text-gray-500" title="Mention" onclick={() => (showMentions = !showMentions)}><Icon name="users" size={15} /></button>
		<button class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-900 text-gray-500" title="Attach file" onclick={() => fileInput.click()}><Icon name="plus" size={15} /></button>
		<input type="file" multiple class="hidden" bind:this={fileInput} onchange={onFiles} />
		<div class="flex-1"></div>
		<button class="text-sm px-3 py-1 rounded bg-teal-600 text-white disabled:opacity-50" disabled={!body.trim()} onclick={send}>Comment</button>
		{#if showMentions}
			<div class="absolute bottom-9 left-0 z-10 w-56 max-h-48 overflow-y-auto rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-lg p-1">
				{#each members as m (m.id)}
					<button class="flex w-full px-2 h-8 items-center rounded text-sm hover:bg-gray-100 dark:hover:bg-gray-800" onclick={() => insertMention(m.id, m.name)}>{m.name}</button>
				{/each}
			</div>
		{/if}
	</div>
</div>
```

- [ ] **Step 4: Create `AttachmentList.svelte`**

Create `src/lib/components/workos/views/detail/AttachmentList.svelte`:

```svelte
<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import { attachments, removeAttachment, roles, currentTeam } from '../../lib/store';
	import { user } from '$lib/stores';
	import { canDeleteAttachment } from '../../lib/roles';
	import * as api from '../../lib/api';

	$: myRole = $currentTeam ? $roles[$currentTeam.id] : undefined;
	$: taskFiles = $attachments.filter((a) => !a.comment_id);
	const isImage = (ct?: string | null) => !!ct && ct.startsWith('image/');
</script>

{#if taskFiles.length}
	<div class="pt-4">
		<div class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold mb-2">Files</div>
		<div class="space-y-1.5">
			{#each taskFiles as a (a.id)}
				<div class="flex items-center gap-2 group">
					{#if isImage(a.content_type)}
						<img src={api.attachmentUrl(a.id)} alt={a.name} class="w-8 h-8 rounded object-cover flex-none" />
					{:else}
						<Icon name="file" size={16} />
					{/if}
					<a class="text-sm text-teal-600 truncate flex-1" href={api.attachmentUrl(a.id)} target="_blank" rel="noreferrer">{a.name}</a>
					<span class="text-[11px] text-gray-400">{Math.max(1, Math.round(a.size / 1024))} KB</span>
					{#if canDeleteAttachment(a, $user?.id ?? '', myRole)}
						<button class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500" title="Remove" onclick={() => removeAttachment(a.id)}><Icon name="trash" size={13} /></button>
					{/if}
				</div>
			{/each}
		</div>
	</div>
{/if}
```

> If `Icon.svelte` has no `file` glyph, use an existing one (check `ui/Icon.svelte`); pick the closest available rather than adding a new icon.

- [ ] **Step 5: Create `Feed.svelte`**

Create `src/lib/components/workos/views/detail/Feed.svelte`:

```svelte
<script lang="ts">
	import { feed } from '../../lib/store';
	import CommentItem from './CommentItem.svelte';
	import ActivityItem from './ActivityItem.svelte';
	import CommentComposer from './CommentComposer.svelte';

	export let taskId: string;
</script>

<div class="pt-4">
	<div class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold mb-2">Activity</div>
	<div class="divide-y divide-gray-100 dark:divide-gray-900">
		{#each $feed as item (item.kind + (item.kind === 'comment' ? item.comment.id : item.activity.id))}
			{#if item.kind === 'comment'}
				<CommentItem comment={item.comment} />
			{:else}
				<ActivityItem activity={item.activity} />
			{/if}
		{/each}
	</div>
	<CommentComposer {taskId} />
</div>
```

- [ ] **Step 6: Wire the feed into `TaskDetail.svelte`**

In `src/lib/components/workos/views/TaskDetail.svelte`, replace the final placeholder line:

```svelte
				<div class="pt-6 text-xs text-gray-400">Comments &amp; activity arrive in Phase 2.</div>
```

with:

```svelte
				<AttachmentList />
				<Feed taskId={t.id} />
```

Add the imports to the `<script>` block (after the existing component imports):

```ts
	import AttachmentList from './detail/AttachmentList.svelte';
	import Feed from './detail/Feed.svelte';
```

- [ ] **Step 7: Verify type-check + the existing detail still mounts**

Run: `npm run check`
Expected: no new errors in `src/lib/components/workos/`.

- [ ] **Step 8: Commit**

```bash
git add src/lib/components/workos/views/TaskDetail.svelte src/lib/components/workos/views/detail/
git commit -m "feat(workos): task detail combined feed, composer, attachments"
```

---

## Task 13: Inbox view + sidebar entry with live badge

**Files:**
- Create: `src/lib/components/workos/views/InboxView.svelte`
- Modify: `src/lib/components/workos/lib/store.ts` (extend `ViewKey`)
- Modify: `src/lib/components/workos/WorkOSApp.svelte`
- Modify: `src/lib/components/workos/chrome/Sidebar.svelte`

**Interfaces:**
- Consumes: `notifications`, `unreadCount`, `loadNotifications`, `markRead`, `markAllRead`, `openTask`, `selectWorkstream`, `view`, `displayName`; `Notification` type.
- Produces: `ViewKey` gains `'inbox'`; a clickable Inbox sidebar entry showing `unreadCount`; the Inbox view rendering the notification list.

- [ ] **Step 1: Extend `ViewKey`**

In `src/lib/components/workos/lib/store.ts`, change:

```ts
export type ViewKey = 'board' | 'list' | 'admin';
```

to:

```ts
export type ViewKey = 'board' | 'list' | 'admin' | 'inbox';
```

- [ ] **Step 2: Create `InboxView.svelte`**

Create `src/lib/components/workos/views/InboxView.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import {
		notifications, loadNotifications, markRead, markAllRead,
		view, selectWorkstream, openTask
	} from '../lib/store';
	import type { Notification } from '../lib/types';

	onMount(loadNotifications);

	function summary(n: Notification): string {
		const who = n.data?.actor_name ?? 'Someone';
		const key = n.data?.task_key ? `${n.data.task_key} ` : '';
		switch (n.type) {
			case 'assigned': return `${who} assigned you ${key}`.trim();
			case 'mentioned': return `${who} mentioned you in ${key}`.trim();
			case 'commented': return `${who} commented on ${key}`.trim();
			case 'status_changed': return `${who} changed status of ${key}`.trim();
			default: return `${who} updated ${key}`.trim();
		}
	}

	async function open(n: Notification) {
		if (!n.read) await markRead([n.id]);
		if (n.data?.workstream_id) await selectWorkstream(n.data.workstream_id);
		if (n.task_id) openTask(n.task_id);
		view.set('board');
	}
</script>

<div class="h-full overflow-y-auto">
	<div class="flex items-center gap-2 px-4 h-12 border-b border-gray-200 dark:border-gray-800">
		<span class="text-sm font-semibold">Inbox</span>
		<div class="flex-1"></div>
		<button class="text-sm text-teal-600 hover:underline" onclick={markAllRead}>Mark all read</button>
	</div>
	{#if !$notifications.length}
		<div class="p-8 text-center text-sm text-gray-400">You're all caught up.</div>
	{:else}
		<div class="divide-y divide-gray-100 dark:divide-gray-900">
			{#each $notifications as n (n.id)}
				<button
					class="flex items-start gap-3 w-full text-left px-4 py-3 hover:bg-gray-100 dark:hover:bg-gray-900"
					onclick={() => open(n)}
				>
					<span class="mt-1.5 w-2 h-2 rounded-full flex-none {n.read ? 'bg-transparent' : 'bg-teal-500'}"></span>
					<div class="min-w-0">
						<div class="text-sm truncate">{summary(n)}</div>
						{#if n.data?.snippet}<div class="text-xs text-gray-400 truncate">{n.data.snippet}</div>{/if}
					</div>
				</button>
			{/each}
		</div>
	{/if}
</div>
```

- [ ] **Step 3: Render the Inbox view in `WorkOSApp.svelte`**

In `src/lib/components/workos/WorkOSApp.svelte`, add the import:

```ts
	import InboxView from './views/InboxView.svelte';
```

Add `view` is already imported. Add an Inbox branch to the view switch — change the `{:else if $view === 'admin'}` chain so an inbox branch is included (place it right after the admin branch):

```svelte
				{:else if $view === 'inbox'}
					<InboxView />
```

(Insert those two lines between the `<AdminApp />` block's closing and the `{:else if !$teams.length}` line.)

- [ ] **Step 4: Add the Inbox entry + badge to the sidebar**

In `src/lib/components/workos/chrome/Sidebar.svelte`, add `view`, `unreadCount` to the store import:

```ts
	import {
		teams, workspaces, workstreams, roles, currentTeam, currentTeamId, currentWorkstreamId,
		selectTeam, selectWorkstream, view, openModal, unreadCount
	} from '../lib/store';
```

Insert an Inbox button at the top of the Workspaces scroll region — directly after the opening `<div class="flex-1 overflow-y-auto px-2 pb-2">` add:

```svelte
		<button
			class="flex items-center gap-2 w-full h-8 px-2 mb-1 rounded text-sm hover:bg-gray-100 dark:hover:bg-gray-900"
			class:bg-teal-50={$view === 'inbox'}
			onclick={() => view.set('inbox')}
		>
			<Icon name="inbox" size={15} />
			<span class="flex-1 text-left">Inbox</span>
			{#if $unreadCount > 0}
				<span class="text-[11px] min-w-5 h-5 px-1.5 rounded-full bg-teal-600 text-white flex items-center justify-center">{$unreadCount}</span>
			{/if}
		</button>
```

> If `Icon.svelte` has no `inbox` glyph, pick an existing one (e.g. `bell` or `mail`); check `ui/Icon.svelte` and use the closest available.

- [ ] **Step 5: Verify type-check is clean**

Run: `npm run check`
Expected: no new errors in `src/lib/components/workos/`.

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/workos/views/InboxView.svelte src/lib/components/workos/WorkOSApp.svelte src/lib/components/workos/chrome/Sidebar.svelte src/lib/components/workos/lib/store.ts
git commit -m "feat(workos): inbox view + sidebar entry with live unread badge"
```

---

## Task 14: Admin Notifications settings UI

**Files:**
- Modify: `src/lib/components/workos/views/admin/RulesTab.svelte`

**Interfaces:**
- Consumes: `api.getAdminSettings`, `api.updateAdminSettings`; `WorkosRules` type.
- Produces: toggles for the four notification categories + a max-attachment-size input, persisted via `PATCH /admin/settings`.

- [ ] **Step 1: Read the current RulesTab to match its pattern**

Read `src/lib/components/workos/views/admin/RulesTab.svelte` and note how it loads settings (likely `getAdminSettings`) and saves (likely `updateAdminSettings`), and its markup style.

- [ ] **Step 2: Add the notifications + attachment controls**

Within `RulesTab.svelte`, add a section (matching the file's existing section markup) bound to a local `settings` object. Use this block, adapting variable names to the file's existing state:

```svelte
<div class="mt-6">
	<div class="text-sm font-semibold mb-2">Notifications</div>
	{#each ['assigned', 'mentioned', 'commented', 'status_changed'] as cat (cat)}
		<label class="flex items-center gap-2 h-8 text-sm">
			<input
				type="checkbox"
				checked={settings.notifications?.[cat] !== false}
				onchange={(e) => {
					settings.notifications = { ...(settings.notifications ?? {}), [cat]: (e.target as HTMLInputElement).checked };
					save();
				}}
			/>
			<span class="capitalize">{cat.replace('_', ' ')}</span>
		</label>
	{/each}
</div>

<div class="mt-4">
	<div class="text-sm font-semibold mb-1">Max attachment size (MB)</div>
	<input
		type="number"
		min="0"
		class="text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded px-2 py-1 w-24"
		value={settings.max_attachment_mb ?? 25}
		onchange={(e) => { settings.max_attachment_mb = parseInt((e.target as HTMLInputElement).value, 10) || 0; save(); }}
	/>
</div>
```

Ensure `save()` calls `api.updateAdminSettings(token, { notifications: settings.notifications, max_attachment_mb: settings.max_attachment_mb })` (merge into the file's existing save function — it likely already sends `team_creation` / `default_workspace_visibility`; add the two new keys to that payload). If the file has no `save()` yet, add one that calls `updateAdminSettings` with the full `settings` object and re-stores the response.

- [ ] **Step 3: Verify type-check is clean**

Run: `npm run check`
Expected: no new errors in `src/lib/components/workos/`.

- [ ] **Step 4: Manual smoke (admin)**

Per [Open WebUI Windows run] memory, run the app (Docker container `osool-ai-open-webui-1`, or `vite dev` for frontend-only). As an admin, open WorkOS → admin (gear in sidebar footer) → Rules tab → toggle a notification category and change max size → confirm it persists across reload (calls `PATCH /admin/settings`).

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/views/admin/RulesTab.svelte
git commit -m "feat(workos): admin notification toggles + max attachment size"
```

---

## Task 15: Full-stack verification + manual browser smoke

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend WorkOS suite**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/ -v`
Expected: all pass (Phase 1 + Phase 2).

- [ ] **Step 2: Run the full frontend WorkOS suite**

Run: `npm run test:frontend -- src/lib/components/workos/`
Expected: all pass (roles/key/store/mentions).

- [ ] **Step 3: Type-check**

Run: `npm run check`
Expected: clean for `src/lib/components/workos/` (only the pre-existing BoardView sortablejs baseline error allowed).

- [ ] **Step 4: Manual browser smoke (real logged-in browser)**

Per [Open WebUI Windows run] memory, the sandboxed preview can't reach host localhost — use the real browser against the running container/`vite dev` at the app URL. Verify end-to-end on a task:
- Add a comment with markdown and an @mention → it renders, appears in the feed, and the mentioned user gets a notification (check as that user, or check the inbox badge increments via a second session).
- Edit and delete your own comment.
- Attach a file at task level and within a comment → image shows a thumbnail; download works; non-member is denied the download URL.
- Change status/assignee → an activity line appears in the feed; the assignee gets an `assigned` notification.
- Open the Inbox → unread badge clears on "Mark all read"; clicking a notification opens the right task.
- Open the same task in two sessions → a comment/attachment posted in one appears live in the other.

- [ ] **Step 5: Update project memory**

Update the WorkOS memory: record that Phase 2 (collaboration & notifications) is BUILT + how it was verified, the migration revision `a2b3c4d5e6f7`, the config-in-WORKOS_RULES decision, and the mention token format. Note the deferred global rail badge.

- [ ] **Step 6: Finalize the branch**

Use the superpowers:finishing-a-development-branch skill to decide merge/PR. Suggested final commit if needed:

```bash
git status
git commit -am "test(workos): phase 2 verification notes" # only if there are pending changes
```

---

## Self-Review Notes (spec coverage)

- Comments (markdown, flat, edit/delete own, admin delete any): Tasks 1, 4, 11, 12. ✔
- Attachments (task + comment level, any type, image thumbnail, gated download, Storage provider): Tasks 2, 6, 12. ✔
- Activity log (auto from mutations, combined feed): Tasks 1, 4, 5, 12. ✔
- @mentions (canonical token, server-parsed, notification-driving, rendered): Tasks 1, 4, 9, 12. ✔
- Notifications (4 triggers, actor-dedup, category toggles, per-user delivery): Tasks 4, 5, 7, 8, 11. ✔
- Inbox + live badge (sidebar entry, mark read/all): Tasks 7, 11, 13. ✔
- Admin Notifications settings (toggles + max size, in WORKOS_RULES): Tasks 8, 14. ✔
- Realtime (room events for comment/activity/attachment; emit_to_users for notifications): Tasks 4, 5, 6, 7, 11. ✔
- Migration off head `f0a1b2c3d4e5`: Task 3. ✔
- Testing (vitest mentions/store; pytest comment/attachment/activity/notification auth + fan-out + emits): Tasks 1–9, 11, 15. ✔
- Deferred (global rail badge, threads, reactions, subscribe table, web-push): not implemented, by design. ✔
