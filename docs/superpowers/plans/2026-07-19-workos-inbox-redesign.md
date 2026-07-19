# WorkOS Inbox Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the WorkOS Inbox as a hybrid dashboard — "Needs you" cards + day-grouped feed with task stacking, desktop split-pane task detail, unread→read→archived lifecycle — per the approved spec `docs/superpowers/specs/2026-07-19-workos-inbox-redesign-design.md` and mockup `docs/mockups/workos-inbox-mockups.html` (**V4 chrome + V1 feed anatomy**).

**Architecture:** Small backend addition (one `archived` column + archive/counts endpoints, all intrinsically user-scoped) feeding a rebuilt `InboxView` split-pane. The existing `TaskDetail` dialog is split into a thin Dialog wrapper + extracted `TaskDetailBody` so the inbox can mount the body inline. Grouping/stacking is pure client logic in `lib/inbox.ts`.

**Tech Stack:** FastAPI + SQLAlchemy async + Alembic (backend), Svelte 4-syntax components in the Svelte 5 app + Tailwind + scoped `.wos-*`/`--wos-*` design tokens, vitest, pytest.

## Global Constraints

- Follow the WorkOS design system (`docs/superpowers/specs/2026-07-09-workos-design-system-design.md`): unread affordance = **primary token** (never `sky-500`); status pills = `StatusBadge` (soft rectangle); radius contract (cards `rounded-lg` in this view, matching My Work's CARD constant; chips `rounded-full`); `focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none` on every new interactive element; `transition-colors duration-150` on hoverables.
- Deliberate deviation (user-picked): feed day headers are **uppercase letter-spaced with trailing hairline** (V1 mockup style).
- Deliberate deviation: task-key chips (`OSL-12`) render `rounded-md` kbd/tag style per the mockup — exempt from the rounded-full chip rule.
- All new endpoints: `require_workos` first, intrinsically scoped to `user.id`, no cross-user access.
- Frontend runs on the user's own Vite hot-reload server — never start a Vite dev server; never rebuild the Docker image for frontend edits. Backend container: `osool-ai-open-webui-1` (restart needed once for the migration).
- Backend tests run with the venv python: `cd backend` then `.venv\Scripts\python.exe -m pytest ...` (Windows).
- Frontend tests: `npm run test:frontend -- --run` (vitest).
- Commits: conventional commits, one per task, `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- NEVER use a haiku-tier subagent for Svelte file edits (cp1252 corruption history).

---

### Task 1: `archived` column — migration, model, DAO

**Files:**
- Create: `backend/open_webui/migrations/versions/a9b0c1d2e3f4_workos_notification_archived.py`
- Modify: `backend/open_webui/models/workos.py` (WorkosNotification ~line 1035, NotificationModel ~line 1062, NotificationsDao ~line 1136)
- Create: `backend/open_webui/test/workos/test_models_notifications.py`

**Interfaces:**
- Consumes: existing `Notifications` DAO singleton, `get_async_db_context`, `WorkosNotification` table.
- Produces (Task 2 relies on these exact signatures):
  - `Notifications.set_archived(user_id: str, ids: Optional[list] = None, all_read: bool = False, archived: bool = True, db=None) -> int`
  - `Notifications.list_for_user(user_id, unread_only=False, limit=50, before=None, before_id=None, archived=False, db=None) -> list` — compound `(created_at, id)` cursor so rows sharing the boundary millisecond are never skipped
  - `Notifications.counts_for_user(user_id: str, db=None) -> dict` returning `{'unread': int, 'by_type': {'assigned': int, 'mentioned': int, 'commented': int, 'status_changed': int}}`
  - `NotificationModel.archived: bool`

- [ ] **Step 1: Write the failing DAO tests**

Create `backend/open_webui/test/workos/test_models_notifications.py`:

```python
import pytest

from open_webui.models.workos import Notifications


@pytest.mark.asyncio
async def test_archive_sets_read_and_leaves_default_list():
    n = await Notifications.insert('u1', 'u2', 'assigned', {}, task_id='t1')
    assert n.archived is False
    count = await Notifications.set_archived('u1', ids=[n.id])
    assert count == 1
    default_list = await Notifications.list_for_user('u1')
    assert default_list == []
    archived = await Notifications.list_for_user('u1', archived=True)
    assert [x.id for x in archived] == [n.id]
    assert archived[0].read is True and archived[0].archived is True


@pytest.mark.asyncio
async def test_unarchive_restores_row_without_unreading():
    n = await Notifications.insert('u1', 'u2', 'commented', {}, task_id='t1')
    await Notifications.set_archived('u1', ids=[n.id])
    await Notifications.set_archived('u1', ids=[n.id], archived=False)
    restored = await Notifications.list_for_user('u1')
    assert [x.id for x in restored] == [n.id]
    assert restored[0].read is True  # unarchive does not un-read


@pytest.mark.asyncio
async def test_archive_scoped_to_owner():
    n = await Notifications.insert('u2', 'u1', 'assigned', {}, task_id='t1')
    count = await Notifications.set_archived('u1', ids=[n.id])
    assert count == 0
    assert [x.id for x in await Notifications.list_for_user('u2')] == [n.id]


@pytest.mark.asyncio
async def test_archive_all_read_sweeps_only_read_rows():
    a = await Notifications.insert('u1', 'u2', 'assigned', {}, task_id='t1')
    b = await Notifications.insert('u1', 'u2', 'commented', {}, task_id='t1')
    await Notifications.mark_read('u1', ids=[a.id])
    count = await Notifications.set_archived('u1', all_read=True)
    assert count == 1
    remaining = await Notifications.list_for_user('u1')
    assert [x.id for x in remaining] == [b.id]


@pytest.mark.asyncio
async def test_counts_for_user_by_type_unread_nonarchived_only():
    await Notifications.insert('u1', 'u2', 'mentioned', {}, task_id='t1')
    await Notifications.insert('u1', 'u2', 'mentioned', {}, task_id='t1')
    n3 = await Notifications.insert('u1', 'u2', 'assigned', {}, task_id='t1')
    n4 = await Notifications.insert('u1', 'u2', 'commented', {}, task_id='t1')
    await Notifications.mark_read('u1', ids=[n3.id])       # read → not counted
    await Notifications.set_archived('u1', ids=[n4.id])    # archived → not counted
    counts = await Notifications.counts_for_user('u1')
    assert counts == {
        'unread': 2,
        'by_type': {'assigned': 0, 'mentioned': 2, 'commented': 0, 'status_changed': 0},
    }


@pytest.mark.asyncio
async def test_pagination_compound_cursor_covers_shared_millisecond(monkeypatch):
    import open_webui.models.workos as mw
    monkeypatch.setattr(mw, '_now', lambda: 12345)  # 3 rows share one millisecond
    ids = {(await Notifications.insert('u1', 'u2', 'commented', {}, task_id='t1')).id for _ in range(3)}
    page1 = await Notifications.list_for_user('u1', limit=2)
    assert len(page1) == 2
    page2 = await Notifications.list_for_user(
        'u1', limit=2, before=page1[-1].created_at, before_id=page1[-1].id
    )
    assert len(page2) == 1
    assert {x.id for x in page1} | {x.id for x in page2} == ids
```

- [ ] **Step 2: Run the tests to verify they fail**

```
cd backend
.venv\Scripts\python.exe -m pytest open_webui/test/workos/test_models_notifications.py -q
```
Expected: FAIL — `AttributeError: 'NotificationModel' object has no attribute 'archived'` on the first test; `AttributeError: ... 'set_archived'` / `TypeError: ... unexpected keyword argument 'archived'` on the rest.

- [ ] **Step 3: Add the migration**

Create `backend/open_webui/migrations/versions/a9b0c1d2e3f4_workos_notification_archived.py`:

```python
"""workos notification archived flag

Adds ``workos_notification.archived`` — inbox lifecycle state
(unread -> read -> archived). Archiving implies read.

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-07-19 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a9b0c1d2e3f4'
down_revision: Union[str, None] = 'f8a9b0c1d2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'workos_notification',
        # sa.false() compiles to the right literal per dialect (0 on SQLite, false on Postgres).
        sa.Column('archived', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    with op.batch_alter_table('workos_notification') as batch:
        batch.drop_column('archived')
```

- [ ] **Step 4: Update model + DAO**

In `backend/open_webui/models/workos.py`:

`WorkosNotification` (after the `read` column):

```python
    read = Column(Boolean, default=False)
    archived = Column(Boolean, default=False, nullable=False)
    created_at = Column(BigInteger)
```

`NotificationModel` (after `read: bool`):

```python
    read: bool
    archived: bool = False
    created_at: int
```

`NotificationsDao.list_for_user` — add the `archived` parameter and filter:

```python
    async def list_for_user(
        self, user_id: str, unread_only: bool = False, limit: int = 50,
        before: Optional[int] = None, before_id: Optional[str] = None,
        archived: bool = False, db: Optional[AsyncSession] = None,
    ) -> list:
        async with get_async_db_context(db) as db:
            q = select(WorkosNotification).filter_by(user_id=user_id)
            q = q.filter(WorkosNotification.archived == archived)  # noqa: E712
            if unread_only:
                q = q.filter(WorkosNotification.read == False)  # noqa: E712
            if before is not None:
                if before_id is not None:
                    # Compound cursor: strictly-older ms, or same ms with a smaller
                    # id — rows sharing the boundary millisecond are never skipped.
                    q = q.filter(
                        (WorkosNotification.created_at < before)
                        | ((WorkosNotification.created_at == before)
                           & (WorkosNotification.id < before_id))
                    )
                else:
                    q = q.filter(WorkosNotification.created_at < before)
            q = q.order_by(
                WorkosNotification.created_at.desc(), WorkosNotification.id.desc()
            ).limit(limit)
            res = await db.execute(q)
            return [NotificationModel.model_validate(r) for r in res.scalars().all()]
```

Add to `NotificationsDao` (after `mark_read`):

```python
    async def set_archived(
        self, user_id: str, ids: Optional[list] = None, all_read: bool = False,
        archived: bool = True, db: Optional[AsyncSession] = None,
    ) -> int:
        """Archive implies read; unarchive never un-reads."""
        async with get_async_db_context(db) as db:
            q = select(WorkosNotification).filter_by(user_id=user_id)
            if all_read:
                q = q.filter(WorkosNotification.read == True,      # noqa: E712
                             WorkosNotification.archived == False)  # noqa: E712
            else:
                q = q.filter(WorkosNotification.id.in_(ids or []))
            res = await db.execute(q)
            rows = res.scalars().all()
            for row in rows:
                row.archived = archived
                if archived:
                    row.read = True
            await db.commit()
            return len(rows)

    async def counts_for_user(self, user_id: str, db: Optional[AsyncSession] = None) -> dict:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosNotification.type, func.count())
                .where(
                    WorkosNotification.user_id == user_id,
                    WorkosNotification.read == False,      # noqa: E712
                    WorkosNotification.archived == False,  # noqa: E712
                )
                .group_by(WorkosNotification.type)
            )
            by_type = {'assigned': 0, 'mentioned': 0, 'commented': 0, 'status_changed': 0}
            by_type.update({t: c for t, c in res.all()})
            return {'unread': sum(by_type.values()), 'by_type': by_type}
```

`func` import: the file's sqlalchemy import line must include `func` (add it if absent, e.g. `from sqlalchemy import ..., func`).

- [ ] **Step 5: Run the tests to verify they pass**

```
cd backend
.venv\Scripts\python.exe -m pytest open_webui/test/workos/test_models_notifications.py -q
```
Expected: 6 passed. (Test DB is created from metadata, so the new column exists without running the migration.)

- [ ] **Step 6: Run the full workos model/router suite for regressions**

```
.venv\Scripts\python.exe -m pytest open_webui/test/workos -q
```
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/open_webui/migrations/versions/a9b0c1d2e3f4_workos_notification_archived.py backend/open_webui/models/workos.py backend/open_webui/test/workos/test_models_notifications.py
git commit -m "feat(workos): notification archived flag - migration, model, DAO"
```

---

### Task 2: Router — archive endpoint, archived filter, counts endpoint (+ access doc)

**Files:**
- Modify: `backend/open_webui/routers/workos.py` (`MarkReadForm` ~line 1225, `list_notifications` ~line 1230, after `mark_notifications_read` ~line 1247)
- Modify: `backend/open_webui/test/workos/test_router_activity_notifications.py`
- Modify: `docs/superpowers/specs/2026-06-26-workos-access-control.md` (§4 Notifications table)

**Interfaces:**
- Consumes: Task 1's `Notifications.set_archived` / `counts_for_user` / `list_for_user(archived=)`.
- Produces (Task 3's api.ts relies on these):
  - `POST /api/v1/workos/notifications/archive` body `{ids?: [...], all_read?: bool, archived?: bool}` → `{'unread': int}`
  - `GET /api/v1/workos/notifications?archived=true|false` (default false) + `before_id` compound-cursor param beside `before`
  - `GET /api/v1/workos/notifications/counts` → `{'unread': int, 'by_type': {...}}`

- [ ] **Step 1: Write the failing router tests**

Append to `backend/open_webui/test/workos/test_router_activity_notifications.py`:

```python
@pytest.mark.asyncio
async def test_archive_endpoint_archives_and_returns_unread(monkeypatch):
    from open_webui.models.workos import Notifications
    async with _client(monkeypatch, user=U1) as c:
        n = await Notifications.insert('u1', 'u2', 'assigned', {}, task_id='t1')
        await Notifications.insert('u1', 'u2', 'mentioned', {}, task_id='t1')
        r = (await c.post('/api/v1/workos/notifications/archive', json={'ids': [n.id]})).json()
        assert r['unread'] == 1  # archive implied read on n
        default = (await c.get('/api/v1/workos/notifications')).json()
        assert len(default) == 1 and default[0]['type'] == 'mentioned'
        archived = (await c.get('/api/v1/workos/notifications?archived=true')).json()
        assert [x['id'] for x in archived] == [n.id]
        assert archived[0]['archived'] is True and archived[0]['read'] is True


@pytest.mark.asyncio
async def test_archive_all_read_sweep_and_unarchive(monkeypatch):
    from open_webui.models.workos import Notifications
    async with _client(monkeypatch, user=U1) as c:
        a = await Notifications.insert('u1', 'u2', 'assigned', {}, task_id='t1')
        await Notifications.insert('u1', 'u2', 'commented', {}, task_id='t1')
        await c.post('/api/v1/workos/notifications/read', json={'ids': [a.id]})
        await c.post('/api/v1/workos/notifications/archive', json={'all_read': True})
        assert len((await c.get('/api/v1/workos/notifications')).json()) == 1
        await c.post('/api/v1/workos/notifications/archive', json={'ids': [a.id], 'archived': False})
        assert len((await c.get('/api/v1/workos/notifications')).json()) == 2


@pytest.mark.asyncio
async def test_archive_cannot_touch_other_users_rows(monkeypatch):
    from open_webui.models.workos import Notifications
    async with _client(monkeypatch, user=U1) as c:
        other = await Notifications.insert('u2', 'u1', 'assigned', {}, task_id='t1')
        await c.post('/api/v1/workos/notifications/archive', json={'ids': [other.id]})
    rows = await Notifications.list_for_user('u2')
    assert [x.id for x in rows] == [other.id]  # untouched


@pytest.mark.asyncio
async def test_counts_endpoint(monkeypatch):
    from open_webui.models.workos import Notifications
    async with _client(monkeypatch, user=U1) as c:
        await Notifications.insert('u1', 'u2', 'mentioned', {}, task_id='t1')
        n = await Notifications.insert('u1', 'u2', 'commented', {}, task_id='t1')
        await c.post('/api/v1/workos/notifications/archive', json={'ids': [n.id]})
        counts = (await c.get('/api/v1/workos/notifications/counts')).json()
        assert counts['unread'] == 1
        assert counts['by_type'] == {'assigned': 0, 'mentioned': 1, 'commented': 0, 'status_changed': 0}
```

- [ ] **Step 2: Run to verify they fail**

```
cd backend
.venv\Scripts\python.exe -m pytest open_webui/test/workos/test_router_activity_notifications.py -q
```
Expected: new tests FAIL with 404 / 405 (routes don't exist); the 6 existing tests still pass.

- [ ] **Step 3: Implement the routes**

In `backend/open_webui/routers/workos.py`, next to `MarkReadForm` add:

```python
class ArchiveForm(BaseModel):
    ids: Optional[list] = None
    all_read: bool = False
    archived: bool = True
```

Change `list_notifications` signature and DAO call (add `archived`):

```python
@router.get('/notifications')
async def list_notifications(
    request: Request, unread_only: bool = False, limit: int = 50, before: Optional[int] = None,
    before_id: Optional[str] = None, archived: bool = False,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    limit = max(1, min(limit, 200))
    return await Notifications.list_for_user(
        user.id, unread_only=unread_only, limit=limit, before=before, before_id=before_id,
        archived=archived, db=db
    )
```

After `mark_notifications_read` add:

```python
@router.get('/notifications/counts')
async def notification_counts(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    return await Notifications.counts_for_user(user.id, db=db)


@router.post('/notifications/archive')
async def archive_notifications(
    request: Request, form: ArchiveForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    """Archive implies read. Intrinsically scoped to the caller's rows."""
    await require_workos(request, user, db)
    await Notifications.set_archived(
        user.id, ids=form.ids, all_read=form.all_read, archived=form.archived, db=db
    )
    return {'unread': await Notifications.unread_count(user.id, db=db)}
```

- [ ] **Step 4: Run to verify they pass**

```
.venv\Scripts\python.exe -m pytest open_webui/test/workos/test_router_activity_notifications.py -q
```
Expected: all pass (10 total).

- [ ] **Step 5: Update the access-control reference doc**

In `docs/superpowers/specs/2026-06-26-workos-access-control.md`, §4 "Notifications" table, add two rows after the `POST /notifications/read` row:

```markdown
| `GET /notifications/counts` | `require_workos`; intrinsically scoped to `user.id`; unread + non-archived per-type counts | [workos.py](backend/open_webui/routers/workos.py) `notification_counts` |
| `POST /notifications/archive` | `require_workos`; `Notifications.set_archived` passed `user.id` (owner-scoped; archive implies read) | [workos.py](backend/open_webui/routers/workos.py) `archive_notifications` |
```

Also note the new `archived` query param on the existing `GET /notifications` row (append "; `archived` query param filters archived vs inbox rows" to its gate cell).

- [ ] **Step 6: Full backend workos suite**

```
.venv\Scripts\python.exe -m pytest open_webui/test/workos -q
```
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_activity_notifications.py docs/superpowers/specs/2026-06-26-workos-access-control.md
git commit -m "feat(workos): notification archive + counts endpoints"
```

---

### Task 3: Frontend data layer — types, api, store

**Files:**
- Modify: `src/lib/components/workos/lib/types.ts` (Notification interface ~line 153)
- Modify: `src/lib/components/workos/lib/api.ts` (notifications block ~line 189)
- Modify: `src/lib/components/workos/lib/store.ts` (stores ~line 106, `selectedTask` ~line 144, `openTask/closeTask` ~line 233, `editTask` ~line 281, `loadNotifications` ~line 416, `markRead/markAllRead/openNotification` ~line 527, `applyNotificationEvent` ~line 571)
- Modify: `src/lib/components/workos/lib/store.test.ts`

**Interfaces:**
- Consumes: Task 2's endpoints.
- Produces (Tasks 6–7 rely on these exact names):
  - types: `Notification.archived?: boolean`; `interface NotificationCounts { unread: number; by_type: Record<NotificationType, number> }`
  - api: `listNotifications(token, opts?: { unreadOnly?: boolean; archived?: boolean; before?: number; beforeId?: string; limit?: number })`; `archiveNotifications(token, body: { ids?: string[]; all_read?: boolean; archived?: boolean })`; `getNotificationCounts(token)`
  - store: `notificationCounts: Writable<NotificationCounts>`, `archivedNotifications: Writable<Notification[]>`, `notificationsHasMore: Writable<boolean>`, `archivedHasMore: Writable<boolean>`, `inboxTask: Writable<Task | null>`, `inboxTaskError: Writable<boolean>`, `highlightCommentId: Writable<string | null>`, `inboxSplit: Readable<boolean>` (min-width 1280px media query — split-pane gate), `loadMoreNotifications()`, `loadArchivedNotifications()`, `loadMoreArchivedNotifications()`, `archiveNotificationsAction(ids: string[], archived?: boolean)`, `archiveAllRead()`, `openInboxNotification(n: Notification)`

- [ ] **Step 1: Write the failing store tests**

Append to `src/lib/components/workos/lib/store.test.ts`. First extend the `vi.mock('./api', ...)` factory at the top of the file with these entries (inside the returned object):

```ts
	listNotifications: vi.fn(async () => []),
	getNotificationCounts: vi.fn(async () => ({
		unread: 0, by_type: { assigned: 0, mentioned: 0, commented: 0, status_changed: 0 }
	})),
	archiveNotifications: vi.fn(async () => ({ unread: 0 })),
	markNotificationsRead: vi.fn(async () => ({ unread: 0 })),
```

Then append the suite:

```ts
// CAREFUL: `notifications`, `unreadCount`, `applyNotificationEvent`, and
// `selectedTaskId` are ALREADY imported by the mid-file import block (~line 89)
// — re-importing them is a duplicate-binding SyntaxError. Import ONLY the new names:
import {
	notificationCounts, archivedNotifications, inboxTask, inboxTaskError,
	archiveNotificationsAction, markRead
} from './store';
import * as apiMock from './api';
import type { Notification } from './types';

const mkN = (over: Partial<Notification>): Notification => ({
	id: 'n1', user_id: 'u1', actor_id: 'u2', task_id: 't1', comment_id: null,
	type: 'commented', data: {}, read: false, archived: false, created_at: 1000, ...over
});

describe('inbox notification store', () => {
	beforeEach(() => {
		notifications.set([]);
		archivedNotifications.set([]);
		inboxTask.set(null);
		inboxTaskError.set(false);
		selectedTaskId.set(null);
		unreadCount.set(0);
		notificationCounts.set({ unread: 0, by_type: { assigned: 0, mentioned: 0, commented: 0, status_changed: 0 } });
	});

	it('applyNotificationEvent prepends and bumps per-type counts', () => {
		applyNotificationEvent(mkN({ id: 'a', type: 'mentioned' }));
		applyNotificationEvent(mkN({ id: 'a', type: 'mentioned' })); // dupe ignored
		expect(get(notifications)).toHaveLength(1);
		expect(get(notificationCounts)).toEqual({
			unread: 1, by_type: { assigned: 0, mentioned: 1, commented: 0, status_changed: 0 }
		});
	});

	it('markRead decrements the matching type count', async () => {
		notifications.set([mkN({ id: 'a', type: 'assigned' })]);
		notificationCounts.set({ unread: 1, by_type: { assigned: 1, mentioned: 0, commented: 0, status_changed: 0 } });
		await markRead(['a']);
		expect(get(notifications)[0].read).toBe(true); // row stays, flipped to read
		expect(get(notificationCounts).by_type.assigned).toBe(0);
		expect(get(notificationCounts).unread).toBe(0);
	});

	it('archiveNotificationsAction moves the row out optimistically and marks it read', async () => {
		notifications.set([mkN({ id: 'a' }), mkN({ id: 'b' })]);
		notificationCounts.set({ unread: 2, by_type: { assigned: 0, mentioned: 0, commented: 2, status_changed: 0 } });
		await archiveNotificationsAction(['a']);
		expect(get(notifications).map((n) => n.id)).toEqual(['b']);
		expect(get(archivedNotifications).map((n) => n.id)).toEqual(['a']);
		expect(get(archivedNotifications)[0].read).toBe(true);
		expect(get(notificationCounts).unread).toBe(1);
	});

	it('archive failure rolls lists and counts back', async () => {
		vi.mocked(apiMock.archiveNotifications).mockRejectedValueOnce(new Error('nope'));
		notifications.set([mkN({ id: 'a' })]);
		notificationCounts.set({ unread: 1, by_type: { assigned: 0, mentioned: 0, commented: 1, status_changed: 0 } });
		await expect(archiveNotificationsAction(['a'])).rejects.toThrow();
		expect(get(notifications).map((n) => n.id)).toEqual(['a']);
		expect(get(archivedNotifications)).toHaveLength(0);
		expect(get(notificationCounts)).toEqual({
			unread: 1, by_type: { assigned: 0, mentioned: 0, commented: 1, status_changed: 0 }
		});
	});

	it('rollback keeps realtime rows that arrived during the failed request', async () => {
		vi.mocked(apiMock.archiveNotifications).mockImplementationOnce(async () => {
			applyNotificationEvent(mkN({ id: 'live', type: 'assigned', created_at: 5000 }));
			throw new Error('nope');
		});
		notifications.set([mkN({ id: 'a' })]);
		notificationCounts.set({ unread: 1, by_type: { assigned: 0, mentioned: 0, commented: 1, status_changed: 0 } });
		await expect(archiveNotificationsAction(['a'])).rejects.toThrow();
		expect(get(notifications).map((n) => n.id)).toEqual(['live', 'a']); // snapshot restore must not eat 'live'
		expect(get(archivedNotifications)).toHaveLength(0);
		expect(get(notificationCounts)).toEqual({
			unread: 2, by_type: { assigned: 1, mentioned: 0, commented: 1, status_changed: 0 }
		});
	});

	it('task.deleted keeps the selection and flags the pane error', () => {
		inboxTask.set({ id: 't9', workstream_id: 'other' } as any);
		selectedTaskId.set('t9');
		applyTaskEvent('workos:task.deleted', { id: 't9', workstream_id: 'other' });
		expect(get(inboxTask)).toBeNull();
		expect(get(inboxTaskError)).toBe(true);
		expect(get(selectedTaskId)).toBe('t9'); // kept: the pane shows "Task no longer available"
	});

	it('unarchive moves the row back sorted by created_at', async () => {
		notifications.set([mkN({ id: 'b', created_at: 2000 })]);
		archivedNotifications.set([mkN({ id: 'a', created_at: 3000, read: true, archived: true })]);
		await archiveNotificationsAction(['a'], false);
		expect(get(notifications).map((n) => n.id)).toEqual(['a', 'b']);
		expect(get(archivedNotifications)).toHaveLength(0);
	});

	it('task.updated reconciles the inbox split-pane task across workstreams', () => {
		inboxTask.set({ id: 't9', workstream_id: 'other', title: 'old' } as any);
		applyTaskEvent('workos:task.updated', { id: 't9', workstream_id: 'other', title: 'new' });
		expect(get(inboxTask)?.title).toBe('new');
	});
});
```

(`applyTaskEvent` is already imported at the top of the existing file — no new import needed for it.)

- [ ] **Step 2: Run to verify they fail**

```
npm run test:frontend -- --run src/lib/components/workos/lib/store.test.ts
```
Expected: FAIL — `notificationCounts` / `archiveNotificationsAction` not exported.

- [ ] **Step 3: types.ts**

In the `Notification` interface add after `read: boolean;`:

```ts
	read: boolean;
	archived?: boolean;
	created_at: number;
```

After the `Notification` interface add:

```ts
export interface NotificationCounts {
	unread: number;
	by_type: Record<NotificationType, number>;
}
```

- [ ] **Step 4: api.ts**

Replace the notifications block:

```ts
// Notifications
export const listNotifications = (
	token: string,
	opts: { unreadOnly?: boolean; archived?: boolean; before?: number; beforeId?: string; limit?: number } = {}
) => {
	const p = new URLSearchParams();
	if (opts.unreadOnly) p.set('unread_only', 'true');
	if (opts.archived) p.set('archived', 'true');
	if (opts.before != null) p.set('before', String(opts.before));
	if (opts.beforeId != null) p.set('before_id', opts.beforeId);
	if (opts.limit != null) p.set('limit', String(opts.limit));
	const qs = p.toString();
	return request<Notification[]>(token, `/notifications${qs ? `?${qs}` : ''}`);
};
export const markNotificationsRead = (token: string, body: { ids?: string[]; all?: boolean }) =>
	request<{ unread: number }>(token, '/notifications/read', 'POST', body);
export const archiveNotifications = (
	token: string, body: { ids?: string[]; all_read?: boolean; archived?: boolean }
) => request<{ unread: number }>(token, '/notifications/archive', 'POST', body);
export const getNotificationCounts = (token: string) =>
	request<NotificationCounts>(token, '/notifications/counts');
```

Add `NotificationCounts` to the type import at the top of api.ts.

- [ ] **Step 5: store.ts**

Import `NotificationCounts` in the types import. After `export const unreadCount` (~line 107) add:

```ts
const EMPTY_COUNTS = (): NotificationCounts => ({
	unread: 0, by_type: { assigned: 0, mentioned: 0, commented: 0, status_changed: 0 }
});
export const notificationCounts: Writable<NotificationCounts> = writable(EMPTY_COUNTS());
export const archivedNotifications: Writable<Notification[]> = writable([]);
export const notificationsHasMore: Writable<boolean> = writable(false);
export const archivedHasMore: Writable<boolean> = writable(false);
const NOTIF_PAGE = 50;
// Split-pane inbox: the opened notification's task may be in neither `tasks` nor
// `myTasks`, so it is fetched into this third `selectedTask` fallback.
export const inboxTask: Writable<Task | null> = writable(null);
export const inboxTaskError: Writable<boolean> = writable(false);
// Comment to scroll-to + highlight in the detail pane (mentioned/commented opens).
export const highlightCommentId: Writable<string | null> = writable(null);
// Workstream room joined for the split-pane task (ref-counted, so overlap with
// the current-workstream / my-work rooms is safe). Left again on closeTask.
let inboxRoomKey: string | null = null;
// Monotonic open counter — a stale openInboxNotification resolution must not
// clobber a newer selection (rapid A→B clicks).
let inboxOpenSeq = 0;
// Split-pane gate: the 256px sidebar + 400px list leave a usable detail pane
// only at ≥1280px viewports; below that the inbox keeps the dialog flow.
export const inboxSplit: Readable<boolean> = readable(false, (set) => {
	if (!browser) return;
	const mq = window.matchMedia('(min-width: 1280px)');
	const update = () => set(mq.matches);
	update();
	mq.addEventListener('change', update);
	return () => mq.removeEventListener('change', update);
});
```

(Add `readable` and `type Readable` to store.ts's existing `svelte/store` import line.)

Extend the `selectedTask` derived (~line 144):

```ts
export const selectedTask = derived(
	// inboxTask FIRST: it is freshly fetched and realtime-reconciled, while
	// `myTasks` can be stale (it persists after leaving My Work and only
	// reconciles while My Work is active) — a stale copy must not shadow it.
	// Then the current workstream's live `tasks`; `myTasks` is the last resort.
	[tasks, myTasks, inboxTask, selectedTaskId],
	([$t, $my, $inbox, $id]) =>
		($inbox && $inbox.id === $id ? $inbox : null) ??
		$t.find((x) => x.id === $id) ??
		$my.find((x) => x.id === $id) ??
		null
);
```

In `closeTask` (~line 237) add at the end:

```ts
	inboxTask.set(null);
	inboxTaskError.set(false);
	highlightCommentId.set(null);
	if (inboxRoomKey) {
		leaveRoom(inboxRoomKey);
		inboxRoomKey = null;
	}
```

(`streamKey` / `enterRoom` / `leaveRoom` already exist further down store.ts as function declarations — hoisted, so callable from here without moving anything.)

In `editTask` (~line 281) mirror every `tasks` write onto `inboxTask`, so split-pane edits of foreign-workstream tasks stay optimistic and roll back:

- after the optimistic `tasks.update(...)` at the top:

```ts
	const beforeInbox = get(inboxTask);
	inboxTask.update((t) => (t && t.id === id ? { ...t, ...fields } : t));
```

- after the second `tasks.update(...)` that applies the server response:

```ts
		inboxTask.update((t) => (t && t.id === id ? { ...t, ...(task as Task) } : t));
```

- in the `catch`, directly after the `if (before) tasks.update(...)` rollback line (before the handled-error early returns):

```ts
		if (beforeInbox) inboxTask.update((t) => (t && t.id === id ? beforeInbox : t));
```

Replace `loadNotifications` (~line 416) and add the new loaders/actions after it:

```ts
export async function loadNotifications(): Promise<void> {
	const [list, counts] = await Promise.all([
		api.listNotifications(token(), { limit: NOTIF_PAGE }).catch(() => [] as Notification[]),
		api.getNotificationCounts(token()).catch(() => null)
	]);
	notifications.set(list);
	notificationsHasMore.set(list.length === NOTIF_PAGE);
	if (counts) {
		notificationCounts.set(counts);
		unreadCount.set(counts.unread);
	}
}

export async function loadMoreNotifications(): Promise<void> {
	const cur = get(notifications);
	// Bulk mutations (sweep read) can empty the page while more rows exist on
	// the server — with no row to derive a cursor from, refill from page 1.
	if (!cur.length) return loadNotifications();
	const oldest = cur[cur.length - 1];
	const more = await api
		.listNotifications(token(), { limit: NOTIF_PAGE, before: oldest.created_at, beforeId: oldest.id })
		.catch(() => [] as Notification[]);
	notifications.update((l) => [...l, ...more.filter((n) => !l.some((x) => x.id === n.id))]);
	notificationsHasMore.set(more.length === NOTIF_PAGE);
}

export async function loadArchivedNotifications(): Promise<void> {
	const list = await api
		.listNotifications(token(), { archived: true, limit: NOTIF_PAGE })
		.catch(() => [] as Notification[]);
	archivedNotifications.set(list);
	archivedHasMore.set(list.length === NOTIF_PAGE);
}

export async function loadMoreArchivedNotifications(): Promise<void> {
	const cur = get(archivedNotifications);
	if (!cur.length) return loadArchivedNotifications(); // emptied by bulk unarchive → refill
	const oldest = cur[cur.length - 1];
	const more = await api
		.listNotifications(token(), {
			archived: true, limit: NOTIF_PAGE, before: oldest.created_at, beforeId: oldest.id
		})
		.catch(() => [] as Notification[]);
	archivedNotifications.update((l) => [...l, ...more.filter((n) => !l.some((x) => x.id === n.id))]);
	archivedHasMore.set(more.length === NOTIF_PAGE);
}

/** Decrement unread + per-type counts for rows that were unread until now. */
function decrementCounts(rows: Notification[]): void {
	const affected = rows.filter((n) => !n.read);
	if (!affected.length) return;
	notificationCounts.update((c) => {
		const by = { ...c.by_type };
		for (const n of affected) by[n.type] = Math.max(0, (by[n.type] ?? 0) - 1);
		return { unread: Math.max(0, c.unread - affected.length), by_type: by };
	});
}

/** Inverse of decrementCounts — re-add unread rows' count contributions. */
function incrementCounts(rows: Notification[]): void {
	const affected = rows.filter((n) => !n.read);
	if (!affected.length) return;
	notificationCounts.update((c) => {
		const by = { ...c.by_type };
		for (const n of affected) by[n.type] = (by[n.type] ?? 0) + 1;
		return { unread: c.unread + affected.length, by_type: by };
	});
}

/** Restore a snapshot but keep rows that arrived (realtime) after it was taken —
 * a plain snapshot restore would silently delete them. */
function restoreKeepingFresh(snapshot: Notification[], cur: Notification[]): Notification[] {
	const fresh = cur.filter((c) => !snapshot.some((s) => s.id === c.id));
	return fresh.length ? [...fresh, ...snapshot].sort((a, b) => b.created_at - a.created_at) : snapshot;
}

export async function archiveNotificationsAction(ids: string[], archived = true): Promise<void> {
	const before = get(notifications);
	const beforeArch = get(archivedNotifications);
	const beforeCounts = get(notificationCounts);
	if (archived) {
		const moving = before.filter((n) => ids.includes(n.id));
		decrementCounts(moving);
		notifications.update((l) => l.filter((n) => !ids.includes(n.id)));
		archivedNotifications.update((l) => [
			...moving.map((n) => ({ ...n, read: true, archived: true })), ...l
		]);
	} else {
		const moving = beforeArch.filter((n) => ids.includes(n.id));
		archivedNotifications.update((l) => l.filter((n) => !ids.includes(n.id)));
		notifications.update((l) =>
			[...moving.map((n) => ({ ...n, archived: false })), ...l].sort((a, b) => b.created_at - a.created_at)
		);
	}
	try {
		const r = await api.archiveNotifications(token(), { ids, archived });
		unreadCount.set(r.unread);
	} catch (e) {
		// Drop this action's own optimistic copies, restore the snapshots while
		// keeping realtime rows that arrived mid-request, then re-add those fresh
		// rows' count contributions (the counts snapshot predates them).
		notifications.update((cur) => restoreKeepingFresh(before, cur.filter((n) => !ids.includes(n.id))));
		archivedNotifications.update((cur) => restoreKeepingFresh(beforeArch, cur.filter((n) => !ids.includes(n.id))));
		notificationCounts.set(beforeCounts);
		incrementCounts(get(notifications).filter((n) => !before.some((b) => b.id === n.id)));
		throw e;
	}
}

export async function archiveAllRead(): Promise<void> {
	const before = get(notifications);
	notifications.update((l) => l.filter((n) => !n.read));
	try {
		await api.archiveNotifications(token(), { all_read: true, archived: true });
	} catch (e) {
		notifications.update((cur) => restoreKeepingFresh(before, cur));
		throw e;
	}
	void loadArchivedNotifications().catch(() => {});
}

/** Inbox split-pane open: mark read + resolve the task beside the list (no view switch). */
export async function openInboxNotification(n: Notification): Promise<void> {
	const seq = ++inboxOpenSeq;
	// Non-blocking: the selection must not wait on — or die with — mark-read.
	// Its own optimistic update + rollback handles the row state independently,
	// and awaiting it would let a slower A-click finish after (and clobber) a
	// faster B-click.
	if (!n.read) markRead([n.id]).catch(() => {});
	highlightCommentId.set(n.comment_id ?? null);
	inboxTask.set(null);
	inboxTaskError.set(false);
	// Join the task's workstream room so comment/activity/task events stream into
	// the pane even when the task lives outside the current workstream. Rooms are
	// ref-counted, so overlapping the current workstream's own room is safe.
	if (inboxRoomKey) {
		leaveRoom(inboxRoomKey);
		inboxRoomKey = null;
	}
	const ws = n.data?.workstream_id;
	if (ws) {
		inboxRoomKey = streamKey(ws);
		enterRoom(inboxRoomKey);
	}
	// Clear the shared detail stores BEFORE switching — otherwise the previous
	// task's comments/activity render under the new task until its fetches land.
	comments.set([]);
	activity.set([]);
	attachments.set([]);
	subtasks.set([]);
	selectedTaskId.set(n.task_id ?? null);
	if (!n.task_id) return;
	void loadTaskDetail(n.task_id);
	const t = await api.getTask(token(), n.task_id).catch(() => null);
	if (seq !== inboxOpenSeq || get(selectedTaskId) !== n.task_id) return; // user moved on
	if (t) inboxTask.set(t);
	else inboxTaskError.set(true);
}
```

Update `markRead` / `markAllRead` (~line 527) to keep counts in sync:

```ts
export async function markRead(ids: string[]): Promise<void> {
	const before = get(notifications);
	const beforeCounts = get(notificationCounts);
	decrementCounts(before.filter((n) => ids.includes(n.id)));
	notifications.update((list) => list.map((n) => (ids.includes(n.id) ? { ...n, read: true } : n)));
	try {
		const r = await api.markNotificationsRead(token(), { ids });
		unreadCount.set(r.unread);
	} catch (e) {
		notifications.update((cur) => restoreKeepingFresh(before, cur));
		notificationCounts.set(beforeCounts);
		incrementCounts(get(notifications).filter((n) => !before.some((b) => b.id === n.id)));
		throw e;
	}
}

export async function markAllRead(): Promise<void> {
	const before = get(notifications);
	const beforeCounts = get(notificationCounts);
	notifications.update((list) => list.map((n) => ({ ...n, read: true })));
	notificationCounts.set(EMPTY_COUNTS());
	try {
		const r = await api.markNotificationsRead(token(), { all: true });
		unreadCount.set(r.unread);
	} catch (e) {
		notifications.update((cur) => restoreKeepingFresh(before, cur));
		notificationCounts.set(beforeCounts);
		incrementCounts(get(notifications).filter((n) => !before.some((b) => b.id === n.id)));
		throw e;
	}
}
```

Update `applyNotificationEvent` (~line 571):

```ts
export function applyNotificationEvent(payload: any): void {
	if (!payload || !payload.id) return;
	const exists = get(notifications).some((n) => n.id === payload.id);
	if (!exists) notifications.update((l) => [payload, ...l]);
	if (!payload.read && !exists) {
		unreadCount.update((n) => n + 1);
		notificationCounts.update((c) => ({
			unread: c.unread + 1,
			by_type: { ...c.by_type, [payload.type]: (c.by_type[payload.type] ?? 0) + 1 }
		}));
	}
}
```

Update `applyTaskEvent` (~line 578) to reconcile the split-pane task **before** its current-workstream guard, so task updates/deletes reach the pane for foreign-workstream tasks (their room is joined by `openInboxNotification`):

```ts
export function applyTaskEvent(event: string, payload: any): void {
	if (!payload) return;
	// Split-pane inbox: the inline task may belong to another workstream.
	if (event === 'workos:task.updated') {
		inboxTask.update((t) => (t && t.id === payload.id ? payload : t));
	} else if (event === 'workos:task.deleted' && get(inboxTask)?.id === payload.id) {
		inboxTask.set(null);
		inboxTaskError.set(true); // pane flips to "Task no longer available"
	}
	const ws = get(currentWorkstreamId);
	if (payload.workstream_id !== ws) return;
	if (event === 'workos:task.created') {
		tasks.update((list) => (list.some((t) => t.id === payload.id) ? list : [...list, payload]));
	} else if (event === 'workos:task.updated') {
		tasks.update((list) => list.map((t) => (t.id === payload.id ? payload : t)));
	} else if (event === 'workos:task.deleted') {
		tasks.update((list) => list.filter((t) => t.id !== payload.id));
		// If the inbox pane owns the selection, inboxTaskError was just set above —
		// keep the id so the pane shows "Task no longer available" instead of
		// snapping to "Select a notification". Board flow (no inbox error) clears.
		if (get(selectedTaskId) === payload.id && !get(inboxTaskError)) selectedTaskId.set(null);
	}
}
```

Leave the existing `openNotification` untouched — the My Work rail and mobile inbox taps keep its navigate-away behavior.

- [ ] **Step 6: Run the store tests**

```
npm run test:frontend -- --run src/lib/components/workos/lib/store.test.ts
```
Expected: all pass (existing + 8 new).

- [ ] **Step 7: Type-check**

```
npm run check
```
Expected: no new errors (pre-existing baseline unchanged).

- [ ] **Step 8: Commit**

```bash
git add src/lib/components/workos/lib/types.ts src/lib/components/workos/lib/api.ts src/lib/components/workos/lib/store.ts src/lib/components/workos/lib/store.test.ts
git commit -m "feat(workos): inbox data layer - counts, archive, split-pane task resolution"
```

---

### Task 4: `lib/inbox.ts` — grouping + stacking

**Files:**
- Create: `src/lib/components/workos/lib/inbox.ts`
- Create: `src/lib/components/workos/lib/inbox.test.ts`

**Interfaces:**
- Consumes: `Notification` type.
- Produces (Task 7 relies on these):
  - `isNeedsYou(n: Notification): boolean`
  - `dayLabelOf(ms: number, now: number): string`
  - `interface FeedEntry { latest: Notification; stack: Notification[] }` (stack includes `latest`, newest-first)
  - `interface DayGroup { label: string; entries: FeedEntry[] }`
  - `groupInbox(list: Notification[], now: number): { needsYou: Notification[]; days: DayGroup[] }` — `list` must be newest-first (API order)

- [ ] **Step 1: Write the failing tests**

Create `src/lib/components/workos/lib/inbox.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { groupInbox, isNeedsYou, dayLabelOf } from './inbox';
import type { Notification } from './types';

const NOW = new Date(2026, 6, 19, 12, 0, 0).getTime(); // local Jul 19 2026 noon

const mk = (over: Partial<Notification>): Notification => ({
	id: Math.random().toString(36).slice(2), user_id: 'u1', actor_id: 'u2', task_id: 't1',
	comment_id: null, type: 'commented', data: {}, read: false, archived: false,
	created_at: NOW - 3_600_000, ...over
});

describe('isNeedsYou', () => {
	it('is true only for unread mentioned/assigned', () => {
		expect(isNeedsYou(mk({ type: 'mentioned' }))).toBe(true);
		expect(isNeedsYou(mk({ type: 'assigned' }))).toBe(true);
		expect(isNeedsYou(mk({ type: 'mentioned', read: true }))).toBe(false);
		expect(isNeedsYou(mk({ type: 'commented' }))).toBe(false);
	});
});

describe('dayLabelOf', () => {
	it('labels today/yesterday/older', () => {
		expect(dayLabelOf(NOW - 60_000, NOW)).toBe('Today');
		expect(dayLabelOf(NOW - 86_400_000, NOW)).toBe('Yesterday');
		expect(dayLabelOf(NOW - 3 * 86_400_000, NOW)).not.toMatch(/Today|Yesterday/);
	});
});

describe('groupInbox', () => {
	it('splits needs-you from the feed', () => {
		const m = mk({ id: 'm', type: 'mentioned' });
		const c = mk({ id: 'c', type: 'commented' });
		const g = groupInbox([m, c], NOW);
		expect(g.needsYou.map((n) => n.id)).toEqual(['m']);
		expect(g.days[0].entries.map((e) => e.latest.id)).toEqual(['c']);
	});

	it('read mentions flow into the feed', () => {
		const m = mk({ id: 'm', type: 'mentioned', read: true });
		const g = groupInbox([m], NOW);
		expect(g.needsYou).toHaveLength(0);
		expect(g.days[0].entries[0].latest.id).toBe('m');
	});

	it('groups by day and stacks only consecutive same-task rows within a day', () => {
		const a1 = mk({ id: 'a1', task_id: 'tA', created_at: NOW - 1000 });
		const a2 = mk({ id: 'a2', task_id: 'tA', created_at: NOW - 2000 });
		const b = mk({ id: 'b', task_id: 'tB', created_at: NOW - 3000 });
		const a3 = mk({ id: 'a3', task_id: 'tA', created_at: NOW - 4000 }); // tA again, but not consecutive
		const old = mk({ id: 'old', task_id: 'tA', created_at: NOW - 86_400_000 }); // yesterday
		const g = groupInbox([a1, a2, b, a3, old], NOW);
		expect(g.days.map((d) => d.label)).toEqual(['Today', 'Yesterday']);
		const today = g.days[0].entries;
		expect(today.map((e) => e.latest.id)).toEqual(['a1', 'b', 'a3']);
		expect(today[0].stack.map((n) => n.id)).toEqual(['a1', 'a2']);
		expect(g.days[1].entries[0].stack).toHaveLength(1); // day boundary breaks the stack
	});

	it('null task_id never stacks', () => {
		const x = mk({ id: 'x', task_id: null, created_at: NOW - 1000 });
		const y = mk({ id: 'y', task_id: null, created_at: NOW - 2000 });
		const g = groupInbox([x, y], NOW);
		expect(g.days[0].entries).toHaveLength(2);
	});
});
```

- [ ] **Step 2: Run to verify failure**

```
npm run test:frontend -- --run src/lib/components/workos/lib/inbox.test.ts
```
Expected: FAIL — module `./inbox` not found.

- [ ] **Step 3: Implement**

Create `src/lib/components/workos/lib/inbox.ts`:

```ts
import type { Notification } from './types';

/** One feed row: `latest` renders; `stack` (incl. latest, newest-first) expands. */
export interface FeedEntry {
	latest: Notification;
	stack: Notification[];
}

export interface DayGroup {
	label: string;
	entries: FeedEntry[];
}

export interface InboxGroups {
	needsYou: Notification[];
	days: DayGroup[];
}

/** "Needs you" = unread mentions + assignments; read ones flow into the feed. */
export function isNeedsYou(n: Notification): boolean {
	return !n.read && (n.type === 'mentioned' || n.type === 'assigned');
}

const startOfDay = (ms: number): number => new Date(ms).setHours(0, 0, 0, 0);

export function dayLabelOf(ms: number, now: number): string {
	const diff = Math.round((startOfDay(now) - startOfDay(ms)) / 86_400_000);
	if (diff <= 0) return 'Today';
	if (diff === 1) return 'Yesterday';
	return new Date(ms).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
}

/**
 * Split a newest-first notification list into the pinned needs-you set and
 * day groups; within a day, consecutive rows on the same task collapse into
 * one FeedEntry (stack). A null task_id never stacks.
 */
export function groupInbox(list: Notification[], now: number): InboxGroups {
	const needsYou: Notification[] = [];
	const days: DayGroup[] = [];
	for (const n of list) {
		if (isNeedsYou(n)) {
			needsYou.push(n);
			continue;
		}
		const label = dayLabelOf(n.created_at, now);
		let day = days[days.length - 1];
		if (!day || day.label !== label) {
			day = { label, entries: [] };
			days.push(day);
		}
		const last = day.entries[day.entries.length - 1];
		if (last && last.latest.task_id != null && last.latest.task_id === n.task_id) {
			last.stack.push(n);
		} else {
			day.entries.push({ latest: n, stack: [n] });
		}
	}
	return { needsYou, days };
}
```

- [ ] **Step 4: Run to verify pass**

```
npm run test:frontend -- --run src/lib/components/workos/lib/inbox.test.ts
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/inbox.ts src/lib/components/workos/lib/inbox.test.ts
git commit -m "feat(workos): inbox grouping - needs-you split, day buckets, task stacking"
```

---

### Task 5: TaskDetail split — extract `TaskDetailBody` + comment highlight

**Files:**
- Create: `src/lib/components/workos/views/detail/TaskDetailBody.svelte` (content moved from TaskDetail, `md:` → container variants)
- Modify: `src/lib/components/workos/views/TaskDetail.svelte` (becomes a thin Dialog wrapper)
- Modify: `src/lib/components/workos/views/detail/CommentItem.svelte` (highlight prop + scroll-into-view + `teamId` prop)
- Modify: `src/lib/components/workos/views/detail/DetailHeader.svelte` (task-derived role + breadcrumb)
- Modify: `src/lib/components/workos/views/detail/AttachmentsPanel.svelte` (`teamId` prop for role; `AttachmentList.svelte` is dead code — imported nowhere, not rendered by AttachmentsPanel — leave it untouched)

**Interfaces:**
- Consumes: all detail stores (`selectedTask`, `comments`, …) — unchanged; `highlightCommentId` from Task 3.
- Produces: `TaskDetailBody` — no props, reads stores, renders the full detail surface with its own root container. `CommentItem` gains `export let highlight = false`.

**This is a mostly mechanical extraction — dialog behavior must not change.** TaskDetail.svelte is ~560 lines: a `<script>` block, a `<svelte:window onpointerdown={onWindowPointerDown} />` line, and a template of the shape `{#if t} <Dialog.Root …> <Dialog.Content …> [INNER CONTENT] </Dialog.Content> </Dialog.Root> {/if}` (Dialog.Root at ~line 221, Dialog.Content ~222–225, closing tags ~558–559). Two deliberate non-mechanical parts: (a) the internal two-column split is viewport-based (`md:` = 768px viewport, with a fixed `md:w-[440px]` left column at line 233) — inside a ~50%-width inbox pane that leaves no room for comments, so those variants become **container queries**; (b) the detail components derive role/breadcrumb/labels from the *current* team, which is wrong for cross-team tasks (a pre-existing My Work defect the inbox makes prominent) — Step 4 fixes the cheap parts.

- [ ] **Step 1: Create `TaskDetailBody.svelte`**

Move into it, unchanged:
- The **entire** `<script lang="ts">` block from TaskDetail.svelte **except** the `import * as Dialog from '$lib/components/ui/dialog';` line. Fix the relative import paths (`../ui/…` → `../../ui/…`, `./detail/…` → `./…`, `../lib/…` → `../../lib/…`). Keep `closeTask` imported (mobile header X uses it if present in the moved markup).
- The `<svelte:window onpointerdown={onWindowPointerDown} />` line.
- The template INNER CONTENT (everything between `<Dialog.Content …>` and `</Dialog.Content>` **except** the `<Dialog.Title class="sr-only">…</Dialog.Title>` and `<Dialog.Description class="sr-only">…</Dialog.Description>` lines at the top — those are Dialog-context components and must stay in the wrapper; moving them would break the compile after the Dialog import is dropped and crash when the body mounts inline without a Dialog.Root), wrapped in:

```svelte
{#if t}
	<div class="@container flex h-full min-h-0 flex-col overflow-hidden bg-white dark:bg-gray-950">
		<!-- [INNER CONTENT moved here] -->
	</div>
{/if}
```

Then convert the moved template's internal-split breakpoints from viewport to **container** variants (the `@container` class on the wrapper above enables them). Exactly 6 lines carry them (source line numbers from TaskDetail.svelte):

| Source line | Change |
|---|---|
| 231 | `md:flex-row` → `@[880px]:flex-row`, `md:overflow-hidden` → `@[880px]:overflow-hidden` |
| 233 | every `md:` prefix (`md:w-[440px] md:flex-none md:min-h-0 md:overflow-y-auto md:px-7 md:py-5 md:border-b-0 md:border-r`) → `@[880px]:` |
| 255 | `md:hidden` → `@[880px]:hidden` |
| 263 | `md:block` → `@[880px]:block` |
| 524 | every `md:` prefix (`md:flex-1 md:min-w-0 md:min-h-0 md:overflow-y-auto md:px-7 md:py-5`) → `@[880px]:` |
| 543 | every `max-md:` prefix → `@max-[880px]:` |

Effect: the 1100px dialog container is ≥880px, so the dialog renders pixel-identically; a narrower inbox pane (or a narrow window's dialog) falls back to the stacked single-column layout, which is the desired compact behavior. Child components (DetailHeader etc.) keep their own viewport variants — fine in both contexts.

Add to its script imports: `import { highlightCommentId } from '../../lib/store';`

In the Comments `Tabs.Content`, change the comment loop to pass the highlight AND the task's team (the `teamId` prop is added to CommentItem in Step 4 — this is the canonical final form of the loop, write it once):

```svelte
{#each sortedComments as c (c.id)}<CommentItem comment={c} highlight={c.id === $highlightCommentId} teamId={t.team_id} />{/each}
```

- [ ] **Step 2: Rewrite `TaskDetail.svelte` as the thin wrapper**

Replace the whole file with:

```svelte
<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog';
	import TaskDetailBody from './detail/TaskDetailBody.svelte';
	import { selectedTask, closeTask } from '../lib/store';

	$: t = $selectedTask;
</script>

{#if t}
	<Dialog.Root open={true} onOpenChange={(o) => { if (!o) closeTask(); }}>
		<Dialog.Content
			showCloseButton={false}
			class="flex flex-col gap-0 p-0 overflow-hidden w-[95vw] max-w-[1100px] sm:max-w-[1100px] max-h-[85vh] max-md:w-screen max-md:max-w-none max-md:h-dvh max-md:max-h-dvh max-md:rounded-none max-md:border-0 bg-white dark:bg-gray-950"
		>
			<Dialog.Title class="sr-only">{t.title}</Dialog.Title>
			<Dialog.Description class="sr-only">Task details</Dialog.Description>
			<TaskDetailBody />
		</Dialog.Content>
	</Dialog.Root>
{/if}
```

(The `class` string is copied verbatim from the current Dialog.Content — do not alter it. The sr-only Title/Description lines are the ones excluded from the Step 1 move — they keep the dialog's accessible name.)

- [ ] **Step 3: CommentItem highlight**

In `src/lib/components/workos/views/detail/CommentItem.svelte`:
- Add to the script: `export let highlight = false;` and:

```ts
	let rootEl: HTMLElement | null = null;
	$: if (highlight && rootEl) rootEl.scrollIntoView({ block: 'center', behavior: 'smooth' });
```

- On the component's root element add `bind:this={rootEl}` and extend its class attribute with:

```
{highlight ? 'bg-primary/5 border-l-2 border-primary' : ''}
```

(Adapt to the root's existing class= form — if it is a plain string, convert to a template `class="existing {highlight ? '…' : ''}"`.)

- [ ] **Step 4: Cross-team detail correctness (task-derived role, breadcrumb, labels)**

The detail surface currently derives everything from the *current* team/workstream — wrong when the inbox opens a task from another team (and already wrong for My Work cross-team opens). The `roles` store is keyed by team id and `workstreams` holds every visible workstream, so:

- `DetailHeader.svelte` (~lines 14–15): derive from the task, not the globals —

```ts
	$: myRole = $roles[task.team_id];
	$: crumb =
		$workstreams.find((w) => w.id === task.workstream_id)?.name ?? $currentWorkstream?.name ?? 'Tasks';
```

(add `workstreams` to the store import; keep `currentWorkstream` as the fallback).
- `CommentItem.svelte` (~line 13) and `AttachmentsPanel.svelte` (~line 19): add `export let teamId: string | null = null;` and change the role line to

```ts
	$: myRole = teamId ? $roles[teamId] : $currentTeam ? $roles[$currentTeam.id] : undefined;
```

TaskDetailBody passes `teamId={t.team_id}` to CommentItem (already done by Step 1's canonical loop) and to AttachmentsPanel. Do NOT touch `AttachmentList.svelte` — it is imported nowhere in src (dead file). (The fallback keeps every other call site behaving exactly as today.)
- **Labels stay team-scoped:** the `labels` store and `createLabel` target the *current* team, so on a foreign-team task the picker would show and create the wrong team's tags. In TaskDetailBody add `currentTeam` to the store import, then `$: foreignTeam = !!t && t.team_id !== ($currentTeam?.id ?? t.team_id);` and wrap the label add/edit UI (the tag picker around source line ~386) in `{#if !foreignTeam}`. Displayed chips resolve through the current-team label map and simply won't render for foreign tasks — acceptable; per-team label fetch is a follow-up if it ever matters.

- [ ] **Step 5: Type-check + test sweep**

```
npm run check
npm run test:frontend -- --run
```
Expected: no new svelte-check errors; all vitest suites pass.

- [ ] **Step 6: Manual sanity (hot reload, no rebuild)**

With the user's Vite server running and the app open: open a task from the Board — the detail dialog must look and behave exactly as before (tabs, comment composer, progress bar drag, subtasks; the ≥880px dialog container renders the converted variants identically). This is the no-behavior-change gate for the extraction. ALSO shrink the window below ~900px viewport (dialog container drops under 880px) and confirm the detail actually stacks single-column — this proves the arbitrary `@[880px]:`/`@max-[880px]:` container variants compile in this Tailwind v4 + legacy container-queries-plugin setup (no repo precedent for arbitrary sizes; a silent no-op variant must be caught here, not in Task 8 smoke).

- [ ] **Step 7: Commit**

```bash
git add src/lib/components/workos/views/TaskDetail.svelte src/lib/components/workos/views/detail/TaskDetailBody.svelte src/lib/components/workos/views/detail/CommentItem.svelte src/lib/components/workos/views/detail/DetailHeader.svelte src/lib/components/workos/views/detail/AttachmentsPanel.svelte
git commit -m "refactor(workos): extract container-responsive TaskDetailBody + cross-team detail context"
```

---

### Task 6: Inbox UI primitives — `TypeGlyph`, `NeedsYouCard`, `FeedRow`

**Files:**
- Modify: `src/lib/components/workos/ui/Icon.svelte` (add `at-sign`, `arrow-right-left` glyphs)
- Create: `src/lib/components/workos/views/inbox/TypeGlyph.svelte`
- Create: `src/lib/components/workos/views/inbox/NeedsYouCard.svelte`
- Create: `src/lib/components/workos/views/inbox/FeedRow.svelte`

**Interfaces:**
- Consumes: `Notification`, `FeedEntry` (Task 4), `StatusBadge`, `Avatar`/`AvatarFallback`, `avatarColors`, `Icon`, `displayName` from store.
- Produces (Task 7 mounts these):
  - `TypeGlyph` props: `type: NotificationType`, `variant?: 'bubble' | 'inline'` (default `bubble`)
  - `NeedsYouCard` props: `n: Notification`, `selected: boolean`, `onopen: () => void`, `onread: () => void`, `onarchive: () => void`
  - A11y shape for both row components: the container is a plain `div`; the open action is a **stretched sibling button** (`absolute inset-0 z-0`), and the hover action buttons / stack pill sit above it (`relative z-10`) — real buttons are never nested inside an interactive element.
  - `FeedRow` props: `entry: FeedEntry`, `selectedId?: string | null` (the selected *notification* id — selection is per-notification, not per-task, so multiple rows for one task never all highlight), `archivedView?: boolean` (default false), `onopen: (n: Notification) => void`, `onread: (n: Notification) => void`, `onarchive: (n: Notification) => void` (in archived view `onarchive` unarchives)

- [ ] **Step 1: Add the two missing icons**

In `src/lib/components/workos/ui/Icon.svelte`'s glyph map add (lucide paths, same format as neighbors):

```ts
		'at-sign': '<circle cx="12" cy="12" r="4"/><path d="M16 8v5a3 3 0 0 0 6 0v-1a10 10 0 1 0-3.92 7.94"/>',
		'arrow-right-left': '<path d="m16 3 4 4-4 4"/><path d="M20 7H4"/><path d="m8 21-4-4 4-4"/><path d="M4 17h16"/>',
```

- [ ] **Step 2: `TypeGlyph.svelte`**

```svelte
<script lang="ts">
	// Tinted per-type glyph: bubble (30px rounded square, feed rows) or inline (bare icon).
	// Hues: mentioned = brand primary, assigned = in-progress teal (data color),
	// commented/status = neutral gray — one meaning per hue (design system D1/D3).
	import Icon from '../../ui/Icon.svelte';
	import { STATUS_COLOR, tint } from '../../lib/colors';
	import type { NotificationType } from '../../lib/types';

	export let type: NotificationType;
	export let variant: 'bubble' | 'inline' = 'bubble';

	const ICON: Record<NotificationType, string> = {
		mentioned: 'at-sign',
		assigned: 'user-plus',
		commented: 'message-square',
		status_changed: 'arrow-right-left'
	};
	// Colored types carry an inline style; neutral ones use theme classes.
	const STYLE: Partial<Record<NotificationType, string>> = {
		mentioned: `color:var(--primary);background:${tint('var(--primary)')}`,
		assigned: `color:${STATUS_COLOR.in_progress};background:${tint(STATUS_COLOR.in_progress)}`
	};
</script>

{#if variant === 'bubble'}
	<span
		class="flex size-[30px] flex-none items-center justify-center rounded-[10px]
			{STYLE[type] ? '' : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'}"
		style={STYLE[type] ?? ''}
	>
		<Icon name={ICON[type]} size={15} />
	</span>
{:else}
	<span
		class="inline-flex flex-none items-center align-[-2px] {STYLE[type] ? '' : 'text-gray-400 dark:text-gray-500'}"
		style={STYLE[type] ? STYLE[type].split(';')[0] : ''}
	>
		<Icon name={ICON[type]} size={13} />
	</span>
{/if}
```

- [ ] **Step 3: `NeedsYouCard.svelte`**

```svelte
<script lang="ts">
	// "Needs you" card — flat rounded-lg card with a 2px primary inset (mockup V4).
	import Icon from '../../ui/Icon.svelte';
	import TypeGlyph from './TypeGlyph.svelte';
	import { Avatar, AvatarFallback } from '$lib/components/ui/avatar';
	import { avatarColors } from '../../lib/avatar';
	import { displayName } from '../../lib/store';
	import { agoShort } from '../../lib/inboxFormat';
	import type { Notification } from '../../lib/types';

	export let n: Notification;
	export let selected = false;
	export let onopen: () => void;
	export let onread: () => void;
	export let onarchive: () => void;

	$: who = n.data?.actor_name ?? displayName(n.actor_id);
	$: initialsOf = (who || '?').trim().split(/\s+/).map((w: string) => w[0]).slice(0, 2).join('').toUpperCase() || '?';
	$: verb = n.type === 'assigned' ? 'assigned you' : 'mentioned you in';
</script>

<div
	class="group relative mx-4 mb-2 flex gap-2.5 rounded-lg border bg-white p-2.5 pl-3
		shadow-[inset_2px_0_0_var(--primary)] transition-colors duration-150 dark:bg-gray-900
		{selected ? 'border-primary' : 'border-gray-200 hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-850'}"
>
	<!-- Stretched primary action: a real sibling button (valid a11y tree) — the
	     hover actions below are z-raised siblings, never nested interactives. -->
	<button
		class="absolute inset-0 z-0 cursor-pointer rounded-lg focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
		aria-label="Open: {who} {verb} {n.data?.task_title ?? ''}"
		onclick={onopen}
	></button>
	<Avatar class="size-7 flex-none">
		<AvatarFallback class="text-[10px] font-semibold text-white" style="background:{avatarColors(n.actor_id ?? who).background}">
			{initialsOf}
		</AvatarFallback>
	</Avatar>
	<div class="min-w-0 flex-1">
		<div class="wos-body">
			<TypeGlyph type={n.type} variant="inline" />
			<span class="font-semibold">{who}</span>
			<span class="text-gray-500 dark:text-gray-400">{verb}</span>
			{#if n.data?.task_key}
				<span class="wos-caption rounded-md border border-gray-200 bg-gray-100 px-1.5 py-px text-gray-600 dark:border-gray-800 dark:bg-gray-850 dark:text-gray-300">{n.data.task_key}</span>
			{/if}
			<span class="font-semibold">{n.data?.task_title ?? ''}</span>
		</div>
		{#if n.data?.snippet}
			<div class="wos-meta mt-1 truncate border-l-2 border-gray-200 pl-2.5 text-gray-500 dark:border-gray-800 dark:text-gray-400">{n.data.snippet}</div>
		{/if}
	</div>
	<div class="flex flex-none flex-col items-end gap-1">
		<span class="wos-caption tabular-nums text-gray-400 dark:text-gray-500">{agoShort(n.created_at)}</span>
		<div class="relative z-10 flex gap-1 opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100">
			<button
				class="flex size-6 items-center justify-center rounded-md border border-gray-200 bg-white text-gray-500 transition-colors duration-150 hover:text-gray-900 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:border-gray-800 dark:bg-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
				title="Mark read" aria-label="Mark read"
				onclick={onread}
			><Icon name="check" size={13} /></button>
			<button
				class="flex size-6 items-center justify-center rounded-md border border-gray-200 bg-white text-gray-500 transition-colors duration-150 hover:text-gray-900 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:border-gray-800 dark:bg-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
				title="Archive" aria-label="Archive"
				onclick={onarchive}
			><Icon name="archive" size={13} /></button>
		</div>
	</div>
</div>
```

Create the tiny shared time helper `src/lib/components/workos/lib/inboxFormat.ts` in this step too (FeedRow uses it as well):

```ts
/** Compact relative age for inbox rows: 45s, 12m, 3h, 2d. */
export function agoShort(ms: number, now = Date.now()): string {
	const s = Math.max(0, Math.floor((now - ms) / 1000));
	if (s < 60) return `${s}s`;
	const m = Math.floor(s / 60);
	if (m < 60) return `${m}m`;
	const h = Math.floor(m / 60);
	if (h < 24) return `${h}h`;
	return `${Math.floor(h / 24)}d`;
}
```

- [ ] **Step 4: `FeedRow.svelte`**

```svelte
<script lang="ts">
	// Feed row — V1 anatomy (user pick): unread dot column, type bubble, two-line body
	// (sentence + snippet/transition), stack pill that expands in place.
	import Icon from '../../ui/Icon.svelte';
	import TypeGlyph from './TypeGlyph.svelte';
	import StatusBadge from '../../ui/StatusBadge.svelte';
	import { displayName } from '../../lib/store';
	import { agoShort } from '../../lib/inboxFormat';
	import type { FeedEntry } from '../../lib/inbox';
	import type { Notification, TaskStatus } from '../../lib/types';

	export let entry: FeedEntry;
	export let selectedId: string | null = null;
	export let archivedView = false;
	export let onopen: (n: Notification) => void;
	export let onread: (n: Notification) => void;
	export let onarchive: (n: Notification) => void;

	let expanded = false;
	$: rows = expanded ? entry.stack : [entry.latest];

	const VERB: Record<string, string> = {
		assigned: 'assigned you', mentioned: 'mentioned you in',
		commented: 'commented on', status_changed: 'moved'
	};
	const who = (x: Notification) => x.data?.actor_name ?? displayName(x.actor_id);
</script>

{#each rows as item, i (item.id)}
	<div
		class="group relative flex items-start gap-2.5 px-4 py-2.5 transition-colors duration-150 hover:bg-gray-50 dark:hover:bg-gray-850
			{selectedId === item.id ? 'bg-primary/5 shadow-[inset_2px_0_0_var(--primary)]' : ''}
			{i > 0 ? 'pl-10' : ''}"
	>
		<!-- Stretched primary action (valid a11y tree: actions are siblings, not nested). -->
		<button
			class="absolute inset-0 z-0 cursor-pointer focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset focus-visible:outline-none"
			aria-label="Open: {who(item)} {VERB[item.type] ?? 'updated'} {item.data?.task_title ?? ''}"
			onclick={() => onopen(item)}
		></button>
		{#if !item.read}
			<span class="mt-[11px] size-2 flex-none rounded-full bg-primary"></span>
		{:else}
			<span class="w-2 flex-none"></span>
		{/if}
		<TypeGlyph type={item.type} />
		<div class="min-w-0 flex-1">
			<div class="wos-body {item.read ? 'text-gray-500 dark:text-gray-400' : ''}">
				<span class={item.read ? 'font-medium' : 'font-semibold'}>{who(item)}</span>
				<span class="text-gray-500 dark:text-gray-400">{VERB[item.type] ?? 'updated'}</span>
				{#if item.data?.task_key}
					<span class="wos-caption rounded-md border border-gray-200 bg-gray-100 px-1.5 py-px text-gray-600 dark:border-gray-800 dark:bg-gray-850 dark:text-gray-300">{item.data.task_key}</span>
				{/if}
				<span class={item.read ? '' : 'font-semibold'}>{item.data?.task_title ?? ''}</span>
				{#if i === 0 && entry.stack.length > 1}
					<button
						class="relative z-10 ml-1 rounded-full bg-gray-100 px-2 py-px text-[11px] font-semibold text-gray-600 transition-colors duration-150 hover:bg-gray-200 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:bg-gray-850 dark:text-gray-300 dark:hover:bg-gray-800"
						onclick={() => (expanded = !expanded)}
					>{expanded ? 'Collapse' : `${entry.stack.length} updates`}</button>
				{/if}
			</div>
			{#if item.type === 'status_changed' && item.data?.from && item.data?.to}
				<div class="mt-1 flex items-center gap-1.5">
					<StatusBadge status={item.data.from as TaskStatus} size="sm" />
					<span class="wos-caption text-gray-400">→</span>
					<StatusBadge status={item.data.to as TaskStatus} size="sm" />
				</div>
			{:else if item.data?.snippet}
				<div class="wos-meta mt-1 line-clamp-2 border-l-2 border-gray-200 pl-2.5 text-gray-500 dark:border-gray-800 dark:text-gray-400">{item.data.snippet}</div>
			{/if}
		</div>
		<span class="wos-caption mt-1 flex-none tabular-nums text-gray-400 dark:text-gray-500">{agoShort(item.created_at)}</span>
		<div class="relative z-10 mt-0.5 flex flex-none gap-1 opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100">
			{#if !archivedView && !item.read}
				<button
					class="flex size-6 items-center justify-center rounded-md border border-gray-200 bg-white text-gray-500 transition-colors duration-150 hover:text-gray-900 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:border-gray-800 dark:bg-gray-950 dark:text-gray-400 dark:hover:text-gray-100"
					title="Mark read" aria-label="Mark read"
					onclick={() => onread(item)}
				><Icon name="check" size={13} /></button>
			{/if}
			<button
				class="flex size-6 items-center justify-center rounded-md border border-gray-200 bg-white text-gray-500 transition-colors duration-150 hover:text-gray-900 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:border-gray-800 dark:bg-gray-950 dark:text-gray-400 dark:hover:text-gray-100"
				title={archivedView ? 'Unarchive' : 'Archive'} aria-label={archivedView ? 'Unarchive' : 'Archive'}
				onclick={() => onarchive(item)}
			><Icon name="archive" size={13} /></button>
		</div>
	</div>
{/each}
```

- [ ] **Step 5: Type-check**

```
npm run check
```
Expected: no new errors.

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/workos/ui/Icon.svelte src/lib/components/workos/views/inbox/TypeGlyph.svelte src/lib/components/workos/views/inbox/NeedsYouCard.svelte src/lib/components/workos/views/inbox/FeedRow.svelte src/lib/components/workos/lib/inboxFormat.ts
git commit -m "feat(workos): inbox row primitives - TypeGlyph, NeedsYouCard, FeedRow"
```

---

### Task 7: InboxView assembly — split-pane, controls, sections (+ app wiring, sidebar badge fix)

**Files:**
- Rewrite: `src/lib/components/workos/views/InboxView.svelte`
- Modify: `src/lib/components/workos/WorkOSApp.svelte` (line 83: drawer suppression)
- Modify: `src/lib/components/workos/chrome/Sidebar.svelte` (lines 50 + 115: `bg-sky-500` → `bg-primary`; line 115 also `text-white` → `text-primary-foreground`)
- Modify: `src/lib/components/workos/chrome/NavDrawer.svelte` (line 42: same badge fix) and `src/lib/components/workos/chrome/MobileHeader.svelte` (line 29: same dot fix)

**Interfaces:**
- Consumes: everything produced by Tasks 3–6 (`groupInbox`, `notificationCounts`, `archiveNotificationsAction`, `archiveAllRead`, `openInboxNotification`, `loadMoreNotifications`, `loadArchivedNotifications`, `loadMoreArchivedNotifications`, `inboxSplit`, `NeedsYouCard`, `FeedRow`, `TaskDetailBody`, `inboxTaskError`), plus `mobile` from `$lib/stores` and `EmptyState`.
- Produces: the finished view.

- [ ] **Step 1: Rewrite `InboxView.svelte`**

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { mobile } from '$lib/stores';
	import Icon from '../ui/Icon.svelte';
	import EmptyState from '../ui/EmptyState.svelte';
	import NeedsYouCard from './inbox/NeedsYouCard.svelte';
	import FeedRow from './inbox/FeedRow.svelte';
	import TaskDetailBody from './detail/TaskDetailBody.svelte';
	import { groupInbox } from '../lib/inbox';
	import { agoShort } from '../lib/inboxFormat';
	import type { Notification, NotificationType } from '../lib/types';
	import {
		notifications, archivedNotifications, notificationCounts, notificationsHasMore, archivedHasMore,
		selectedTaskId, selectedTask, inboxTaskError, inboxSplit,
		loadNotifications, loadMoreNotifications, loadArchivedNotifications, loadMoreArchivedNotifications,
		markRead, markAllRead, archiveNotificationsAction, archiveAllRead,
		openInboxNotification, openNotification, closeTask
	} from '../lib/store';

	let now = Date.now();

	onMount(() => {
		void loadNotifications();
		const tick = setInterval(() => (now = Date.now()), 60_000); // keep day labels + ages fresh
		return () => {
			clearInterval(tick);
			// Desktop: leaving the inbox clears the split-pane selection. Mobile taps
			// navigate away (openNotification → view 'board'), which unmounts this
			// view — that selection must survive the unmount or the full-screen
			// task dialog would be closed before it ever opens.
			if (!$mobile) closeTask();
		};
	});

	type Tab = 'all' | NotificationType;
	const TABS: { k: Tab; label: string }[] = [
		{ k: 'all', label: 'All' },
		{ k: 'mentioned', label: 'Mentions' },
		{ k: 'assigned', label: 'Assigned' },
		{ k: 'commented', label: 'Comments' },
		{ k: 'status_changed', label: 'Status' }
	];
	let tab: Tab = 'all';
	let unreadOnly = false;
	let showArchived = false;

	function toggleArchived(): void {
		showArchived = !showArchived;
		unreadOnly = false; // archived rows are always read — a stale unread filter would blank the list
		if (showArchived) void loadArchivedNotifications();
	}

	$: counts = $notificationCounts;
	$: tabCount = (k: Tab) => (k === 'all' ? counts.unread : counts.by_type[k]);
	$: source = showArchived ? $archivedNotifications : $notifications;
	$: filtered = source.filter(
		(n) => (tab === 'all' || n.type === tab) && (!unreadOnly || !n.read)
	);
	$: groups = groupInbox(filtered, now);

	$: needsCount = counts.by_type.mentioned + counts.by_type.assigned;
	$: updatesCount = Math.max(0, counts.unread - needsCount);
	$: oldestUnread = [...$notifications].reverse().find((n) => !n.read);

	// Selection is per-notification (not per-task): several rows can share a task
	// and must not all light up. Cleared when the pane selection closes.
	let selectedNotifId: string | null = null;
	$: if (!$selectedTaskId) selectedNotifId = null;

	// ≥1280px: split pane. 768–1279px: same selection flow, but WorkOSApp renders
	// the task dialog over the inbox (no view switch — highlight + realtime intact).
	// Mobile: old navigate-away flow.
	function open(n: Notification): void {
		if ($mobile) {
			void openNotification(n);
		} else {
			selectedNotifId = n.id;
			void openInboxNotification(n);
		}
	}
	const read = (n: Notification) => void markRead([n.id]);
	const archive = (n: Notification) => void archiveNotificationsAction([n.id], !showArchived);
</script>

<div class="flex h-full min-h-0">
	<!-- ─────────── left: list pane ───────────
	     Full-width below xl (no split pane — selection opens the dialog instead;
	     sidebar 256px + list would leave a useless sliver). At ≥xl the list is
	     fixed-width so the detail pane gets every remaining pixel
	     (TaskDetailBody stacks below an 880px container width). -->
	<div class="flex w-full min-w-0 flex-col border-r border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-950 xl:w-[400px] xl:flex-none 2xl:w-[440px]">
		<!-- header -->
		<div class="px-4 pt-4">
			<h1 class="text-[22px] font-semibold tracking-tight text-gray-900 dark:text-gray-100">
				{showArchived ? 'Archived' : 'Inbox'}
			</h1>
			{#if !showArchived}
				<p class="wos-body mt-0.5 text-gray-400 dark:text-gray-500">
					{#if counts.unread === 0}
						You're all caught up.
					{:else}
						<span class="font-semibold text-gray-600 dark:text-gray-300">{needsCount} need{needsCount === 1 ? 's' : ''} your attention</span>
						· {updatesCount} more update{updatesCount === 1 ? '' : 's'}
						{#if oldestUnread}· oldest unread {agoShort(oldestUnread.created_at, now)}{/if}
					{/if}
				</p>
			{:else}
				<p class="wos-body mt-0.5 text-gray-400 dark:text-gray-500">Archived notifications — unarchive to move them back.</p>
			{/if}
		</div>
		<!-- controls -->
		<div class="flex flex-wrap items-center gap-2 border-b border-gray-100 px-4 py-3 dark:border-gray-900">
			<div class="flex min-w-0 max-w-full shrink gap-0.5 overflow-x-auto rounded-full bg-gray-100 p-[3px] dark:bg-gray-900">
				{#each TABS as t (t.k)}
					<button
						class="flex flex-none items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-1 text-xs font-medium transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none
							{tab === t.k
								? 'bg-white font-semibold text-gray-900 shadow-sm dark:bg-gray-850 dark:text-gray-100'
								: 'text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200'}"
						onclick={() => (tab = t.k)}
					>
						{t.label}
						{#if !showArchived && tabCount(t.k) > 0}
							<span class="min-w-4 rounded-full px-1 text-center text-[10px] font-semibold tabular-nums
								{tab === t.k ? 'bg-primary text-primary-foreground' : 'bg-gray-200 text-gray-600 dark:bg-gray-800 dark:text-gray-300'}">{tabCount(t.k)}</span>
						{/if}
					</button>
				{/each}
			</div>
			<div class="flex-1"></div>
			{#if !showArchived}
				<button
					type="button" role="switch" aria-checked={unreadOnly}
					class="inline-flex h-7 items-center gap-1.5 rounded-[10px] border pl-2.5 pr-1.5 text-xs font-medium transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none
						{unreadOnly
							? 'border-primary/40 bg-primary/10 text-primary'
							: 'border-gray-200 text-gray-600 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-850'}"
					onclick={() => (unreadOnly = !unreadOnly)}
				>
					Unread only
					<span class="relative inline-block h-[15px] w-[26px] rounded-full transition-colors duration-150 {unreadOnly ? 'bg-primary' : 'bg-gray-300 dark:bg-gray-700'}">
						<span class="absolute top-0.5 h-[11px] w-[11px] rounded-full bg-white shadow transition-transform duration-150 {unreadOnly ? 'translate-x-[13px]' : 'translate-x-0.5'}"></span>
					</span>
				</button>
			{/if}
			<button
				class="flex h-7 items-center gap-1.5 rounded-[10px] border px-2.5 text-xs font-medium transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none
					{showArchived
						? 'border-primary/40 bg-primary/10 text-primary'
						: 'border-gray-200 text-gray-600 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-850'}"
				title={showArchived ? 'Back to inbox' : 'Archived'}
				onclick={toggleArchived}
			>
				<Icon name={showArchived ? 'arrow-left' : 'archive'} size={13} />
				{showArchived ? 'Back' : 'Archived'}
			</button>
			{#if !showArchived && counts.unread > 0}
				<button
					class="flex h-7 items-center gap-1.5 rounded-[10px] border border-gray-200 px-2.5 text-xs font-medium text-gray-600 transition-colors duration-150 hover:bg-gray-50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-850"
					onclick={() => void markAllRead()}
				>
					<Icon name="check" size={13} /> Mark all read
				</button>
			{/if}
			{#if !showArchived && $notifications.some((n) => n.read)}
				<button
					class="flex h-7 items-center gap-1.5 rounded-[10px] border border-gray-200 px-2.5 text-xs font-medium text-gray-600 transition-colors duration-150 hover:bg-gray-50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-850"
					title="Archive all read"
					onclick={() => void archiveAllRead()}
				>
					<Icon name="archive" size={13} /> Sweep read
				</button>
			{/if}
		</div>
		<!-- scroll region -->
		<div class="min-h-0 flex-1 overflow-y-auto pb-6">
			{#if !filtered.length}
				<EmptyState
					icon="inbox"
					title={showArchived ? 'Nothing archived' : unreadOnly || tab !== 'all' ? 'Nothing here' : "You're all caught up"}
					sub={showArchived ? 'Archived notifications will show up here.' : 'Mentions, assignments and updates will show up here.'}
				/>
			{:else}
				{#if !showArchived && groups.needsYou.length}
					<div class="flex items-center gap-2 px-4 pb-2 pt-4">
						<span class="text-primary"><Icon name="at-sign" size={14} /></span>
						<span class="wos-body font-medium text-gray-600 dark:text-gray-300">Needs you</span>
						<span class="rounded-full bg-primary/10 px-2 text-[11px] font-semibold text-primary">{groups.needsYou.length}</span>
					</div>
					{#each groups.needsYou as n (n.id)}
						<NeedsYouCard
							{n}
							selected={$inboxSplit && selectedNotifId === n.id}
							onopen={() => open(n)}
							onread={() => read(n)}
							onarchive={() => archive(n)}
						/>
					{/each}
				{/if}
				{#each groups.days as day (day.label)}
					<div class="flex items-center gap-2.5 px-4 pb-1.5 pt-4">
						<span class="wos-caption font-semibold uppercase tracking-[0.06em] text-gray-400 dark:text-gray-500">{day.label}</span>
						<span class="h-px flex-1 bg-gray-100 dark:bg-gray-900"></span>
					</div>
					{#each day.entries as entry (entry.latest.id)}
						<FeedRow
							{entry}
							archivedView={showArchived}
							selectedId={$inboxSplit ? selectedNotifId : null}
							onopen={open}
							onread={read}
							onarchive={archive}
						/>
					{/each}
				{/each}
			{/if}
			<!-- Outside the empty-check: a filter can empty the LOADED page while older
			     matches exist on the server — pagination must stay reachable. -->
			{#if showArchived ? $archivedHasMore : $notificationsHasMore}
				<button
					class="mx-4 mt-3 flex h-8 w-[calc(100%-2rem)] items-center justify-center rounded-lg border border-gray-200 text-xs font-medium text-gray-500 transition-colors duration-150 hover:bg-gray-50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:border-gray-800 dark:text-gray-400 dark:hover:bg-gray-850"
					onclick={() => void (showArchived ? loadMoreArchivedNotifications() : loadMoreNotifications())}
				>Load more</button>
			{/if}
		</div>
	</div>
	<!-- ─────────── right: detail pane (≥1280px only) ───────────
	     Error checked BEFORE the body: a deleted/404 task can still resolve a
	     stale copy from `myTasks`, which must not render over the error state. -->
	{#if $inboxSplit}
		<div class="flex min-w-0 flex-1 flex-col bg-white dark:bg-gray-950">
			{#if $selectedTaskId && $inboxTaskError}
				<EmptyState icon="inbox" title="Task no longer available" sub="It may have been deleted, or you no longer have access to it." />
			{:else if $selectedTask}
				<TaskDetailBody />
			{:else if $selectedTaskId}
				<div class="flex h-full items-center justify-center text-sm text-gray-400">Loading…</div>
			{:else}
				<EmptyState icon="message-square" title="Select a notification" sub="The task opens here so you keep your place in the inbox." />
			{/if}
		</div>
	{/if}
</div>
```

- [ ] **Step 2: Suppress the global drawer only when the split pane is active**

In `src/lib/components/workos/WorkOSApp.svelte` line 83, change:

```svelte
{#if $selectedTask}
	<TaskDetail />
{/if}
```

to:

```svelte
{#if $selectedTask && !($view === 'inbox' && $inboxSplit)}
	<TaskDetail />
{/if}
```

Add `inboxSplit` to WorkOSApp's `./lib/store` import. Effect: ≥1280px the pane owns the detail; 768–1279px an inbox selection opens the normal task dialog **over** the inbox (no view switch, highlight + inbox room join intact); mobile is unchanged.

- [ ] **Step 3: Unread badges → primary token, all chrome (design-system D1 fix)**

`sky-500` lives in four spots across desktop + mobile chrome — fix all of them:
- `src/lib/components/workos/chrome/Sidebar.svelte` line 50: `bg-sky-500` → `bg-primary`
- `src/lib/components/workos/chrome/Sidebar.svelte` line 115: `bg-sky-500 text-white` → `bg-primary text-primary-foreground`
- `src/lib/components/workos/chrome/NavDrawer.svelte` line 42: `bg-sky-500 text-white` → `bg-primary text-primary-foreground`
- `src/lib/components/workos/chrome/MobileHeader.svelte` line 29: `bg-sky-500` → `bg-primary`

Then confirm no `sky-500` remains anywhere in WorkOS:

```
rg 'sky-500' src/lib/components/workos
```
Expected: no hits.

- [ ] **Step 4: Type-check + full frontend tests**

```
npm run check
npm run test:frontend -- --run
```
Expected: clean / all pass.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/views/InboxView.svelte src/lib/components/workos/WorkOSApp.svelte src/lib/components/workos/chrome/Sidebar.svelte src/lib/components/workos/chrome/NavDrawer.svelte src/lib/components/workos/chrome/MobileHeader.svelte
git commit -m "feat(workos): inbox split-pane view - needs-you, day feed, archive, counts"
```

---

### Task 8: Verification sweep

**Files:** none created — checks only.

- [ ] **Step 1: Full backend suite**

```
cd backend
.venv\Scripts\python.exe -m pytest open_webui/test/workos -q
```
Expected: all pass.

- [ ] **Step 2: Full frontend suite + types**

```
npm run test:frontend -- --run
npm run check
```
Expected: all pass; no new svelte-check errors vs baseline.

- [ ] **Step 3: Design-system greps**

```
rg 'sky-500' src/lib/components/workos                                  # → no hits
rg -o 'text-\[[0-9.]+px\]' src/lib/components/workos/views/inbox src/lib/components/workos/views/InboxView.svelte
rg 'focus-visible' src/lib/components/workos/views/inbox src/lib/components/workos/views/InboxView.svelte  # → present
```
The `text-[Npx]` check: only sizes matching the type-ramp steps (10/11/12/13/14/17/22/28px equivalents) may appear.

- [ ] **Step 4: Restart the backend container (migration) and browser smoke**

```
docker restart osool-ai-open-webui-1
```

Smoke checklist (user's Vite hot-reload server; seed by acting as a second user in another browser profile, or via direct `Notifications.insert` in a container shell):
1. All four notification types render correctly (glyph colors, sentence, snippet, from→to chips).
2. Unread mention/assignment appears under "Needs you"; marking read moves it into the day feed.
3. Same-task consecutive comments stack ("N updates" → expand/collapse).
4. Click opens the task in the right pane, mentioned/commented scrolls to + highlights the comment; inbox scroll position keeps.
5. Tabs filter + counts match; "Unread only" toggle; Mark all read hides at zero; Sweep read archives.
6. Archived view lists archived rows; Unarchive returns them.
7. Realtime: new notification while the inbox is open prepends + bumps counts + unread badges (primary teal in the sidebar, nav drawer, and mobile header — not sky blue). With a task from a *different* workstream open in the split pane, a comment posted by the second user appears live in the right pane (inbox room join), and a status change made by them updates the pane header.
8. Mobile width (<768px): full-width list, tap opens full-screen detail (old flow).
9. Dark mode pass over all of the above.
10. Board view task drawer still works exactly as before (TaskDetailBody extraction regression check — the ≥880px dialog container must render the converted variants identically).
11. Filter dead-end fix: pick a tab whose matches aren't in the loaded page (or toggle "Unread only" with everything read) — the list may be empty, but "Load more" stays visible and fetches older rows. Archived view paginates past 50 the same way. After "Sweep read" empties the loaded page, "Load more" refills from page 1 instead of no-opping.
12. Cross-team notification (task from a team that is not the current team): breadcrumb shows the task's workstream, delete affordances follow the task team's role, label editing is hidden. If the same task also sits in a stale My Work list, the pane still shows the freshly fetched data (inboxTask wins the lookup).
13. Breakpoints: ≥1280px shows the split pane; at ~1000–1200px the inbox stays full-width and selecting opens the task dialog over it (no view switch; highlight + realtime intact). In a narrow-ish ≥1280px window the detail pane stacks single-column (container query). The tab row scrolls horizontally when cramped.
14. Keyboard/a11y: Tab reaches the row's stretched open button (Enter opens), then the hover action buttons as siblings — action Enter never also opens the row; the accessibility tree has no nested interactive elements.
15. Rapidly click two unread notifications A then B: the pane lands on B and stays there (non-blocking mark-read + open-generation guard), and B's pane never shows A's comments/activity (stale-store clear).
16. Second user deletes the task open in the pane: it flips to "Task no longer available" — both when the task is in the current workstream and when it is foreign.

- [ ] **Step 5: Update memory + report**

Record smoke results; if all green, the feature is merge-ready on `osool`.
