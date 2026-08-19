# Usage Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give admins visibility into user behavior across all Osool tools via an in-house event pipeline: `usage_event` table, batch ingest endpoint, frontend tracker, server-side emission at 15 action points (9 workos + 5 policy + 1 chat), and a "Usage" tab in the admin Analytics page.

**Architecture:** One new table + DAO (`models/usage.py`), one new ingest router (`routers/usage.py`), five admin query endpoints appended to the existing `routers/analytics.py`, inline `UsageEvents.emit()` calls in `workos.py` / `policy_review.py` / `main.py`, a fire-and-forget frontend tracker (`src/lib/utils/usage.ts`) wired into the root layout and WorkOS app, and new Svelte components under `src/lib/components/admin/Analytics/`.

**Tech Stack:** FastAPI + SQLAlchemy async + Alembic (backend), Svelte 4/5-runes mix + vitest (frontend), pytest + httpx ASGITransport (backend tests).

**Spec:** `docs/superpowers/specs/2026-08-19-usage-analytics-design.md`

## Global Constraints

- Backend house style: single quotes, `_now() -> int` epoch **milliseconds**, `_id() -> str` uuid4 (copy from `models/workos.py:23-50`).
- Telemetry must NEVER break a real action: `UsageEvents.emit()` swallows all exceptions and uses its OWN DB session (a failed insert in a shared session would poison the caller's transaction — deliberate refinement of spec §4.2, same intent).
- Properties hold ids only — never task titles, comment bodies, document content.
- Admin query endpoints: `user=Depends(get_admin_user)` — same as existing analytics endpoints.
- Client ingest: `user_id` ALWAYS from token; `source` forced to `'client'`; only server-kind allowlist events accepted from `emit()`, only client-kind from ingest.
- Rate limit: 1,000 ingest **requests**/user/hour via existing `RateLimiter` (`utils/rate_limit.py`). Deliberately looser than spec §4.3's 1,000 *events*/hour (a request can carry 50 events, so ceiling is 50k events/hr) — acceptable for an internal tool; the cap exists to stop runaway loops, not abuse.
- Spec drift, deliberate: allowlist is curated to 18 events (spec said "~35"); spec's `chat.new` / generic `search.used` client events and the overview-card "trend arrow" (spec §6) are dropped from v1 — add later if wanted.
- Delivery on page leave uses `fetch(..., {keepalive: true})`, not `sendBeacon` — sendBeacon cannot carry the Authorization header (refinement of spec §4.1, same guarantee).
- Migration chain head is `c2d3e4f5a6b7` — the new migration MUST set `down_revision = 'c2d3e4f5a6b7'`.
- Backend tests run from `backend/`: `.venv/Scripts/python.exe -m pytest open_webui/test/usage/ -v`
- Frontend tests: `npm run test:frontend` (vitest). NEVER start a Vite dev server without asking the user first.
- Frontend edits hot-reload via the user's own Vite server — do not rebuild the Docker image for frontend changes. The migration requires a container restart at smoke time (user does this).
- Commit after every task. Commit messages end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: Migration + model + allowlist + insert/emit DAO

**Files:**
- Create: `backend/open_webui/migrations/versions/d3e4f5a6b7c8_usage_events.py`
- Create: `backend/open_webui/models/usage.py`
- Create: `backend/open_webui/test/usage/__init__.py` (empty)
- Create: `backend/open_webui/test/usage/conftest.py`
- Test: `backend/open_webui/test/usage/test_models_usage.py`

**Interfaces:**
- Consumes: `open_webui.internal.db` (`Base`, `get_async_db_context`), house helpers copied from `models/workos.py`.
- Produces (later tasks rely on these exact names):
  - `EVENT_ALLOWLIST: dict[str, tuple[str, str]]` — event_name → (tool, kind), kind ∈ {'client','server'}
  - `TOOLS: set[str]`
  - `UsageEvents.emit(user_id: str, event_name: str, properties: dict | None = None) -> None` (async, never raises)
  - `UsageEvents.insert_client_batch(user_id: str, events: list[dict], db=None) -> tuple[int, int]` (accepted, rejected)
  - Table `usage_event` with columns id, user_id, event_name, tool, properties(JSON), session_id, source, duration_ms, created_at

- [ ] **Step 1: Read the house patterns you will copy**

Read `backend/open_webui/models/workos.py` lines 23–60 (helpers) and the `CommentsDao.insert` method (search `class CommentsDao`) to copy the exact commit semantics used inside `get_async_db_context`. Mirror whatever that insert does (explicit `await db.commit()` or not) in every write method below.

- [ ] **Step 2: Write the migration**

`backend/open_webui/migrations/versions/d3e4f5a6b7c8_usage_events.py`:

```python
"""usage_event table for usage analytics

Spec: docs/superpowers/specs/2026-08-19-usage-analytics-design.md

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'usage_event',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('event_name', sa.Text(), nullable=False),
        sa.Column('tool', sa.Text(), nullable=False),
        sa.Column('properties', sa.JSON(), nullable=True),
        sa.Column('session_id', sa.Text(), nullable=True),
        sa.Column('source', sa.Text(), nullable=False),
        sa.Column('duration_ms', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_usage_event_created_at', 'usage_event', ['created_at'])
    op.create_index('ix_usage_event_user_created', 'usage_event', ['user_id', 'created_at'])
    op.create_index('ix_usage_event_name_created', 'usage_event', ['event_name', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_usage_event_name_created', table_name='usage_event')
    op.drop_index('ix_usage_event_user_created', table_name='usage_event')
    op.drop_index('ix_usage_event_created_at', table_name='usage_event')
    op.drop_table('usage_event')
```

(`duration_ms` is a real column, extracted from `page.leave` properties at ingest, so averages are plain SQL — no cross-DB JSON extraction.)

- [ ] **Step 3: Write the failing tests**

`backend/open_webui/test/usage/conftest.py` — mirror `backend/open_webui/test/workos/conftest.py` exactly (read it first), with two changes: import `open_webui.models.usage` instead of workos models, and create/drop the `usage_event` table. Keep the same `DATABASE_URL` tempfile + `ENABLE_DB_MIGRATIONS=false` + manual `config` table setup, done BEFORE importing open_webui.

`backend/open_webui/test/usage/test_models_usage.py`:

```python
import pytest

from open_webui.models.usage import EVENT_ALLOWLIST, TOOLS, UsageEvents


@pytest.mark.asyncio
async def test_insert_client_batch_accepts_valid_and_rejects_invalid():
    events = [
        {'name': 'page.view', 'properties': {'tool': 'workos', 'view': 'board', 'path': '/workos'}, 'session_id': 's1'},
        {'name': 'page.leave', 'properties': {'tool': 'workos', 'view': 'board', 'duration_ms': 5000}, 'session_id': 's1'},
        {'name': 'workos.task.create', 'properties': {}, 'session_id': 's1'},  # server-kind -> rejected
        {'name': 'not.a.event', 'properties': {}, 'session_id': 's1'},  # unknown -> rejected
        {'name': 'page.view', 'properties': {'tool': 'nope'}, 'session_id': 's1'},  # bad tool -> rejected
    ]
    accepted, rejected = await UsageEvents.insert_client_batch('u1', events)
    assert accepted == 2
    assert rejected == 3
    rows = await UsageEvents.user_activity('u1', since_ms=0, page=1, limit=10)
    assert rows['total'] == 2
    leave = next(r for r in rows['events'] if r['event_name'] == 'page.leave')
    assert leave['tool'] == 'workos'


@pytest.mark.asyncio
async def test_insert_client_batch_rejects_oversize_properties():
    big = {'x': 'a' * 3000}
    accepted, rejected = await UsageEvents.insert_client_batch(
        'u1', [{'name': 'page.view', 'properties': {'tool': 'chat', **big}, 'session_id': 's1'}]
    )
    assert (accepted, rejected) == (0, 1)


@pytest.mark.asyncio
async def test_emit_writes_server_event():
    await UsageEvents.emit('u2', 'workos.task.create', {'task_id': 't1', 'team_id': 'tm1'})
    rows = await UsageEvents.user_activity('u2', since_ms=0, page=1, limit=10)
    assert rows['total'] == 1
    assert rows['events'][0]['source'] == 'server'
    assert rows['events'][0]['tool'] == 'workos'


@pytest.mark.asyncio
async def test_emit_never_raises_on_unknown_or_client_event():
    await UsageEvents.emit('u3', 'totally.unknown')  # must not raise
    await UsageEvents.emit('u3', 'page.view')  # client-kind: refused, must not raise
    rows = await UsageEvents.user_activity('u3', since_ms=0, page=1, limit=10)
    assert rows['total'] == 0


def test_allowlist_shape():
    assert all(
        kind in ('client', 'server') and (tool in TOOLS or tool == 'app')
        for tool, kind in EVENT_ALLOWLIST.values()
    )
```

(`user_activity` is part of this task so the tests can read back rows — full aggregates come in Task 5.)

- [ ] **Step 4: Run tests to verify they fail**

From `backend/`: `.venv/Scripts/python.exe -m pytest open_webui/test/usage/ -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'open_webui.models.usage'`

- [ ] **Step 5: Write `backend/open_webui/models/usage.py`**

```python
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from open_webui.internal.db import Base, get_async_db_context
from sqlalchemy import BigInteger, Column, JSON, Text, delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)


def _now() -> int:
    return int(time.time() * 1000)


def _id() -> str:
    return str(uuid.uuid4())


TOOLS = {'chat', 'workos', 'policy', 'home', 'admin', 'settings', 'notes', 'other'}

# event_name -> (tool, kind). kind 'client' events may only arrive via the
# ingest endpoint; kind 'server' events may only be written by emit().
# page.view/page.leave carry their real tool in properties['tool'] ('app' here
# is a placeholder, replaced at validation time).
EVENT_ALLOWLIST: dict[str, tuple[str, str]] = {
    # client
    'page.view': ('app', 'client'),
    'page.leave': ('app', 'client'),
    'workos.view.switch': ('workos', 'client'),
    'workos.search.used': ('workos', 'client'),
    # server
    'chat.message.sent': ('chat', 'server'),
    'workos.task.create': ('workos', 'server'),
    'workos.task.complete': ('workos', 'server'),
    'workos.task.delete': ('workos', 'server'),
    'workos.comment.create': ('workos', 'server'),
    'workos.team.member_add': ('workos', 'server'),
    'workos.team.member_remove': ('workos', 'server'),
    'workos.workspace.member_add': ('workos', 'server'),
    'workos.workspace.member_remove': ('workos', 'server'),
    'workos.workspace.visibility_change': ('workos', 'server'),
    'policy.review.submit': ('policy', 'server'),
    'policy.review.approve': ('policy', 'server'),
    'policy.review.reject': ('policy', 'server'),
    'policy.doc.upload': ('policy', 'server'),
}

MAX_PROPERTIES_BYTES = 2048


class UsageEvent(Base):
    __tablename__ = 'usage_event'

    id = Column(Text, primary_key=True, unique=True)
    user_id = Column(Text, nullable=False)
    event_name = Column(Text, nullable=False)
    tool = Column(Text, nullable=False)
    properties = Column(JSON, default=dict)
    session_id = Column(Text, nullable=True)
    source = Column(Text, nullable=False)
    duration_ms = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger, nullable=False)


def _validate_client_event(ev: dict) -> Optional[dict]:
    name = ev.get('name')
    meta = EVENT_ALLOWLIST.get(name)
    if not meta or meta[1] != 'client':
        return None
    props = ev.get('properties') or {}
    if not isinstance(props, dict):
        return None
    try:
        if len(json.dumps(props)) > MAX_PROPERTIES_BYTES:
            return None
    except (TypeError, ValueError):
        return None
    tool = meta[0]
    duration_ms = None
    if name in ('page.view', 'page.leave'):
        tool = props.get('tool')
        if tool not in TOOLS:
            return None
    if name == 'page.leave':
        d = props.get('duration_ms')
        if not isinstance(d, int) or isinstance(d, bool) or d < 0 or d > 86_400_000:
            return None
        duration_ms = d
    session_id = ev.get('session_id')
    if session_id is not None and (not isinstance(session_id, str) or len(session_id) > 64):
        session_id = None
    return {
        'name': name,
        'tool': tool,
        'properties': props,
        'session_id': session_id,
        'duration_ms': duration_ms,
    }


class UsageEventsDao:
    async def insert_client_batch(
        self, user_id: str, events: list[dict], db: Optional[AsyncSession] = None
    ) -> tuple[int, int]:
        rows = []
        rejected = 0
        now = _now()
        for ev in events:
            valid = _validate_client_event(ev)
            if valid is None:
                rejected += 1
                continue
            rows.append(
                UsageEvent(
                    id=_id(),
                    user_id=user_id,
                    event_name=valid['name'],
                    tool=valid['tool'],
                    properties=valid['properties'],
                    session_id=valid['session_id'],
                    source='client',
                    duration_ms=valid['duration_ms'],
                    created_at=now,
                )
            )
        if rows:
            async with get_async_db_context(db) as db:
                db.add_all(rows)
                await db.commit()
        return len(rows), rejected

    async def emit(
        self, user_id: str, event_name: str, properties: Optional[dict] = None
    ) -> None:
        # Own session on purpose: a failed telemetry insert must never poison
        # the caller's transaction, and any exception is swallowed.
        try:
            meta = EVENT_ALLOWLIST.get(event_name)
            if not meta or meta[1] != 'server':
                log.warning(f'usage emit refused for event {event_name}')
                return
            async with get_async_db_context(None) as db:
                db.add(
                    UsageEvent(
                        id=_id(),
                        user_id=user_id,
                        event_name=event_name,
                        tool=meta[0],
                        properties=properties or {},
                        session_id=None,
                        source='server',
                        duration_ms=None,
                        created_at=_now(),
                    )
                )
                await db.commit()
        except Exception:
            log.exception(f'usage emit failed for event {event_name}')

    async def user_activity(
        self,
        user_id: str,
        since_ms: int,
        page: int = 1,
        limit: int = 50,
        tool: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> dict:
        async with get_async_db_context(db) as db:
            q = select(UsageEvent).filter(
                UsageEvent.user_id == user_id, UsageEvent.created_at >= since_ms
            )
            cq = select(func.count(UsageEvent.id)).filter(
                UsageEvent.user_id == user_id, UsageEvent.created_at >= since_ms
            )
            if tool:
                q = q.filter(UsageEvent.tool == tool)
                cq = cq.filter(UsageEvent.tool == tool)
            total = (await db.execute(cq)).scalar() or 0
            res = await db.execute(
                q.order_by(desc(UsageEvent.created_at))
                .limit(limit)
                .offset((page - 1) * limit)
            )
            events = [
                {
                    'event_name': r.event_name,
                    'tool': r.tool,
                    'properties': r.properties or {},
                    'source': r.source,
                    'created_at': r.created_at,
                }
                for r in res.scalars().all()
            ]
            return {'events': events, 'total': total}


UsageEvents = UsageEventsDao()
```

Commit semantics resolved at review time: `CommentsDao.insert` (models/workos.py:1059-1073) DOES call `await db.commit()` explicitly, and `get_async_db_context` never commits on exit (sessionmaker is `autocommit=False`) — keep the explicit commits above. Note `get_async_db_context(db)` only reuses a passed session when `DATABASE_ENABLE_SESSION_SHARING` is on (default off), so the threaded `db=` params are house-style consistency, not shared-transaction semantics.

- [ ] **Step 6: Run tests to verify they pass**

`.venv/Scripts/python.exe -m pytest open_webui/test/usage/ -v`
Expected: 5 PASS

- [ ] **Step 7: Sanity-run the whole workos suite (no regressions from new model import)**

`.venv/Scripts/python.exe -m pytest open_webui/test/workos/ -q`
Expected: all pass (same count as before this task).

- [ ] **Step 8: Commit**

```bash
git add backend/open_webui/migrations/versions/d3e4f5a6b7c8_usage_events.py backend/open_webui/models/usage.py backend/open_webui/test/usage/
git commit -m "feat(usage): usage_event table, allowlist, insert/emit DAO"
```

---

### Task 2: Config flag + ingest router + wiring in main.py

**Files:**
- Modify: `backend/open_webui/config.py` (next to `WORKOS_RULES`, ~line 1685)
- Create: `backend/open_webui/routers/usage.py`
- Modify: `backend/open_webui/main.py` (import block ~line 425, config assignment ~line 937, router mount ~line 1477, `/api/config` features ~line 2435)
- Test: `backend/open_webui/test/usage/test_router_usage.py`

**Interfaces:**
- Consumes: `UsageEvents.insert_client_batch` (Task 1), `RateLimiter` from `open_webui.utils.rate_limit`, `get_redis_client` (copy the exact import from `routers/auths.py:~97`).
- Produces: `POST /api/v1/usage/events` accepting `{"events": [{"name", "properties?", "session_id?"}]}` returning `{"accepted": int, "rejected": int}`; persistent config `ENABLE_USAGE_TRACKING` on `app.state.config`; `/api/config` features key `enable_usage_tracking`.

- [ ] **Step 1: Write the failing tests**

`backend/open_webui/test/usage/test_router_usage.py`:

```python
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

import open_webui.routers.usage as ur
from open_webui.models.usage import UsageEvents
from open_webui.utils.auth import get_verified_user

U1 = SimpleNamespace(id='u1', name='Lara', role='user')


def _make_app(user, enabled=True):
    app = FastAPI()
    app.state.config = SimpleNamespace(ENABLE_USAGE_TRACKING=enabled)
    app.include_router(ur.router, prefix='/api/v1/usage')
    app.dependency_overrides[get_verified_user] = lambda: user
    return app


def _client(*, user=U1, enabled=True):
    return httpx.AsyncClient(
        transport=ASGITransport(app=_make_app(user, enabled)), base_url='http://test'
    )


def _ev(name='page.view', **props):
    return {'name': name, 'properties': {'tool': 'workos', 'view': 'board', **props}, 'session_id': 's1'}


@pytest.mark.asyncio
async def test_ingest_accepts_valid_batch():
    async with _client() as c:
        r = await c.post('/api/v1/usage/events', json={'events': [_ev(), _ev()]})
    assert r.status_code == 200
    assert r.json() == {'accepted': 2, 'rejected': 0}


@pytest.mark.asyncio
async def test_ingest_rejects_server_kind_and_unknown_names():
    async with _client() as c:
        r = await c.post(
            '/api/v1/usage/events',
            json={'events': [{'name': 'workos.task.create', 'properties': {}, 'session_id': 's1'},
                             {'name': 'nope', 'properties': {}, 'session_id': 's1'}]},
        )
    assert r.status_code == 200
    assert r.json() == {'accepted': 0, 'rejected': 2}


@pytest.mark.asyncio
async def test_ingest_batch_cap():
    async with _client() as c:
        r = await c.post('/api/v1/usage/events', json={'events': [_ev()] * 51})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_ingest_disabled_flag_drops_everything():
    async with _client(enabled=False) as c:
        r = await c.post('/api/v1/usage/events', json={'events': [_ev()]})
    assert r.status_code == 200
    assert r.json() == {'accepted': 0, 'rejected': 1}


@pytest.mark.asyncio
async def test_ingest_user_id_comes_from_token_not_payload(monkeypatch):
    seen = {}
    real = UsageEvents.insert_client_batch

    async def spy(user_id, events, db=None):
        seen['user_id'] = user_id
        return await real(user_id, events, db=db)

    monkeypatch.setattr(UsageEvents, 'insert_client_batch', spy)
    async with _client() as c:
        await c.post('/api/v1/usage/events', json={'events': [_ev(user_id='attacker')]})
    assert seen['user_id'] == 'u1'


@pytest.mark.asyncio
async def test_ingest_rate_limited(monkeypatch):
    monkeypatch.setattr(ur.ingest_rate_limiter, 'is_limited', lambda key: True)
    async with _client() as c:
        r = await c.post('/api/v1/usage/events', json={'events': [_ev()]})
    assert r.status_code == 429
```

- [ ] **Step 2: Run tests to verify they fail**

`.venv/Scripts/python.exe -m pytest open_webui/test/usage/test_router_usage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'open_webui.routers.usage'`

- [ ] **Step 3: Write `backend/open_webui/routers/usage.py`**

Verified against auths.py: import is `from open_webui.utils.redis import get_redis_client` (auths.py:80), construction is module-level `RateLimiter(redis_client=get_redis_client(), ...)` (auths.py:97), `is_limited` is SYNC (do not await), and `RateLimiter` falls back to an in-memory store when `get_redis_client()` returns None (Redis unconfigured — e.g. in tests). The snippet below is safe as written.

```python
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.constants import ERROR_MESSAGES
from open_webui.internal.db import get_async_session
from open_webui.models.usage import UsageEvents
from open_webui.utils.auth import get_verified_user
from open_webui.utils.rate_limit import RateLimiter
from open_webui.utils.redis import get_redis_client

router = APIRouter()

# 1000 ingest requests/user/hour — far above normal use (tracker flushes at
# most every 10s => ~360/hr).
ingest_rate_limiter = RateLimiter(
    redis_client=get_redis_client(), limit=1000, window=3600
)

MAX_BATCH = 50


class ClientEventForm(BaseModel):
    name: str
    properties: dict = Field(default_factory=dict)
    session_id: str | None = None


class IngestForm(BaseModel):
    events: list[ClientEventForm]


class IngestResponse(BaseModel):
    accepted: int
    rejected: int


@router.post('/events', response_model=IngestResponse)
async def ingest_events(
    request: Request,
    form: IngestForm,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    if not request.app.state.config.ENABLE_USAGE_TRACKING:
        return IngestResponse(accepted=0, rejected=len(form.events))
    if len(form.events) > MAX_BATCH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'batch exceeds {MAX_BATCH} events',
        )
    if ingest_rate_limiter.is_limited(f'usage:{user.id}'):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=ERROR_MESSAGES.RATE_LIMIT_EXCEEDED,
        )
    accepted, rejected = await UsageEvents.insert_client_batch(
        user.id, [e.model_dump() for e in form.events], db=db
    )
    return IngestResponse(accepted=accepted, rejected=rejected)
```

- [ ] **Step 4: Add the persistent config flag**

In `backend/open_webui/config.py`, directly after the `WORKOS_RULES` block (~line 1685):

```python
ENABLE_USAGE_TRACKING = PersistentConfig(
    'ENABLE_USAGE_TRACKING',
    'usage.enable_tracking',
    os.environ.get('ENABLE_USAGE_TRACKING', 'True').lower() == 'true',
)
```

- [ ] **Step 5: Wire into main.py (four spots)**

1. Import block (~line 425, where `WORKOS_RULES` is imported from config): add `ENABLE_USAGE_TRACKING`.
2. Router imports (where `workos` router is imported): add `usage`.
3. Config assignment (~line 937, next to `app.state.config.WORKOS_RULES = WORKOS_RULES`):
   ```python
   app.state.config.ENABLE_USAGE_TRACKING = ENABLE_USAGE_TRACKING
   ```
4. Router mount (next to workos mount ~line 1477):
   ```python
   app.include_router(usage.router, prefix='/api/v1/usage', tags=['usage'])
   ```
5. `/api/config` features dict — inside the `if user is not None` spread (~line 2435, next to `'enable_admin_analytics'`):
   ```python
   'enable_usage_tracking': app.state.config.ENABLE_USAGE_TRACKING,
   ```

- [ ] **Step 6: Run tests to verify they pass**

`.venv/Scripts/python.exe -m pytest open_webui/test/usage/ -v`
Expected: all PASS (Task 1's 5 + Task 2's 6).

- [ ] **Step 7: Import smoke on main.py wiring**

`.venv/Scripts/python.exe -c "import ast; ast.parse(open('open_webui/main.py', encoding='utf-8').read()); ast.parse(open('open_webui/config.py', encoding='utf-8').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 8: Commit**

```bash
git add backend/open_webui/routers/usage.py backend/open_webui/config.py backend/open_webui/main.py backend/open_webui/test/usage/test_router_usage.py
git commit -m "feat(usage): ingest endpoint, ENABLE_USAGE_TRACKING flag, config exposure"
```

---

### Task 3: Server-side emission — workos.py (9 hooks)

**Files:**
- Modify: `backend/open_webui/routers/workos.py`
- Test: `backend/open_webui/test/workos/test_usage_emission.py`

**Interfaces:**
- Consumes: `UsageEvents.emit` (Task 1). Import at top of workos.py: `from open_webui.models.usage import UsageEvents`.
- Produces: server events fired from the 9 endpoints below.

**Context:** all line numbers are pre-edit anchors; each insertion goes AFTER the DB write succeeds and before the endpoint returns. Read `docs/superpowers/specs/2026-06-26-workos-access-control.md` before touching the membership endpoints (standing rule) — emission only observes, never alters access logic.

- [ ] **Step 1: Write the failing tests**

`backend/open_webui/test/workos/test_usage_emission.py` — reuse the existing minimal-app pattern (`_client`, `U1` from `test_router_teams`), monkeypatching `emit` so no usage table is needed in the workos conftest:

```python
from unittest.mock import AsyncMock

import pytest

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_comments import _task
from open_webui.test.workos.test_router_task import _stream
from open_webui.test.workos.test_router_teams import U1, _client


@pytest.fixture()
def emit_spy(monkeypatch):
    spy = AsyncMock()
    monkeypatch.setattr(wr.UsageEvents, 'emit', spy)
    return spy


def _emitted(spy):
    return [c.args[1] for c in spy.await_args_list]


@pytest.mark.asyncio
async def test_task_create_emits(monkeypatch, emit_spy):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        r = await c.post(
            f"/api/v1/workos/workstreams/{s['id']}/tasks",
            json={'title': 'task', 'assignee_ids': [U1.id]},
        )
        assert r.status_code == 200
    assert 'workos.task.create' in _emitted(emit_spy)


@pytest.mark.asyncio
async def test_task_complete_emits_only_on_transition_to_done(monkeypatch, emit_spy):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s, task = await _task(c)
        await c.patch(f"/api/v1/workos/tasks/{task['id']}", json={'status': 'in_progress'})
        assert 'workos.task.complete' not in _emitted(emit_spy)
        await c.patch(f"/api/v1/workos/tasks/{task['id']}", json={'status': 'done'})
        assert 'workos.task.complete' in _emitted(emit_spy)
        emit_spy.reset_mock()
        await c.patch(f"/api/v1/workos/tasks/{task['id']}", json={'title': 'renamed'})
        assert 'workos.task.complete' not in _emitted(emit_spy)


@pytest.mark.asyncio
async def test_task_delete_and_comment_emit(monkeypatch, emit_spy):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s, task = await _task(c)
        await c.post(f"/api/v1/workos/tasks/{task['id']}/comments", json={'body': 'hi'})
        assert 'workos.comment.create' in _emitted(emit_spy)
        await c.delete(f"/api/v1/workos/tasks/{task['id']}")
        assert 'workos.task.delete' in _emitted(emit_spy)


@pytest.mark.asyncio
async def test_membership_changes_emit(monkeypatch, emit_spy):
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'T', 'key': 'T'})).json()
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        assert 'workos.team.member_add' in _emitted(emit_spy)
        await c.delete(f"/api/v1/workos/teams/{team['id']}/members/u2")
        assert 'workos.team.member_remove' in _emitted(emit_spy)
```

Hierarchy setup reuses verified existing helpers: `_stream(c) -> (team, ws, s)` from `test_router_task.py:6` and `_task(c) -> (team, ws, s, t)` from `test_router_comments.py:8`. `_client` signature verified: `_client(monkeypatch, *, user, allow=True, rules=None)` (test_router_teams.py:25), monkeypatching `wa.has_permission` — the `monkeypatch.setattr(wr, ...)` spy pattern matches existing precedent (`test_realtime.py:30` patches `wr.emit_event`). BEFORE running: eyeball the helpers' current return shapes and the team-create payload (existing tests pass `{'name', 'key'}`) in case they drifted.

- [ ] **Step 2: Run tests to verify they fail**

`.venv/Scripts/python.exe -m pytest open_webui/test/workos/test_usage_emission.py -v`
Expected: FAIL — `AttributeError: module 'open_webui.routers.workos' has no attribute 'UsageEvents'` (or assert failures once import added).

- [ ] **Step 3: Add the import and 9 emit calls to workos.py**

Import (top of file, near the `from open_webui.models.workos import ...` block):

```python
from open_webui.models.usage import UsageEvents
```

Hooks (anchors from recon; adjust to current lines):

1. **`create_task`** (~line 698–718) — after the `Tasks.insert` + `emit_event` + notify block, before `return task`:
   ```python
   await UsageEvents.emit(user.id, 'workos.task.create', {'task_id': task.id, 'team_id': task.team_id, 'workstream_id': workstream_id})
   ```
2. **`update_task`** (~line 731–788) — inside the existing status-transition block at ~784 (`if 'status' in fields and updated.status != before.get('status'):`), add:
   ```python
   if updated.status == 'done':
       await UsageEvents.emit(user.id, 'workos.task.complete', {'task_id': updated.id, 'team_id': updated.team_id})
   ```
3. **`delete_task`** (~line 792–803) — after `deleted = await Tasks.delete(...)`, gate on `if deleted:`:
   ```python
   if deleted:
       await UsageEvents.emit(user.id, 'workos.task.delete', {'task_id': task_id, 'team_id': task.team_id})
   ```
4. **`create_comment`** (~line 1044–1086) — after `comment = await Comments.insert(...)`:
   ```python
   await UsageEvents.emit(user.id, 'workos.comment.create', {'task_id': task_id, 'team_id': task.team_id, 'is_reply': bool(form.parent_id)})
   ```
5. **`add_member`** (~line 282–292) — split the single-expression return:
   ```python
   member = await TeamMembers.add(team_id, form.user_id, form.role, db=db)
   await UsageEvents.emit(user.id, 'workos.team.member_add', {'team_id': team_id, 'member_id': form.user_id, 'role': form.role})
   return member
   ```
6. **`remove_member`** (~line 317–333) — after the write, gated:
   ```python
   if removed:
       await UsageEvents.emit(user.id, 'workos.team.member_remove', {'team_id': team_id, 'member_id': user_id})
   ```
   (`user_id` here is the removed member's path param — check the actual param name in the signature.)
7. **`add_workspace_member`** (~line 489–499) — same split pattern as hook 5, event `'workos.workspace.member_add'`, props `{'workspace_id': workspace_id, 'member_id': form.user_id}`.
8. **`remove_workspace_member`** (~line 518–532) — same gated pattern as hook 6, event `'workos.workspace.member_remove'`.
9. **`update_workspace`** (~line 446–457) — after `updated = await Workspaces.update_fields(...)`:
   ```python
   if before.visibility != updated.visibility:
       await UsageEvents.emit(user.id, 'workos.workspace.visibility_change', {'workspace_id': workspace_id, 'from': before.visibility, 'to': updated.visibility})
   ```

- [ ] **Step 4: Run tests to verify they pass**

`.venv/Scripts/python.exe -m pytest open_webui/test/workos/ -v`
Expected: new file all PASS, zero regressions in the rest.

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_usage_emission.py
git commit -m "feat(usage): server-side event emission in workos router"
```

---

### Task 4: Server-side emission — policy_review.py (5 hooks) + chat (1 hook)

**Files:**
- Modify: `backend/open_webui/routers/policy_review.py`
- Modify: `backend/open_webui/main.py` (`chat_completion`, ~line 2005)
- Test: extend `backend/open_webui/test/policy_review/test_router_reviews.py` with emission tests, same monkeypatch-spy pattern as Task 3. (Do NOT glob for `test*policy*.py` — that matches only `test/workos/test_policy_module.py`, which is about `workos_access`, and misses the real suite under `test/policy_review/`.)

**Interfaces:**
- Consumes: `UsageEvents.emit` (Task 1).
- Produces: `policy.review.submit/approve/reject`, `policy.doc.upload`, `chat.message.sent` events.

- [ ] **Step 1: Write failing tests for policy emission**

Add to `test/policy_review/test_router_reviews.py` (reusing ITS existing client/fixture pattern — read the file first, mirror how it builds reviews and drives submit/approve). Its conventions differ from workos: it patches `pr_router.has_permission` on the ROUTER module (not the utils module), offers `_client(monkeypatch, *, user, allow=True)` and `_client_keys(monkeypatch, *, user, keys=())` helpers, and has an autouse `_seed_active` fixture seeding an active checklist version. Note `test/policy_review/conftest.py` runs `Base.metadata.create_all` with NO table filter, so once `models/usage.py` exists its table is auto-created there — but keep the emit spy anyway for assertion access.

```python
from unittest.mock import AsyncMock

import open_webui.routers.policy_review as pr


@pytest.fixture()
def emit_spy(monkeypatch):
    spy = AsyncMock()
    monkeypatch.setattr(pr.UsageEvents, 'emit', spy)
    return spy


def _emitted(spy):
    return [c.args[1] for c in spy.await_args_list]
```

Then one test each asserting `'policy.doc.upload' in _emitted(emit_spy)` after driving the existing create-review flow, `'policy.review.submit'` after submit, `'policy.review.approve'` after approve, `'policy.review.reject'` after reject — each built on whatever helpers those tests already use (do not invent new request shapes).

- [ ] **Step 2: Run to verify they fail**

`.venv/Scripts/python.exe -m pytest open_webui/test/policy_review/test_router_reviews.py -v -k emit`
Expected: FAIL — no `UsageEvents` attribute on the policy router module.

- [ ] **Step 3: Add import + 5 emit calls to policy_review.py**

Import: `from open_webui.models.usage import UsageEvents`.

1. **`create_review`** (~line 264–339) — next to the existing `PolicyAudits.insert(... 'document_uploaded' ...)` call (~line 338):
   ```python
   await UsageEvents.emit(user.id, 'policy.doc.upload', {'review_id': review.id})
   ```
2. **`replace_review_document`** (~line 404–449) — after its success audits (~448): same `'policy.doc.upload'` emit.
3. **`submit_review`** (~line 453–472) — after the status write + audit:
   ```python
   await UsageEvents.emit(user.id, 'policy.review.submit', {'review_id': review_id})
   ```
4. **`approve_review`** (~line 476–543) — after the status flip (~540):
   ```python
   await UsageEvents.emit(user.id, 'policy.review.approve', {'review_id': review_id})
   ```
5. **`reject_review`** (~line 547–567) — after the write (~565):
   ```python
   await UsageEvents.emit(user.id, 'policy.review.reject', {'review_id': review_id})
   ```

- [ ] **Step 4: Add the chat hook in main.py**

In `chat_completion` (~line 1717), right after `request.state.metadata = metadata` (~line 2005) — the user message is persisted by this point, before dispatch:

```python
    await UsageEvents.emit(
        user.id, 'chat.message.sent', {'model': model_id, 'chat_id': metadata.get('chat_id')}
    )
```

Add `from open_webui.models.usage import UsageEvents` to main.py's imports. Variable names verified in the current tree: `model_id` set at ~line 1725, `metadata` at ~1729, `user` is the endpoint param; user message IS persisted before line 2005 (new-chat path `Chats.insert_new_chat` ~1870, existing-chat `upsert_message_to_chat_by_id_and_message_id` ~1933). This hook fires once per user-sent message including multi-model chats (one request), and even if the model call later fails — that matches "message sent". Known accepted caveat: the custom-model fallback (~line 1767-1770) rewrites `form_data['model']` but NOT `model_id`, so properties record the originally requested model, which is fine for adoption analytics. No automated test (main.py monolith); verified at browser smoke.

- [ ] **Step 5: Run tests to verify they pass**

`.venv/Scripts/python.exe -m pytest open_webui/test/ -q`
Expected: all pass, including new policy emission tests.

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/routers/policy_review.py backend/open_webui/main.py backend/open_webui/test/
git commit -m "feat(usage): server-side event emission in policy router and chat"
```

---

### Task 5: DAO aggregates + admin query endpoints

**Files:**
- Modify: `backend/open_webui/models/usage.py` (add aggregate methods to `UsageEventsDao`)
- Modify: `backend/open_webui/routers/analytics.py` (append 5 endpoints)
- Test: `backend/open_webui/test/usage/test_aggregates.py`

**Interfaces:**
- Consumes: Task 1's table + DAO; `get_admin_user` (same import analytics.py already has).
- Produces (frontend Task 9 relies on these exact routes/shapes):
  - `GET /api/v1/analytics/usage/overview?days=30` → `{'tools': [{'tool', 'active_users', 'sessions', 'events', 'avg_page_ms'}]}`
  - `GET /api/v1/analytics/usage/daily?days=30&tool=` → `{'days': [{'date': 'YYYY-MM-DD', 'tools': {tool: dau}, 'events': int}]}`
  - `GET /api/v1/analytics/usage/events?days=30&tool=` → `{'events': [{'event_name', 'tool', 'count', 'unique_users'}]}`
  - `GET /api/v1/analytics/usage/users?days=30&sort=events|last_seen&page=1` → `{'users': [{'user_id', 'name', 'last_seen', 'sessions', 'events', 'tools': {tool: count}}], 'total': int}`
  - `GET /api/v1/analytics/usage/users/{user_id}/activity?days=30&page=1&tool=` → `{'events': [{'event_name', 'tool', 'properties', 'source', 'created_at'}], 'total': int}`
  - DAO methods: `overview(since_ms, db=None)`, `daily(since_ms, tool=None, db=None)`, `event_counts(since_ms, tool=None, db=None)`, `user_rollup(since_ms, sort='events', page=1, limit=25, db=None)`, `delete_before(cutoff_ms, db=None) -> int`

- [ ] **Step 1: Write the failing tests**

`backend/open_webui/test/usage/test_aggregates.py`:

```python
import pytest

from open_webui.models.usage import UsageEvents, _now


async def _seed():
    # u1: workos page + task create; u2: chat message
    await UsageEvents.insert_client_batch('u1', [
        {'name': 'page.view', 'properties': {'tool': 'workos', 'view': 'board'}, 'session_id': 's1'},
        {'name': 'page.leave', 'properties': {'tool': 'workos', 'view': 'board', 'duration_ms': 4000}, 'session_id': 's1'},
    ])
    await UsageEvents.emit('u1', 'workos.task.create', {'task_id': 't1'})
    await UsageEvents.emit('u2', 'chat.message.sent', {'model': 'm1'})


@pytest.mark.asyncio
async def test_overview():
    await _seed()
    tools = {t['tool']: t for t in await UsageEvents.overview(since_ms=0)}
    assert tools['workos']['active_users'] == 1
    assert tools['workos']['events'] == 3
    assert tools['workos']['avg_page_ms'] == 4000
    assert tools['chat']['active_users'] == 1


@pytest.mark.asyncio
async def test_daily_and_event_counts():
    await _seed()
    days = await UsageEvents.daily(since_ms=0)
    assert len(days) == 1
    assert days[0]['tools']['workos'] == 1
    assert days[0]['events'] == 4
    counts = {e['event_name']: e for e in await UsageEvents.event_counts(since_ms=0)}
    assert counts['workos.task.create']['count'] == 1
    assert counts['page.view']['unique_users'] == 1


@pytest.mark.asyncio
async def test_user_rollup_and_sort():
    await _seed()
    res = await UsageEvents.user_rollup(since_ms=0, sort='events', page=1, limit=10)
    assert res['total'] == 2
    assert res['users'][0]['user_id'] == 'u1'  # 3 events > 1
    assert res['users'][0]['tools']['workos'] == 3


@pytest.mark.asyncio
async def test_delete_before():
    await _seed()
    deleted = await UsageEvents.delete_before(_now() + 1000)
    assert deleted == 4
    assert (await UsageEvents.user_rollup(since_ms=0))['total'] == 0
```

- [ ] **Step 2: Run to verify they fail**

`.venv/Scripts/python.exe -m pytest open_webui/test/usage/test_aggregates.py -v`
Expected: FAIL — `AttributeError: 'UsageEventsDao' object has no attribute 'overview'`

- [ ] **Step 3: Add aggregate methods to `UsageEventsDao`**

```python
    async def overview(self, since_ms: int, db: Optional[AsyncSession] = None) -> list[dict]:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(
                    UsageEvent.tool,
                    func.count(func.distinct(UsageEvent.user_id)),
                    func.count(func.distinct(UsageEvent.session_id)),
                    func.count(UsageEvent.id),
                )
                .filter(UsageEvent.created_at >= since_ms)
                .group_by(UsageEvent.tool)
            )
            rows = res.all()
            dres = await db.execute(
                select(UsageEvent.tool, func.avg(UsageEvent.duration_ms))
                .filter(
                    UsageEvent.created_at >= since_ms,
                    UsageEvent.event_name == 'page.leave',
                )
                .group_by(UsageEvent.tool)
            )
            durations = dict(dres.all())
            return [
                {
                    'tool': t,
                    'active_users': u,
                    'sessions': s,
                    'events': e,
                    'avg_page_ms': int(durations.get(t) or 0),
                }
                for t, u, s, e in rows
            ]

    async def daily(
        self, since_ms: int, tool: Optional[str] = None, db: Optional[AsyncSession] = None
    ) -> list[dict]:
        day = (UsageEvent.created_at.op('/')(86_400_000)).label('day')
        async with get_async_db_context(db) as db:
            q = (
                select(
                    day,
                    UsageEvent.tool,
                    func.count(func.distinct(UsageEvent.user_id)),
                    func.count(UsageEvent.id),
                )
                .filter(UsageEvent.created_at >= since_ms)
                .group_by(day, UsageEvent.tool)
                .order_by(day)
            )
            if tool:
                q = q.filter(UsageEvent.tool == tool)
            out: dict[int, dict] = {}
            for d, t, dau, cnt in (await db.execute(q)).all():
                d = int(d)
                bucket = out.setdefault(
                    d,
                    {
                        'date': datetime.fromtimestamp(d * 86400, tz=timezone.utc).strftime('%Y-%m-%d'),
                        'tools': {},
                        'events': 0,
                    },
                )
                bucket['tools'][t] = dau
                bucket['events'] += cnt
            return [out[k] for k in sorted(out)]

    async def event_counts(
        self, since_ms: int, tool: Optional[str] = None, db: Optional[AsyncSession] = None
    ) -> list[dict]:
        async with get_async_db_context(db) as db:
            q = (
                select(
                    UsageEvent.event_name,
                    UsageEvent.tool,
                    func.count(UsageEvent.id).label('count'),
                    func.count(func.distinct(UsageEvent.user_id)),
                )
                .filter(UsageEvent.created_at >= since_ms)
                .group_by(UsageEvent.event_name, UsageEvent.tool)
                .order_by(desc('count'))
            )
            if tool:
                q = q.filter(UsageEvent.tool == tool)
            return [
                {'event_name': n, 'tool': t, 'count': c, 'unique_users': u}
                for n, t, c, u in (await db.execute(q)).all()
            ]

    async def user_rollup(
        self,
        since_ms: int,
        sort: str = 'events',
        page: int = 1,
        limit: int = 25,
        db: Optional[AsyncSession] = None,
    ) -> dict:
        async with get_async_db_context(db) as db:
            total = (
                await db.execute(
                    select(func.count(func.distinct(UsageEvent.user_id))).filter(
                        UsageEvent.created_at >= since_ms
                    )
                )
            ).scalar() or 0
            base = (
                select(
                    UsageEvent.user_id,
                    func.max(UsageEvent.created_at).label('last_seen'),
                    func.count(func.distinct(UsageEvent.session_id)).label('sessions'),
                    func.count(UsageEvent.id).label('events'),
                )
                .filter(UsageEvent.created_at >= since_ms)
                .group_by(UsageEvent.user_id)
                .order_by(desc('last_seen' if sort == 'last_seen' else 'events'))
                .limit(limit)
                .offset((page - 1) * limit)
            )
            rows = (await db.execute(base)).all()
            ids = [r[0] for r in rows]
            tool_counts: dict[str, dict[str, int]] = {}
            if ids:
                tres = await db.execute(
                    select(UsageEvent.user_id, UsageEvent.tool, func.count(UsageEvent.id))
                    .filter(UsageEvent.created_at >= since_ms, UsageEvent.user_id.in_(ids))
                    .group_by(UsageEvent.user_id, UsageEvent.tool)
                )
                for uid, t, c in tres.all():
                    tool_counts.setdefault(uid, {})[t] = c
            return {
                'users': [
                    {
                        'user_id': uid,
                        'last_seen': last_seen,
                        'sessions': sessions,
                        'events': events,
                        'tools': tool_counts.get(uid, {}),
                    }
                    for uid, last_seen, sessions, events in rows
                ],
                'total': total,
            }

    async def delete_before(
        self, cutoff_ms: int, db: Optional[AsyncSession] = None
    ) -> int:
        async with get_async_db_context(db) as db:
            res = await db.execute(delete(UsageEvent).filter(UsageEvent.created_at < cutoff_ms))
            await db.commit()
            return res.rowcount or 0
```

(Apply the same commit-semantics adjustment as Task 1 Step 5 if needed.)

- [ ] **Step 4: Run DAO tests**

`.venv/Scripts/python.exe -m pytest open_webui/test/usage/test_aggregates.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Append the 5 endpoints to analytics.py**

At the end of `backend/open_webui/routers/analytics.py`, following its exact house style (pydantic response models, `get_admin_user`, `db` injection). Add import `from open_webui.models.usage import UsageEvents` and `import time`. Display names: analytics.py already imports `Users` (line 11) and resolves batches via `Users.get_users_by_user_ids(ids, db=db)` (see line 94) — reuse exactly that.

```python
def _since_ms(days: int) -> int:
    return int(time.time() * 1000) - days * 86_400_000


class UsageToolOverview(BaseModel):
    tool: str
    active_users: int
    sessions: int
    events: int
    avg_page_ms: int


class UsageOverviewResponse(BaseModel):
    tools: list[UsageToolOverview]


@router.get('/usage/overview', response_model=UsageOverviewResponse)
async def get_usage_overview(
    days: int = Query(30, ge=1, le=365),
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    tools = await UsageEvents.overview(_since_ms(days), db=db)
    return UsageOverviewResponse(tools=[UsageToolOverview(**t) for t in tools])


class UsageDailyEntry(BaseModel):
    date: str
    tools: dict[str, int]
    events: int


class UsageDailyResponse(BaseModel):
    days: list[UsageDailyEntry]


@router.get('/usage/daily', response_model=UsageDailyResponse)
async def get_usage_daily(
    days: int = Query(30, ge=1, le=365),
    tool: Optional[str] = Query(None),
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    rows = await UsageEvents.daily(_since_ms(days), tool=tool, db=db)
    return UsageDailyResponse(days=[UsageDailyEntry(**r) for r in rows])


class UsageEventEntry(BaseModel):
    event_name: str
    tool: str
    count: int
    unique_users: int


class UsageEventsResponse(BaseModel):
    events: list[UsageEventEntry]


@router.get('/usage/events', response_model=UsageEventsResponse)
async def get_usage_event_counts(
    days: int = Query(30, ge=1, le=365),
    tool: Optional[str] = Query(None),
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    rows = await UsageEvents.event_counts(_since_ms(days), tool=tool, db=db)
    return UsageEventsResponse(events=[UsageEventEntry(**r) for r in rows])


class UsageUserEntry(BaseModel):
    user_id: str
    name: str
    last_seen: int
    sessions: int
    events: int
    tools: dict[str, int]


class UsageUsersResponse(BaseModel):
    users: list[UsageUserEntry]
    total: int


@router.get('/usage/users', response_model=UsageUsersResponse)
async def get_usage_users(
    days: int = Query(30, ge=1, le=365),
    sort: str = Query('events', pattern='^(events|last_seen)$'),
    page: int = Query(1, ge=1),
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    res = await UsageEvents.user_rollup(_since_ms(days), sort=sort, page=page, db=db)
    ids = [u['user_id'] for u in res['users']]
    user_info = (
        {u.id: u for u in await Users.get_users_by_user_ids(ids, db=db)} if ids else {}
    )
    return UsageUsersResponse(
        users=[
            UsageUserEntry(
                **u,
                name=user_info[u['user_id']].name
                if u['user_id'] in user_info
                else 'removed user',
            )
            for u in res['users']
        ],
        total=res['total'],
    )


class UsageActivityEntry(BaseModel):
    event_name: str
    tool: str
    properties: dict
    source: str
    created_at: int


class UsageActivityResponse(BaseModel):
    events: list[UsageActivityEntry]
    total: int


@router.get('/usage/users/{user_id}/activity', response_model=UsageActivityResponse)
async def get_usage_user_activity(
    user_id: str,
    days: int = Query(30, ge=1, le=365),
    page: int = Query(1, ge=1),
    tool: Optional[str] = Query(None),
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    res = await UsageEvents.user_activity(user_id, _since_ms(days), page=page, tool=tool, db=db)
    return UsageActivityResponse(
        events=[UsageActivityEntry(**e) for e in res['events']], total=res['total']
    )
```

(Name lookup above is the verified analytics.py:94 mechanism — `Users` import already present in that file.)

- [ ] **Step 6: Add endpoint tests**

Append to `test_aggregates.py` — minimal app mounting `analytics.router` with `get_admin_user` overridden (admin) and one test asserting a non-admin gets 401/403 (do NOT override, expect failure), plus one happy-path test per endpoint asserting 200 + shape after `_seed()`. Follow the `_make_app`/`_client` pattern from `test_router_usage.py`, overriding `get_admin_user` instead.

- [ ] **Step 7: Run full usage suite**

`.venv/Scripts/python.exe -m pytest open_webui/test/usage/ -v`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/open_webui/models/usage.py backend/open_webui/routers/analytics.py backend/open_webui/test/usage/test_aggregates.py
git commit -m "feat(usage): DAO aggregates and admin query endpoints"
```

---

### Task 6: Retention cleanup task

**Files:**
- Modify: `backend/open_webui/main.py` (lifespan, next to `asyncio.create_task(periodic_usage_pool_cleanup())` ~line 695)

**Interfaces:**
- Consumes: `UsageEvents.delete_before` (Task 5, already tested there).
- Produces: daily deletion of events older than 365 days.

- [ ] **Step 1: Add the loop to main.py**

Near the other periodic tasks in `lifespan`:

```python
    async def periodic_usage_events_cleanup():
        from open_webui.models.usage import UsageEvents

        while True:
            try:
                cutoff = int(time.time() * 1000) - 365 * 86_400_000
                deleted = await UsageEvents.delete_before(cutoff)
                if deleted:
                    log.info(f'usage cleanup: removed {deleted} events older than 365d')
            except Exception:
                log.exception('usage cleanup failed')
            await asyncio.sleep(24 * 3600)

    asyncio.create_task(periodic_usage_events_cleanup())
```

No Redis lock: single-container deployment, and `delete_before` is idempotent. (`delete_before` itself is covered by `test_delete_before` in Task 5.)

- [ ] **Step 2: Syntax check**

`.venv/Scripts/python.exe -c "import ast; ast.parse(open('open_webui/main.py', encoding='utf-8').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/open_webui/main.py
git commit -m "feat(usage): daily 365-day retention cleanup"
```

---

### Task 7: Frontend tracker module

**Files:**
- Create: `src/lib/utils/usage.ts`
- Test: `src/lib/utils/usage.test.ts`

**Interfaces:**
- Consumes: `WEBUI_API_BASE_URL` from `$lib/constants`.
- Produces (Task 8 relies on these exact exports):
  - `initUsageTracking(token: string, enabled: boolean): void`
  - `track(name, properties?): void`
  - `pageEnter(pathname: string): void`
  - `routeToTool(pathname: string): { tool: string; view: string }`
  - `flushNow(): void` (exported for tests and unload)

- [ ] **Step 1: Write the failing tests**

`src/lib/utils/usage.test.ts` (vitest; stub browser globals — the suite may run in node env):

```ts
import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('$lib/constants', () => ({ WEBUI_API_BASE_URL: '/api/v1' }));

import { initUsageTracking, track, pageEnter, routeToTool, flushNow, _resetForTests } from './usage';

const fetchMock = vi.fn(async () => ({ ok: true }));

beforeEach(() => {
	vi.useFakeTimers();
	vi.stubGlobal('fetch', fetchMock);
	vi.stubGlobal('navigator', {});
	vi.stubGlobal('document', { addEventListener: vi.fn(), visibilityState: 'visible' });
	vi.stubGlobal('sessionStorage', {
		store: {} as Record<string, string>,
		getItem(k: string) { return this.store[k] ?? null; },
		setItem(k: string, v: string) { this.store[k] = v; }
	});
	vi.stubGlobal('crypto', { randomUUID: () => 'uuid-1' });
	fetchMock.mockClear();
	_resetForTests();
});

describe('routeToTool', () => {
	it('maps known prefixes', () => {
		expect(routeToTool('/workos').tool).toBe('workos');
		expect(routeToTool('/admin/analytics').tool).toBe('admin');
		expect(routeToTool('/home').tool).toBe('home');
		expect(routeToTool('/').tool).toBe('chat');
		expect(routeToTool('/c/abc123').tool).toBe('chat');
		expect(routeToTool('/weird').tool).toBe('other');
	});
});

describe('tracker', () => {
	it('does nothing when disabled', () => {
		initUsageTracking('tok', false);
		track('workos.view.switch', { view: 'board' });
		flushNow();
		expect(fetchMock).not.toHaveBeenCalled();
	});

	it('flushes at 20 queued events', () => {
		initUsageTracking('tok', true);
		for (let i = 0; i < 20; i++) track('workos.view.switch', { view: 'board' });
		expect(fetchMock).toHaveBeenCalledTimes(1);
		const body = JSON.parse(fetchMock.mock.calls[0][1].body);
		expect(body.events).toHaveLength(20);
		expect(body.events[0].session_id).toBe('uuid-1');
	});

	it('flushes on the 10s interval', () => {
		initUsageTracking('tok', true);
		track('workos.view.switch', { view: 'list' });
		expect(fetchMock).not.toHaveBeenCalled();
		vi.advanceTimersByTime(10_000);
		expect(fetchMock).toHaveBeenCalledTimes(1);
	});

	it('pageEnter emits page.view, next pageEnter emits page.leave with duration', () => {
		initUsageTracking('tok', true);
		pageEnter('/workos');
		vi.advanceTimersByTime(5_000);
		pageEnter('/home');
		flushNow();
		const events = JSON.parse(fetchMock.mock.calls[0][1].body).events;
		const names = events.map((e: { name: string }) => e.name);
		expect(names).toEqual(['page.view', 'page.leave', 'page.view']);
		const leave = events[1];
		expect(leave.properties.tool).toBe('workos');
		expect(leave.properties.duration_ms).toBeGreaterThanOrEqual(5000);
	});

	it('swallows fetch failures silently', async () => {
		fetchMock.mockRejectedValueOnce(new Error('down'));
		initUsageTracking('tok', true);
		track('workos.view.switch', { view: 'board' });
		expect(() => flushNow()).not.toThrow();
	});
});
```

(Duration uses `Date.now()` — with fake timers `advanceTimersByTime` advances it; if the installed vitest version doesn't fake `Date` by default, pass `vi.useFakeTimers({ toFake: ['setInterval', 'setTimeout', 'Date'] })`.)

- [ ] **Step 2: Run to verify they fail**

`npm run test:frontend -- src/lib/utils/usage.test.ts`
Expected: FAIL — cannot resolve `./usage`.

- [ ] **Step 3: Write `src/lib/utils/usage.ts`**

```ts
import { WEBUI_API_BASE_URL } from '$lib/constants';

export type ClientEventName = 'page.view' | 'page.leave' | 'workos.view.switch' | 'workos.search.used';

type QueuedEvent = { name: ClientEventName; properties: Record<string, unknown>; session_id: string };

const FLUSH_INTERVAL_MS = 10_000;
const FLUSH_AT = 20;
const MAX_BATCH = 50;

let queue: QueuedEvent[] = [];
let timer: ReturnType<typeof setInterval> | null = null;
let enabled = false;
let token = '';
let currentPage: { tool: string; view: string; path: string; since: number } | null = null;

const sessionId = (): string => {
	let id = sessionStorage.getItem('usageSessionId');
	if (!id) {
		id = crypto.randomUUID();
		sessionStorage.setItem('usageSessionId', id);
	}
	return id;
};

export const routeToTool = (pathname: string): { tool: string; view: string } => {
	if (pathname.startsWith('/workos')) return { tool: 'workos', view: 'workos' };
	if (pathname.startsWith('/admin')) return { tool: 'admin', view: pathname.split('/')[2] ?? 'admin' };
	if (pathname.startsWith('/home')) return { tool: 'home', view: 'home' };
	if (pathname.startsWith('/policy')) return { tool: 'policy', view: pathname.split('/')[2] ?? 'policy' };
	if (pathname.startsWith('/notes')) return { tool: 'notes', view: 'notes' };
	if (pathname === '/' || pathname.startsWith('/c/')) return { tool: 'chat', view: 'chat' };
	return { tool: 'other', view: pathname.split('/')[1] || 'root' };
};

export const track = (name: ClientEventName, properties: Record<string, unknown> = {}): void => {
	if (!enabled) return;
	queue.push({ name, properties, session_id: sessionId() });
	if (queue.length >= FLUSH_AT) flushNow();
};

export const pageEnter = (pathname: string): void => {
	if (!enabled) return;
	const now = Date.now();
	if (currentPage) {
		track('page.leave', {
			tool: currentPage.tool,
			view: currentPage.view,
			path: currentPage.path,
			duration_ms: now - currentPage.since
		});
	}
	const { tool, view } = routeToTool(pathname);
	currentPage = { tool, view, path: pathname, since: now };
	track('page.view', { tool, view, path: pathname });
};

export const flushNow = (): void => {
	if (!enabled || !queue.length) return;
	const events = queue.splice(0, MAX_BATCH);
	// keepalive lets the request survive tab close and, unlike sendBeacon,
	// carries the Authorization header.
	fetch(`${WEBUI_API_BASE_URL}/usage/events`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', authorization: `Bearer ${token}` },
		body: JSON.stringify({ events }),
		keepalive: true
	}).catch(() => {
		// fire-and-forget: drop on failure
	});
};

export const initUsageTracking = (authToken: string, isEnabled: boolean): void => {
	enabled = isEnabled;
	token = authToken;
	if (!enabled || timer) return;
	timer = setInterval(flushNow, FLUSH_INTERVAL_MS);
	document.addEventListener('visibilitychange', () => {
		if (document.visibilityState === 'hidden') {
			if (currentPage) {
				track('page.leave', {
					tool: currentPage.tool,
					view: currentPage.view,
					path: currentPage.path,
					duration_ms: Date.now() - currentPage.since
				});
			}
			flushNow();
		} else if (currentPage) {
			// Reset on return so time spent hidden never counts into the
			// next page.leave duration.
			currentPage.since = Date.now();
		}
	});
};

export const _resetForTests = (): void => {
	queue = [];
	if (timer) clearInterval(timer);
	timer = null;
	enabled = false;
	token = '';
	currentPage = null;
};
```

- [ ] **Step 4: Run tests to verify they pass**

`npm run test:frontend -- src/lib/utils/usage.test.ts`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/utils/usage.ts src/lib/utils/usage.test.ts
git commit -m "feat(usage): frontend tracker with batching and page-view lifecycle"
```

---

### Task 8: Wire the tracker into the app

**Files:**
- Modify: `src/routes/+layout.svelte` (init + afterNavigate, next to the existing `beforeNavigate` ~line 100)
- Modify: `src/lib/components/workos/WorkOSApp.svelte` (view-switch events)
- Modify: `src/lib/components/workos/chrome/FilterBar.svelte` (search events)

**Interfaces:**
- Consumes: `initUsageTracking`, `pageEnter`, `track` (Task 7); `$config.features.enable_usage_tracking` (Task 2); WorkOS `view` store (`src/lib/components/workos/lib/store.ts:56`).
- Produces: live `page.view`/`page.leave`/`workos.view.switch`/`workos.search.used` events.

- [ ] **Step 1: Root layout wiring**

In `src/routes/+layout.svelte`: add `afterNavigate` to the existing `$app/navigation` import, import the tracker, and initialize once config + auth are available (find the spot where `config` and the session user are set after backend load — init there, matching that file's existing style):

```ts
import { afterNavigate } from '$app/navigation';
import { initUsageTracking, pageEnter } from '$lib/utils/usage';
```

```ts
// after config + session are established:
initUsageTracking(
	localStorage.token ?? '',
	$config?.features?.enable_usage_tracking ?? false
);
pageEnter(window.location.pathname);

afterNavigate((nav) => {
	if (nav.to?.url) pageEnter(nav.to.url.pathname);
});
```

No popstate listener needed for page views: WorkOS shallow-routing pushState only changes the query string, never the pathname — internal WorkOS view changes are covered by the `view` store subscription in Step 2. Guard so `initUsageTracking`/`pageEnter` run only for authenticated sessions (no tracking on `/auth`).

- [ ] **Step 2: WorkOS view-switch + search wiring**

In `src/lib/components/workos/WorkOSApp.svelte`, `onMount` (add to the existing onMount, keep its cleanup pattern):

```ts
import { track } from '$lib/utils/usage';
import { view } from './lib/store';

let firstView = true;
const unsubView = view.subscribe((v) => {
	if (firstView) {
		firstView = false;
		return;
	}
	track('workos.view.switch', { view: v });
});
onDestroy(unsubView);
```

For `workos.search.used`: there is NO dedicated search store (verified) — search text lives in the `text` field of the `TaskFilter` stores (`boardFilter`/`myWorkFilter`, store.ts:57-58), and `FilterBar.svelte` binds it via `bind:value={$filter.text}` (FilterBar.svelte:30). Instrument `FilterBar.svelte` directly (one spot covers board, list, and My Work) with a debounced reactive statement — do NOT subscribe to the filter stores in WorkOSApp, since those fire on every facet change (status/priority/labels/assignees), not just text:

```ts
// FilterBar.svelte <script>, alongside the existing helpers
import { onDestroy } from 'svelte';
import { track } from '$lib/utils/usage';

let searchTimer: ReturnType<typeof setTimeout> | null = null;
let lastTrackedText = '';
$: if ($filter.text !== lastTrackedText) {
	lastTrackedText = $filter.text;
	if ($filter.text) {
		if (searchTimer) clearTimeout(searchTimer);
		searchTimer = setTimeout(() => track('workos.search.used', {}), 2000);
	}
}
onDestroy(() => {
	if (searchTimer) clearTimeout(searchTimer);
});
```

- [ ] **Step 3: Static verification**

`npm run test:frontend` — all pass.
`npx svelte-check --threshold error 2>&1 | Select-String -Pattern "usage|WorkOSApp|FilterBar|\+layout" -Context 0,2` — no NEW errors in the touched files (the repo may have pre-existing warnings; compare against `git stash` state if unsure).

- [ ] **Step 4: Commit**

```bash
git add src/routes/+layout.svelte src/lib/components/workos/WorkOSApp.svelte src/lib/components/workos/chrome/FilterBar.svelte
git commit -m "feat(usage): wire tracker into root layout and WorkOS app"
```

---

### Task 9: Admin API client + Usage dashboard tab

**Files:**
- Modify: `src/lib/apis/analytics/index.ts` (append 5 fetch functions)
- Modify: `src/lib/components/admin/Analytics.svelte` (add tab bar)
- Create: `src/lib/components/admin/Analytics/Usage.svelte`
- Create: `src/lib/components/admin/Analytics/UsageUserModal.svelte`

**Interfaces:**
- Consumes: Task 5's endpoints (exact shapes listed there); `ChartLine.svelte` props `{ data: {date: string; models: Record<string, number>}[], models: string[], colors: string[], height?, period? }`.
- Produces: "Usage" tab in admin → Analytics.

- [ ] **Step 1: API client functions**

Append to `src/lib/apis/analytics/index.ts`, copying the exact fetch/error pattern of `getModelAnalytics` (token param, `WEBUI_API_BASE_URL`, throw `error`):

```ts
export const getUsageOverview = async (token: string = '', days: number = 30) => { /* GET /analytics/usage/overview?days= */ };
export const getUsageDaily = async (token: string = '', days: number = 30, tool: string | null = null) => { /* GET /analytics/usage/daily */ };
export const getUsageEventCounts = async (token: string = '', days: number = 30, tool: string | null = null) => { /* GET /analytics/usage/events */ };
export const getUsageUsers = async (token: string = '', days: number = 30, sort: string = 'events', page: number = 1) => { /* GET /analytics/usage/users */ };
export const getUsageUserActivity = async (token: string = '', userId: string, days: number = 30, page: number = 1, tool: string | null = null) => { /* GET /analytics/usage/users/{userId}/activity */ };
```

Each body is a full copy of the `getModelAnalytics` implementation with the URL/params swapped — write them out completely, comments above are route reminders only.

- [ ] **Step 2: Tab bar in Analytics.svelte**

Read `src/lib/components/admin/Analytics.svelte` first (it has an admin-role gate then renders `<Dashboard />`). Keep its script style (runes or legacy — match). Add a two-tab switcher above the content, styled like the admin section tabs in `src/routes/(app)/admin/+layout.svelte:70-78` (text links, active = default color, inactive = `text-gray-300`):

```svelte
<script>
	// ...existing imports/gate...
	import Usage from './Analytics/Usage.svelte';
	let tab = 'models';
</script>

<!-- after the gate, before <Dashboard /> -->
<div class="flex gap-3 mb-2">
	<button class="min-w-fit p-1.5 {tab === 'models' ? '' : 'text-gray-300 dark:text-gray-600'}" on:click={() => (tab = 'models')}>Models</button>
	<button class="min-w-fit p-1.5 {tab === 'usage' ? '' : 'text-gray-300 dark:text-gray-600'}" on:click={() => (tab = 'usage')}>Usage</button>
</div>
{#if tab === 'models'}
	<Dashboard />
{:else}
	<Usage />
{/if}
```

(Verified: `Analytics.svelte` is legacy Svelte 4 — `on:click` as written is correct. FYI a route `/admin/analytics/[tab]` already exists and currently ignores its param; driving `tab` from it would give deep-linkable tabs, but that's optional polish, not part of this task.)

- [ ] **Step 3: Usage.svelte**

`src/lib/components/admin/Analytics/Usage.svelte` — follow `Dashboard.svelte`'s structure (read it first: period select persisted to localStorage, card grid, table styling — mirror its classes). Content:

1. Period select: 7/30/90 days → `days` param, persisted as `localStorage.usageAnalyticsPeriod`.
2. Overview cards: one card per tool from `getUsageOverview` — tool name, `active_users` large, `events` + `avg_page_ms` (rendered as `Xm Ys`) small. Server-only tools (e.g. policy) legitimately have `sessions: 0` and `avg_page_ms: 0` (server events carry no session_id and no page.leave) — render a dash for zeros there, not a misleading `0m 0s`.
3. Daily chart: `<ChartLine data={dailyData} models={toolNames} colors={toolColors} />` where `toolNames` = union of tool keys across all days, `toolColors` = the color array Dashboard already uses (copy the inline `chartColors` at Dashboard.svelte:264-273), and days are zero-filled so every entry has every tool key: `dailyData = days.map((d) => ({ date: d.date, models: Object.fromEntries(toolNames.map((t) => [t, d.tools[t] ?? 0])) }))`.
4. Events table: event_name / tool / count / unique_users from `getUsageEventCounts`.
5. Users table: name / last_seen (relative date) / sessions / events / top tool from `getUsageUsers`, sort toggle (events|last_seen), pagination buttons; row click sets `selectedUser` + `showUserModal = true`.
6. Modal mechanism (verified): `Dashboard.svelte` uses two-way binding plus a callback prop, NOT events — `Modal.svelte` has no dispatcher, so `on:close` would silently never fire. Copy: `<UsageUserModal bind:show={showUserModal} user={selectedUser} {days} onClose={() => (selectedUser = null)} />` (same shape as `<AnalyticsModelModal bind:show=... onClose=.../>` at Dashboard.svelte:224-229).

All data loads in `onMount` via `Promise.all`, token from `localStorage.token` (same as Dashboard).

- [ ] **Step 4: UsageUserModal.svelte**

Pattern after `AnalyticsModelModal.svelte` (read it first — reuse its modal shell/close mechanics: props `show` + `onClose: () => void = () => {}`, shell `<Modal size="md" bind:show>`, local `close()` that resets state then calls `onClose()`). Content: the user's name as title, tool filter select, paginated list from `getUsageUserActivity`: rows of `created_at` (formatted datetime), `event_name`, `tool`, `source` badge. "Load more" button increments page and appends.

- [ ] **Step 5: Static verification**

`npm run test:frontend` — pass.
`npx svelte-check --threshold error` filtered to the four touched files — no new errors.

- [ ] **Step 6: Commit**

```bash
git add src/lib/apis/analytics/index.ts src/lib/components/admin/Analytics.svelte src/lib/components/admin/Analytics/Usage.svelte src/lib/components/admin/Analytics/UsageUserModal.svelte
git commit -m "feat(usage): admin Usage dashboard tab with per-user activity"
```

---

### Task 10: Full verification sweep

**Files:** none new.

- [ ] **Step 1: Full backend suite**

From `backend/`: `.venv/Scripts/python.exe -m pytest open_webui/test/ -q`
Expected: all pass.

- [ ] **Step 2: Full frontend suite**

`npm run test:frontend`
Expected: all pass.

- [ ] **Step 3: Migration dry-check**

Confirm exactly one migration file has `down_revision = 'c2d3e4f5a6b7'` (the new one) and no other file revises `d3e4f5a6b7c8`:

```bash
grep -rl "c2d3e4f5a6b7" backend/open_webui/migrations/versions/
```

Expected: exactly two files — the old head and the new migration.

- [ ] **Step 4: Report to user**

Summarize: what was built, test counts, and the smoke checklist. Remind the user: **restart the Docker container** (`osool-ai-open-webui-1`) so the Alembic migration applies before smoke. Browser smoke needs: (1) navigate between tools → page events appear in DB; (2) switch WorkOS views; (3) create/complete a task; (4) send a chat message; (5) approve a policy review; (6) admin → Analytics → Usage tab shows all of it; (7) per-user drawer; (8) non-admin cannot load `/api/v1/analytics/usage/*`. Do NOT start a Vite server without asking.

- [ ] **Step 5: Commit any stragglers**

```bash
git status
git add -A && git commit -m "chore(usage): verification fixes"
```

(Only if the sweep produced fixes; otherwise skip.)
