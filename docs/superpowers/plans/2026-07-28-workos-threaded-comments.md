# WorkOS Threaded Comments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat task-comment list with threaded comments (unlimited-depth replies), emoji reactions, a rich mention composer with chips, tombstone deletes, a `replied` notification type, and image-only comment attachments with lightbox previews.

**Architecture:** Additive DB migration (`parent_id` + `deleted_at` on `workos_comment`, new `workos_comment_reaction` table); router grows a reactions endpoint, reply validation, tombstone-vs-hard-delete fork, and a mentioned > replied > commented notification precedence; the frontend builds a comment tree client-side from the flat fetch and renders it with a new recursive `CommentThread` + rewritten `CommentItem`, fed by a new contenteditable `RichComposer`.

**Tech Stack:** FastAPI + SQLAlchemy async + alembic (backend), Svelte 4 + Tailwind + shadcn-svelte primitives + vitest (frontend), pytest-asyncio (backend tests).

**Spec:** `docs/superpowers/specs/2026-07-28-workos-threaded-comments-design.md` (mockup: `docs/superpowers/specs/assets/2026-07-28-comments-mockup.html`)

## Global Constraints

- Emoji reaction allowlist, exact: 👍 ❤️ 🎉 👀 😂 🚀 (6 emoji, server-enforced).
- All comment-UI accents use the existing **primary token** (`--primary` / `text-primary` / `bg-primary`), NOT hardcoded green teal. (Primary is the Osool ink #003b4a family.)
- Visual indent cap: depth 0–2 indent with rails; depth ≥ 3 renders at depth-2 indent with a `↳ replying to @Name` chip. (Spec speaks of "levels 1–3"; zero-indexed depth 0,1,2 indent, depth ≥3 flattens.)
- Wire format for mentions is UNCHANGED: `@[Name](mention:ID)`. `parse_mentions` (backend) and `mentionToken`/`parseMentions` (frontend) are not modified.
- Tombstone = `deleted_at` set, `body=''`, `mentions=[]`, reactions purged. Attachment rows are never touched by delete/tombstone.
- Reactions notify nobody. Reply notifications: precedence mentioned > replied > commented, one notification per recipient, self excluded, all through the existing visibility-gated `notify()`.
- When `comment_id` is set on attachment upload, content type must start with `image/` (server-enforced 400 otherwise).
- Esc handlers inside inputs/overlays must call `stopPropagation()` so the task drawer stays open.
- Backend tests: `cd backend && .venv/Scripts/python.exe -m pytest open_webui/test/workos/<file> -v` (Windows venv python — plain `python` may lack torch DLL workaround).
- Frontend tests: `npm run test:frontend -- run <file>` from repo root.
- NEVER start a Vite dev server without asking the user first (standing rule). The user runs their own hot-reload server.
- Update `docs/superpowers/specs/2026-06-26-workos-access-control.md` whenever access/notification/realtime surface changes (standing rule) — done in Task 4.

## File Structure

**Backend:**
- Modify `backend/open_webui/models/workos.py` — comment columns, reaction table + DAO, model fields.
- Create `backend/open_webui/migrations/versions/c2d3e4f5a6b7_workos_threaded_comments.py`.
- Modify `backend/open_webui/routers/workos.py` — comment endpoints, reactions endpoint, notification precedence, MIME rule.
- Create `backend/open_webui/test/workos/test_router_threaded_comments.py`.

**Frontend (all under `src/lib/components/workos/`):**
- Modify `lib/types.ts`, `lib/api.ts`, `lib/store.ts`, `lib/mentions.ts`, `lib/inbox.ts`, `lib/inboxFormat.ts`, `ui/Icon.svelte`.
- Create `lib/commentTree.ts` (+ test), `lib/richText.ts` (+ test).
- Create `views/detail/RichComposer.svelte`, `views/detail/CommentThread.svelte`, `views/detail/CommentsPanel.svelte`, `views/detail/ImageLightbox.svelte`.
- Rewrite `views/detail/CommentItem.svelte`; delete `views/detail/CommentComposer.svelte`.
- Modify `views/detail/TaskDetailBody.svelte`, `views/inbox/TypeGlyph.svelte`, `views/inbox/FeedRow.svelte`, `views/admin/RulesTab.svelte`.

---

### Task 1: Data layer — migration, model columns, reaction table, DAO methods

**Files:**
- Modify: `backend/open_webui/models/workos.py` (WorkosComment ~line 947, CommentModel ~line 972, CommentsDao ~line 1039)
- Create: `backend/open_webui/migrations/versions/c2d3e4f5a6b7_workos_threaded_comments.py`
- Test: `backend/open_webui/test/workos/test_models_threaded_comments.py`

**Interfaces:**
- Consumes: existing `_id()`, `_now()`, `get_async_db_context`, `CommentModel`.
- Produces (later tasks rely on these exact signatures):
  - `CommentModel` fields `parent_id: Optional[str]`, `deleted_at: Optional[int]`, `reactions: list = []`
  - `Comments.insert(task_id, user_id, body, mentions, parent_id=None, db=None) -> CommentModel`
  - `Comments.has_children(id, db=None) -> bool`
  - `Comments.tombstone(id, db=None) -> Optional[CommentModel]`
  - `Reactions.toggle(comment_id, user_id, emoji, db=None) -> bool` (True = added, False = removed)
  - `Reactions.purge_for_comment(comment_id, db=None) -> None`
  - `Reactions.aggregate_for_comments(comment_ids: list, db=None) -> dict` mapping `comment_id -> [{'emoji','count','user_ids'}]` (insertion-ordered by first reaction)

- [ ] **Step 1: Write the failing test**

Create `backend/open_webui/test/workos/test_models_threaded_comments.py`:

```python
import pytest

from open_webui.models.workos import Comments, Reactions


@pytest.mark.asyncio
async def test_insert_with_parent_and_defaults():
    root = await Comments.insert('t1', 'u1', 'root', [])
    child = await Comments.insert('t1', 'u2', 'child', [], parent_id=root.id)
    assert root.parent_id is None and root.deleted_at is None and root.reactions == []
    assert child.parent_id == root.id


@pytest.mark.asyncio
async def test_has_children():
    root = await Comments.insert('t1', 'u1', 'root', [])
    assert await Comments.has_children(root.id) is False
    await Comments.insert('t1', 'u2', 'child', [], parent_id=root.id)
    assert await Comments.has_children(root.id) is True


@pytest.mark.asyncio
async def test_tombstone_blanks_body_and_mentions():
    c = await Comments.insert('t1', 'u1', 'secret @[X](mention:u9)', ['u9'])
    tomb = await Comments.tombstone(c.id)
    assert tomb.deleted_at is not None
    assert tomb.body == '' and tomb.mentions == []
    assert await Comments.tombstone('nope') is None


@pytest.mark.asyncio
async def test_reaction_toggle_and_aggregate():
    c = await Comments.insert('t1', 'u1', 'hi', [])
    assert await Reactions.toggle(c.id, 'u1', '👍') is True
    assert await Reactions.toggle(c.id, 'u2', '👍') is True
    assert await Reactions.toggle(c.id, 'u2', '🎉') is True
    agg = await Reactions.aggregate_for_comments([c.id])
    entries = {e['emoji']: e for e in agg[c.id]}
    assert entries['👍']['count'] == 2 and set(entries['👍']['user_ids']) == {'u1', 'u2'}
    assert entries['🎉']['count'] == 1
    # toggle off
    assert await Reactions.toggle(c.id, 'u1', '👍') is False
    agg = await Reactions.aggregate_for_comments([c.id])
    entries = {e['emoji']: e for e in agg[c.id]}
    assert entries['👍']['count'] == 1


@pytest.mark.asyncio
async def test_reaction_purge_and_empty_aggregate():
    c = await Comments.insert('t1', 'u1', 'hi', [])
    await Reactions.toggle(c.id, 'u1', '👍')
    await Reactions.purge_for_comment(c.id)
    assert await Reactions.aggregate_for_comments([c.id]) == {}
    assert await Reactions.aggregate_for_comments([]) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python.exe -m pytest open_webui/test/workos/test_models_threaded_comments.py -v`
Expected: FAIL — `ImportError: cannot import name 'Reactions'` (and/or `TypeError: insert() got an unexpected keyword argument 'parent_id'`).

- [ ] **Step 3: Add columns + table + model fields in `models/workos.py`**

In `WorkosComment` (after `mentions` column):

```python
    parent_id = Column(Text, nullable=True)   # threading: null = top-level; parent is on the same task
    deleted_at = Column(BigInteger, nullable=True)  # tombstone marker (body/mentions blanked when set)
```

After `WorkosActivity` class, add:

```python
class WorkosCommentReaction(Base):
    __tablename__ = 'workos_comment_reaction'

    id = Column(Text, primary_key=True, unique=True)
    comment_id = Column(Text)
    user_id = Column(Text)
    emoji = Column(Text)
    created_at = Column(BigInteger)

    __table_args__ = (
        UniqueConstraint('comment_id', 'user_id', 'emoji', name='uq_workos_reaction'),
    )
```

`UniqueConstraint` must be imported — extend the existing `from sqlalchemy import ...` line at the top of the file with `UniqueConstraint` if absent.

In `CommentModel` (after `mentions`):

```python
    parent_id: Optional[str] = None
    deleted_at: Optional[int] = None
    reactions: list = []
```

- [ ] **Step 4: Extend `CommentsDao` and add `ReactionsDao`**

Replace `CommentsDao.insert` with:

```python
    async def insert(
        self, task_id: str, user_id: str, body: str, mentions: list,
        parent_id: Optional[str] = None, db: Optional[AsyncSession] = None,
    ) -> CommentModel:
        async with get_async_db_context(db) as db:
            now = _now()
            row = WorkosComment(
                id=_id(), task_id=task_id, user_id=user_id, body=body,
                mentions=mentions or [], parent_id=parent_id, deleted_at=None,
                edited_at=None, created_at=now, updated_at=now,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return CommentModel.model_validate(row)
```

Add to `CommentsDao` (after `delete`):

```python
    async def has_children(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosComment.id).filter_by(parent_id=id).limit(1))
            return res.scalars().first() is not None

    async def tombstone(self, id: str, db: Optional[AsyncSession] = None) -> Optional[CommentModel]:
        """Soft-delete: blank content, keep the row so replies stay attached."""
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosComment).filter_by(id=id))
            row = res.scalars().first()
            if not row:
                return None
            now = _now()
            row.deleted_at = now
            row.body = ''
            row.mentions = []
            row.updated_at = now
            await db.commit()
            await db.refresh(row)
            return CommentModel.model_validate(row)
```

After `ActivityDao`, add:

```python
class ReactionsDao:
    async def toggle(
        self, comment_id: str, user_id: str, emoji: str, db: Optional[AsyncSession] = None
    ) -> bool:
        """Add the reaction, or remove it if it already exists. True = added."""
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosCommentReaction).filter_by(
                comment_id=comment_id, user_id=user_id, emoji=emoji))
            row = res.scalars().first()
            if row:
                await db.execute(delete(WorkosCommentReaction).filter_by(id=row.id))
                await db.commit()
                return False
            db.add(WorkosCommentReaction(
                id=_id(), comment_id=comment_id, user_id=user_id, emoji=emoji, created_at=_now(),
            ))
            await db.commit()
            return True

    async def purge_for_comment(self, comment_id: str, db: Optional[AsyncSession] = None) -> None:
        async with get_async_db_context(db) as db:
            await db.execute(delete(WorkosCommentReaction).filter_by(comment_id=comment_id))
            await db.commit()

    async def aggregate_for_comments(
        self, comment_ids: list, db: Optional[AsyncSession] = None
    ) -> dict:
        """{comment_id: [{'emoji','count','user_ids'}]} — entries ordered by first reaction."""
        if not comment_ids:
            return {}
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosCommentReaction)
                .where(WorkosCommentReaction.comment_id.in_(comment_ids))
                .order_by(WorkosCommentReaction.created_at.asc())
            )
            out: dict = {}
            for row in res.scalars().all():
                per = out.setdefault(row.comment_id, {})
                agg = per.setdefault(row.emoji, {'emoji': row.emoji, 'count': 0, 'user_ids': []})
                agg['count'] += 1
                agg['user_ids'].append(row.user_id)
            return {cid: list(per.values()) for cid, per in out.items()}
```

Next to `Comments = CommentsDao()` add:

```python
Reactions = ReactionsDao()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python.exe -m pytest open_webui/test/workos/test_models_threaded_comments.py -v`
Expected: 5 passed.

- [ ] **Step 6: Write the migration**

Create `backend/open_webui/migrations/versions/c2d3e4f5a6b7_workos_threaded_comments.py`:

```python
"""workos threaded comments

Adds ``workos_comment.parent_id`` (threading; NULL = top-level) and
``workos_comment.deleted_at`` (tombstone), plus the
``workos_comment_reaction`` table (6-emoji allowlist enforced at the
router). Existing comments stay top-level (parent_id NULL) — additive only.
Spec: docs/superpowers/specs/2026-07-28-workos-threaded-comments-design.md

Revision ID: c2d3e4f5a6b7
Revises: b0c1d2e3f4a5
Create Date: 2026-07-28 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, None] = 'b0c1d2e3f4a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workos_comment', sa.Column('parent_id', sa.Text(), nullable=True))
    op.add_column('workos_comment', sa.Column('deleted_at', sa.BigInteger(), nullable=True))
    op.create_table(
        'workos_comment_reaction',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('comment_id', sa.Text(), nullable=True),
        sa.Column('user_id', sa.Text(), nullable=True),
        sa.Column('emoji', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('comment_id', 'user_id', 'emoji', name='uq_workos_reaction'),
    )
    op.create_index('ix_workos_comment_parent_id', 'workos_comment', ['parent_id'])
    op.create_index('ix_workos_reaction_comment_id', 'workos_comment_reaction', ['comment_id'])


def downgrade() -> None:
    op.drop_index('ix_workos_reaction_comment_id', table_name='workos_comment_reaction')
    op.drop_index('ix_workos_comment_parent_id', table_name='workos_comment')
    op.drop_table('workos_comment_reaction')
    with op.batch_alter_table('workos_comment') as batch:
        batch.drop_column('deleted_at')
        batch.drop_column('parent_id')
```

- [ ] **Step 7: Sanity-run the whole workos model suite**

Run: `cd backend && .venv/Scripts/python.exe -m pytest open_webui/test/workos/test_models_collab.py open_webui/test/workos/test_models_threaded_comments.py -v`
Expected: all pass (schema is built from `Base.metadata` in conftest, so the new table/columns exist automatically).

- [ ] **Step 8: Commit**

```bash
git add backend/open_webui/models/workos.py backend/open_webui/migrations/versions/c2d3e4f5a6b7_workos_threaded_comments.py backend/open_webui/test/workos/test_models_threaded_comments.py
git commit -m "feat(workos): comment threading + reaction data layer (parent_id, tombstone, reaction table)"
```

---

### Task 2: Router — reply validation, tombstone delete fork, GET aggregation

**Files:**
- Modify: `backend/open_webui/routers/workos.py` (CommentForm ~line 935, list/create/update/delete comment endpoints ~lines 1005–1087)
- Test: `backend/open_webui/test/workos/test_router_threaded_comments.py` (create)

**Interfaces:**
- Consumes: Task 1's `Comments.insert(..., parent_id=)`, `Comments.has_children`, `Comments.tombstone`, `Reactions.purge_for_comment`, `Reactions.aggregate_for_comments`.
- Produces:
  - `POST /tasks/{id}/comments` accepts `{'body': str, 'parent_id': str|None}`; 404 unknown parent, 400 cross-task parent, 400 tombstoned parent.
  - `DELETE /comments/{id}` returns `{'deleted': True, 'tombstoned': True}` when children exist (emits `workos:comment.updated` with the tombstone), else `{'deleted': bool}` (emits `workos:comment.deleted`).
  - `PATCH /comments/{id}` → 400 when comment is tombstoned.
  - `GET /tasks/{id}/comments` items are dicts including `parent_id`, `deleted_at`, `reactions`.

- [ ] **Step 1: Write the failing tests**

Create `backend/open_webui/test/workos/test_router_threaded_comments.py`:

```python
import pytest

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_teams import _client, U1, U2
from open_webui.test.workos.test_router_task import _stream


async def _task(c):
    team, ws, s = await _stream(c)
    t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                      json={'title': 'T', 'assignee_ids': ['u1']})).json()
    return team, ws, s, t


async def _comment(c, task_id, body='root', parent_id=None):
    payload = {'body': body}
    if parent_id is not None:
        payload['parent_id'] = parent_id
    r = await c.post(f"/api/v1/workos/tasks/{task_id}/comments", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_reply_chain_and_list_fields(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        root = await _comment(c, t['id'], 'root')
        child = await _comment(c, t['id'], 'child', parent_id=root['id'])
        grand = await _comment(c, t['id'], 'grand', parent_id=child['id'])
        assert root['parent_id'] is None and child['parent_id'] == root['id']
        assert grand['parent_id'] == child['id']
        listed = (await c.get(f"/api/v1/workos/tasks/{t['id']}/comments")).json()
        by_id = {x['id']: x for x in listed}
        assert by_id[root['id']]['deleted_at'] is None
        assert by_id[root['id']]['reactions'] == []


@pytest.mark.asyncio
async def test_reply_parent_validation(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t1 = await _task(c)
        _, _, _, t2 = await _task(c)
        r = await c.post(f"/api/v1/workos/tasks/{t1['id']}/comments",
                         json={'body': 'x', 'parent_id': 'missing'})
        assert r.status_code == 404
        foreign = await _comment(c, t2['id'], 'other-task root')
        r = await c.post(f"/api/v1/workos/tasks/{t1['id']}/comments",
                         json={'body': 'x', 'parent_id': foreign['id']})
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_delete_with_children_tombstones(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        root = await _comment(c, t['id'], 'root @[X](mention:u2)')
        await _comment(c, t['id'], 'child', parent_id=root['id'])
        r = (await c.delete(f"/api/v1/workos/comments/{root['id']}")).json()
        assert r == {'deleted': True, 'tombstoned': True}
        listed = (await c.get(f"/api/v1/workos/tasks/{t['id']}/comments")).json()
        tomb = next(x for x in listed if x['id'] == root['id'])
        assert tomb['deleted_at'] is not None and tomb['body'] == '' and tomb['mentions'] == []
        # child survives
        assert any(x['parent_id'] == root['id'] for x in listed)
        # tombstone cannot be edited or replied to
        assert (await c.patch(f"/api/v1/workos/comments/{root['id']}",
                              json={'body': 'zombie'})).status_code == 400
        assert (await c.post(f"/api/v1/workos/tasks/{t['id']}/comments",
                             json={'body': 'x', 'parent_id': root['id']})).status_code == 400


@pytest.mark.asyncio
async def test_delete_childless_hard_deletes(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        com = await _comment(c, t['id'], 'lonely')
        r = (await c.delete(f"/api/v1/workos/comments/{com['id']}")).json()
        assert r.get('deleted') is True and 'tombstoned' not in r
        listed = (await c.get(f"/api/v1/workos/tasks/{t['id']}/comments")).json()
        assert all(x['id'] != com['id'] for x in listed)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/Scripts/python.exe -m pytest open_webui/test/workos/test_router_threaded_comments.py -v`
Expected: FAIL — `parent_id` ignored (`child['parent_id']` KeyError) / delete returns plain `{'deleted': True}`.

- [ ] **Step 3: Implement router changes**

Import `Reactions` — extend the existing `from open_webui.models.workos import ...` block with `Reactions`.

`CommentForm` becomes:

```python
class CommentForm(BaseModel):
    body: str
    parent_id: Optional[str] = None  # create-only; ignored on PATCH
```

In `create_comment`, after the empty-body check and before `Comments.insert`:

```python
    parent = None
    if form.parent_id:
        parent = await Comments.get_by_id(form.parent_id, db=db)
        if not parent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Parent comment not found.')
        if parent.task_id != task_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail='Parent comment belongs to another task.')
        if parent.deleted_at:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail='Cannot reply to a deleted comment.')
```

Change the insert line to:

```python
    comment = await Comments.insert(task_id, user.id, body, mentions, parent_id=form.parent_id, db=db)
```

(The `parent` variable is used again in Task 4 for the `replied` notification — keep it in scope.)

In `update_comment`, right after the 404 check on `existing`:

```python
    if existing.deleted_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Comment was deleted.')
```

In `delete_comment`, replace the body after the capability check with:

```python
    if await Comments.has_children(comment_id, db=db):
        await Reactions.purge_for_comment(comment_id, db=db)
        tomb = await Comments.tombstone(comment_id, db=db)
        payload = {**tomb.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id}
        await _emit_task_room('workos:comment.updated', task, payload)
        return {'deleted': True, 'tombstoned': True}
    await Reactions.purge_for_comment(comment_id, db=db)
    deleted = await Comments.delete(comment_id, db=db)
    await _emit_task_room('workos:comment.deleted',
                          task, {'id': comment_id, 'task_id': task.id, 'workstream_id': task.workstream_id,
                                 'actor_id': user.id})
    return {'deleted': deleted}
```

Replace `list_comments`'s return with reaction aggregation:

```python
    items = await Comments.list_for_task(task_id, db=db)
    reactions = await Reactions.aggregate_for_comments([c.id for c in items], db=db)
    out = []
    for c in items:
        d = c.model_dump()
        d['reactions'] = reactions.get(c.id, [])
        out.append(d)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest open_webui/test/workos/test_router_threaded_comments.py open_webui/test/workos/test_router_comments.py -v`
Expected: all pass (old comment tests must stay green).

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_threaded_comments.py
git commit -m "feat(workos): threaded replies + tombstone delete on comment endpoints"
```

---

### Task 3: Router — reactions endpoint + realtime event

**Files:**
- Modify: `backend/open_webui/routers/workos.py` (add endpoint after `delete_comment`)
- Test: `backend/open_webui/test/workos/test_router_threaded_comments.py` (append)

**Interfaces:**
- Consumes: Task 1's `Reactions.toggle` / `aggregate_for_comments`; Task 2's tombstone state.
- Produces:
  - `POST /comments/{comment_id}/reactions` body `{'emoji': str}` → `{'added': bool, 'reactions': [{'emoji','count','user_ids'}]}`
  - Realtime event `workos:comment.reaction` payload `{'comment_id','task_id','workstream_id','reactions','actor_id'}` on the workstream room.
  - Module constant `REACTION_EMOJI` (the allowlist).

- [ ] **Step 1: Write the failing tests (append to test_router_threaded_comments.py)**

```python
@pytest.mark.asyncio
async def test_reaction_toggle_allowlist_and_list(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        com = await _comment(c, t['id'], 'react to me')
        r = await c.post(f"/api/v1/workos/comments/{com['id']}/reactions", json={'emoji': '👍'})
        assert r.status_code == 200, r.text
        assert r.json()['added'] is True
        assert r.json()['reactions'] == [{'emoji': '👍', 'count': 1, 'user_ids': ['u1']}]
        # toggle off
        r = await c.post(f"/api/v1/workos/comments/{com['id']}/reactions", json={'emoji': '👍'})
        assert r.json() == {'added': False, 'reactions': []}
        # allowlist
        r = await c.post(f"/api/v1/workos/comments/{com['id']}/reactions", json={'emoji': '🦖'})
        assert r.status_code == 400
        # unknown comment
        r = await c.post("/api/v1/workos/comments/nope/reactions", json={'emoji': '👍'})
        assert r.status_code == 404
        # reactions come back on GET
        await c.post(f"/api/v1/workos/comments/{com['id']}/reactions", json={'emoji': '🎉'})
        listed = (await c.get(f"/api/v1/workos/tasks/{t['id']}/comments")).json()
        got = next(x for x in listed if x['id'] == com['id'])
        assert got['reactions'] == [{'emoji': '🎉', 'count': 1, 'user_ids': ['u1']}]


@pytest.mark.asyncio
async def test_reaction_rejected_on_tombstone(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        root = await _comment(c, t['id'], 'root')
        await _comment(c, t['id'], 'child', parent_id=root['id'])
        await c.delete(f"/api/v1/workos/comments/{root['id']}")
        r = await c.post(f"/api/v1/workos/comments/{root['id']}/reactions", json={'emoji': '👍'})
        assert r.status_code == 400
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && .venv/Scripts/python.exe -m pytest open_webui/test/workos/test_router_threaded_comments.py -v -k reaction`
Expected: FAIL with 404/405 (endpoint missing).

- [ ] **Step 3: Implement the endpoint**

After `delete_comment` in `routers/workos.py`:

```python
REACTION_EMOJI = {'👍', '❤️', '🎉', '👀', '😂', '🚀'}


class ReactionForm(BaseModel):
    emoji: str


@router.post('/comments/{comment_id}/reactions')
async def toggle_reaction(
    request: Request, comment_id: str, form: ReactionForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    """Toggle the caller's emoji reaction. Any task-visible user may react — no
    capability entry (deliberate; reactions are lightweight, like viewing)."""
    await require_workos(request, user, db)
    existing = await Comments.get_by_id(comment_id, db=db)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Comment not found.')
    task, _ = await require_task_visible(user, existing.task_id, db)
    if form.emoji not in REACTION_EMOJI:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unsupported emoji.')
    if existing.deleted_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Comment was deleted.')
    added = await Reactions.toggle(comment_id, user.id, form.emoji, db=db)
    agg = await Reactions.aggregate_for_comments([comment_id], db=db)
    reactions = agg.get(comment_id, [])
    await _emit_task_room('workos:comment.reaction', task,
                          {'comment_id': comment_id, 'task_id': task.id,
                           'workstream_id': task.workstream_id, 'reactions': reactions,
                           'actor_id': user.id})
    return {'added': added, 'reactions': reactions}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest open_webui/test/workos/test_router_threaded_comments.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_threaded_comments.py
git commit -m "feat(workos): comment emoji reactions endpoint + realtime aggregate event"
```

---

### Task 4: Router — `replied` notification precedence + image-only comment attachments + access doc

**Files:**
- Modify: `backend/open_webui/routers/workos.py` (create_comment fan-out ~line 1031; upload_attachment ~line 1163)
- Modify: `docs/superpowers/specs/2026-06-26-workos-access-control.md`
- Test: `backend/open_webui/test/workos/test_router_threaded_comments.py` (append)

**Interfaces:**
- Consumes: Task 2's `parent` variable in `create_comment`; existing `notify()`, `_participants`, `can_see_workstream`, `is_app_admin`.
- Produces:
  - Notification type `'replied'` (own toggle key in `WORKOS_RULES.notifications`; `_notif_enabled` already defaults unknown keys to True — no config change needed).
  - Precedence per recipient: mentioned > replied > commented.
  - `POST /tasks/{id}/attachments` with `comment_id` → 400 unless `content_type` starts with `image/`.

- [ ] **Step 1: Write the failing tests (append)**

```python
@pytest.mark.asyncio
async def test_replied_notification_precedence(monkeypatch):
    sent = []

    async def _eu(event, payload, user_ids):
        sent.append((event, tuple(user_ids), payload.get('type')))

    monkeypatch.setattr(wr, 'emit_users', _eu)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        await c.post(f"/api/v1/workos/teams/{t['team_id']}/members", json={'user_id': 'u2', 'role': 'member'})
        root = await _comment(c, t['id'], 'root by u1')
    async with _client(monkeypatch, user=U2) as c:
        sent.clear()
        await _comment(c, t['id'], 'reply to u1', parent_id=root['id'])
    types_for_u1 = [ty for _e, ids, ty in sent if 'u1' in ids]
    assert 'replied' in types_for_u1          # parent author got replied…
    assert 'commented' not in types_for_u1    # …and not a duplicate commented
    assert all('u2' not in ids for _e, ids, _t in sent)  # actor never notified


@pytest.mark.asyncio
async def test_mention_beats_replied(monkeypatch):
    sent = []

    async def _eu(event, payload, user_ids):
        sent.append((event, tuple(user_ids), payload.get('type')))

    monkeypatch.setattr(wr, 'emit_users', _eu)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        await c.post(f"/api/v1/workos/teams/{t['team_id']}/members", json={'user_id': 'u2', 'role': 'member'})
        root = await _comment(c, t['id'], 'root by u1')
    async with _client(monkeypatch, user=U2) as c:
        sent.clear()
        await _comment(c, t['id'], 'ping @[A](mention:u1)', parent_id=root['id'])
    types_for_u1 = [ty for _e, ids, ty in sent if 'u1' in ids]
    assert types_for_u1 == ['mentioned']  # exactly one notification, the mention


@pytest.mark.asyncio
async def test_comment_attachment_must_be_image(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        com = await _comment(c, t['id'], 'has files')
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/attachments?comment_id={com['id']}",
                         files={'file': ('note.txt', b'hello', 'text/plain')})
        assert r.status_code == 400
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/attachments?comment_id={com['id']}",
                         files={'file': ('shot.png', b'\x89PNG fake', 'image/png')})
        assert r.status_code == 200, r.text
        # task-level upload (no comment_id) still takes non-images
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/attachments",
                         files={'file': ('note.txt', b'hello', 'text/plain')})
        assert r.status_code == 200, r.text
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && .venv/Scripts/python.exe -m pytest open_webui/test/workos/test_router_threaded_comments.py -v -k "replied or mention_beats or must_be_image"`
Expected: FAIL — no `replied` type emitted; txt upload with comment_id returns 200.

- [ ] **Step 3: Implement notification precedence**

In `create_comment`, replace the fan-out block (from `mentioned = set()` through the `commented` notify) with:

```python
    # Notification fan-out precedence: mentioned > replied > commented — one per recipient.
    mentioned = set()
    for m in mentions:
        if await can_see_workstream(m, await is_app_admin(m, db), task.workstream_id, db=db):
            mentioned.add(m)
    await notify(request, db, recipients=mentioned, actor=user, type='mentioned', task=task,
                 comment_id=comment.id, snippet=body)
    replied_to = set()
    if parent and parent.user_id and parent.user_id not in mentioned:
        replied_to = {parent.user_id}
        await notify(request, db, recipients=replied_to, actor=user, type='replied', task=task,
                     comment_id=comment.id, snippet=body)
    participants = await _participants(task, db) - mentioned - replied_to
    await notify(request, db, recipients=participants, actor=user, type='commented', task=task,
                 comment_id=comment.id, snippet=body)
```

(`notify()` already strips the actor and applies `can_see_workstream` per recipient — the `replied` set inherits both gates.)

- [ ] **Step 4: Implement the image-only rule**

In `upload_attachment`, inside the existing `if comment_id is not None:` block, after the comment/task check:

```python
        if not (file.content_type or '').startswith('image/'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail='Comment attachments must be images.')
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/Scripts/python.exe -m pytest open_webui/test/workos/test_router_threaded_comments.py open_webui/test/workos/test_router_comments.py open_webui/test/workos/test_router_attachments.py open_webui/test/workos/test_router_activity_notifications.py -v`
Expected: all pass.

- [ ] **Step 6: Update the access-control reference doc**

In `docs/superpowers/specs/2026-06-26-workos-access-control.md`:
- Comments/activity endpoint table: update the `POST /tasks/{id}/comments` row to mention `parent_id` validation (parent exists on the same task, not tombstoned) and the mentioned > replied > commented precedence; update `DELETE /comments/{id}` to note the tombstone fork; add a row for `POST /comments/{id}/reactions` (`require_workos` + fetch 404 + `require_task_visible` + allowlist; no capability entry; notifies nobody).
- Attachments row for `POST /tasks/{id}/attachments`: note the image-only rule when `comment_id` is set.
- §5 Channel A: add `workos:comment.reaction` to the room-event list; note tombstoning emits `comment.updated`.
- Notification-type list: add `replied` (own toggle key; recipient = parent comment author; visibility-gated like all types).

- [ ] **Step 7: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_threaded_comments.py docs/superpowers/specs/2026-06-26-workos-access-control.md
git commit -m "feat(workos): replied notification precedence + image-only comment attachments"
```

---

### Task 5: Frontend data layer — types, api, comment tree, store actions + realtime

**Files:**
- Modify: `src/lib/components/workos/lib/types.ts` (Comment ~line 92, NotificationType ~line 152)
- Modify: `src/lib/components/workos/lib/api.ts` (comments section ~line 132)
- Modify: `src/lib/components/workos/lib/store.ts` (postComment ~line 413, applyCollabEvent ~line 984, COLLAB_EVENTS ~line 1081)
- Create: `src/lib/components/workos/lib/commentTree.ts`
- Test: `src/lib/components/workos/lib/commentTree.test.ts`, additions to `src/lib/components/workos/lib/store.test.ts`

**Interfaces:**
- Consumes: backend shapes from Tasks 2–4.
- Produces:
  - `interface ReactionAggregate { emoji: string; count: number; user_ids: string[] }`
  - `Comment` gains `parent_id?: string | null; deleted_at?: number | null; reactions?: ReactionAggregate[]`
  - `NotificationType` includes `'replied'`
  - `api.createComment(token, taskId, { body, parent_id? })`, `api.toggleReaction(token, id, emoji) -> {added, reactions}`
  - `buildCommentTree(list, sort: 'newest'|'oldest') -> CommentNode[]` with `CommentNode { comment, children, depth }`; `countReplies(node) -> number`
  - `postComment(taskId, body, parentId?) -> Promise<Comment>`; `toggleReactionAction(commentId, emoji) -> Promise<void>`
  - `applyCollabEvent` handles `workos:comment.reaction`

- [ ] **Step 1: Write the failing tree test**

Create `src/lib/components/workos/lib/commentTree.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { buildCommentTree, countReplies } from './commentTree';
import type { Comment } from './types';

const c = (id: string, at: number, parent: string | null = null): Comment =>
	({ id, task_id: 't', user_id: 'u', body: id, mentions: [], parent_id: parent,
	   created_at: at, updated_at: at }) as Comment;

describe('buildCommentTree', () => {
	it('nests replies under parents, children always oldest-first', () => {
		const tree = buildCommentTree([c('a', 1), c('b', 2, 'a'), c('c', 3, 'a'), c('d', 4, 'b')], 'oldest');
		expect(tree.map((n) => n.comment.id)).toEqual(['a']);
		expect(tree[0].children.map((n) => n.comment.id)).toEqual(['b', 'c']);
		expect(tree[0].children[0].children[0].comment.id).toBe('d');
		expect(tree[0].children[0].children[0].depth).toBe(2);
	});

	it('sorts top-level per direction, replies stay ascending', () => {
		const list = [c('a', 1), c('b', 5), c('r2', 4, 'b'), c('r1', 3, 'b')];
		expect(buildCommentTree(list, 'newest').map((n) => n.comment.id)).toEqual(['b', 'a']);
		expect(buildCommentTree(list, 'oldest').map((n) => n.comment.id)).toEqual(['a', 'b']);
		const b = buildCommentTree(list, 'newest')[0];
		expect(b.children.map((n) => n.comment.id)).toEqual(['r1', 'r2']);
	});

	it('promotes orphans (parent hard-deleted before fetch) to top-level', () => {
		const tree = buildCommentTree([c('a', 1), c('orphan', 2, 'gone')], 'oldest');
		expect(tree.map((n) => n.comment.id)).toEqual(['a', 'orphan']);
		expect(tree[1].depth).toBe(0);
	});

	it('countReplies counts the whole subtree', () => {
		const tree = buildCommentTree([c('a', 1), c('b', 2, 'a'), c('d', 4, 'b'), c('e', 5, 'd')], 'oldest');
		expect(countReplies(tree[0])).toBe(3);
	});
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npm run test:frontend -- run src/lib/components/workos/lib/commentTree.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement types + tree**

`types.ts` — inside `Comment` after `mentions: string[];` add:

```ts
	parent_id?: string | null;
	deleted_at?: number | null;
	reactions?: ReactionAggregate[];
```

Above the `Comment` interface add:

```ts
export interface ReactionAggregate {
	emoji: string;
	count: number;
	user_ids: string[];
}
```

Change `NotificationType` to:

```ts
export type NotificationType =
	| 'assigned' | 'subtask_assigned' | 'mentioned' | 'replied' | 'commented' | 'status_changed';
```

Create `src/lib/components/workos/lib/commentTree.ts`:

```ts
// Pure comment-tree builder — leaf module (no store/api deps) so it stays unit-testable.
import type { Comment } from './types';

export interface CommentNode {
	comment: Comment;
	children: CommentNode[];
	depth: number;
}

export type CommentSort = 'newest' | 'oldest';

/** Build a render tree from the flat fetched list. Top-level order follows `sort`;
 * replies are always chronological (oldest first). Orphans — replies whose parent
 * was hard-deleted before this fetch — are promoted to top-level, not dropped. */
export function buildCommentTree(list: Comment[], sort: CommentSort): CommentNode[] {
	const byId = new Set(list.map((c) => c.id));
	const roots: Comment[] = [];
	const kids = new Map<string, Comment[]>();
	for (const c of list) {
		if (c.parent_id && byId.has(c.parent_id)) {
			const arr = kids.get(c.parent_id) ?? [];
			arr.push(c);
			kids.set(c.parent_id, arr);
		} else {
			roots.push(c);
		}
	}
	const asc = (a: Comment, b: Comment) => a.created_at - b.created_at;
	roots.sort(sort === 'newest' ? (a, b) => b.created_at - a.created_at : asc);
	const toNode = (c: Comment, depth: number): CommentNode => ({
		comment: c,
		depth,
		children: (kids.get(c.id) ?? []).sort(asc).map((k) => toNode(k, depth + 1))
	});
	return roots.map((c) => toNode(c, 0));
}

/** Total replies in a node's subtree (for the "N replies" collapse toggle). */
export function countReplies(node: CommentNode): number {
	return node.children.reduce((sum, k) => sum + 1 + countReplies(k), 0);
}
```

- [ ] **Step 4: Run tree tests**

Run: `npm run test:frontend -- run src/lib/components/workos/lib/commentTree.test.ts`
Expected: 4 passed.

- [ ] **Step 5: api + store changes**

`api.ts` — replace `createComment` and add `toggleReaction` after `deleteComment`:

```ts
export const createComment = (
	token: string, taskId: string, body: { body: string; parent_id?: string }
) => request<Comment>(token, `/tasks/${taskId}/comments`, 'POST', body);
export const toggleReaction = (token: string, id: string, emoji: string) =>
	request<{ added: boolean; reactions: ReactionAggregate[] }>(
		token, `/comments/${id}/reactions`, 'POST', { emoji }
	);
```

Add `ReactionAggregate` to the `types` import in api.ts.

`store.ts` — replace `postComment` with (now returns the saved comment so the composer can attach images to it):

```ts
export async function postComment(taskId: string, body: string, parentId?: string): Promise<Comment> {
	const saved = await api.createComment(token(), taskId, {
		body,
		...(parentId ? { parent_id: parentId } : {})
	});
	comments.update((list) => (list.some((c) => c.id === saved.id) ? list : [...list, saved]));
	void loadTaskDetail(taskId); // refresh activity (comment_added) too
	return saved;
}
```

Add after `deleteCommentAction`:

```ts
export async function toggleReactionAction(commentId: string, emoji: string): Promise<void> {
	const res = await api.toggleReaction(token(), commentId, emoji);
	comments.update((list) =>
		list.map((c) => (c.id === commentId ? { ...c, reactions: res.reactions } : c))
	);
}
```

(`Comment` must be in store.ts's type imports — add it if absent.)

In `applyCollabEvent`, after the `workos:comment.deleted` branch add:

```ts
	} else if (event === 'workos:comment.reaction') {
		comments.update((l) =>
			l.map((c) => (c.id === payload.comment_id ? { ...c, reactions: payload.reactions } : c))
		);
```

In `COLLAB_EVENTS` add `'workos:comment.reaction'` to the comment events line.

- [ ] **Step 6: Store tests (append to store.test.ts, matching its existing setup style)**

Find the existing `applyCollabEvent` describe block in `src/lib/components/workos/lib/store.test.ts` and add tests following the file's established fixtures (it already opens a selected task and seeds `comments`):

```ts
	it('comment.reaction event swaps the aggregate on the target comment', () => {
		selectedTaskId.set('t1');
		comments.set([{ id: 'c1', task_id: 't1', user_id: 'u1', body: 'x', mentions: [],
			created_at: 1, updated_at: 1, reactions: [] } as any]);
		applyCollabEvent('workos:comment.reaction', {
			task_id: 't1', comment_id: 'c1',
			reactions: [{ emoji: '👍', count: 2, user_ids: ['u1', 'u2'] }]
		});
		expect(get(comments)[0].reactions).toEqual([{ emoji: '👍', count: 2, user_ids: ['u1', 'u2'] }]);
	});

	it('tombstone arrives as comment.updated and merges deleted_at', () => {
		selectedTaskId.set('t1');
		comments.set([{ id: 'c1', task_id: 't1', user_id: 'u1', body: 'x', mentions: [],
			created_at: 1, updated_at: 1 } as any]);
		applyCollabEvent('workos:comment.updated', {
			id: 'c1', task_id: 't1', body: '', mentions: [], deleted_at: 99
		});
		expect(get(comments)[0].deleted_at).toBe(99);
		expect(get(comments)[0].body).toBe('');
	});
```

(Adjust imports/fixture names to match the file's existing conventions — it already imports `applyCollabEvent`, `comments`, `selectedTaskId`, `get`.)

- [ ] **Step 7: Run frontend suite**

Run: `npm run test:frontend -- run src/lib/components/workos`
Expected: all pass, including pre-existing store tests.

- [ ] **Step 8: Commit**

```bash
git add src/lib/components/workos/lib/types.ts src/lib/components/workos/lib/api.ts src/lib/components/workos/lib/store.ts src/lib/components/workos/lib/commentTree.ts src/lib/components/workos/lib/commentTree.test.ts src/lib/components/workos/lib/store.test.ts
git commit -m "feat(workos): frontend comment threading data layer (tree, reactions, realtime)"
```

---

### Task 6: Rich mention composer — serialization utils + RichComposer.svelte

**Files:**
- Create: `src/lib/components/workos/lib/richText.ts`
- Create: `src/lib/components/workos/views/detail/RichComposer.svelte`
- Modify: `src/lib/components/workos/ui/Icon.svelte` (add 4 icons)
- Test: `src/lib/components/workos/lib/richText.test.ts`

**Interfaces:**
- Consumes: `directory` store (`Record<string, {name: string}>`), `mentionToken` format, `avatarColors`.
- Produces:
  - `serializeEditor(root: HTMLElement): string` — DOM → body text with `@[Name](mention:ID)` tokens; DIV/P/BR → `\n`; trimmed.
  - `bodyToEditorHtml(body: string): string` — body text → HTML with chip spans (for edit mode).
  - `mentionChipHtml(id: string, name: string): string`
  - `RichComposer.svelte` props: `taskId: string`, `placeholder = 'Write a comment…'`, `compact = false`, `allowImages = true`, `initialBody = ''`, `submitLabel = 'Comment'`, `parentId: string | null = null`, `mode: 'create' | 'edit' = 'create'`, callbacks `onSubmitted: (() => void) | null`, `onCancel: (() => void) | null`, and for edit mode `commentId: string | null = null`.
  - Behavior: Enter submits, Shift+Enter newline, Esc calls `onCancel` with `stopPropagation`; `@` opens typeahead (filtered directory, ↑↓/Enter/Esc); create mode calls `postComment(taskId, body, parentId ?? undefined)` then `uploadFiles(taskId, pendingImages, saved.id)`; edit mode calls `editComment(commentId, body)`.
  - New Icon names: `'corner-up-left'` (reply), `'arrow-up-down'` (sort), `'smile-plus'` (add reaction), `'image'` (attach image).

- [ ] **Step 1: Write the failing serialization tests**

Create `src/lib/components/workos/lib/richText.test.ts`:

```ts
// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { bodyToEditorHtml, mentionChipHtml, serializeEditor } from './richText';

function editorWith(html: string): HTMLElement {
	const el = document.createElement('div');
	el.innerHTML = html;
	return el;
}

describe('serializeEditor', () => {
	it('serializes text and chips to the wire token format', () => {
		const el = editorWith(`hello ${mentionChipHtml('u1', 'Felwa')} world`);
		expect(serializeEditor(el)).toBe('hello @[Felwa](mention:u1) world');
	});

	it('turns BR and block elements into newlines', () => {
		const el = editorWith('line1<br>line2<div>line3</div>');
		expect(serializeEditor(el)).toBe('line1\nline2\nline3');
	});

	it('round-trips: bodyToEditorHtml then serializeEditor is identity', () => {
		const body = 'ping @[Noah Pierre](mention:u7) check\nsecond line';
		expect(serializeEditor(editorWith(bodyToEditorHtml(body)))).toBe(body);
	});

	it('escapes HTML in plain text (no injection through bodyToEditorHtml)', () => {
		const html = bodyToEditorHtml('<img src=x onerror=alert(1)>');
		expect(html).not.toContain('<img');
		const el = editorWith(html);
		expect(serializeEditor(el)).toBe('<img src=x onerror=alert(1)>');
	});
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npm run test:frontend -- run src/lib/components/workos/lib/richText.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `richText.ts`**

```ts
// Contenteditable <-> wire-format helpers for the comment composer. Pure DOM
// functions (no Svelte) so they unit-test under jsdom. Wire format is the
// existing mention token: @[Name](mention:ID) — see mentions.ts.

const TOKEN_RE = /@\[([^\]]*)\]\(mention:([^)\s]+)\)/g;

function escapeHtml(s: string): string {
	return s
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;');
}

/** Non-editable inline chip. data-mention-id/-name carry the token payload. */
export function mentionChipHtml(id: string, name: string): string {
	return (
		`<span contenteditable="false" data-mention-id="${escapeHtml(id)}"` +
		` data-mention-name="${escapeHtml(name)}"` +
		` class="wos-mention-chip">@${escapeHtml(name)}</span>`
	);
}

/** Body text -> editor HTML: tokens become chips, newlines become <br>, rest escaped. */
export function bodyToEditorHtml(body: string): string {
	let out = '';
	let last = 0;
	for (const m of (body ?? '').matchAll(TOKEN_RE)) {
		out += escapeHtml(body.slice(last, m.index)).replace(/\n/g, '<br>');
		out += mentionChipHtml(m[2], m[1]);
		last = (m.index ?? 0) + m[0].length;
	}
	out += escapeHtml(body.slice(last)).replace(/\n/g, '<br>');
	return out;
}

/** Editor DOM -> body text. Chips serialize to tokens; DIV/P boundaries and BR
 * become newlines. Result is trimmed. */
export function serializeEditor(root: HTMLElement): string {
	let out = '';
	const walk = (node: Node): void => {
		if (node.nodeType === Node.TEXT_NODE) {
			out += node.textContent ?? '';
			return;
		}
		if (node.nodeType !== Node.ELEMENT_NODE) return;
		const el = node as HTMLElement;
		const id = el.dataset?.mentionId;
		if (id) {
			out += `@[${el.dataset.mentionName ?? ''}](mention:${id})`;
			return;
		}
		if (el.tagName === 'BR') {
			out += '\n';
			return;
		}
		const block = el.tagName === 'DIV' || el.tagName === 'P';
		if (block && out.length && !out.endsWith('\n')) out += '\n';
		el.childNodes.forEach(walk);
	};
	root.childNodes.forEach(walk);
	return out.trim();
}
```

- [ ] **Step 4: Run to verify pass**

Run: `npm run test:frontend -- run src/lib/components/workos/lib/richText.test.ts`
Expected: 4 passed.

- [ ] **Step 5: Add icons**

In `ui/Icon.svelte`'s `LUCIDE` record add:

```ts
		'corner-up-left': '<polyline points="9 14 4 9 9 4"/><path d="M20 20v-7a4 4 0 0 0-4-4H4"/>',
		'arrow-up-down': '<path d="m21 16-4 4-4-4"/><path d="M17 20V4"/><path d="m3 8 4-4 4 4"/><path d="M7 4v16"/>',
		'smile-plus': '<path d="M22 11v1a10 10 0 1 1-9-10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" x2="9.01" y1="9" y2="9"/><line x1="15" x2="15.01" y1="9" y2="9"/><path d="M16 5h6"/><path d="M19 2v6"/>',
		image: '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>',
```

- [ ] **Step 6: Implement `RichComposer.svelte`**

Create `src/lib/components/workos/views/detail/RichComposer.svelte`:

```svelte
<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import { Button } from '$lib/components/ui/button';
	import { directory, postComment, editComment, uploadFiles } from '../../lib/store';
	import { avatarColors } from '../../lib/avatar';
	import { bodyToEditorHtml, mentionChipHtml, serializeEditor } from '../../lib/richText';

	export let taskId: string;
	export let placeholder = 'Write a comment…';
	export let compact = false;
	export let allowImages = true;
	export let initialBody = '';
	export let submitLabel = 'Comment';
	export let parentId: string | null = null;
	export let mode: 'create' | 'edit' = 'create';
	export let commentId: string | null = null;
	export let onSubmitted: (() => void) | null = null;
	export let onCancel: (() => void) | null = null;
	export let autofocus = false;

	let editor: HTMLDivElement;
	let fileInput: HTMLInputElement;
	let pending: File[] = [];
	let pendingUrls: string[] = [];
	let busy = false;
	let empty = !initialBody;

	// ── mention typeahead ──
	let taOpen = false;
	let taQuery = '';
	let taIndex = 0;
	let taRange: Range | null = null; // covers the "@query" text being replaced

	$: members = Object.entries($directory).map(([id, u]) => ({ id, name: u.name }));
	$: taMatches = members
		.filter((m) => m.name.toLowerCase().includes(taQuery.toLowerCase()))
		.slice(0, 6);
	$: if (taOpen && taIndex >= taMatches.length) taIndex = 0;

	export function focus(): void {
		editor?.focus();
	}

	function syncEmpty(): void {
		empty = !(editor?.textContent ?? '').trim() && !editor?.querySelector('[data-mention-id]');
	}

	/** Find an "@query" run ending at the caret; open/refresh the typeahead for it. */
	function detectMention(): void {
		const sel = window.getSelection();
		if (!sel || !sel.rangeCount || !sel.isCollapsed) return void (taOpen = false);
		const node = sel.anchorNode;
		if (!node || node.nodeType !== Node.TEXT_NODE || !editor.contains(node)) {
			taOpen = false;
			return;
		}
		const text = (node.textContent ?? '').slice(0, sel.anchorOffset);
		const at = text.lastIndexOf('@');
		// "@" must start the text or follow whitespace, and the query has no spaces.
		if (at === -1 || (at > 0 && !/\s/.test(text[at - 1])) || /\s/.test(text.slice(at + 1))) {
			taOpen = false;
			return;
		}
		taQuery = text.slice(at + 1);
		const r = document.createRange();
		r.setStart(node, at);
		r.setEnd(node, sel.anchorOffset);
		taRange = r;
		taIndex = 0;
		taOpen = true;
	}

	function pickMention(m: { id: string; name: string }): void {
		if (!taRange) return;
		taRange.deleteContents();
		const frag = document.createRange().createContextualFragment(mentionChipHtml(m.id, m.name) + ' ');
		const lastChild = frag.lastChild as ChildNode;
		taRange.insertNode(frag);
		// caret after the inserted space
		const sel = window.getSelection();
		if (sel && lastChild) {
			const r = document.createRange();
			r.setStartAfter(lastChild);
			r.collapse(true);
			sel.removeAllRanges();
			sel.addRange(r);
		}
		taOpen = false;
		taRange = null;
		syncEmpty();
		editor.focus();
	}

	function onKeydown(e: KeyboardEvent): void {
		if (taOpen) {
			if (e.key === 'ArrowDown') { e.preventDefault(); taIndex = (taIndex + 1) % Math.max(1, taMatches.length); return; }
			if (e.key === 'ArrowUp') { e.preventDefault(); taIndex = (taIndex - 1 + Math.max(1, taMatches.length)) % Math.max(1, taMatches.length); return; }
			if (e.key === 'Enter' && taMatches.length) { e.preventDefault(); pickMention(taMatches[taIndex]); return; }
			if (e.key === 'Escape') { e.stopPropagation(); taOpen = false; return; }
		}
		if (e.key === 'Escape' && onCancel) {
			e.stopPropagation(); // keep the task drawer open (subtask-panel lesson)
			onCancel();
			return;
		}
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			void submit();
		}
	}

	function onPaste(e: ClipboardEvent): void {
		e.preventDefault();
		const text = e.clipboardData?.getData('text/plain') ?? '';
		document.execCommand('insertText', false, text);
	}

	function onFiles(e: Event): void {
		const files = (e.target as HTMLInputElement).files;
		if (files) {
			for (const f of Array.from(files)) {
				if (!f.type.startsWith('image/')) continue;
				pending = [...pending, f];
				pendingUrls = [...pendingUrls, URL.createObjectURL(f)];
			}
		}
		(e.target as HTMLInputElement).value = '';
	}

	function removePending(i: number): void {
		URL.revokeObjectURL(pendingUrls[i]);
		pending = pending.filter((_, x) => x !== i);
		pendingUrls = pendingUrls.filter((_, x) => x !== i);
	}

	async function submit(): Promise<void> {
		const body = serializeEditor(editor);
		if ((!body && !pending.length) || busy) return;
		busy = true;
		try {
			if (mode === 'edit' && commentId) {
				await editComment(commentId, body);
			} else {
				const saved = await postComment(taskId, body || '…', parentId ?? undefined);
				if (pending.length) await uploadFiles(taskId, pending, saved.id);
			}
			editor.innerHTML = '';
			pendingUrls.forEach((u) => URL.revokeObjectURL(u));
			pending = [];
			pendingUrls = [];
			syncEmpty();
			onSubmitted?.();
		} finally {
			busy = false;
		}
	}

	import { onMount } from 'svelte';
	onMount(() => {
		if (initialBody) editor.innerHTML = bodyToEditorHtml(initialBody);
		syncEmpty();
		if (autofocus) editor.focus();
	});
</script>

<div class="relative">
	{#if taOpen && taMatches.length}
		<div class="absolute bottom-full left-0 z-20 mb-1.5 w-60 rounded-xl border border-gray-200 bg-white p-1 shadow-lg dark:border-gray-800 dark:bg-gray-900">
			{#each taMatches as m, i (m.id)}
				<button
					class="flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left {i === taIndex ? 'bg-primary/10' : 'hover:bg-gray-100 dark:hover:bg-gray-800'}"
					onmousedown={(e) => { e.preventDefault(); pickMention(m); }}
				>
					<span class="flex size-6 flex-none items-center justify-center rounded-full text-[10px] font-bold"
						style="background:{avatarColors(m.id).background};color:{avatarColors(m.id).foreground}">
						{m.name.slice(0, 2).toUpperCase()}
					</span>
					<span class="text-sm font-medium">{m.name}</span>
				</button>
			{/each}
		</div>
	{/if}

	<div class="rounded-xl border border-gray-200 bg-white transition-shadow focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/15 dark:border-gray-800 dark:bg-gray-950">
		<div
			bind:this={editor}
			contenteditable="true"
			role="textbox"
			aria-multiline="true"
			aria-label={placeholder}
			data-placeholder={placeholder}
			class="wos-composer-input max-h-48 overflow-y-auto px-3 py-2.5 text-sm leading-relaxed outline-none {compact ? 'min-h-9' : 'min-h-16'}"
			oninput={() => { syncEmpty(); detectMention(); }}
			onkeydown={onKeydown}
			onpaste={onPaste}
			onclick={detectMention}
		></div>

		{#if pending.length}
			<div class="flex gap-2 px-3 pb-2">
				{#each pendingUrls as url, i (url)}
					<span class="relative size-[52px] overflow-hidden rounded-lg border border-gray-200 dark:border-gray-800">
						<img src={url} alt="" class="size-full object-cover" />
						<button
							class="absolute right-0.5 top-0.5 flex size-4 items-center justify-center rounded-full bg-black/55 text-white"
							title="Remove image" onclick={() => removePending(i)}
						><Icon name="x" size={10} /></button>
					</span>
				{/each}
			</div>
		{/if}

		<div class="flex items-center gap-1 border-t border-gray-100 px-2 py-1.5 dark:border-gray-900">
			{#if allowImages}
				<Button variant="ghost" size="icon-sm" class="text-gray-400" title="Attach image"
					onclick={() => fileInput.click()}><Icon name="image" size={15} /></Button>
				<input type="file" accept="image/*" multiple class="hidden" bind:this={fileInput} onchange={onFiles} />
			{/if}
			<span class="ml-1 hidden text-[11px] text-gray-400 sm:block">
				Enter to send · Shift+Enter for new line · @ to mention
			</span>
			<div class="flex-1"></div>
			{#if onCancel}
				<Button variant="ghost" size="sm" onclick={() => onCancel?.()}>Cancel</Button>
			{/if}
			<Button size="sm" disabled={empty && !pending.length} onclick={() => void submit()}>
				{busy ? '…' : submitLabel}
			</Button>
		</div>
	</div>
</div>

<style>
	.wos-composer-input:empty::before {
		content: attr(data-placeholder);
		color: rgb(156 163 175);
		pointer-events: none;
	}
	:global(.wos-mention-chip) {
		display: inline;
		border-radius: 6px;
		padding: 0 4px;
		font-weight: 600;
		color: var(--primary);
		background: color-mix(in srgb, var(--primary) 10%, transparent);
		white-space: nowrap;
	}
</style>
```

Note: typeahead anchors to the composer top edge (`bottom-full`) rather than the exact caret rect — the spec allows this fallback and it is robust in the narrow drawer/mobile.

- [ ] **Step 7: Type-check**

Run: `npm run check 2>&1 | tail -20`
Expected: no NEW errors in workos files (the repo may have pre-existing unrelated warnings — compare against `git stash`-free baseline if unsure).

- [ ] **Step 8: Commit**

```bash
git add src/lib/components/workos/lib/richText.ts src/lib/components/workos/lib/richText.test.ts src/lib/components/workos/views/detail/RichComposer.svelte src/lib/components/workos/ui/Icon.svelte
git commit -m "feat(workos): rich mention composer with chips, caret typeahead, pending images"
```

---

### Task 7: Comment rendering — mentions upgrade, agoLong, CommentItem rewrite, CommentThread, ImageLightbox

**Files:**
- Modify: `src/lib/components/workos/lib/mentions.ts` (renderMentions), `src/lib/components/workos/lib/inboxFormat.ts` (add agoLong)
- Rewrite: `src/lib/components/workos/views/detail/CommentItem.svelte`
- Create: `src/lib/components/workos/views/detail/CommentThread.svelte`, `src/lib/components/workos/views/detail/ImageLightbox.svelte`
- Test: `src/lib/components/workos/lib/mentions.test.ts` (update expectations)

**Interfaces:**
- Consumes: Task 5 (`toggleReactionAction`, `ReactionAggregate`, `CommentNode`, `countReplies`), Task 6 (`RichComposer`), existing `attachments` store, `attachmentUrl(id)`, `displayName`, `avatarColors`, `canDeleteComment`.
- Produces:
  - `renderMentions(body, name)` now maps tokens to `[@Name](#mention-ID)` markdown links (styled as chips via CSS; DOMPurify-safe because the href is a fragment).
  - `agoLong(ts, now?) -> string` ("just now", "58 minutes ago", "2 hours ago", "3 days ago", then short date).
  - `CommentItem.svelte` props: `node: CommentNode`, `taskId: string`, `teamId: string | null`, `highlight = false`, `replyToName: string | null = null`, callback `onReply: (commentId: string) => void`.
  - `CommentThread.svelte` props: `node: CommentNode`, `taskId`, `teamId`, `highlightId: string | null`, `replyingToId: string | null`, `onReply`, `onCloseReply: () => void`. Recursive (imports itself); indent cap depth ≥ 3; collapse toggle.
  - `ImageLightbox.svelte` props: `src: string`, `alt: string`, `onClose: () => void`.

- [ ] **Step 1: Update mentions test expectations (failing first)**

In `src/lib/components/workos/lib/mentions.test.ts`, update the `renderMentions` assertions to the new link format:

```ts
	it('renders tokens as fragment mention links', () => {
		const out = renderMentions('hi @[Felwa](mention:u1)!', () => 'Felwa');
		expect(out).toBe('hi [@Felwa](#mention-u1)!');
	});
```

(Replace the existing bold-format expectation; keep other tests intact.)

Run: `npm run test:frontend -- run src/lib/components/workos/lib/mentions.test.ts`
Expected: FAIL (still emits `**@Felwa**`).

- [ ] **Step 2: Implement renderMentions + agoLong**

`mentions.ts` — replace `renderMentions`:

```ts
/** Replace mention tokens with fragment links (`[@Name](#mention-ID)`) for markdown
 * rendering. Fragment hrefs survive DOMPurify; CommentItem styles/intercepts them. */
export function renderMentions(body: string, name: (id: string) => string): string {
	return (body ?? '').replace(MENTION_RE, (_full, id) => `[@${name(id)}](#mention-${id})`);
}
```

`inboxFormat.ts` — add next to `agoShort`:

```ts
/** Long-form relative time for comment headers: "just now", "58 minutes ago",
 * "2 hours ago", "3 days ago"; older than a week falls back to a short date. */
export function agoLong(ts: number, now: number = Date.now()): string {
	const s = Math.max(0, Math.floor((now - ts) / 1000));
	if (s < 60) return 'just now';
	const m = Math.floor(s / 60);
	if (m < 60) return `${m} minute${m === 1 ? '' : 's'} ago`;
	const h = Math.floor(m / 60);
	if (h < 24) return `${h} hour${h === 1 ? '' : 's'} ago`;
	const d = Math.floor(h / 24);
	if (d < 7) return `${d} day${d === 1 ? '' : 's'} ago`;
	return new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}
```

Run: `npm run test:frontend -- run src/lib/components/workos/lib/mentions.test.ts` — Expected: pass.

- [ ] **Step 3: Create `ImageLightbox.svelte`**

```svelte
<script lang="ts">
	export let src: string;
	export let alt = '';
	export let onClose: () => void;

	function onKeydown(e: KeyboardEvent): void {
		if (e.key === 'Escape') {
			e.stopPropagation(); // keep the task drawer open
			onClose();
		}
	}
</script>

<svelte:window on:keydown|capture={onKeydown} />

<!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
<div
	class="fixed inset-0 z-[100] flex items-center justify-center bg-black/75 p-6"
	onclick={(e) => { e.stopPropagation(); onClose(); }}
	role="dialog" aria-modal="true" aria-label={alt || 'Image preview'}
>
	<img
		{src} {alt}
		class="max-h-full max-w-full rounded-xl object-contain shadow-2xl"
		onclick={(e) => e.stopPropagation()}
	/>
	<button
		class="absolute right-4 top-4 flex size-9 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20"
		title="Close" onclick={(e) => { e.stopPropagation(); onClose(); }}
	>✕</button>
</div>
```

- [ ] **Step 4: Rewrite `CommentItem.svelte`**

```svelte
<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import Markdown from '$lib/components/chat/Messages/Markdown.svelte';
	import { Button } from '$lib/components/ui/button';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { user } from '$lib/stores';
	import {
		displayName, deleteCommentAction, toggleReactionAction, roles, currentTeam, attachments
	} from '../../lib/store';
	import { renderMentions } from '../../lib/mentions';
	import { agoLong } from '../../lib/inboxFormat';
	import { avatarColors } from '../../lib/avatar';
	import { canDeleteComment } from '../../lib/roles';
	import { attachmentUrl } from '../../lib/api';
	import type { CommentNode } from '../../lib/commentTree';
	import RichComposer from './RichComposer.svelte';
	import ImageLightbox from './ImageLightbox.svelte';

	export let node: CommentNode;
	export let taskId: string;
	export let teamId: string | null = null;
	export let highlight = false;
	export let replyToName: string | null = null;
	export let onReply: (commentId: string) => void;

	const EMOJI = ['👍', '❤️', '🎉', '👀', '😂', '🚀'];

	$: comment = node.comment;
	$: tombstoned = !!comment.deleted_at;
	$: myRole = teamId ? $roles[teamId] : $currentTeam ? $roles[$currentTeam.id] : undefined;
	$: rendered = renderMentions(comment.body, displayName);
	$: mine = comment.user_id === ($user?.id ?? '');
	$: colors = avatarColors(comment.user_id);
	$: initials = displayName(comment.user_id).slice(0, 2).toUpperCase();
	$: images = $attachments.filter(
		(a) => a.comment_id === comment.id && (a.content_type ?? '').startsWith('image/')
	);
	$: reactions = comment.reactions ?? [];
	$: myId = $user?.id ?? '';

	let rootEl: HTMLElement | null = null;
	$: if (highlight && rootEl) rootEl.scrollIntoView({ block: 'center', behavior: 'smooth' });

	let editing = false;
	let pickerOpen = false;
	let lightboxSrc: string | null = null;
	let lightboxAlt = '';

	function interceptMentionClick(e: MouseEvent): void {
		const a = (e.target as HTMLElement).closest?.('a[href^="#mention-"]');
		if (a) e.preventDefault(); // mention chips are labels, not links
	}
</script>

<div bind:this={rootEl}
	class="group flex gap-2.5 py-2.5 {highlight ? 'rounded-lg bg-primary/5 px-2 ring-1 ring-primary/20' : ''}">
	<span class="flex flex-none items-center justify-center rounded-full font-bold {node.depth === 0 ? 'size-8 text-[12px]' : 'size-[26px] text-[10px]'}"
		style="background:{tombstoned ? 'rgb(156 163 175)' : colors.background};color:{tombstoned ? '#fff' : colors.foreground}">
		{tombstoned ? '?' : initials}
	</span>

	<div class="min-w-0 flex-1">
		{#if replyToName}
			<span class="mb-0.5 inline-flex items-center gap-1 rounded-md bg-primary/10 px-1.5 py-px text-[11px] font-medium text-primary">
				<Icon name="corner-up-left" size={11} /> replying to @{replyToName}
			</span>
		{/if}

		{#if tombstoned}
			<div class="flex items-baseline gap-2">
				<span class="text-[13px] font-semibold text-gray-400">Comment deleted</span>
				<span class="text-[11px] tabular-nums text-gray-400">{agoLong(comment.created_at)}</span>
			</div>
			<div class="mt-1 rounded-lg bg-gray-100 px-2.5 py-1.5 text-[13px] italic text-gray-400 dark:bg-gray-900">
				This comment was deleted.
			</div>
		{:else}
			<div class="flex items-baseline gap-2">
				<span class="text-[13.5px] font-semibold">{displayName(comment.user_id)}</span>
				<span class="text-[11px] tabular-nums text-gray-400">{agoLong(comment.created_at)}</span>
				{#if comment.edited_at}<span class="text-[10.5px] italic text-gray-400">(edited)</span>{/if}
			</div>

			{#if editing}
				<div class="mt-1">
					<RichComposer
						{taskId} mode="edit" commentId={comment.id} compact allowImages={false}
						initialBody={comment.body} submitLabel="Save" autofocus
						onSubmitted={() => (editing = false)} onCancel={() => (editing = false)}
					/>
				</div>
			{:else}
				<!-- svelte-ignore a11y-click-events-have-key-events a11y-no-static-element-interactions -->
				<div class="wos-comment-prose prose prose-sm mt-0.5 max-w-none text-[13.5px] dark:prose-invert"
					onclick={interceptMentionClick}>
					<Markdown id={comment.id} content={rendered} />
				</div>

				{#if images.length}
					<div class="mt-1.5 flex flex-wrap gap-2">
						{#each images as img (img.id)}
							<button
								class="h-[68px] w-24 overflow-hidden rounded-lg border border-gray-200 dark:border-gray-800"
								title="Click to expand"
								onclick={() => { lightboxSrc = attachmentUrl(img.id); lightboxAlt = img.name; }}
							>
								<img src={attachmentUrl(img.id)} alt={img.name} class="size-full cursor-zoom-in object-cover" />
							</button>
						{/each}
					</div>
				{/if}

				<div class="mt-1.5 flex items-center gap-1.5">
					{#each reactions as r (r.emoji)}
						<button
							class="flex items-center gap-1 rounded-full border px-2 py-px text-[12px] transition-colors
								{r.user_ids.includes(myId)
									? 'border-primary bg-primary/10 font-semibold text-primary'
									: 'border-gray-200 hover:border-gray-300 dark:border-gray-800 dark:hover:border-gray-700'}"
							title={r.user_ids.map((id) => displayName(id)).join(', ')}
							onclick={() => void toggleReactionAction(comment.id, r.emoji)}
						>{r.emoji} {r.count}</button>
					{/each}

					<div class="relative">
						<button
							class="flex items-center rounded-full border border-dashed border-gray-200 px-1.5 py-px text-gray-400 hover:border-gray-300 hover:text-gray-500 dark:border-gray-800"
							title="Add reaction" onclick={() => (pickerOpen = !pickerOpen)}
						><Icon name="smile-plus" size={13} /></button>
						{#if pickerOpen}
							<div class="absolute bottom-6 left-0 z-10 flex gap-0.5 rounded-full border border-gray-200 bg-white px-1.5 py-1 shadow-lg dark:border-gray-800 dark:bg-gray-900">
								{#each EMOJI as e (e)}
									<button class="rounded-md px-1 text-[15px] hover:bg-gray-100 dark:hover:bg-gray-800"
										onclick={() => { pickerOpen = false; void toggleReactionAction(comment.id, e); }}
									>{e}</button>
								{/each}
							</div>
						{/if}
					</div>

					<button class="rounded-md px-1.5 py-px text-[12px] font-semibold text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
						onclick={() => onReply(comment.id)}>Reply</button>

					<div class="flex-1"></div>

					{#if mine || canDeleteComment(comment, myId, myRole)}
						<DropdownMenu.Root>
							<DropdownMenu.Trigger>
								<Button variant="ghost" size="icon-xs"
									class="text-gray-400 opacity-0 group-hover:opacity-100 data-[state=open]:opacity-100">
									<Icon name="more-horizontal" size={14} />
								</Button>
							</DropdownMenu.Trigger>
							<DropdownMenu.Content align="end">
								{#if mine}
									<DropdownMenu.Item onclick={() => (editing = true)}>
										<Icon name="pencil" size={13} /> Edit
									</DropdownMenu.Item>
								{/if}
								{#if canDeleteComment(comment, myId, myRole)}
									<DropdownMenu.Item class="text-red-600" onclick={() => void deleteCommentAction(comment.id)}>
										<Icon name="trash" size={13} /> Delete
									</DropdownMenu.Item>
								{/if}
							</DropdownMenu.Content>
						</DropdownMenu.Root>
					{/if}
				</div>
			{/if}
		{/if}
	</div>
</div>

{#if lightboxSrc}
	<ImageLightbox src={lightboxSrc} alt={lightboxAlt} onClose={() => (lightboxSrc = null)} />
{/if}

<style>
	:global(.wos-comment-prose a[href^='#mention-']) {
		color: var(--primary);
		background: color-mix(in srgb, var(--primary) 10%, transparent);
		border-radius: 6px;
		padding: 0 4px;
		font-weight: 600;
		text-decoration: none;
	}
</style>
```

Note on tombstone delete semantics for the store: `deleteCommentAction` optimistically removes the row; for a tombstoned delete the server emits `workos:comment.updated` which re-adds nothing (updates a missing row is a no-op in `applyCollabEvent`'s map). Fix in the same step — make `deleteCommentAction` NOT optimistic anymore, relying on the response:

In `store.ts`, replace `deleteCommentAction`:

```ts
export async function deleteCommentAction(id: string): Promise<void> {
	const res = await api.deleteComment(token(), id);
	if ((res as any).tombstoned) {
		// Server soft-deleted: refetch swaps in the tombstone (realtime also emits comment.updated).
		const open = get(selectedTaskId);
		if (open) void loadTaskDetail(open);
	} else {
		comments.update((list) => list.filter((c) => c.id !== id));
	}
}
```

And in `api.ts` update the deleteComment return type:

```ts
export const deleteComment = (token: string, id: string) =>
	request<{ deleted: boolean; tombstoned?: boolean }>(token, `/comments/${id}`, 'DELETE');
```

- [ ] **Step 5: Create `CommentThread.svelte` (recursive)**

```svelte
<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import CommentItem from './CommentItem.svelte';
	import RichComposer from './RichComposer.svelte';
	import { displayName } from '../../lib/store';
	import { countReplies, type CommentNode } from '../../lib/commentTree';

	export let node: CommentNode;
	export let taskId: string;
	export let teamId: string | null = null;
	export let highlightId: string | null = null;
	export let replyingToId: string | null = null;
	export let onReply: (commentId: string) => void;
	export let onCloseReply: () => void;

	// Visual indent cap: depth 0-2 indent with rails; deeper children stay flat
	// with a "replying to" chip on each reply (see CommentItem replyToName).
	const INDENT_CAP = 3;

	let collapsed = false;
	$: replies = countReplies(node);
	$: indentKids = node.depth < INDENT_CAP - 1;
</script>

<CommentItem
	{node} {taskId} {teamId}
	highlight={node.comment.id === highlightId}
	replyToName={node.depth >= INDENT_CAP ? displayName(node.comment.parent_id ?? '') : null}
	{onReply}
/>

{#if replyingToId === node.comment.id}
	<div class={indentKids ? 'ml-[15px] border-l-2 border-transparent pl-5' : ''}>
		<RichComposer
			{taskId} parentId={node.comment.id} compact autofocus
			placeholder="Write a reply…" submitLabel="Reply"
			onSubmitted={onCloseReply} onCancel={onCloseReply}
		/>
	</div>
{/if}

{#if node.children.length}
	<button
		class="ml-[42px] flex items-center gap-1.5 py-0.5 text-[12px] font-semibold text-primary"
		onclick={() => (collapsed = !collapsed)}
	>
		<Icon name={collapsed ? 'chevron-right' : 'chevron-down'} size={13} />
		{replies} {replies === 1 ? 'reply' : 'replies'}
	</button>
	{#if !collapsed}
		<div class={indentKids ? 'ml-[15px] border-l-2 border-gray-200 pl-5 @max-[880px]:ml-2 @max-[880px]:pl-3 dark:border-gray-800' : ''}>
			{#each node.children as child (child.comment.id)}
				<svelte:self
					node={child} {taskId} {teamId} {highlightId} {replyingToId} {onReply} {onCloseReply}
				/>
			{/each}
		</div>
	{/if}
{/if}
```

Note: `replyToName` resolves the parent author via `displayName(parent_id's comment.user_id)` — but `parent_id` is a comment id, not a user id. Fix: `CommentThread` passes the parent *author name* down instead. Replace the `<CommentItem ...>` block's `replyToName` with a prop computed by the parent invocation: add `export let parentAuthorName: string | null = null;` to CommentThread, pass `replyToName={node.depth >= INDENT_CAP ? parentAuthorName : null}` to CommentItem, and in the recursive `<svelte:self>` call pass `parentAuthorName={displayName(node.comment.user_id)}`. (The top-level caller in Task 8 omits it → null.)

- [ ] **Step 6: Type-check**

Run: `npm run check 2>&1 | tail -20`
Expected: no new workos errors. (CommentsPanel does not exist yet; CommentThread/CommentItem compile standalone.)

- [ ] **Step 7: Run frontend tests**

Run: `npm run test:frontend -- run src/lib/components/workos`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/lib/components/workos/lib/mentions.ts src/lib/components/workos/lib/mentions.test.ts src/lib/components/workos/lib/inboxFormat.ts src/lib/components/workos/lib/store.ts src/lib/components/workos/lib/api.ts src/lib/components/workos/views/detail/CommentItem.svelte src/lib/components/workos/views/detail/CommentThread.svelte src/lib/components/workos/views/detail/ImageLightbox.svelte
git commit -m "feat(workos): threaded comment cards — reactions, tombstones, image lightbox, mention chips"
```

---

### Task 8: CommentsPanel — header, sort, show-more, composer + TaskDetailBody integration

**Files:**
- Create: `src/lib/components/workos/views/detail/CommentsPanel.svelte`
- Modify: `src/lib/components/workos/views/detail/TaskDetailBody.svelte` (comments tab ~lines 543–549; imports ~lines 11–12)
- Delete: `src/lib/components/workos/views/detail/CommentComposer.svelte`

**Interfaces:**
- Consumes: Tasks 5–7 (`buildCommentTree`, `CommentThread`, `RichComposer`, `comments`/`highlightCommentId` stores).
- Produces: `CommentsPanel.svelte` props `taskId: string`, `teamId: string | null` — the entire Comments tab content (list + composer).

- [ ] **Step 1: Create `CommentsPanel.svelte`**

```svelte
<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import { Badge } from '$lib/components/ui/badge';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import CommentThread from './CommentThread.svelte';
	import RichComposer from './RichComposer.svelte';
	import { comments, highlightCommentId } from '../../lib/store';
	import { buildCommentTree, type CommentSort } from '../../lib/commentTree';

	export let taskId: string;
	export let teamId: string | null = null;

	const PAGE = 10;
	let sort: CommentSort = 'newest';
	let shown = PAGE;
	let replyingToId: string | null = null;

	$: tree = buildCommentTree($comments, sort);
	$: visible = tree.slice(0, shown);
	$: hidden = tree.length - visible.length;

	// When a highlighted (deep-linked) comment sits beyond the pagination window
	// or in a hidden subtree, reveal everything so scrollIntoView can find it.
	$: if ($highlightCommentId && tree.length > shown) shown = tree.length;
</script>

<div class="pt-3">
	<div class="mb-1.5 flex items-center gap-2">
		<h3 class="text-[15px] font-bold">Comments</h3>
		{#if $comments.length}
			<Badge class="bg-primary px-2 py-0 text-white hover:bg-primary">{$comments.length}</Badge>
		{/if}
		<div class="flex-1"></div>
		<DropdownMenu.Root>
			<DropdownMenu.Trigger
				class="flex items-center gap-1 rounded-lg border border-gray-200 px-2.5 py-1 text-[12.5px] text-gray-500 hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-900">
				<Icon name="arrow-up-down" size={12} />
				{sort === 'newest' ? 'Most recent' : 'Oldest first'}
				<Icon name="chevron-down" size={12} />
			</DropdownMenu.Trigger>
			<DropdownMenu.Content align="end">
				<DropdownMenu.Item onclick={() => (sort = 'newest')}>Most recent</DropdownMenu.Item>
				<DropdownMenu.Item onclick={() => (sort = 'oldest')}>Oldest first</DropdownMenu.Item>
			</DropdownMenu.Content>
		</DropdownMenu.Root>
	</div>

	{#if !tree.length}
		<p class="py-6 text-center text-[13px] text-gray-400">No comments yet — start the conversation.</p>
	{/if}

	{#each visible as node (node.comment.id)}
		<CommentThread
			{node} {taskId} {teamId}
			highlightId={$highlightCommentId}
			{replyingToId}
			onReply={(id) => (replyingToId = replyingToId === id ? null : id)}
			onCloseReply={() => (replyingToId = null)}
		/>
	{/each}

	{#if hidden > 0}
		<button
			class="mx-auto block py-2 text-[12.5px] font-bold text-primary hover:underline"
			onclick={() => (shown += PAGE)}
		>Show {Math.min(hidden, PAGE)} more ↓</button>
	{/if}

	<div class="mt-3 border-t border-gray-200 pt-3 dark:border-gray-800">
		<RichComposer {taskId} />
	</div>
</div>
```

- [ ] **Step 2: Wire into `TaskDetailBody.svelte`**

Replace the imports (lines ~11–12):

```ts
	import CommentsPanel from './CommentsPanel.svelte';
```

(drop the `CommentItem` and `CommentComposer` imports; `sortedComments` stays only for the tab badge count — simplify it to `$: commentCount = $comments.length;` and use `commentCount` in the Tabs.Trigger badge.)

Replace the comments Tabs.Content block:

```svelte
						<Tabs.Content value="comments">
							<div class="@max-[880px]:pb-[env(safe-area-inset-bottom)]">
								<CommentsPanel taskId={t.id} teamId={t.team_id} />
							</div>
						</Tabs.Content>
```

(The old sticky-composer wrapper goes away — the composer now lives inside the panel; keep the mobile safe-area padding.)

Delete `src/lib/components/workos/views/detail/CommentComposer.svelte` (`git rm`).
Check nothing else imports it: `grep -r "CommentComposer" src/` must return nothing.

- [ ] **Step 3: Type-check + tests**

Run: `npm run check 2>&1 | tail -20` — no new workos errors.
Run: `npm run test:frontend -- run src/lib/components/workos` — all pass.

- [ ] **Step 4: Commit**

```bash
git add -A src/lib/components/workos/views/detail
git commit -m "feat(workos): CommentsPanel — sort, count, show-more, threaded rendering"
```

---

### Task 9: Inbox + admin — `replied` notification type end-to-end

**Files:**
- Modify: `src/lib/components/workos/lib/inbox.ts` (isNeedsYou ~line 21), `views/inbox/TypeGlyph.svelte`, `views/inbox/FeedRow.svelte` (VERB ~line 22), `views/admin/RulesTab.svelte` (~line 73)
- Test: `src/lib/components/workos/lib/inbox.test.ts` (append)

**Interfaces:**
- Consumes: Task 5's `NotificationType` including `'replied'`.
- Produces: `replied` renders in inbox (needs-you bucket, `corner-up-left` glyph in primary hue, verb "replied to your comment on") and is toggleable in admin Rules.

- [ ] **Step 1: Failing test (append to inbox.test.ts, matching its fixture style)**

```ts
	it('replied notifications are needs-you when unread', () => {
		const n = { id: 'r1', user_id: 'me', type: 'replied', read: false, archived: false,
			data: {}, created_at: 1 } as any;
		expect(isNeedsYou(n)).toBe(true);
		expect(isNeedsYou({ ...n, read: true })).toBe(false);
	});
```

(If `isNeedsYou` is not exported, assert through the file's existing split/bucket helper the same way neighboring tests do.)

Run: `npm run test:frontend -- run src/lib/components/workos/lib/inbox.test.ts` — Expected: FAIL.

- [ ] **Step 2: Implement**

`inbox.ts` line ~21:

```ts
	return !n.read && (n.type === 'mentioned' || n.type === 'replied' || n.type === 'assigned' || n.type === 'subtask_assigned');
```

`TypeGlyph.svelte` — add to `ICON`:

```ts
		replied: 'corner-up-left',
```

and to `STYLE` (primary hue, same as mentioned):

```ts
		replied: `color:var(--primary);background:${tint('var(--primary)')}`,
```

`FeedRow.svelte` VERB record — add:

```ts
		replied: 'replied to your comment on',
```

`RulesTab.svelte` line ~73 — extend the list:

```ts
		{#each ['assigned', 'mentioned', 'replied', 'commented', 'status_changed'] as cat (cat)}
```

- [ ] **Step 3: Run tests + check**

Run: `npm run test:frontend -- run src/lib/components/workos` — all pass.
Run: `npm run check 2>&1 | tail -20` — no new errors (NotificationCounts `by_type` is `Record<NotificationType, number>` — adding the union member is compile-safe because the backend counts endpoint seeds all types; if `check` flags a missing key in a test fixture, add `replied: 0` to that fixture).

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/lib/inbox.ts src/lib/components/workos/lib/inbox.test.ts src/lib/components/workos/views/inbox/TypeGlyph.svelte src/lib/components/workos/views/inbox/FeedRow.svelte src/lib/components/workos/views/admin/RulesTab.svelte
git commit -m "feat(workos): replied notification type in inbox + admin rules"
```

---

### Task 10: Full verification + browser smoke

**Files:**
- No new code (fixes only if verification fails).

- [ ] **Step 1: Full backend suite**

Run: `cd backend && .venv/Scripts/python.exe -m pytest open_webui/test/workos -v`
Expected: all pass (including pre-existing suites — comments, attachments, notifications, capability matrix).

- [ ] **Step 2: Full frontend suite + type-check**

Run: `npm run test:frontend -- run src/lib/components/workos`
Run: `npm run check 2>&1 | tail -30`
Expected: all tests pass; no new check errors vs. the branch baseline.

- [ ] **Step 3: Apply the migration in the running container**

The Docker container (`osool-ai-open-webui-1`) must be restarted so alembic applies `c2d3e4f5a6b7` on boot. **Ask the user before restarting** — then:

```bash
docker restart osool-ai-open-webui-1
```

Verify with: `docker logs osool-ai-open-webui-1 --tail 50` — look for the alembic upgrade line and no startup errors.

- [ ] **Step 4: Browser smoke checklist (manual, in-app browser; frontend edits are live via the user's Vite hot-reload server — do NOT start one)**

1. Post a top-level comment; reply; reply-to-reply; reply 4 deep — depth-4 shows `↳ replying to @Name` chip at capped indent.
2. Collapse/expand a thread — count label correct.
3. Sort toggle: Most recent ↔ Oldest first (top-level only; replies stay chronological).
4. 11+ top-level comments → "Show more" appears and pages.
5. `@` typeahead: keyboard-only (↑↓, Enter), chip inserted, single backspace removes chip; sent comment renders the mention as a primary-colored chip.
6. React with two emojis; toggle one off; second account's reaction updates live (realtime).
7. Second account replies → first account gets `replied` inbox row (glyph + verb) and needs-you placement.
8. Delete a comment with replies → tombstone appears live, replies intact, no Reply/reactions on it. Delete a childless comment → row disappears.
9. Attach an image in the composer → pending chip with ✕ → send → thumbnail in comment → click → lightbox → Esc closes lightbox only (drawer stays open).
10. Try attaching a .txt via composer file picker (should be filtered client-side; API returns 400 if forced).
11. Edit own comment with the rich composer (chips preserved).
12. Dark mode pass over all of the above.
13. Mobile width (<880px): rails narrowed, composer usable, typeahead visible.

- [ ] **Step 5: Update memory + finish**

Update `workos-*` memory (new memory file for threaded comments: BUILT status, migration id `c2d3e4f5a6b7`, container-restart requirement, smoke state). Then use superpowers:finishing-a-development-branch.

---

## Self-Review Notes (resolved during planning)

- `deleteCommentAction` optimistic removal conflicted with tombstoning → rewritten non-optimistic in Task 7 Step 4.
- `replyToName` needed the parent *author*, not the parent comment id → CommentThread passes `parentAuthorName` down (Task 7 Step 5 note).
- DOMPurify would strip `mention://` protocol links → fragment hrefs (`#mention-ID`) used instead.
- `_notif_enabled` defaults unknown types to True → no config migration needed for `replied`; RulesTab exposes the toggle (Task 9).
- Old `test_router_comments.py` expectations (hard delete, plain create) remain valid — Task 2/4 runs them alongside the new suite.
