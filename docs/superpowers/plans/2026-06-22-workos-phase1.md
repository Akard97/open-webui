# WorkOS Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the WorkOS task-management spine inside Osool — persisted Team→Workspace→Workstream→Task hierarchy with membership/roles, Board + List views, a task-detail slide-over, realtime updates, and a lean admin center — replacing the `/workos` placeholder.

**Architecture:** Mirror the Policy Review tool. Backend: SQLAlchemy tables + async DAO (`models/workos.py`), a FastAPI router at `/api/v1/workos` (`routers/workos.py`), an Alembic migration, an env-gated seeder, and Socket.IO handlers for realtime. Frontend: a self-contained tool under `src/lib/components/workos/` (writable/derived Svelte stores, fetch wrappers, chrome + views + admin), reusing shared primitives where they exist.

**Tech Stack:** Python 3.11/3.12, FastAPI 0.135.1, SQLAlchemy 2.0.48 (async), Alembic 1.18.4, python-socketio 5.16.1, pytest + pytest-asyncio, httpx ASGITransport. Frontend: SvelteKit (Svelte 5), TypeScript, Tailwind, vitest, sortablejs 1.15.6.

## Global Constraints

- **Spec:** `docs/superpowers/specs/2026-06-22-workos-phase1-design.md` — this plan implements it section by section.
- **DB id convention:** all primary keys are `Text` UUID strings via `str(uuid.uuid4())`.
- **Timestamps:** `created_at`/`updated_at`/`completed_at` are nanosecond epochs via `int(time.time_ns())` (helper `_now()`). `due_date` is a millisecond epoch (nullable).
- **User references** (`*_id` pointing at OWUI users) are `Text` columns, NOT enforced DB FKs (matches OWUI convention).
- **Async DB:** routers inject `db: AsyncSession = Depends(get_async_session)`; DAO methods take `db: Optional[AsyncSession] = None` and wrap with `async with get_async_db_context(db) as db:`.
- **Auth:** every route uses `user=Depends(get_verified_user)` and `request: Request`. Permission gate via `has_permission(user.id, 'features.<key>', request.app.state.config.USER_PERMISSIONS, db=db)`; system admins (`user.role == 'admin'`) always pass.
- **Permission keys:** `features.workos` (use the tool) and `features.workos_admin` (admin center).
- **Router prefix:** `/api/v1/workos`, tag `workos`.
- **Quotes/format:** single quotes in Python (ruff `flake8-quotes.inline-quotes = single`), line length 120, `black --skip-string-normalization`. TypeScript uses single quotes.
- **Statuses (fixed):** `backlog`, `todo`, `in_progress`, `in_review`, `done`, `canceled`. Status display order: `backlog, todo, in_progress, in_review, done` (canceled hidden from board columns, shown only when set).
- **Priorities (fixed):** `urgent`, `high`, `medium`, `low`, plus `null` (no priority).
- **Roles:** Team `owner`/`admin`/`member`; Workspace `admin`/`member`.
- **Migration chain:** new migration's `down_revision = 'c3d4e5f6a7b8'` (current Alembic head). alembic.ini is at `backend/open_webui/alembic.ini`.
- **Backend tests:** live under `backend/open_webui/test/workos/`; run from `backend/` with `python -m pytest open_webui/test/workos/ -v`. Use `@pytest.mark.asyncio` on async tests.
- **Frontend tests:** vitest, run `npm run test:frontend -- <path>`. Frontend code lives under `src/lib/components/workos/`.
- **Socket rooms:** `workos:workstream:{id}` (task events) and `workos:team:{id}` (nav events). Reuse `from open_webui.socket.main import sio, emit_to_users`.
- **Commit style:** conventional commits, scope `workos`. End commit body with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Branch is `osool` (not main) — commit there.

---

## Backend

### Task 1: Permission flags + global rules config

**Files:**
- Modify: `backend/open_webui/config.py` (add env vars ~line 1577; add features keys after `policy_admin` ~line 1654; add `WORKOS_RULES` PersistentConfig near other PersistentConfigs)
- Test: `backend/open_webui/test/workos/test_config.py`
- Create: `backend/open_webui/test/workos/__init__.py` (empty)

**Interfaces:**
- Produces: `DEFAULT_USER_PERMISSIONS['features']['workos']` and `['workos_admin']` (bools); `WORKOS_RULES` PersistentConfig at config path `workos.rules` defaulting to `{'team_creation': 'all_users', 'default_workspace_visibility': 'team'}`.

- [ ] **Step 1: Write the failing test**

Create `backend/open_webui/test/workos/__init__.py` (empty), then `backend/open_webui/test/workos/test_config.py`:

```python
def test_workos_permission_flags_present():
    from open_webui.config import DEFAULT_USER_PERMISSIONS

    features = DEFAULT_USER_PERMISSIONS['features']
    assert 'workos' in features
    assert 'workos_admin' in features
    assert isinstance(features['workos'], bool)
    assert isinstance(features['workos_admin'], bool)


def test_workos_rules_default():
    from open_webui.config import WORKOS_RULES

    assert WORKOS_RULES.value['team_creation'] in ('all_users', 'admins_only')
    assert WORKOS_RULES.value['default_workspace_visibility'] in ('team', 'restricted')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest open_webui/test/workos/test_config.py -v`
Expected: FAIL — `KeyError: 'workos'` (and ImportError for `WORKOS_RULES`).

- [ ] **Step 3: Implement the config changes**

In `backend/open_webui/config.py`, after the `USER_PERMISSIONS_FEATURES_POLICY_ADMIN` env block (~line 1576) add:

```python
USER_PERMISSIONS_FEATURES_WORKOS = (
    os.environ.get('USER_PERMISSIONS_FEATURES_WORKOS', 'True').lower() == 'true'
)

USER_PERMISSIONS_FEATURES_WORKOS_ADMIN = (
    os.environ.get('USER_PERMISSIONS_FEATURES_WORKOS_ADMIN', 'False').lower() == 'true'
)
```

In the `DEFAULT_USER_PERMISSIONS['features']` dict, after the `'policy_admin': ...` line add:

```python
        'workos': USER_PERMISSIONS_FEATURES_WORKOS,
        'workos_admin': USER_PERMISSIONS_FEATURES_WORKOS_ADMIN,
```

After the `USER_PERMISSIONS = PersistentConfig(...)` block, add (note `json` is already imported in config.py):

```python
WORKOS_RULES = PersistentConfig(
    'WORKOS_RULES',
    'workos.rules',
    json.loads(
        os.environ.get(
            'WORKOS_RULES',
            '{"team_creation": "all_users", "default_workspace_visibility": "team"}',
        )
    ),
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest open_webui/test/workos/test_config.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/config.py backend/open_webui/test/workos/
git commit -m "feat(workos): add features.workos/workos_admin permissions + rules config"
```

---

### Task 2: Models — Team + TeamMember DAO

**Files:**
- Create: `backend/open_webui/models/workos.py`
- Test: `backend/open_webui/test/workos/conftest.py`, `backend/open_webui/test/workos/test_models_team.py`

**Interfaces:**
- Produces: tables `WorkosTeam`, `WorkosTeamMember`; Pydantic `TeamModel`, `TeamMemberModel`; DAO singletons `Teams`, `TeamMembers` with:
  - `Teams.insert(name, key, icon, created_by_id, db=None) -> TeamModel`
  - `Teams.get_by_id(id, db=None) -> Optional[TeamModel]`
  - `Teams.get_by_key(key, db=None) -> Optional[TeamModel]`
  - `Teams.list_for_user(user_id, db=None) -> list[TeamModel]` (teams the user is a member of)
  - `Teams.list_all(db=None) -> list[TeamModel]`
  - `Teams.update_fields(id, fields, db=None) -> Optional[TeamModel]`
  - `Teams.delete(id, db=None) -> bool`
  - `Teams.next_task_number(team_id, db=None) -> int` (atomic increment of `task_seq`, returns new value)
  - `TeamMembers.add(team_id, user_id, role, db=None) -> TeamMemberModel`
  - `TeamMembers.get(team_id, user_id, db=None) -> Optional[TeamMemberModel]`
  - `TeamMembers.list_for_team(team_id, db=None) -> list[TeamMemberModel]`
  - `TeamMembers.list_for_user(user_id, db=None) -> list[TeamMemberModel]`
  - `TeamMembers.update_role(team_id, user_id, role, db=None) -> Optional[TeamMemberModel]`
  - `TeamMembers.remove(team_id, user_id, db=None) -> bool`

- [ ] **Step 1: Write the failing test**

Create `backend/open_webui/test/workos/conftest.py` (copied from the policy_review conftest pattern; registers the workos tables on `Base`):

```python
import os
import tempfile

_DB_FILE = tempfile.mktemp(suffix='.db')
os.environ['DATABASE_URL'] = f'sqlite:///{_DB_FILE}'
os.environ['ENABLE_DB_MIGRATIONS'] = 'false'

import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402

from open_webui.internal.db import Base, async_engine, engine  # noqa: E402
import open_webui.models.workos  # noqa: E402,F401  (register tables on Base)

with engine.begin() as _conn:
    _conn.execute(
        text(
            'CREATE TABLE IF NOT EXISTS config ('
            'id INTEGER PRIMARY KEY, data JSON, version INTEGER, '
            'created_at TIMESTAMP, updated_at TIMESTAMP)'
        )
    )


@pytest_asyncio.fixture(autouse=True)
async def _create_schema():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
```

Create `backend/open_webui/test/workos/test_models_team.py`:

```python
import pytest

from open_webui.models.workos import Teams, TeamMembers


@pytest.mark.asyncio
async def test_insert_and_get_team():
    team = await Teams.insert(name='Acme', key='OSL', icon=None, created_by_id='u1')
    assert team.name == 'Acme'
    assert team.key == 'OSL'
    assert team.task_seq == 0
    got = await Teams.get_by_id(team.id)
    assert got is not None and got.id == team.id
    assert (await Teams.get_by_key('OSL')).id == team.id


@pytest.mark.asyncio
async def test_next_task_number_increments_atomically():
    team = await Teams.insert(name='Acme', key='OSL', icon=None, created_by_id='u1')
    n1 = await Teams.next_task_number(team.id)
    n2 = await Teams.next_task_number(team.id)
    assert (n1, n2) == (1, 2)
    assert (await Teams.get_by_id(team.id)).task_seq == 2


@pytest.mark.asyncio
async def test_membership_add_list_role_remove():
    team = await Teams.insert(name='Acme', key='OSL', icon=None, created_by_id='u1')
    await TeamMembers.add(team.id, 'u1', 'owner')
    await TeamMembers.add(team.id, 'u2', 'member')
    assert {m.user_id for m in await TeamMembers.list_for_team(team.id)} == {'u1', 'u2'}
    assert (await TeamMembers.get(team.id, 'u1')).role == 'owner'
    await TeamMembers.update_role(team.id, 'u2', 'admin')
    assert (await TeamMembers.get(team.id, 'u2')).role == 'admin'
    assert [t.id for t in await Teams.list_for_user('u2')] == [team.id]
    assert await TeamMembers.remove(team.id, 'u2') is True
    assert await TeamMembers.get(team.id, 'u2') is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest open_webui/test/workos/test_models_team.py -v`
Expected: FAIL — `ModuleNotFoundError`/`ImportError: cannot import name 'Teams'`.

- [ ] **Step 3: Implement `models/workos.py` (Team + TeamMember portion)**

Create `backend/open_webui/models/workos.py`:

```python
import time
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Float,
    Integer,
    JSON,
    Text,
    UniqueConstraint,
    select,
    delete,
)
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.internal.db import Base, get_async_db_context


def _now() -> int:
    return int(time.time_ns())


def _id() -> str:
    return str(uuid.uuid4())


# ──────────────────────────── Tables ────────────────────────────


class WorkosTeam(Base):
    __tablename__ = 'workos_team'

    id = Column(Text, primary_key=True, unique=True)
    key = Column(Text, unique=True)
    name = Column(Text)
    icon = Column(Text, nullable=True)
    task_seq = Column(BigInteger, default=0)
    archived = Column(Boolean, default=False)
    created_by_id = Column(Text, nullable=True)
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


class WorkosTeamMember(Base):
    __tablename__ = 'workos_team_member'
    __table_args__ = (UniqueConstraint('team_id', 'user_id', name='uq_workos_team_member'),)

    id = Column(Text, primary_key=True, unique=True)
    team_id = Column(Text)
    user_id = Column(Text)
    role = Column(Text)  # owner | admin | member
    created_at = Column(BigInteger)


# ──────────────────────────── Pydantic ────────────────────────────


class TeamModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    key: str
    name: str
    icon: Optional[str] = None
    task_seq: int
    archived: bool
    created_by_id: Optional[str] = None
    created_at: int
    updated_at: int


class TeamMemberModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    team_id: str
    user_id: str
    role: str
    created_at: int


# ──────────────────────────── DAO ────────────────────────────


class TeamsDao:
    async def insert(
        self, name: str, key: str, icon: Optional[str], created_by_id: Optional[str],
        db: Optional[AsyncSession] = None,
    ) -> TeamModel:
        async with get_async_db_context(db) as db:
            row = WorkosTeam(
                id=_id(), key=key, name=name, icon=icon, task_seq=0, archived=False,
                created_by_id=created_by_id, created_at=_now(), updated_at=_now(),
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return TeamModel.model_validate(row)

    async def get_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[TeamModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTeam).filter_by(id=id))
            row = res.scalars().first()
            return TeamModel.model_validate(row) if row else None

    async def get_by_key(self, key: str, db: Optional[AsyncSession] = None) -> Optional[TeamModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTeam).filter_by(key=key))
            row = res.scalars().first()
            return TeamModel.model_validate(row) if row else None

    async def list_all(self, db: Optional[AsyncSession] = None) -> list[TeamModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTeam).order_by(WorkosTeam.created_at.desc()))
            return [TeamModel.model_validate(r) for r in res.scalars().all()]

    async def list_for_user(self, user_id: str, db: Optional[AsyncSession] = None) -> list[TeamModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosTeam)
                .join(WorkosTeamMember, WorkosTeamMember.team_id == WorkosTeam.id)
                .filter(WorkosTeamMember.user_id == user_id)
                .order_by(WorkosTeam.created_at.desc())
            )
            return [TeamModel.model_validate(r) for r in res.scalars().all()]

    async def update_fields(self, id: str, fields: dict, db: Optional[AsyncSession] = None) -> Optional[TeamModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTeam).filter_by(id=id))
            row = res.scalars().first()
            if not row:
                return None
            for k, v in fields.items():
                setattr(row, k, v)
            row.updated_at = _now()
            await db.commit()
            await db.refresh(row)
            return TeamModel.model_validate(row)

    async def delete(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTeam).filter_by(id=id))
            if not res.scalars().first():
                return False
            await db.execute(delete(WorkosTeam).filter_by(id=id))
            await db.commit()
            return True

    async def next_task_number(self, team_id: str, db: Optional[AsyncSession] = None) -> int:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTeam).filter_by(id=team_id).with_for_update())
            row = res.scalars().first()
            if not row:
                raise ValueError('team not found')
            row.task_seq = (row.task_seq or 0) + 1
            new_value = row.task_seq
            await db.commit()
            return new_value


class TeamMembersDao:
    async def add(self, team_id: str, user_id: str, role: str, db: Optional[AsyncSession] = None) -> TeamMemberModel:
        async with get_async_db_context(db) as db:
            row = WorkosTeamMember(id=_id(), team_id=team_id, user_id=user_id, role=role, created_at=_now())
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return TeamMemberModel.model_validate(row)

    async def get(self, team_id: str, user_id: str, db: Optional[AsyncSession] = None) -> Optional[TeamMemberModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTeamMember).filter_by(team_id=team_id, user_id=user_id))
            row = res.scalars().first()
            return TeamMemberModel.model_validate(row) if row else None

    async def list_for_team(self, team_id: str, db: Optional[AsyncSession] = None) -> list[TeamMemberModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTeamMember).filter_by(team_id=team_id))
            return [TeamMemberModel.model_validate(r) for r in res.scalars().all()]

    async def list_for_user(self, user_id: str, db: Optional[AsyncSession] = None) -> list[TeamMemberModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTeamMember).filter_by(user_id=user_id))
            return [TeamMemberModel.model_validate(r) for r in res.scalars().all()]

    async def update_role(
        self, team_id: str, user_id: str, role: str, db: Optional[AsyncSession] = None
    ) -> Optional[TeamMemberModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTeamMember).filter_by(team_id=team_id, user_id=user_id))
            row = res.scalars().first()
            if not row:
                return None
            row.role = role
            await db.commit()
            await db.refresh(row)
            return TeamMemberModel.model_validate(row)

    async def remove(self, team_id: str, user_id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTeamMember).filter_by(team_id=team_id, user_id=user_id))
            if not res.scalars().first():
                return False
            await db.execute(delete(WorkosTeamMember).filter_by(team_id=team_id, user_id=user_id))
            await db.commit()
            return True


Teams = TeamsDao()
TeamMembers = TeamMembersDao()
```

> Note: `with_for_update()` is a no-op on SQLite but correct on Postgres; the test asserts sequential increments which holds on both.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest open_webui/test/workos/test_models_team.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/models/workos.py backend/open_webui/test/workos/conftest.py backend/open_webui/test/workos/test_models_team.py
git commit -m "feat(workos): add Team + TeamMember models and DAO"
```

---

### Task 3: Models — Workspace, WorkspaceMember, Workstream DAO

**Files:**
- Modify: `backend/open_webui/models/workos.py` (append tables, Pydantic, DAO)
- Test: `backend/open_webui/test/workos/test_models_workspace.py`

**Interfaces:**
- Consumes: `Base`, `_now`, `_id`, `get_async_db_context` from Task 2.
- Produces: tables `WorkosWorkspace`, `WorkosWorkspaceMember`, `WorkosWorkstream`; models `WorkspaceModel`, `WorkspaceMemberModel`, `WorkstreamModel`; DAO singletons `Workspaces`, `WorkspaceMembers`, `Workstreams` with:
  - `Workspaces.insert(team_id, name, icon, visibility, created_by_id, db=None) -> WorkspaceModel`
  - `Workspaces.get_by_id(id, db=None)`, `Workspaces.list_for_team(team_id, db=None)`, `Workspaces.update_fields(id, fields, db=None)`, `Workspaces.delete(id, db=None)`
  - `WorkspaceMembers.add/get/list_for_workspace/update_role/remove` (same shape as `TeamMembers`, role `admin`/`member`)
  - `Workstreams.insert(workspace_id, name, icon, created_by_id, db=None) -> WorkstreamModel`
  - `Workstreams.get_by_id(id, db=None)`, `Workstreams.list_for_workspace(workspace_id, db=None)`, `Workstreams.update_fields(id, fields, db=None)`, `Workstreams.delete(id, db=None)`

- [ ] **Step 1: Write the failing test**

Create `backend/open_webui/test/workos/test_models_workspace.py`:

```python
import pytest

from open_webui.models.workos import Teams, Workspaces, WorkspaceMembers, Workstreams


@pytest.mark.asyncio
async def test_workspace_crud_and_listing():
    team = await Teams.insert('Acme', 'OSL', None, 'u1')
    ws = await Workspaces.insert(team.id, 'Engineering', 'briefcase', 'team', 'u1')
    assert ws.visibility == 'team'
    assert [w.id for w in await Workspaces.list_for_team(team.id)] == [ws.id]
    ws2 = await Workspaces.update_fields(ws.id, {'name': 'Eng', 'visibility': 'restricted'})
    assert ws2.name == 'Eng' and ws2.visibility == 'restricted'
    assert await Workspaces.delete(ws.id) is True
    assert await Workspaces.get_by_id(ws.id) is None


@pytest.mark.asyncio
async def test_workspace_membership():
    team = await Teams.insert('Acme', 'OSL', None, 'u1')
    ws = await Workspaces.insert(team.id, 'Engineering', None, 'restricted', 'u1')
    await WorkspaceMembers.add(ws.id, 'u2', 'member')
    assert (await WorkspaceMembers.get(ws.id, 'u2')).role == 'member'
    await WorkspaceMembers.update_role(ws.id, 'u2', 'admin')
    assert (await WorkspaceMembers.get(ws.id, 'u2')).role == 'admin'
    assert {m.user_id for m in await WorkspaceMembers.list_for_workspace(ws.id)} == {'u2'}
    assert await WorkspaceMembers.remove(ws.id, 'u2') is True


@pytest.mark.asyncio
async def test_workstream_crud():
    team = await Teams.insert('Acme', 'OSL', None, 'u1')
    ws = await Workspaces.insert(team.id, 'Engineering', None, 'team', 'u1')
    s = await Workstreams.insert(ws.id, 'Platform', 'layers', 'u1')
    assert [x.id for x in await Workstreams.list_for_workspace(ws.id)] == [s.id]
    s2 = await Workstreams.update_fields(s.id, {'name': 'Core'})
    assert s2.name == 'Core'
    assert await Workstreams.delete(s.id) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest open_webui/test/workos/test_models_workspace.py -v`
Expected: FAIL — `ImportError: cannot import name 'Workspaces'`.

- [ ] **Step 3: Implement (append to `models/workos.py`)**

Add tables (after `WorkosTeamMember`):

```python
class WorkosWorkspace(Base):
    __tablename__ = 'workos_workspace'

    id = Column(Text, primary_key=True, unique=True)
    team_id = Column(Text)
    name = Column(Text)
    icon = Column(Text, nullable=True)
    visibility = Column(Text, default='team')  # team | restricted
    archived = Column(Boolean, default=False)
    created_by_id = Column(Text, nullable=True)
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


class WorkosWorkspaceMember(Base):
    __tablename__ = 'workos_workspace_member'
    __table_args__ = (UniqueConstraint('workspace_id', 'user_id', name='uq_workos_workspace_member'),)

    id = Column(Text, primary_key=True, unique=True)
    workspace_id = Column(Text)
    user_id = Column(Text)
    role = Column(Text)  # admin | member
    created_at = Column(BigInteger)


class WorkosWorkstream(Base):
    __tablename__ = 'workos_workstream'

    id = Column(Text, primary_key=True, unique=True)
    workspace_id = Column(Text)
    name = Column(Text)
    icon = Column(Text, nullable=True)
    archived = Column(Boolean, default=False)
    created_by_id = Column(Text, nullable=True)
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)
```

Add Pydantic models (after `TeamMemberModel`):

```python
class WorkspaceModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    team_id: str
    name: str
    icon: Optional[str] = None
    visibility: str
    archived: bool
    created_by_id: Optional[str] = None
    created_at: int
    updated_at: int


class WorkspaceMemberModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    user_id: str
    role: str
    created_at: int


class WorkstreamModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspace_id: str
    name: str
    icon: Optional[str] = None
    archived: bool
    created_by_id: Optional[str] = None
    created_at: int
    updated_at: int
```

Add DAO classes (before the singleton assignments at the bottom):

```python
class WorkspacesDao:
    async def insert(
        self, team_id: str, name: str, icon: Optional[str], visibility: str,
        created_by_id: Optional[str], db: Optional[AsyncSession] = None,
    ) -> WorkspaceModel:
        async with get_async_db_context(db) as db:
            row = WorkosWorkspace(
                id=_id(), team_id=team_id, name=name, icon=icon, visibility=visibility,
                archived=False, created_by_id=created_by_id, created_at=_now(), updated_at=_now(),
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return WorkspaceModel.model_validate(row)

    async def get_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[WorkspaceModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosWorkspace).filter_by(id=id))
            row = res.scalars().first()
            return WorkspaceModel.model_validate(row) if row else None

    async def list_for_team(self, team_id: str, db: Optional[AsyncSession] = None) -> list[WorkspaceModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosWorkspace).filter_by(team_id=team_id).order_by(WorkosWorkspace.created_at.asc())
            )
            return [WorkspaceModel.model_validate(r) for r in res.scalars().all()]

    async def update_fields(self, id: str, fields: dict, db: Optional[AsyncSession] = None) -> Optional[WorkspaceModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosWorkspace).filter_by(id=id))
            row = res.scalars().first()
            if not row:
                return None
            for k, v in fields.items():
                setattr(row, k, v)
            row.updated_at = _now()
            await db.commit()
            await db.refresh(row)
            return WorkspaceModel.model_validate(row)

    async def delete(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosWorkspace).filter_by(id=id))
            if not res.scalars().first():
                return False
            await db.execute(delete(WorkosWorkspace).filter_by(id=id))
            await db.commit()
            return True


class WorkspaceMembersDao:
    async def add(
        self, workspace_id: str, user_id: str, role: str, db: Optional[AsyncSession] = None
    ) -> WorkspaceMemberModel:
        async with get_async_db_context(db) as db:
            row = WorkosWorkspaceMember(
                id=_id(), workspace_id=workspace_id, user_id=user_id, role=role, created_at=_now()
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return WorkspaceMemberModel.model_validate(row)

    async def get(
        self, workspace_id: str, user_id: str, db: Optional[AsyncSession] = None
    ) -> Optional[WorkspaceMemberModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosWorkspaceMember).filter_by(workspace_id=workspace_id, user_id=user_id))
            row = res.scalars().first()
            return WorkspaceMemberModel.model_validate(row) if row else None

    async def list_for_workspace(
        self, workspace_id: str, db: Optional[AsyncSession] = None
    ) -> list[WorkspaceMemberModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosWorkspaceMember).filter_by(workspace_id=workspace_id))
            return [WorkspaceMemberModel.model_validate(r) for r in res.scalars().all()]

    async def update_role(
        self, workspace_id: str, user_id: str, role: str, db: Optional[AsyncSession] = None
    ) -> Optional[WorkspaceMemberModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosWorkspaceMember).filter_by(workspace_id=workspace_id, user_id=user_id))
            row = res.scalars().first()
            if not row:
                return None
            row.role = role
            await db.commit()
            await db.refresh(row)
            return WorkspaceMemberModel.model_validate(row)

    async def remove(self, workspace_id: str, user_id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosWorkspaceMember).filter_by(workspace_id=workspace_id, user_id=user_id))
            if not res.scalars().first():
                return False
            await db.execute(delete(WorkosWorkspaceMember).filter_by(workspace_id=workspace_id, user_id=user_id))
            await db.commit()
            return True


class WorkstreamsDao:
    async def insert(
        self, workspace_id: str, name: str, icon: Optional[str], created_by_id: Optional[str],
        db: Optional[AsyncSession] = None,
    ) -> WorkstreamModel:
        async with get_async_db_context(db) as db:
            row = WorkosWorkstream(
                id=_id(), workspace_id=workspace_id, name=name, icon=icon, archived=False,
                created_by_id=created_by_id, created_at=_now(), updated_at=_now(),
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return WorkstreamModel.model_validate(row)

    async def get_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[WorkstreamModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosWorkstream).filter_by(id=id))
            row = res.scalars().first()
            return WorkstreamModel.model_validate(row) if row else None

    async def list_for_workspace(self, workspace_id: str, db: Optional[AsyncSession] = None) -> list[WorkstreamModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosWorkstream).filter_by(workspace_id=workspace_id).order_by(WorkosWorkstream.created_at.asc())
            )
            return [WorkstreamModel.model_validate(r) for r in res.scalars().all()]

    async def update_fields(self, id: str, fields: dict, db: Optional[AsyncSession] = None) -> Optional[WorkstreamModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosWorkstream).filter_by(id=id))
            row = res.scalars().first()
            if not row:
                return None
            for k, v in fields.items():
                setattr(row, k, v)
            row.updated_at = _now()
            await db.commit()
            await db.refresh(row)
            return WorkstreamModel.model_validate(row)

    async def delete(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosWorkstream).filter_by(id=id))
            if not res.scalars().first():
                return False
            await db.execute(delete(WorkosWorkstream).filter_by(id=id))
            await db.commit()
            return True
```

Add to the singleton block at the bottom:

```python
Workspaces = WorkspacesDao()
WorkspaceMembers = WorkspaceMembersDao()
Workstreams = WorkstreamsDao()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest open_webui/test/workos/test_models_workspace.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/models/workos.py backend/open_webui/test/workos/test_models_workspace.py
git commit -m "feat(workos): add Workspace, WorkspaceMember, Workstream models and DAO"
```

---

### Task 4: Models — Label + Task DAO (key generation, sort_key)

**Files:**
- Modify: `backend/open_webui/models/workos.py`
- Test: `backend/open_webui/test/workos/test_models_task.py`

**Interfaces:**
- Consumes: `Teams.next_task_number`, helpers from Task 2.
- Produces: tables `WorkosLabel`, `WorkosTask`; models `LabelModel`, `TaskModel`; DAO singletons `Labels`, `Tasks` with:
  - `Labels.insert(team_id, name, color, db=None)`, `Labels.list_for_team(team_id, db=None)`, `Labels.update_fields(id, fields, db=None)`, `Labels.delete(id, db=None)`
  - `Tasks.insert(workstream_id, team_id, team_key, title, created_by_id, *, description=None, status='backlog', priority=None, assignee_id=None, due_date=None, labels=None, db=None) -> TaskModel` (computes `number` via `Teams.next_task_number`, `key=f'{team_key}-{number}'`, `sort_key=_now()` float)
  - `Tasks.get_by_id(id, db=None)`, `Tasks.list_for_workstream(workstream_id, db=None)` (ordered by `status` then `sort_key`), `Tasks.update_fields(id, fields, db=None)`, `Tasks.delete(id, db=None)`

- [ ] **Step 1: Write the failing test**

Create `backend/open_webui/test/workos/test_models_task.py`:

```python
import pytest

from open_webui.models.workos import Teams, Workspaces, Workstreams, Labels, Tasks


async def _stream():
    team = await Teams.insert('Acme', 'OSL', None, 'u1')
    ws = await Workspaces.insert(team.id, 'Engineering', None, 'team', 'u1')
    s = await Workstreams.insert(ws.id, 'Platform', None, 'u1')
    return team, s


@pytest.mark.asyncio
async def test_task_create_generates_sequential_keys():
    team, s = await _stream()
    t1 = await Tasks.insert(s.id, team.id, team.key, 'First', 'u1')
    t2 = await Tasks.insert(s.id, team.id, team.key, 'Second', 'u1')
    assert t1.key == 'OSL-1' and t1.number == 1
    assert t2.key == 'OSL-2' and t2.number == 2
    assert t1.status == 'backlog' and t1.priority is None and t1.progress == 0
    assert t1.labels == []


@pytest.mark.asyncio
async def test_task_update_and_list_order():
    team, s = await _stream()
    a = await Tasks.insert(s.id, team.id, team.key, 'A', 'u1')
    b = await Tasks.insert(s.id, team.id, team.key, 'B', 'u1')
    await Tasks.update_fields(a.id, {'status': 'todo', 'sort_key': 200.0})
    await Tasks.update_fields(b.id, {'status': 'todo', 'sort_key': 100.0})
    ordered = await Tasks.list_for_workstream(s.id)
    todo = [t.key for t in ordered if t.status == 'todo']
    assert todo == [b.key, a.key]  # ascending sort_key within status


@pytest.mark.asyncio
async def test_labels_crud():
    team, _ = await _stream()
    lab = await Labels.insert(team.id, 'backend', 'cyan')
    assert [x.id for x in await Labels.list_for_team(team.id)] == [lab.id]
    lab2 = await Labels.update_fields(lab.id, {'name': 'infra'})
    assert lab2.name == 'infra'
    assert await Labels.delete(lab.id) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest open_webui/test/workos/test_models_task.py -v`
Expected: FAIL — `ImportError: cannot import name 'Tasks'`.

- [ ] **Step 3: Implement (append to `models/workos.py`)**

Add tables:

```python
class WorkosLabel(Base):
    __tablename__ = 'workos_label'

    id = Column(Text, primary_key=True, unique=True)
    team_id = Column(Text)
    name = Column(Text)
    color = Column(Text)
    created_at = Column(BigInteger)


class WorkosTask(Base):
    __tablename__ = 'workos_task'

    id = Column(Text, primary_key=True, unique=True)
    workstream_id = Column(Text)
    team_id = Column(Text)
    number = Column(BigInteger)
    key = Column(Text)
    title = Column(Text)
    description = Column(Text, nullable=True)
    status = Column(Text, default='backlog')
    priority = Column(Text, nullable=True)
    assignee_id = Column(Text, nullable=True)
    due_date = Column(BigInteger, nullable=True)
    progress = Column(Integer, default=0)
    labels = Column(JSON, default=list)
    sort_key = Column(Float, default=0.0)
    created_by_id = Column(Text, nullable=True)
    completed_at = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)
```

Add Pydantic models:

```python
class LabelModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    team_id: str
    name: str
    color: str
    created_at: int


class TaskModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workstream_id: str
    team_id: str
    number: int
    key: str
    title: str
    description: Optional[str] = None
    status: str
    priority: Optional[str] = None
    assignee_id: Optional[str] = None
    due_date: Optional[int] = None
    progress: int
    labels: list = []
    sort_key: float
    created_by_id: Optional[str] = None
    completed_at: Optional[int] = None
    created_at: int
    updated_at: int
```

Add DAO classes:

```python
class LabelsDao:
    async def insert(self, team_id: str, name: str, color: str, db: Optional[AsyncSession] = None) -> LabelModel:
        async with get_async_db_context(db) as db:
            row = WorkosLabel(id=_id(), team_id=team_id, name=name, color=color, created_at=_now())
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return LabelModel.model_validate(row)

    async def list_for_team(self, team_id: str, db: Optional[AsyncSession] = None) -> list[LabelModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosLabel).filter_by(team_id=team_id).order_by(WorkosLabel.created_at.asc()))
            return [LabelModel.model_validate(r) for r in res.scalars().all()]

    async def update_fields(self, id: str, fields: dict, db: Optional[AsyncSession] = None) -> Optional[LabelModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosLabel).filter_by(id=id))
            row = res.scalars().first()
            if not row:
                return None
            for k, v in fields.items():
                setattr(row, k, v)
            await db.commit()
            await db.refresh(row)
            return LabelModel.model_validate(row)

    async def delete(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosLabel).filter_by(id=id))
            if not res.scalars().first():
                return False
            await db.execute(delete(WorkosLabel).filter_by(id=id))
            await db.commit()
            return True


class TasksDao:
    async def insert(
        self, workstream_id: str, team_id: str, team_key: str, title: str, created_by_id: Optional[str],
        *, description: Optional[str] = None, status: str = 'backlog', priority: Optional[str] = None,
        assignee_id: Optional[str] = None, due_date: Optional[int] = None, labels: Optional[list] = None,
        db: Optional[AsyncSession] = None,
    ) -> TaskModel:
        number = await Teams.next_task_number(team_id, db=db)
        async with get_async_db_context(db) as db:
            now = _now()
            row = WorkosTask(
                id=_id(), workstream_id=workstream_id, team_id=team_id, number=number,
                key=f'{team_key}-{number}', title=title, description=description, status=status,
                priority=priority, assignee_id=assignee_id, due_date=due_date, progress=0,
                labels=labels or [], sort_key=float(now), created_by_id=created_by_id,
                completed_at=now if status == 'done' else None, created_at=now, updated_at=now,
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return TaskModel.model_validate(row)

    async def get_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[TaskModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTask).filter_by(id=id))
            row = res.scalars().first()
            return TaskModel.model_validate(row) if row else None

    async def list_for_workstream(self, workstream_id: str, db: Optional[AsyncSession] = None) -> list[TaskModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosTask).filter_by(workstream_id=workstream_id)
                .order_by(WorkosTask.status.asc(), WorkosTask.sort_key.asc())
            )
            return [TaskModel.model_validate(r) for r in res.scalars().all()]

    async def update_fields(self, id: str, fields: dict, db: Optional[AsyncSession] = None) -> Optional[TaskModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTask).filter_by(id=id))
            row = res.scalars().first()
            if not row:
                return None
            for k, v in fields.items():
                setattr(row, k, v)
            if 'status' in fields:
                row.completed_at = _now() if fields['status'] == 'done' else None
            row.updated_at = _now()
            await db.commit()
            await db.refresh(row)
            return TaskModel.model_validate(row)

    async def delete(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(WorkosTask).filter_by(id=id))
            if not res.scalars().first():
                return False
            await db.execute(delete(WorkosTask).filter_by(id=id))
            await db.commit()
            return True
```

Add to the singleton block:

```python
Labels = LabelsDao()
Tasks = TasksDao()
```

> Note: `Tasks.insert` calls `Teams.next_task_number(team_id, db=db)` BEFORE opening its own session block so the counter commit is independent; passing `db=db` keeps it on the caller's session when one is supplied.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest open_webui/test/workos/test_models_task.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/models/workos.py backend/open_webui/test/workos/test_models_task.py
git commit -m "feat(workos): add Label + Task models and DAO with key generation"
```

---

### Task 5: Alembic migration — create WorkOS tables

**Files:**
- Create: `backend/open_webui/migrations/versions/f0a1b2c3d4e5_add_workos_tables.py`

**Interfaces:**
- Consumes: the table shapes from Tasks 2–4. `down_revision = 'c3d4e5f6a7b8'` (current head).
- Produces: the 7 `workos_*` tables in a real database. Tests use `Base.metadata.create_all` (Task 2 conftest) and do NOT exercise this migration; verification here is running alembic up/down cleanly.

- [ ] **Step 1: Write the migration file**

Create `backend/open_webui/migrations/versions/f0a1b2c3d4e5_add_workos_tables.py`:

```python
"""add workos tables

Revision ID: f0a1b2c3d4e5
Revises: c3d4e5f6a7b8
Create Date: 2026-06-22 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f0a1b2c3d4e5'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'workos_team',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('key', sa.Text(), nullable=True),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('icon', sa.Text(), nullable=True),
        sa.Column('task_seq', sa.BigInteger(), nullable=True),
        sa.Column('archived', sa.Boolean(), nullable=True),
        sa.Column('created_by_id', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    op.create_table(
        'workos_team_member',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('team_id', sa.Text(), nullable=True),
        sa.Column('user_id', sa.Text(), nullable=True),
        sa.Column('role', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'user_id', name='uq_workos_team_member'),
    )
    op.create_index('ix_workos_team_member_user_id', 'workos_team_member', ['user_id'])
    op.create_table(
        'workos_workspace',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('team_id', sa.Text(), nullable=True),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('icon', sa.Text(), nullable=True),
        sa.Column('visibility', sa.Text(), nullable=True),
        sa.Column('archived', sa.Boolean(), nullable=True),
        sa.Column('created_by_id', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_workos_workspace_team_id', 'workos_workspace', ['team_id'])
    op.create_table(
        'workos_workspace_member',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('workspace_id', sa.Text(), nullable=True),
        sa.Column('user_id', sa.Text(), nullable=True),
        sa.Column('role', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'user_id', name='uq_workos_workspace_member'),
    )
    op.create_table(
        'workos_workstream',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('workspace_id', sa.Text(), nullable=True),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('icon', sa.Text(), nullable=True),
        sa.Column('archived', sa.Boolean(), nullable=True),
        sa.Column('created_by_id', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_workos_workstream_workspace_id', 'workos_workstream', ['workspace_id'])
    op.create_table(
        'workos_label',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('team_id', sa.Text(), nullable=True),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('color', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'workos_task',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('workstream_id', sa.Text(), nullable=True),
        sa.Column('team_id', sa.Text(), nullable=True),
        sa.Column('number', sa.BigInteger(), nullable=True),
        sa.Column('key', sa.Text(), nullable=True),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('priority', sa.Text(), nullable=True),
        sa.Column('assignee_id', sa.Text(), nullable=True),
        sa.Column('due_date', sa.BigInteger(), nullable=True),
        sa.Column('progress', sa.Integer(), nullable=True),
        sa.Column('labels', sa.JSON(), nullable=True),
        sa.Column('sort_key', sa.Float(), nullable=True),
        sa.Column('created_by_id', sa.Text(), nullable=True),
        sa.Column('completed_at', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_workos_task_workstream_id', 'workos_task', ['workstream_id'])
    op.create_index('ix_workos_task_assignee_id', 'workos_task', ['assignee_id'])


def downgrade() -> None:
    op.drop_index('ix_workos_task_assignee_id', table_name='workos_task')
    op.drop_index('ix_workos_task_workstream_id', table_name='workos_task')
    op.drop_table('workos_task')
    op.drop_table('workos_label')
    op.drop_index('ix_workos_workstream_workspace_id', table_name='workos_workstream')
    op.drop_table('workos_workstream')
    op.drop_table('workos_workspace_member')
    op.drop_index('ix_workos_workspace_team_id', table_name='workos_workspace')
    op.drop_table('workos_workspace')
    op.drop_index('ix_workos_team_member_user_id', table_name='workos_team_member')
    op.drop_table('workos_team_member')
    op.drop_table('workos_team')
```

- [ ] **Step 2: Verify the migration chains to head**

Run: `cd backend/open_webui && python -m alembic heads`
Expected: shows a single head `f0a1b2c3d4e5 (head)`. If it shows multiple heads, fix `down_revision`.

- [ ] **Step 3: Apply and roll back against a scratch DB**

Run:
```bash
cd backend/open_webui
DATABASE_URL="sqlite:///$(mktemp -t workosmig.XXXX.db)" python -m alembic upgrade head
```
Expected: `Running upgrade c3d4e5f6a7b8 -> f0a1b2c3d4e5, add workos tables` with no error.

Then verify downgrade is clean (same DATABASE_URL value):
```bash
cd backend/open_webui
DBURL="sqlite:///$(mktemp -t workosmig2.XXXX.db)"; DATABASE_URL="$DBURL" python -m alembic upgrade head && DATABASE_URL="$DBURL" python -m alembic downgrade -1
```
Expected: upgrade then `Running downgrade f0a1b2c3d4e5 -> c3d4e5f6a7b8` with no error.

- [ ] **Step 4: Commit**

```bash
git add backend/open_webui/migrations/versions/f0a1b2c3d4e5_add_workos_tables.py
git commit -m "feat(workos): add alembic migration for workos tables"
```

---

### Task 6: Router scaffold — access helpers, /bootstrap, Teams CRUD, members; register in main.py

**Files:**
- Create: `backend/open_webui/routers/workos.py`
- Modify: `backend/open_webui/main.py` (import + `include_router`)
- Test: `backend/open_webui/test/workos/test_router_teams.py`

**Interfaces:**
- Consumes: DAO singletons from Tasks 2–4; `get_verified_user`, `has_permission`, `get_async_session`.
- Produces (used by all later router tasks): in `routers/workos.py`:
  - `router` (APIRouter)
  - `async def _require_workos(request, user, db) -> None` — 401 unless admin or `features.workos`
  - `async def _require_workos_admin(request, user, db) -> None` — 403 unless admin or `features.workos_admin`
  - `async def team_role(user, team_id, db) -> Optional[str]` — `'admin'` if system admin, else the membership role or `None`
  - `async def require_team_visible(user, team_id, db) -> TeamModel` — 404 if team missing/not visible
  - `async def require_team_role(user, team_id, db, allowed: set[str]) -> TeamModel` — 403 unless role in allowed
  - Endpoints: `GET /bootstrap`, `GET /teams`, `POST /teams`, `GET /teams/{team_id}`, `PATCH /teams/{team_id}`, `DELETE /teams/{team_id}`, `GET /teams/{team_id}/members`, `POST /teams/{team_id}/members`, `PATCH /teams/{team_id}/members/{user_id}`, `DELETE /teams/{team_id}/members/{user_id}`
- Bootstrap response shape: `{'teams': [TeamModel...], 'workspaces': [WorkspaceModel...], 'workstreams': [WorkstreamModel...], 'roles': {team_id: role}}` covering only entities the user can see.

- [ ] **Step 1: Write the failing test**

Create `backend/open_webui/test/workos/test_router_teams.py`:

```python
import pytest
import pytest_asyncio
from types import SimpleNamespace

import httpx
from httpx import ASGITransport
from fastapi import FastAPI

import open_webui.routers.workos as wr
from open_webui.utils.auth import get_verified_user


def _make_app(user):
    app = FastAPI()
    app.state.config = SimpleNamespace(
        USER_PERMISSIONS={},
        WORKOS_RULES={'team_creation': 'all_users', 'default_workspace_visibility': 'team'},
    )
    app.include_router(wr.router, prefix='/api/v1/workos')
    app.dependency_overrides[get_verified_user] = lambda: user
    return app


def _client(monkeypatch, *, user, allow=True):
    async def _hp(user_id, key, permissions, db=None):
        return allow
    monkeypatch.setattr(wr, 'has_permission', _hp)
    return httpx.AsyncClient(transport=ASGITransport(app=_make_app(user)), base_url='http://test')


U1 = SimpleNamespace(id='u1', name='Lara', role='user')
U2 = SimpleNamespace(id='u2', name='Yusuf', role='user')


@pytest.mark.asyncio
async def test_create_team_makes_creator_owner_and_lists(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        r = await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})
        assert r.status_code == 200, r.text
        team = r.json()
        assert team['key'] == 'OSL'

        r = await c.get('/api/v1/workos/teams')
        assert [t['id'] for t in r.json()] == [team['id']]

        r = await c.get('/api/v1/workos/bootstrap')
        body = r.json()
        assert body['roles'][team['id']] == 'owner'


@pytest.mark.asyncio
async def test_non_member_cannot_see_team(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
    async with _client(monkeypatch, user=U2) as c:
        r = await c.get(f"/api/v1/workos/teams/{team['id']}")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_only_owner_can_add_members(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        r = await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        assert r.status_code == 200
    # u2 is now a member but not owner/admin -> cannot add a third member
    async with _client(monkeypatch, user=U2) as c:
        r = await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u3', 'role': 'member'})
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_gate_denied_returns_401(monkeypatch):
    async with _client(monkeypatch, user=U1, allow=False) as c:
        r = await c.get('/api/v1/workos/teams')
        assert r.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest open_webui/test/workos/test_router_teams.py -v`
Expected: FAIL — `ModuleNotFoundError: open_webui.routers.workos`.

- [ ] **Step 3: Implement `routers/workos.py` (scaffold + teams)**

Create `backend/open_webui/routers/workos.py`:

```python
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.internal.db import get_async_session
from open_webui.utils.auth import get_verified_user
from open_webui.utils.access_control import has_permission
from open_webui.models.workos import (
    Teams, TeamMembers, Workspaces, WorkspaceMembers, Workstreams,
    TeamModel,
)

log = logging.getLogger(__name__)

router = APIRouter()

TEAM_ROLES = {'owner', 'admin', 'member'}


# ──────────────────────── permission / access helpers ────────────────────────


async def _require_workos(request: Request, user, db: AsyncSession) -> None:
    if user.role != 'admin' and not await has_permission(
        user.id, 'features.workos', request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='WorkOS access required.')


async def _require_workos_admin(request: Request, user, db: AsyncSession) -> None:
    if user.role != 'admin' and not await has_permission(
        user.id, 'features.workos_admin', request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='WorkOS admin required.')


async def team_role(user, team_id: str, db: AsyncSession) -> Optional[str]:
    if user.role == 'admin':
        return 'admin'
    m = await TeamMembers.get(team_id, user.id, db=db)
    return m.role if m else None


async def require_team_visible(user, team_id: str, db: AsyncSession) -> TeamModel:
    team = await Teams.get_by_id(team_id, db=db)
    if not team or await team_role(user, team_id, db) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Team not found.')
    return team


async def require_team_role(user, team_id: str, db: AsyncSession, allowed: set) -> TeamModel:
    team = await require_team_visible(user, team_id, db)
    if (await team_role(user, team_id, db)) not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Insufficient role.')
    return team


# ──────────────────────────────── schemas ────────────────────────────────


class TeamForm(BaseModel):
    name: str
    key: str
    icon: Optional[str] = None


class TeamUpdateForm(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    archived: Optional[bool] = None


class MemberForm(BaseModel):
    user_id: str
    role: str = 'member'


class MemberRoleForm(BaseModel):
    role: str


# ──────────────────────────────── bootstrap ────────────────────────────────


@router.get('/bootstrap')
async def bootstrap(request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)):
    await _require_workos(request, user, db)
    teams = await Teams.list_for_user(user.id, db=db) if user.role != 'admin' else await Teams.list_all(db=db)
    roles: dict = {}
    workspaces = []
    workstreams = []
    for t in teams:
        roles[t.id] = await team_role(user, t.id, db)
        for w in await Workspaces.list_for_team(t.id, db=db):
            if w.visibility == 'team' or user.role == 'admin' or await WorkspaceMembers.get(w.id, user.id, db=db):
                workspaces.append(w)
                workstreams.extend(await Workstreams.list_for_workspace(w.id, db=db))
    return {'teams': teams, 'workspaces': workspaces, 'workstreams': workstreams, 'roles': roles}


# ──────────────────────────────── teams ────────────────────────────────


@router.get('/teams')
async def list_teams(request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)):
    await _require_workos(request, user, db)
    return await (Teams.list_all(db=db) if user.role == 'admin' else Teams.list_for_user(user.id, db=db))


@router.post('/teams')
async def create_team(
    request: Request, form: TeamForm, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    rules = request.app.state.config.WORKOS_RULES or {}
    if rules.get('team_creation') == 'admins_only' and user.role != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Team creation is restricted to admins.')
    key = form.key.strip().upper()
    if not key or await Teams.get_by_key(key, db=db):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Team key missing or already in use.')
    team = await Teams.insert(name=form.name, key=key, icon=form.icon, created_by_id=user.id, db=db)
    await TeamMembers.add(team.id, user.id, 'owner', db=db)
    return team


@router.get('/teams/{team_id}')
async def get_team(
    request: Request, team_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    return await require_team_visible(user, team_id, db)


@router.patch('/teams/{team_id}')
async def update_team(
    request: Request, team_id: str, form: TeamUpdateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    await require_team_role(user, team_id, db, {'owner'})
    fields = {k: v for k, v in form.model_dump(exclude_none=True).items()}
    return await Teams.update_fields(team_id, fields, db=db)


@router.delete('/teams/{team_id}')
async def delete_team(
    request: Request, team_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    await require_team_role(user, team_id, db, {'owner'})
    return {'deleted': await Teams.delete(team_id, db=db)}


@router.get('/teams/{team_id}/members')
async def list_members(
    request: Request, team_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    await require_team_visible(user, team_id, db)
    return await TeamMembers.list_for_team(team_id, db=db)


@router.post('/teams/{team_id}/members')
async def add_member(
    request: Request, team_id: str, form: MemberForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    await require_team_role(user, team_id, db, {'owner', 'admin'})
    if form.role not in TEAM_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid role.')
    if await TeamMembers.get(team_id, form.user_id, db=db):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Already a member.')
    return await TeamMembers.add(team_id, form.user_id, form.role, db=db)


@router.patch('/teams/{team_id}/members/{user_id}')
async def update_member(
    request: Request, team_id: str, user_id: str, form: MemberRoleForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    # Only owners may grant/revoke owner or admin; admins may manage members.
    await require_team_role(user, team_id, db, {'owner'} if form.role in {'owner', 'admin'} else {'owner', 'admin'})
    if form.role not in TEAM_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid role.')
    updated = await TeamMembers.update_role(team_id, user_id, form.role, db=db)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Member not found.')
    return updated


@router.delete('/teams/{team_id}/members/{user_id}')
async def remove_member(
    request: Request, team_id: str, user_id: str,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    await require_team_role(user, team_id, db, {'owner', 'admin'})
    return {'removed': await TeamMembers.remove(team_id, user_id, db=db)}
```

- [ ] **Step 4: Register the router in `main.py`**

In `backend/open_webui/main.py`, add to the routers import group (near `policy_review,` ~line 91):

```python
    workos,
```

And after the policy_review `include_router` line (~line 1448):

```python
app.include_router(workos.router, prefix='/api/v1/workos', tags=['workos'])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest open_webui/test/workos/test_router_teams.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/main.py backend/open_webui/test/workos/test_router_teams.py
git commit -m "feat(workos): add router scaffold, bootstrap, teams CRUD + members"
```

---

### Task 7: Router — Workspaces CRUD, members, visibility

**Files:**
- Modify: `backend/open_webui/routers/workos.py`
- Test: `backend/open_webui/test/workos/test_router_workspace.py`

**Interfaces:**
- Consumes: helpers from Task 6.
- Produces: access helpers `async def workspace_visible(user, workspace, db) -> bool`, `async def require_workspace_visible(user, workspace_id, db) -> WorkspaceModel`, `async def require_workspace_manage(user, workspace_id, db) -> WorkspaceModel` (team owner/admin OR workspace admin). Endpoints: `GET /teams/{team_id}/workspaces`, `POST /teams/{team_id}/workspaces`, `GET /workspaces/{workspace_id}`, `PATCH /workspaces/{workspace_id}`, `DELETE /workspaces/{workspace_id}`, and workspace members `GET/POST/PATCH/DELETE /workspaces/{workspace_id}/members`.

- [ ] **Step 1: Write the failing test**

Create `backend/open_webui/test/workos/test_router_workspace.py`:

```python
import pytest
from types import SimpleNamespace

from open_webui.test.workos.test_router_teams import _client, U1, U2


async def _team(c):
    return (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()


@pytest.mark.asyncio
async def test_create_and_list_workspace(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = await _team(c)
        r = await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                         json={'name': 'Engineering', 'visibility': 'team'})
        assert r.status_code == 200, r.text
        ws = r.json()
        r = await c.get(f"/api/v1/workos/teams/{team['id']}/workspaces")
        assert [w['id'] for w in r.json()] == [ws['id']]


@pytest.mark.asyncio
async def test_restricted_workspace_hidden_from_non_member(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = await _team(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                          json={'name': 'Secret', 'visibility': 'restricted'})).json()
    async with _client(monkeypatch, user=U2) as c:
        # u2 is a team member but not a workspace member -> 404 on the restricted workspace
        r = await c.get(f"/api/v1/workos/workspaces/{ws['id']}")
        assert r.status_code == 404
        # not listed either
        r = await c.get(f"/api/v1/workos/teams/{team['id']}/workspaces")
        assert ws['id'] not in [w['id'] for w in r.json()]


@pytest.mark.asyncio
async def test_member_cannot_create_workspace(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = await _team(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    async with _client(monkeypatch, user=U2) as c:
        r = await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces", json={'name': 'X', 'visibility': 'team'})
        assert r.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest open_webui/test/workos/test_router_workspace.py -v`
Expected: FAIL — 404/405 (routes not defined).

- [ ] **Step 3: Implement (append to `routers/workos.py`)**

Add imports at the top (extend the `from open_webui.models.workos import (...)`) to also import `WorkspaceModel`. Add helpers + schemas + endpoints:

```python
WORKSPACE_ROLES = {'admin', 'member'}


class WorkspaceForm(BaseModel):
    name: str
    icon: Optional[str] = None
    visibility: str = 'team'


class WorkspaceUpdateForm(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    visibility: Optional[str] = None
    archived: Optional[bool] = None


async def workspace_visible(user, workspace, db: AsyncSession) -> bool:
    if await team_role(user, workspace.team_id, db) is None:
        return False
    if workspace.visibility == 'team' or user.role == 'admin':
        return True
    return (await WorkspaceMembers.get(workspace.id, user.id, db=db)) is not None


async def require_workspace_visible(user, workspace_id: str, db: AsyncSession):
    ws = await Workspaces.get_by_id(workspace_id, db=db)
    if not ws or not await workspace_visible(user, ws, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Workspace not found.')
    return ws


async def require_workspace_manage(user, workspace_id: str, db: AsyncSession):
    ws = await require_workspace_visible(user, workspace_id, db)
    if (await team_role(user, ws.team_id, db)) in {'owner', 'admin'}:
        return ws
    wm = await WorkspaceMembers.get(ws.id, user.id, db=db)
    if wm and wm.role == 'admin':
        return ws
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Workspace management requires admin.')


@router.get('/teams/{team_id}/workspaces')
async def list_workspaces(
    request: Request, team_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    await require_team_visible(user, team_id, db)
    out = []
    for ws in await Workspaces.list_for_team(team_id, db=db):
        if await workspace_visible(user, ws, db):
            out.append(ws)
    return out


@router.post('/teams/{team_id}/workspaces')
async def create_workspace(
    request: Request, team_id: str, form: WorkspaceForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    await require_team_role(user, team_id, db, {'owner', 'admin'})
    if form.visibility not in {'team', 'restricted'}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid visibility.')
    ws = await Workspaces.insert(team_id, form.name, form.icon, form.visibility, user.id, db=db)
    if form.visibility == 'restricted':
        await WorkspaceMembers.add(ws.id, user.id, 'admin', db=db)
    return ws


@router.get('/workspaces/{workspace_id}')
async def get_workspace(
    request: Request, workspace_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    return await require_workspace_visible(user, workspace_id, db)


@router.patch('/workspaces/{workspace_id}')
async def update_workspace(
    request: Request, workspace_id: str, form: WorkspaceUpdateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    await require_workspace_manage(user, workspace_id, db)
    fields = form.model_dump(exclude_none=True)
    if 'visibility' in fields and fields['visibility'] not in {'team', 'restricted'}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid visibility.')
    return await Workspaces.update_fields(workspace_id, fields, db=db)


@router.delete('/workspaces/{workspace_id}')
async def delete_workspace(
    request: Request, workspace_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    ws = await require_workspace_visible(user, workspace_id, db)
    await require_team_role(user, ws.team_id, db, {'owner', 'admin'})
    return {'deleted': await Workspaces.delete(workspace_id, db=db)}


@router.get('/workspaces/{workspace_id}/members')
async def list_workspace_members(
    request: Request, workspace_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    await require_workspace_visible(user, workspace_id, db)
    return await WorkspaceMembers.list_for_workspace(workspace_id, db=db)


@router.post('/workspaces/{workspace_id}/members')
async def add_workspace_member(
    request: Request, workspace_id: str, form: MemberForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    await require_workspace_manage(user, workspace_id, db)
    if form.role not in WORKSPACE_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid role.')
    if await WorkspaceMembers.get(workspace_id, form.user_id, db=db):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Already a member.')
    return await WorkspaceMembers.add(workspace_id, form.user_id, form.role, db=db)


@router.patch('/workspaces/{workspace_id}/members/{user_id}')
async def update_workspace_member(
    request: Request, workspace_id: str, user_id: str, form: MemberRoleForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    await require_workspace_manage(user, workspace_id, db)
    if form.role not in WORKSPACE_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid role.')
    updated = await WorkspaceMembers.update_role(workspace_id, user_id, form.role, db=db)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Member not found.')
    return updated


@router.delete('/workspaces/{workspace_id}/members/{user_id}')
async def remove_workspace_member(
    request: Request, workspace_id: str, user_id: str,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    await require_workspace_manage(user, workspace_id, db)
    return {'removed': await WorkspaceMembers.remove(workspace_id, user_id, db=db)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest open_webui/test/workos/test_router_workspace.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_workspace.py
git commit -m "feat(workos): add workspace CRUD, members, and visibility enforcement"
```

---

### Task 8: Router — Workstreams CRUD

**Files:**
- Modify: `backend/open_webui/routers/workos.py`
- Test: `backend/open_webui/test/workos/test_router_workstream.py`

**Interfaces:**
- Consumes: `require_workspace_visible`, `require_workspace_manage` from Task 7.
- Produces: helper `async def require_workstream_visible(user, workstream_id, db) -> (WorkstreamModel, WorkspaceModel)`. Endpoints: `GET /workspaces/{workspace_id}/workstreams`, `POST /workspaces/{workspace_id}/workstreams`, `PATCH /workstreams/{workstream_id}`, `DELETE /workstreams/{workstream_id}`.

- [ ] **Step 1: Write the failing test**

Create `backend/open_webui/test/workos/test_router_workstream.py`:

```python
import pytest

from open_webui.test.workos.test_router_teams import _client, U1, U2


async def _ws(c):
    team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
    ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                       json={'name': 'Engineering', 'visibility': 'team'})).json()
    return team, ws


@pytest.mark.asyncio
async def test_workstream_crud(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws = await _ws(c)
        r = await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'Platform'})
        assert r.status_code == 200, r.text
        s = r.json()
        r = await c.get(f"/api/v1/workos/workspaces/{ws['id']}/workstreams")
        assert [x['id'] for x in r.json()] == [s['id']]
        r = await c.patch(f"/api/v1/workos/workstreams/{s['id']}", json={'name': 'Core'})
        assert r.json()['name'] == 'Core'
        r = await c.delete(f"/api/v1/workos/workstreams/{s['id']}")
        assert r.json()['deleted'] is True


@pytest.mark.asyncio
async def test_non_member_cannot_list_workstreams(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws = await _ws(c)
    async with _client(monkeypatch, user=U2) as c:
        r = await c.get(f"/api/v1/workos/workspaces/{ws['id']}/workstreams")
        assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest open_webui/test/workos/test_router_workstream.py -v`
Expected: FAIL — routes not defined.

- [ ] **Step 3: Implement (append to `routers/workos.py`)**

Extend the models import to include `WorkstreamModel`. Add:

```python
class WorkstreamForm(BaseModel):
    name: str
    icon: Optional[str] = None


class WorkstreamUpdateForm(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    archived: Optional[bool] = None


async def require_workstream_visible(user, workstream_id: str, db: AsyncSession):
    stream = await Workstreams.get_by_id(workstream_id, db=db)
    if not stream:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Workstream not found.')
    ws = await require_workspace_visible(user, stream.workspace_id, db)
    return stream, ws


@router.get('/workspaces/{workspace_id}/workstreams')
async def list_workstreams(
    request: Request, workspace_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    await require_workspace_visible(user, workspace_id, db)
    return await Workstreams.list_for_workspace(workspace_id, db=db)


@router.post('/workspaces/{workspace_id}/workstreams')
async def create_workstream(
    request: Request, workspace_id: str, form: WorkstreamForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    await require_workspace_manage(user, workspace_id, db)
    return await Workstreams.insert(workspace_id, form.name, form.icon, user.id, db=db)


@router.patch('/workstreams/{workstream_id}')
async def update_workstream(
    request: Request, workstream_id: str, form: WorkstreamUpdateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    stream, _ = await require_workstream_visible(user, workstream_id, db)
    await require_workspace_manage(user, stream.workspace_id, db)
    return await Workstreams.update_fields(workstream_id, form.model_dump(exclude_none=True), db=db)


@router.delete('/workstreams/{workstream_id}')
async def delete_workstream(
    request: Request, workstream_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    stream, _ = await require_workstream_visible(user, workstream_id, db)
    await require_workspace_manage(user, stream.workspace_id, db)
    return {'deleted': await Workstreams.delete(workstream_id, db=db)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest open_webui/test/workos/test_router_workstream.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_workstream.py
git commit -m "feat(workos): add workstream CRUD with inherited visibility"
```

---

### Task 9: Router — Tasks CRUD + Labels CRUD

**Files:**
- Modify: `backend/open_webui/routers/workos.py`
- Test: `backend/open_webui/test/workos/test_router_task.py`

**Interfaces:**
- Consumes: `require_workstream_visible` (Task 8), `require_team_role`/`require_team_visible` (Task 6), DAO `Tasks`, `Labels`.
- Produces: constants `STATUSES`, `PRIORITIES`. Endpoints: `GET /workstreams/{workstream_id}/tasks`, `POST /workstreams/{workstream_id}/tasks`, `GET /tasks/{task_id}`, `PATCH /tasks/{task_id}`, `DELETE /tasks/{task_id}`; labels `GET /teams/{team_id}/labels`, `POST /teams/{team_id}/labels`, `PATCH /labels/{label_id}`, `DELETE /labels/{label_id}`. Helper `async def require_task_visible(user, task_id, db) -> (TaskModel, WorkstreamModel)`.

- [ ] **Step 1: Write the failing test**

Create `backend/open_webui/test/workos/test_router_task.py`:

```python
import pytest

from open_webui.test.workos.test_router_teams import _client, U1, U2


async def _stream(c):
    team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
    ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                       json={'name': 'Eng', 'visibility': 'team'})).json()
    s = (await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'Platform'})).json()
    return team, ws, s


@pytest.mark.asyncio
async def test_task_create_patch_delete(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'Migrate billing'})
        assert r.status_code == 200, r.text
        t = r.json()
        assert t['key'] == 'OSL-1' and t['status'] == 'backlog'
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}",
                          json={'status': 'in_progress', 'priority': 'high', 'sort_key': 5.0})
        assert r.json()['status'] == 'in_progress' and r.json()['priority'] == 'high'
        r = await c.get(f"/api/v1/workos/workstreams/{s['id']}/tasks")
        assert len(r.json()) == 1
        assert (await c.delete(f"/api/v1/workos/tasks/{t['id']}")).json()['deleted'] is True


@pytest.mark.asyncio
async def test_task_patch_rejects_bad_status(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'X'})).json()
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'status': 'bogus'})
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_labels_crud(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        r = await c.post(f"/api/v1/workos/teams/{team['id']}/labels", json={'name': 'backend', 'color': 'cyan'})
        assert r.status_code == 200
        lab = r.json()
        assert [x['id'] for x in (await c.get(f"/api/v1/workos/teams/{team['id']}/labels")).json()] == [lab['id']]
        assert (await c.delete(f"/api/v1/workos/labels/{lab['id']}")).json()['deleted'] is True


@pytest.mark.asyncio
async def test_non_member_cannot_create_task(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
    async with _client(monkeypatch, user=U2) as c:
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'X'})
        assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest open_webui/test/workos/test_router_task.py -v`
Expected: FAIL — routes not defined.

- [ ] **Step 3: Implement (append to `routers/workos.py`)**

Extend the models import to include `Labels`, `Tasks`, `TaskModel`, `LabelModel`. Add:

```python
STATUSES = {'backlog', 'todo', 'in_progress', 'in_review', 'done', 'canceled'}
PRIORITIES = {'urgent', 'high', 'medium', 'low'}


class TaskCreateForm(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = 'backlog'
    priority: Optional[str] = None
    assignee_id: Optional[str] = None
    due_date: Optional[int] = None
    labels: Optional[list] = None


class TaskUpdateForm(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee_id: Optional[str] = None
    due_date: Optional[int] = None
    progress: Optional[int] = None
    labels: Optional[list] = None
    sort_key: Optional[float] = None


class LabelForm(BaseModel):
    name: str
    color: str


class LabelUpdateForm(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None


async def require_task_visible(user, task_id: str, db: AsyncSession):
    task = await Tasks.get_by_id(task_id, db=db)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Task not found.')
    stream, _ = await require_workstream_visible(user, task.workstream_id, db)
    return task, stream


def _validate_task_fields(fields: dict) -> None:
    if fields.get('status') is not None and fields['status'] not in STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid status.')
    if fields.get('priority') is not None and fields['priority'] not in PRIORITIES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid priority.')
    if fields.get('progress') is not None and not (0 <= fields['progress'] <= 100):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Progress out of range.')


@router.get('/workstreams/{workstream_id}/tasks')
async def list_tasks(
    request: Request, workstream_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    await require_workstream_visible(user, workstream_id, db)
    return await Tasks.list_for_workstream(workstream_id, db=db)


@router.post('/workstreams/{workstream_id}/tasks')
async def create_task(
    request: Request, workstream_id: str, form: TaskCreateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    stream, _ = await require_workstream_visible(user, workstream_id, db)
    _validate_task_fields(form.model_dump())
    team = await require_team_visible(user, (await Workspaces.get_by_id(stream.workspace_id, db=db)).team_id, db)
    return await Tasks.insert(
        workstream_id, team.id, team.key, form.title, user.id,
        description=form.description, status=form.status, priority=form.priority,
        assignee_id=form.assignee_id, due_date=form.due_date, labels=form.labels, db=db,
    )


@router.get('/tasks/{task_id}')
async def get_task(
    request: Request, task_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    task, _ = await require_task_visible(user, task_id, db)
    return task


@router.patch('/tasks/{task_id}')
async def update_task(
    request: Request, task_id: str, form: TaskUpdateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    task, _ = await require_task_visible(user, task_id, db)
    fields = form.model_dump(exclude_none=True)
    _validate_task_fields(fields)
    return await Tasks.update_fields(task_id, fields, db=db)


@router.delete('/tasks/{task_id}')
async def delete_task(
    request: Request, task_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    task, stream = await require_task_visible(user, task_id, db)
    ws = await Workspaces.get_by_id(stream.workspace_id, db=db)
    is_admin = (await team_role(user, ws.team_id, db)) in {'owner', 'admin'}
    if not is_admin and task.created_by_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Only the creator or an admin may delete.')
    return {'deleted': await Tasks.delete(task_id, db=db)}


@router.get('/teams/{team_id}/labels')
async def list_labels(
    request: Request, team_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    await require_team_visible(user, team_id, db)
    return await Labels.list_for_team(team_id, db=db)


@router.post('/teams/{team_id}/labels')
async def create_label(
    request: Request, team_id: str, form: LabelForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    await require_team_role(user, team_id, db, {'owner', 'admin'})
    return await Labels.insert(team_id, form.name, form.color, db=db)


@router.patch('/labels/{label_id}')
async def update_label(
    request: Request, label_id: str, form: LabelUpdateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    existing = await Labels.update_fields(label_id, {}, db=db)  # fetch-only to read team_id
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Label not found.')
    await require_team_role(user, existing.team_id, db, {'owner', 'admin'})
    return await Labels.update_fields(label_id, form.model_dump(exclude_none=True), db=db)


@router.delete('/labels/{label_id}')
async def delete_label(
    request: Request, label_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    existing = await Labels.update_fields(label_id, {}, db=db)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Label not found.')
    await require_team_role(user, existing.team_id, db, {'owner', 'admin'})
    return {'deleted': await Labels.delete(label_id, db=db)}
```

> Note: `Labels.update_fields(label_id, {}, ...)` returns the row unchanged (no fields) — used as a fetch-by-id since the DAO has no `get_by_id` for labels. If you prefer, add `Labels.get_by_id` in Task 4's DAO and use it here.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest open_webui/test/workos/test_router_task.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_task.py
git commit -m "feat(workos): add task and label CRUD with validation + delete rules"
```

---

### Task 10: Router — Admin oversight + settings

**Files:**
- Modify: `backend/open_webui/routers/workos.py`
- Test: `backend/open_webui/test/workos/test_router_admin.py`

**Interfaces:**
- Consumes: `_require_workos_admin`, `Teams`, `TeamMembers`.
- Produces: endpoints `GET /admin/teams` → `[{team: TeamModel, owner_ids: [..], member_count: int}]`; `GET /admin/settings` → `WORKOS_RULES` dict; `PATCH /admin/settings` (admin-only) updating `WORKOS_RULES`.

- [ ] **Step 1: Write the failing test**

Create `backend/open_webui/test/workos/test_router_admin.py`:

```python
import pytest
from types import SimpleNamespace

from open_webui.test.workos.test_router_teams import _client, U1

ADMIN = SimpleNamespace(id='admin1', name='Admin', role='admin')


@pytest.mark.asyncio
async def test_admin_lists_all_teams_with_counts(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
    async with _client(monkeypatch, user=ADMIN) as c:
        r = await c.get('/api/v1/workos/admin/teams')
        assert r.status_code == 200
        rows = r.json()
        row = next(x for x in rows if x['team']['id'] == team['id'])
        assert row['member_count'] == 1
        assert 'u1' in row['owner_ids']


@pytest.mark.asyncio
async def test_settings_get_and_patch(monkeypatch):
    async with _client(monkeypatch, user=ADMIN) as c:
        r = await c.get('/api/v1/workos/admin/settings')
        assert r.json()['team_creation'] in ('all_users', 'admins_only')
        r = await c.patch('/api/v1/workos/admin/settings', json={'team_creation': 'admins_only'})
        assert r.json()['team_creation'] == 'admins_only'


@pytest.mark.asyncio
async def test_settings_patch_forbidden_for_non_admin(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        r = await c.patch('/api/v1/workos/admin/settings', json={'team_creation': 'admins_only'})
        assert r.status_code == 403
```

> Note: the test app's `app.state.config.WORKOS_RULES` is a plain dict (see `_make_app`), so PATCH mutates it in place; in production it is a `PersistentConfig` whose assignment persists to the DB.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest open_webui/test/workos/test_router_admin.py -v`
Expected: FAIL — routes not defined.

- [ ] **Step 3: Implement (append to `routers/workos.py`)**

```python
class SettingsForm(BaseModel):
    team_creation: Optional[str] = None
    default_workspace_visibility: Optional[str] = None


@router.get('/admin/teams')
async def admin_list_teams(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos_admin(request, user, db)
    out = []
    for team in await Teams.list_all(db=db):
        members = await TeamMembers.list_for_team(team.id, db=db)
        out.append({
            'team': team,
            'owner_ids': [m.user_id for m in members if m.role == 'owner'],
            'member_count': len(members),
        })
    return out


@router.get('/admin/settings')
async def admin_get_settings(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos_admin(request, user, db)
    return request.app.state.config.WORKOS_RULES


@router.patch('/admin/settings')
async def admin_update_settings(
    request: Request, form: SettingsForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos_admin(request, user, db)
    if form.team_creation is not None and form.team_creation not in {'all_users', 'admins_only'}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid team_creation.')
    if form.default_workspace_visibility is not None and form.default_workspace_visibility not in {'team', 'restricted'}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid default_workspace_visibility.')
    rules = dict(request.app.state.config.WORKOS_RULES or {})
    rules.update(form.model_dump(exclude_none=True))
    request.app.state.config.WORKOS_RULES = rules
    return request.app.state.config.WORKOS_RULES
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest open_webui/test/workos/test_router_admin.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_admin.py
git commit -m "feat(workos): add admin oversight + settings endpoints"
```

---

### Task 11: Realtime — socket subscribe handler + router emits

**Files:**
- Modify: `backend/open_webui/models/workos.py` (add boolean access helpers for the socket layer)
- Modify: `backend/open_webui/socket/main.py` (add `workos:subscribe` / `workos:unsubscribe` handlers)
- Modify: `backend/open_webui/routers/workos.py` (add `emit_event` helper + emit after mutations)
- Test: `backend/open_webui/test/workos/test_realtime.py`

**Interfaces:**
- Produces in `models/workos.py`: `async def can_see_team(user_id, is_admin, team_id, db=None) -> bool`, `async def can_see_workstream(user_id, is_admin, workstream_id, db=None) -> bool`.
- Produces in `routers/workos.py`: `async def emit_event(event: str, room: str, payload: dict) -> None` (lazy-imports `sio`). Mutations emit: task create/update/delete → `workos:task.created/updated/deleted` to `workos:workstream:{workstream_id}`; workspace/workstream create/update/delete → `workos:workspace.*` / `workos:workstream.*` to `workos:team:{team_id}`.
- Socket events the client emits: `workos:subscribe` `{auth:{token}, team_id?, workstream_id?}`, `workos:unsubscribe` `{team_id?, workstream_id?}`.

- [ ] **Step 1: Write the failing test**

Create `backend/open_webui/test/workos/test_realtime.py`:

```python
import pytest
from types import SimpleNamespace

import open_webui.routers.workos as wr
from open_webui.models.workos import can_see_team, can_see_workstream, Teams, TeamMembers, Workspaces, Workstreams
from open_webui.test.workos.test_router_teams import _client, U1, U2


@pytest.mark.asyncio
async def test_can_see_helpers():
    team = await Teams.insert('Acme', 'OSL', None, 'u1')
    await TeamMembers.add(team.id, 'u1', 'owner')
    ws = await Workspaces.insert(team.id, 'Eng', None, 'team', 'u1')
    s = await Workstreams.insert(ws.id, 'Platform', None, 'u1')
    assert await can_see_team('u1', False, team.id) is True
    assert await can_see_team('u2', False, team.id) is False
    assert await can_see_workstream('u1', False, s.id) is True
    assert await can_see_workstream('u2', False, s.id) is False
    assert await can_see_workstream('u2', True, s.id) is True  # admin override


@pytest.mark.asyncio
async def test_task_create_emits_event(monkeypatch):
    events = []

    async def _rec(event, room, payload):
        events.append((event, room))

    monkeypatch.setattr(wr, 'emit_event', _rec)
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                          json={'name': 'Eng', 'visibility': 'team'})).json()
        s = (await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'P'})).json()
        await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'X'})
    assert ('workos:task.created', f"workos:workstream:{s['id']}") in events
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest open_webui/test/workos/test_realtime.py -v`
Expected: FAIL — `ImportError: cannot import name 'can_see_team'` / no `emit_event`.

- [ ] **Step 3a: Add boolean access helpers to `models/workos.py`**

Append (after the DAO singletons):

```python
async def can_see_team(user_id: str, is_admin: bool, team_id: str, db: Optional[AsyncSession] = None) -> bool:
    if is_admin:
        return (await Teams.get_by_id(team_id, db=db)) is not None
    return (await TeamMembers.get(team_id, user_id, db=db)) is not None


async def can_see_workstream(
    user_id: str, is_admin: bool, workstream_id: str, db: Optional[AsyncSession] = None
) -> bool:
    stream = await Workstreams.get_by_id(workstream_id, db=db)
    if not stream:
        return False
    ws = await Workspaces.get_by_id(stream.workspace_id, db=db)
    if not ws:
        return False
    if not await can_see_team(user_id, is_admin, ws.team_id, db=db):
        return False
    if ws.visibility == 'team' or is_admin:
        return True
    return (await WorkspaceMembers.get(ws.id, user_id, db=db)) is not None
```

- [ ] **Step 3b: Add the `emit_event` helper + emits to `routers/workos.py`**

Add near the top (after `log = ...`):

```python
async def emit_event(event: str, room: str, payload: dict) -> None:
    try:
        from open_webui.socket.main import sio

        await sio.emit(event, payload, room=room)
    except Exception as e:  # pragma: no cover - emit is best-effort
        log.debug(f'workos emit failed for {event}: {e}')
```

Then add emit calls at the end of the relevant endpoints (return values already computed — emit just before `return`):

- In `create_workspace`, before `return ws`:
  ```python
  await emit_event('workos:workspace.created', f'workos:team:{team_id}', ws.model_dump())
  ```
- In `update_workspace`, capture the result then emit:
  ```python
  updated = await Workspaces.update_fields(workspace_id, fields, db=db)
  await emit_event('workos:workspace.updated', f'workos:team:{updated.team_id}', updated.model_dump())
  return updated
  ```
- In `delete_workspace`, before return: `await emit_event('workos:workspace.deleted', f'workos:team:{ws.team_id}', {'id': workspace_id})`
- In `create_workstream`:
  ```python
  stream = await Workstreams.insert(workspace_id, form.name, form.icon, user.id, db=db)
  ws_row = await Workspaces.get_by_id(workspace_id, db=db)
  await emit_event('workos:workstream.created', f'workos:team:{ws_row.team_id}', stream.model_dump())
  return stream
  ```
- In `update_workstream` / `delete_workstream`: emit `workos:workstream.updated` / `.deleted` to `workos:team:{ws_row.team_id}` (fetch `ws_row = await Workspaces.get_by_id(stream.workspace_id, db=db)`), payload `updated.model_dump()` / `{'id': workstream_id, 'workspace_id': stream.workspace_id}`.
- In `create_task`:
  ```python
  task = await Tasks.insert(...)  # existing
  await emit_event('workos:task.created', f'workos:workstream:{workstream_id}', task.model_dump())
  return task
  ```
- In `update_task`:
  ```python
  updated = await Tasks.update_fields(task_id, fields, db=db)
  await emit_event('workos:task.updated', f'workos:workstream:{updated.workstream_id}', updated.model_dump())
  return updated
  ```
- In `delete_task`, before return: `await emit_event('workos:task.deleted', f'workos:workstream:{task.workstream_id}', {'id': task_id, 'workstream_id': task.workstream_id})`

- [ ] **Step 3c: Add socket handlers to `socket/main.py`**

After the `join-note` handler, add:

```python
@sio.on('workos:subscribe')
async def workos_subscribe(sid, data):
    auth = data.get('auth') if isinstance(data, dict) else None
    if not auth or 'token' not in auth:
        return
    token_data = decode_token(auth['token'])
    if token_data is None or 'id' not in token_data:
        return
    user = await Users.get_user_by_id(token_data['id'])
    if not user:
        return

    from open_webui.models.workos import can_see_team, can_see_workstream

    is_admin = user.role == 'admin'
    team_id = data.get('team_id')
    workstream_id = data.get('workstream_id')
    if team_id and await can_see_team(user.id, is_admin, team_id):
        await sio.enter_room(sid, f'workos:team:{team_id}')
    if workstream_id and await can_see_workstream(user.id, is_admin, workstream_id):
        await sio.enter_room(sid, f'workos:workstream:{workstream_id}')


@sio.on('workos:unsubscribe')
async def workos_unsubscribe(sid, data):
    if not isinstance(data, dict):
        return
    if data.get('team_id'):
        await sio.leave_room(sid, f"workos:team:{data['team_id']}")
    if data.get('workstream_id'):
        await sio.leave_room(sid, f"workos:workstream:{data['workstream_id']}")
```

> `decode_token` and `Users` are already imported at the top of `socket/main.py` (used by `connect`/`join-note`).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest open_webui/test/workos/test_realtime.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && python -m pytest open_webui/test/workos/ -v`
Expected: all WorkOS tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/models/workos.py backend/open_webui/socket/main.py backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_realtime.py
git commit -m "feat(workos): realtime socket subscribe + per-mutation event emits"
```

---

### Task 12: Seeder — env-gated demo data

**Files:**
- Create: `backend/open_webui/internal/workos/__init__.py` (empty), `backend/open_webui/internal/workos/seeder.py`
- Modify: `backend/open_webui/main.py` (invoke in lifespan)
- Test: `backend/open_webui/test/workos/test_seeder.py`

**Interfaces:**
- Consumes: DAO from Tasks 2–4.
- Produces: `async def seed_workos_demo() -> None` — idempotent (skips if any team exists), gated by `WORKOS_SEED_DEMO` env truthy. Seeds team `Acme`(key `OSL`) owned by the first admin user, workspaces Engineering/Design, workstreams Platform/Mobile/Growth/Brand System, the 6 labels, and ~10 demo tasks in Platform.

- [ ] **Step 1: Write the failing test**

Create `backend/open_webui/test/workos/test_seeder.py`:

```python
import os
import pytest

from open_webui.models.workos import Teams


@pytest.mark.asyncio
async def test_seeder_is_idempotent_and_gated(monkeypatch):
    from open_webui.internal.workos import seeder

    monkeypatch.setattr(seeder, '_first_admin_id', lambda db=None: _async_str('admin1'))

    # Gate off -> no-op
    monkeypatch.delenv('WORKOS_SEED_DEMO', raising=False)
    await seeder.seed_workos_demo()
    assert await Teams.list_all() == []

    # Gate on -> seeds once
    monkeypatch.setenv('WORKOS_SEED_DEMO', 'true')
    await seeder.seed_workos_demo()
    teams = await Teams.list_all()
    assert len(teams) == 1 and teams[0].key == 'OSL'

    # Second run is idempotent
    await seeder.seed_workos_demo()
    assert len(await Teams.list_all()) == 1


def _async_str(v):
    async def _f(db=None):
        return v
    return _f()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest open_webui/test/workos/test_seeder.py -v`
Expected: FAIL — `ModuleNotFoundError: open_webui.internal.workos`.

- [ ] **Step 3: Implement the seeder**

Create `backend/open_webui/internal/workos/__init__.py` (empty), then `backend/open_webui/internal/workos/seeder.py`:

```python
import logging
import os
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.internal.db import get_async_db_context
from open_webui.models.users import User
from open_webui.models.workos import Teams, TeamMembers, Workspaces, Workstreams, Labels, Tasks

log = logging.getLogger(__name__)

LABELS = [
    ('frontend', 'teal'), ('backend', 'cyan'), ('bug', 'red'),
    ('research', 'purple'), ('design', 'orange'), ('infra', 'green'),
]

DEMO_TASKS = [
    ('Migrate billing service to new ledger', 'in_progress', 'urgent', 60),
    ('Redesign task detail side panel', 'in_review', 'high', 85),
    ('Add keyboard shortcuts to board view', 'todo', 'medium', 0),
    ('Investigate slow workspace switching', 'in_progress', 'high', 35),
    ('Spec out Workstream templates', 'backlog', 'low', 0),
    ('Audit notification email deliverability', 'todo', 'medium', 0),
    ('Ship comment @mentions', 'done', 'high', 100),
    ('Roll out SSO for enterprise tier', 'done', 'urgent', 100),
    ('Empty states for new Workspaces', 'in_review', 'low', 70),
    ('Rate-limit the public API', 'backlog', 'medium', 0),
]


async def _first_admin_id(db: Optional[AsyncSession] = None) -> Optional[str]:
    async with get_async_db_context(db) as db:
        res = await db.execute(select(User).filter_by(role='admin').order_by(User.created_at.asc()))
        row = res.scalars().first()
        return row.id if row else None


async def seed_workos_demo() -> None:
    if os.environ.get('WORKOS_SEED_DEMO', 'false').lower() != 'true':
        return
    if await Teams.list_all():
        return  # idempotent: only seed an empty WorkOS
    owner_id = await _first_admin_id()
    if not owner_id:
        log.info('WorkOS seed skipped: no admin user yet.')
        return

    team = await Teams.insert('Acme', 'OSL', 'briefcase', owner_id)
    await TeamMembers.add(team.id, owner_id, 'owner')
    for name, color in LABELS:
        await Labels.insert(team.id, name, color)

    eng = await Workspaces.insert(team.id, 'Engineering', 'briefcase', 'team', owner_id)
    await Workspaces.insert(team.id, 'Design', 'palette', 'team', owner_id)
    platform = await Workstreams.insert(eng.id, 'Platform', 'layers', owner_id)
    await Workstreams.insert(eng.id, 'Mobile', 'smartphone', owner_id)
    await Workstreams.insert(eng.id, 'Growth', 'trending-up', owner_id)

    for title, st, prio, prog in DEMO_TASKS:
        t = await Tasks.insert(
            platform.id, team.id, team.key, title, owner_id, status=st, priority=prio, assignee_id=owner_id
        )
        if prog:
            await Tasks.update_fields(t.id, {'progress': prog})
    log.info('WorkOS demo data seeded.')
```

- [ ] **Step 4: Invoke in `main.py`**

In the lifespan startup, after the Policy Review seeder block (~line 754), add:

```python
    try:
        from open_webui.internal.workos.seeder import seed_workos_demo
        await seed_workos_demo()
    except Exception as e:
        log.exception(f'WorkOS seeding failed: {e}')
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && python -m pytest open_webui/test/workos/test_seeder.py -v`
Expected: PASS (1 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/internal/workos/ backend/open_webui/main.py backend/open_webui/test/workos/test_seeder.py
git commit -m "feat(workos): add env-gated demo seeder"
```

---

## Frontend

> The decoded prototype components (Sidebar, Topbar, BoardView/TaskCard, ListView, TaskDetail, MyWork) in `C:\Users\aalsawarieh\Downloads\Osool Task App.html` are the visual reference. Open it in a browser to see the target. The Svelte build is a faithful port using the store/api below. Svelte component tasks are verified by `npm run check` + a manual browser smoke (no component unit-test harness exists in this repo); the tested logic lives in `lib/`.

### Task 13: Frontend types + API client

**Files:**
- Create: `src/lib/components/workos/lib/types.ts`, `src/lib/components/workos/lib/api.ts`

**Interfaces:**
- Produces types: `TeamRole`, `WorkspaceRole`, `TaskStatus`, `TaskPriority`, `Visibility`, `Team`, `Workspace`, `Workstream`, `Label`, `Task`, `Member`, `Bootstrap`, `WorkosRules`, and constants `STATUS_ORDER`, `STATUS_LABEL`, `PRIORITY_ORDER`.
- Produces api functions (all take `token` first): `getBootstrap`, `listTeams`, `createTeam`, `getTeam`, `updateTeam`, `deleteTeam`, `listTeamMembers`, `addTeamMember`, `updateTeamMember`, `removeTeamMember`, `listWorkspaces`, `createWorkspace`, `getWorkspace`, `updateWorkspace`, `deleteWorkspace`, `listWorkspaceMembers`, `addWorkspaceMember`, `updateWorkspaceMember`, `removeWorkspaceMember`, `listWorkstreams`, `createWorkstream`, `updateWorkstream`, `deleteWorkstream`, `listTasks`, `createTask`, `getTask`, `updateTask`, `deleteTask`, `listLabels`, `createLabel`, `updateLabel`, `deleteLabel`, `adminListTeams`, `getAdminSettings`, `updateAdminSettings`.

- [ ] **Step 1: Create `lib/types.ts`**

```typescript
export type TeamRole = 'owner' | 'admin' | 'member';
export type WorkspaceRole = 'admin' | 'member';
export type TaskStatus = 'backlog' | 'todo' | 'in_progress' | 'in_review' | 'done' | 'canceled';
export type TaskPriority = 'urgent' | 'high' | 'medium' | 'low';
export type Visibility = 'team' | 'restricted';

export interface Team {
	id: string;
	key: string;
	name: string;
	icon?: string | null;
	task_seq: number;
	archived: boolean;
	created_by_id?: string | null;
	created_at: number;
	updated_at: number;
}

export interface Workspace {
	id: string;
	team_id: string;
	name: string;
	icon?: string | null;
	visibility: Visibility;
	archived: boolean;
	created_by_id?: string | null;
	created_at: number;
	updated_at: number;
}

export interface Workstream {
	id: string;
	workspace_id: string;
	name: string;
	icon?: string | null;
	archived: boolean;
	created_by_id?: string | null;
	created_at: number;
	updated_at: number;
}

export interface Label {
	id: string;
	team_id: string;
	name: string;
	color: string;
	created_at: number;
}

export interface Task {
	id: string;
	workstream_id: string;
	team_id: string;
	number: number;
	key: string;
	title: string;
	description?: string | null;
	status: TaskStatus;
	priority?: TaskPriority | null;
	assignee_id?: string | null;
	due_date?: number | null;
	progress: number;
	labels: string[];
	sort_key: number;
	created_by_id?: string | null;
	completed_at?: number | null;
	created_at: number;
	updated_at: number;
}

export interface Member {
	id: string;
	team_id?: string;
	workspace_id?: string;
	user_id: string;
	role: TeamRole | WorkspaceRole;
	created_at: number;
}

export interface Bootstrap {
	teams: Team[];
	workspaces: Workspace[];
	workstreams: Workstream[];
	roles: Record<string, TeamRole>;
}

export interface WorkosRules {
	team_creation: 'all_users' | 'admins_only';
	default_workspace_visibility: Visibility;
}

export const STATUS_ORDER: TaskStatus[] = ['backlog', 'todo', 'in_progress', 'in_review', 'done'];

export const STATUS_LABEL: Record<TaskStatus, string> = {
	backlog: 'Backlog',
	todo: 'Todo',
	in_progress: 'In Progress',
	in_review: 'In Review',
	done: 'Done',
	canceled: 'Canceled'
};

export const PRIORITY_ORDER: TaskPriority[] = ['urgent', 'high', 'medium', 'low'];
```

- [ ] **Step 2: Create `lib/api.ts`**

```typescript
import { WEBUI_API_BASE_URL } from '$lib/constants';
import type {
	Bootstrap, Team, Workspace, Workstream, Label, Task, Member, WorkosRules,
	TaskStatus, TaskPriority, Visibility, TeamRole, WorkspaceRole
} from './types';

const BASE = `${WEBUI_API_BASE_URL}/workos`;

async function request<T>(token: string, path: string, method = 'GET', body?: unknown): Promise<T> {
	let error: unknown = null;
	const res = await fetch(`${BASE}${path}`, {
		method,
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		...(body !== undefined ? { body: JSON.stringify(body) } : {})
	})
		.then(async (r) => {
			if (!r.ok) throw await r.json();
			return r.json();
		})
		.catch((err) => {
			error = err?.detail ?? err;
			console.error('[workos api]', error);
			return null;
		});
	if (error) throw error;
	return res as T;
}

// Bootstrap
export const getBootstrap = (token: string) => request<Bootstrap>(token, '/bootstrap');

// Teams
export const listTeams = (token: string) => request<Team[]>(token, '/teams');
export const createTeam = (token: string, body: { name: string; key: string; icon?: string }) =>
	request<Team>(token, '/teams', 'POST', body);
export const getTeam = (token: string, id: string) => request<Team>(token, `/teams/${id}`);
export const updateTeam = (token: string, id: string, body: Partial<Pick<Team, 'name' | 'icon' | 'archived'>>) =>
	request<Team>(token, `/teams/${id}`, 'PATCH', body);
export const deleteTeam = (token: string, id: string) => request<{ deleted: boolean }>(token, `/teams/${id}`, 'DELETE');
export const listTeamMembers = (token: string, id: string) => request<Member[]>(token, `/teams/${id}/members`);
export const addTeamMember = (token: string, id: string, body: { user_id: string; role: TeamRole }) =>
	request<Member>(token, `/teams/${id}/members`, 'POST', body);
export const updateTeamMember = (token: string, id: string, userId: string, body: { role: TeamRole }) =>
	request<Member>(token, `/teams/${id}/members/${userId}`, 'PATCH', body);
export const removeTeamMember = (token: string, id: string, userId: string) =>
	request<{ removed: boolean }>(token, `/teams/${id}/members/${userId}`, 'DELETE');

// Workspaces
export const listWorkspaces = (token: string, teamId: string) =>
	request<Workspace[]>(token, `/teams/${teamId}/workspaces`);
export const createWorkspace = (
	token: string, teamId: string, body: { name: string; icon?: string; visibility: Visibility }
) => request<Workspace>(token, `/teams/${teamId}/workspaces`, 'POST', body);
export const getWorkspace = (token: string, id: string) => request<Workspace>(token, `/workspaces/${id}`);
export const updateWorkspace = (
	token: string, id: string, body: Partial<Pick<Workspace, 'name' | 'icon' | 'visibility' | 'archived'>>
) => request<Workspace>(token, `/workspaces/${id}`, 'PATCH', body);
export const deleteWorkspace = (token: string, id: string) =>
	request<{ deleted: boolean }>(token, `/workspaces/${id}`, 'DELETE');
export const listWorkspaceMembers = (token: string, id: string) =>
	request<Member[]>(token, `/workspaces/${id}/members`);
export const addWorkspaceMember = (token: string, id: string, body: { user_id: string; role: WorkspaceRole }) =>
	request<Member>(token, `/workspaces/${id}/members`, 'POST', body);
export const updateWorkspaceMember = (token: string, id: string, userId: string, body: { role: WorkspaceRole }) =>
	request<Member>(token, `/workspaces/${id}/members/${userId}`, 'PATCH', body);
export const removeWorkspaceMember = (token: string, id: string, userId: string) =>
	request<{ removed: boolean }>(token, `/workspaces/${id}/members/${userId}`, 'DELETE');

// Workstreams
export const listWorkstreams = (token: string, workspaceId: string) =>
	request<Workstream[]>(token, `/workspaces/${workspaceId}/workstreams`);
export const createWorkstream = (token: string, workspaceId: string, body: { name: string; icon?: string }) =>
	request<Workstream>(token, `/workspaces/${workspaceId}/workstreams`, 'POST', body);
export const updateWorkstream = (
	token: string, id: string, body: Partial<Pick<Workstream, 'name' | 'icon' | 'archived'>>
) => request<Workstream>(token, `/workstreams/${id}`, 'PATCH', body);
export const deleteWorkstream = (token: string, id: string) =>
	request<{ deleted: boolean }>(token, `/workstreams/${id}`, 'DELETE');

// Tasks
export const listTasks = (token: string, workstreamId: string) =>
	request<Task[]>(token, `/workstreams/${workstreamId}/tasks`);
export const createTask = (
	token: string, workstreamId: string,
	body: { title: string; description?: string; status?: TaskStatus; priority?: TaskPriority | null;
		assignee_id?: string | null; due_date?: number | null; labels?: string[] }
) => request<Task>(token, `/workstreams/${workstreamId}/tasks`, 'POST', body);
export const getTask = (token: string, id: string) => request<Task>(token, `/tasks/${id}`);
export const updateTask = (
	token: string, id: string,
	body: Partial<Pick<Task, 'title' | 'description' | 'status' | 'priority' | 'assignee_id' | 'due_date'
		| 'progress' | 'labels' | 'sort_key'>>
) => request<Task>(token, `/tasks/${id}`, 'PATCH', body);
export const deleteTask = (token: string, id: string) => request<{ deleted: boolean }>(token, `/tasks/${id}`, 'DELETE');

// Labels
export const listLabels = (token: string, teamId: string) => request<Label[]>(token, `/teams/${teamId}/labels`);
export const createLabel = (token: string, teamId: string, body: { name: string; color: string }) =>
	request<Label>(token, `/teams/${teamId}/labels`, 'POST', body);
export const updateLabel = (token: string, id: string, body: { name?: string; color?: string }) =>
	request<Label>(token, `/labels/${id}`, 'PATCH', body);
export const deleteLabel = (token: string, id: string) => request<{ deleted: boolean }>(token, `/labels/${id}`, 'DELETE');

// Admin
export const adminListTeams = (token: string) =>
	request<{ team: Team; owner_ids: string[]; member_count: number }[]>(token, '/admin/teams');
export const getAdminSettings = (token: string) => request<WorkosRules>(token, '/admin/settings');
export const updateAdminSettings = (token: string, body: Partial<WorkosRules>) =>
	request<WorkosRules>(token, '/admin/settings', 'PATCH', body);
```

- [ ] **Step 3: Type-check**

Run: `npm run check`
Expected: no new TypeScript errors in `src/lib/components/workos/lib/`.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/lib/types.ts src/lib/components/workos/lib/api.ts
git commit -m "feat(workos): add frontend types and API client"
```

---

### Task 14: Frontend authorization helpers (`roles.ts`)

**Files:**
- Create: `src/lib/components/workos/lib/roles.ts`, `src/lib/components/workos/lib/roles.test.ts`

**Interfaces:**
- Produces: `canManageTeam(role)`, `canManageMembers(role)`, `canCreateWorkspace(role)`, `canManageWorkspace(teamRole, wsRole)`, `canDeleteTask(task, userId, teamRole)`, `canUseAdmin(user)`. Mirrors the backend matrix (spec §6).

- [ ] **Step 1: Write the failing test**

Create `src/lib/components/workos/lib/roles.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import {
	canManageTeam, canManageMembers, canCreateWorkspace, canManageWorkspace, canDeleteTask, canUseAdmin
} from './roles';
import type { Task } from './types';

const task = (over: Partial<Task> = {}): Task => ({
	id: 't', workstream_id: 'w', team_id: 'tm', number: 1, key: 'OSL-1', title: 'x',
	status: 'todo', progress: 0, labels: [], sort_key: 1, created_by_id: 'u1',
	created_at: 0, updated_at: 0, ...over
});

describe('roles', () => {
	it('only owner manages the team', () => {
		expect(canManageTeam('owner')).toBe(true);
		expect(canManageTeam('admin')).toBe(false);
		expect(canManageTeam(undefined)).toBe(false);
	});
	it('owner/admin manage members and create workspaces', () => {
		expect(canManageMembers('admin')).toBe(true);
		expect(canManageMembers('member')).toBe(false);
		expect(canCreateWorkspace('owner')).toBe(true);
		expect(canCreateWorkspace('member')).toBe(false);
	});
	it('workspace management: team owner/admin OR workspace admin', () => {
		expect(canManageWorkspace('admin', undefined)).toBe(true);
		expect(canManageWorkspace('member', 'admin')).toBe(true);
		expect(canManageWorkspace('member', 'member')).toBe(false);
	});
	it('task deletion: creator or team admin', () => {
		expect(canDeleteTask(task({ created_by_id: 'u1' }), 'u1', 'member')).toBe(true);
		expect(canDeleteTask(task({ created_by_id: 'u9' }), 'u1', 'member')).toBe(false);
		expect(canDeleteTask(task({ created_by_id: 'u9' }), 'u1', 'admin')).toBe(true);
	});
	it('admin center: system admin or workos_admin permission', () => {
		expect(canUseAdmin({ role: 'admin', permissions: {} })).toBe(true);
		expect(canUseAdmin({ role: 'user', permissions: { features: { workos_admin: true } } })).toBe(true);
		expect(canUseAdmin({ role: 'user', permissions: { features: { workos_admin: false } } })).toBe(false);
	});
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- src/lib/components/workos/lib/roles.test.ts`
Expected: FAIL — cannot resolve `./roles`.

- [ ] **Step 3: Create `lib/roles.ts`**

```typescript
import type { Task, TeamRole, WorkspaceRole } from './types';

export function canManageTeam(role: TeamRole | undefined): boolean {
	return role === 'owner';
}

export function canManageMembers(role: TeamRole | undefined): boolean {
	return role === 'owner' || role === 'admin';
}

export function canCreateWorkspace(role: TeamRole | undefined): boolean {
	return role === 'owner' || role === 'admin';
}

export function canManageWorkspace(
	teamRole: TeamRole | undefined,
	workspaceRole: WorkspaceRole | undefined
): boolean {
	return teamRole === 'owner' || teamRole === 'admin' || workspaceRole === 'admin';
}

export function canDeleteTask(task: Task, userId: string, teamRole: TeamRole | undefined): boolean {
	return task.created_by_id === userId || teamRole === 'owner' || teamRole === 'admin';
}

export function canUseAdmin(user: { role?: string; permissions?: any } | null | undefined): boolean {
	if (!user) return false;
	return user.role === 'admin' || !!user?.permissions?.features?.workos_admin;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test:frontend -- src/lib/components/workos/lib/roles.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/roles.ts src/lib/components/workos/lib/roles.test.ts
git commit -m "feat(workos): add frontend authorization helpers with tests"
```

---

### Task 15: Frontend ordering helpers (`key.ts`)

**Files:**
- Create: `src/lib/components/workos/lib/key.ts`, `src/lib/components/workos/lib/key.test.ts`

**Interfaces:**
- Produces: `midpoint(before: number | null, after: number | null): number` (sort_key for a card dropped between two neighbors), `needsRebalance(keys: number[]): boolean`, `rebalance(count: number): number[]` (evenly spaced keys), `parseKey(key: string): { prefix: string; number: number } | null`.

- [ ] **Step 1: Write the failing test**

Create `src/lib/components/workos/lib/key.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { midpoint, needsRebalance, rebalance, parseKey } from './key';

describe('ordering helpers', () => {
	it('midpoint between two keys', () => {
		expect(midpoint(10, 20)).toBe(15);
	});
	it('midpoint at the top (no before)', () => {
		expect(midpoint(null, 20)).toBe(10);
	});
	it('midpoint at the bottom (no after)', () => {
		expect(midpoint(10, null)).toBe(1010);
	});
	it('midpoint of empty column', () => {
		expect(midpoint(null, null)).toBe(1000);
	});
	it('flags rebalance when neighbors converge', () => {
		expect(needsRebalance([1, 1.0000001])).toBe(true);
		expect(needsRebalance([1, 2, 3])).toBe(false);
	});
	it('rebalance produces evenly spaced ascending keys', () => {
		expect(rebalance(3)).toEqual([1000, 2000, 3000]);
	});
	it('parseKey splits prefix and number', () => {
		expect(parseKey('OSL-2841')).toEqual({ prefix: 'OSL', number: 2841 });
		expect(parseKey('nope')).toBeNull();
	});
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- src/lib/components/workos/lib/key.test.ts`
Expected: FAIL — cannot resolve `./key`.

- [ ] **Step 3: Create `lib/key.ts`**

```typescript
const STEP = 1000;
const MIN_GAP = 1e-4;

/** sort_key for a card dropped between `before` and `after` (either may be null at an edge). */
export function midpoint(before: number | null, after: number | null): number {
	if (before == null && after == null) return STEP;
	if (before == null) return (after as number) - STEP / 2 > 0 ? (after as number) / 2 : (after as number) - 1;
	if (after == null) return before + STEP;
	return (before + after) / 2;
}

/** True if any two adjacent keys are closer than MIN_GAP (float precision risk). */
export function needsRebalance(keys: number[]): boolean {
	for (let i = 1; i < keys.length; i++) {
		if (Math.abs(keys[i] - keys[i - 1]) < MIN_GAP) return true;
	}
	return false;
}

/** Evenly spaced ascending keys for `count` items. */
export function rebalance(count: number): number[] {
	return Array.from({ length: count }, (_, i) => (i + 1) * STEP);
}

export function parseKey(key: string): { prefix: string; number: number } | null {
	const m = /^([A-Za-z]+)-(\d+)$/.exec(key);
	return m ? { prefix: m[1], number: parseInt(m[2], 10) } : null;
}
```

> Check the `midpoint(null, 20)` case: `20/2 = 10` (the test expects 10). For `midpoint(10, null)` → `10 + 1000 = 1010`. For empty → `1000`. These match the test.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test:frontend -- src/lib/components/workos/lib/key.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/key.ts src/lib/components/workos/lib/key.test.ts
git commit -m "feat(workos): add sort-key ordering helpers with tests"
```

---

### Task 16: Frontend store (state, optimistic, socket reconcile)

**Files:**
- Create: `src/lib/components/workos/lib/store.ts`, `src/lib/components/workos/lib/store.test.ts`

**Interfaces:**
- Consumes: `./api`, `./types`, `./key` (`midpoint`); global `socket`, `user` from `$lib/stores`.
- Produces stores: `teams`, `workspaces`, `workstreams`, `roles`, `currentTeamId`, `currentWorkstreamId`, `tasks`, `labels`, `members`, `view`, `selectedTaskId`, `loading`; derived `currentTeam`, `currentWorkstream`, `selectedTask`, `tasksByStatus`.
- Produces actions: `loadBootstrap()`, `selectTeam(id)`, `selectWorkstream(id)`, `openTask(id)`, `closeTask()`, `addTask(workstreamId, fields)`, `editTask(id, fields)`, `moveTask(id, status, beforeKey, afterKey)`, `removeTask(id)`, `applyTaskEvent(event, payload)`, `connectRealtime()`, `disconnectRealtime()`, and `token()`.
- `view` type: `'board' | 'list' | 'admin'`.

- [ ] **Step 1: Write the failing test**

Create `src/lib/components/workos/lib/store.test.ts`:

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';

vi.mock('./api', () => ({
	getBootstrap: vi.fn(async () => ({ teams: [], workspaces: [], workstreams: [], roles: {} })),
	listTasks: vi.fn(async () => []),
	listLabels: vi.fn(async () => []),
	createTask: vi.fn(async (t, ws, body) => ({
		id: 'srv-1', workstream_id: ws, team_id: 'tm', number: 1, key: 'OSL-1',
		title: body.title, status: body.status ?? 'backlog', priority: null, progress: 0,
		labels: [], sort_key: 5, created_by_id: 'u1', created_at: 0, updated_at: 0
	})),
	updateTask: vi.fn(async (t, id, body) => ({ id, ...body })),
	deleteTask: vi.fn(async () => ({ deleted: true }))
}));

vi.mock('$lib/stores', () => {
	const { writable } = require('svelte/store');
	return { socket: writable(null), user: writable({ id: 'u1', name: 'Lara', role: 'user' }) };
});

import { tasks, tasksByStatus, applyTaskEvent, currentWorkstreamId } from './store';
import type { Task } from './types';

const mk = (over: Partial<Task>): Task => ({
	id: 'x', workstream_id: 'w1', team_id: 'tm', number: 1, key: 'OSL-1', title: 't',
	status: 'todo', progress: 0, labels: [], sort_key: 1, created_by_id: 'u1',
	created_at: 0, updated_at: 0, ...over
});

beforeEach(() => {
	tasks.set([]);
	currentWorkstreamId.set('w1');
});

describe('store realtime reconcile', () => {
	it('applyTaskEvent created adds a task once (dedupes by id)', () => {
		applyTaskEvent('workos:task.created', mk({ id: 'a' }));
		applyTaskEvent('workos:task.created', mk({ id: 'a' }));
		expect(get(tasks).filter((t) => t.id === 'a')).toHaveLength(1);
	});
	it('applyTaskEvent updated replaces fields', () => {
		tasks.set([mk({ id: 'a', title: 'old' })]);
		applyTaskEvent('workos:task.updated', mk({ id: 'a', title: 'new' }));
		expect(get(tasks)[0].title).toBe('new');
	});
	it('applyTaskEvent deleted removes the task', () => {
		tasks.set([mk({ id: 'a' }), mk({ id: 'b' })]);
		applyTaskEvent('workos:task.deleted', { id: 'a', workstream_id: 'w1' });
		expect(get(tasks).map((t) => t.id)).toEqual(['b']);
	});
	it('ignores events for a different workstream', () => {
		applyTaskEvent('workos:task.created', mk({ id: 'z', workstream_id: 'other' }));
		expect(get(tasks)).toHaveLength(0);
	});
	it('tasksByStatus groups by status', () => {
		tasks.set([mk({ id: 'a', status: 'todo' }), mk({ id: 'b', status: 'done' })]);
		const grouped = get(tasksByStatus);
		expect(grouped.todo.map((t) => t.id)).toEqual(['a']);
		expect(grouped.done.map((t) => t.id)).toEqual(['b']);
	});
});

describe('store optimistic add', () => {
	it('addTask inserts optimistically then reconciles to the server task', async () => {
		const { addTask } = await import('./store');
		await addTask('w1', { title: 'New' });
		const ids = get(tasks).map((t) => t.id);
		expect(ids).toContain('srv-1'); // server id present after reconcile
		expect(get(tasks).filter((t) => t.title === 'New')).toHaveLength(1); // no duplicate
	});
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- src/lib/components/workos/lib/store.test.ts`
Expected: FAIL — cannot resolve `./store`.

- [ ] **Step 3: Create `lib/store.ts`**

```typescript
import { writable, derived, get, type Writable } from 'svelte/store';
import { browser } from '$app/environment';
import { socket, user } from '$lib/stores';
import * as api from './api';
import { midpoint } from './key';
import {
	STATUS_ORDER,
	type Team, type Workspace, type Workstream, type Label, type Task, type Member,
	type TeamRole, type TaskStatus, type TaskPriority
} from './types';

export type ViewKey = 'board' | 'list' | 'admin';

export const teams: Writable<Team[]> = writable([]);
export const workspaces: Writable<Workspace[]> = writable([]);
export const workstreams: Writable<Workstream[]> = writable([]);
export const roles: Writable<Record<string, TeamRole>> = writable({});
export const currentTeamId: Writable<string | null> = writable(null);
export const currentWorkstreamId: Writable<string | null> = writable(null);
export const tasks: Writable<Task[]> = writable([]);
export const labels: Writable<Label[]> = writable([]);
export const members: Writable<Member[]> = writable([]);
export const view: Writable<ViewKey> = writable('board');
export const selectedTaskId: Writable<string | null> = writable(null);
export const loading: Writable<boolean> = writable(false);

export const currentTeam = derived([teams, currentTeamId], ([$t, $id]) => $t.find((x) => x.id === $id) ?? null);
export const currentWorkstream = derived(
	[workstreams, currentWorkstreamId],
	([$s, $id]) => $s.find((x) => x.id === $id) ?? null
);
export const selectedTask = derived(
	[tasks, selectedTaskId],
	([$t, $id]) => $t.find((x) => x.id === $id) ?? null
);
export const tasksByStatus = derived(tasks, ($tasks) => {
	const out: Record<TaskStatus, Task[]> = {
		backlog: [], todo: [], in_progress: [], in_review: [], done: [], canceled: []
	};
	for (const t of [...$tasks].sort((a, b) => a.sort_key - b.sort_key)) out[t.status]?.push(t);
	return out;
});

export function token(): string {
	return browser ? localStorage.token : '';
}

export async function loadBootstrap(): Promise<void> {
	loading.set(true);
	try {
		const b = await api.getBootstrap(token());
		teams.set(b.teams);
		workspaces.set(b.workspaces);
		workstreams.set(b.workstreams);
		roles.set(b.roles);
		if (!get(currentTeamId) && b.teams.length) currentTeamId.set(b.teams[0].id);
		const team = get(currentTeam);
		if (team) labels.set(await api.listLabels(token(), team.id).catch(() => []));
		const firstStream = b.workstreams.find((s) => {
			const ws = b.workspaces.find((w) => w.id === s.workspace_id);
			return ws && ws.team_id === get(currentTeamId);
		});
		if (firstStream && !get(currentWorkstreamId)) await selectWorkstream(firstStream.id);
	} finally {
		loading.set(false);
	}
}

export async function selectTeam(id: string): Promise<void> {
	currentTeamId.set(id);
	currentWorkstreamId.set(null);
	tasks.set([]);
	labels.set(await api.listLabels(token(), id).catch(() => []));
}

export async function selectWorkstream(id: string): Promise<void> {
	const prev = get(currentWorkstreamId);
	if (prev && prev !== id) unsubscribeRoom(prev);
	currentWorkstreamId.set(id);
	selectedTaskId.set(null);
	tasks.set(await api.listTasks(token(), id).catch(() => []));
	subscribeRoom(id);
}

export function openTask(id: string): void {
	selectedTaskId.set(id);
}
export function closeTask(): void {
	selectedTaskId.set(null);
}

export async function addTask(
	workstreamId: string,
	fields: { title: string; status?: TaskStatus; priority?: TaskPriority | null; assignee_id?: string | null }
): Promise<void> {
	const tempId = `temp-${Date.now()}-${Math.round(performance.now())}`;
	const optimistic: Task = {
		id: tempId, workstream_id: workstreamId, team_id: get(currentTeam)?.id ?? '', number: 0, key: '…',
		title: fields.title, status: fields.status ?? 'backlog', priority: fields.priority ?? null,
		assignee_id: fields.assignee_id ?? null, due_date: null, progress: 0, labels: [],
		sort_key: Date.now(), created_by_id: get(user)?.id ?? null, completed_at: null,
		created_at: Date.now(), updated_at: Date.now()
	};
	tasks.update((list) => [...list, optimistic]);
	try {
		const saved = await api.createTask(token(), workstreamId, fields);
		tasks.update((list) => list.map((t) => (t.id === tempId ? saved : t)));
	} catch (e) {
		tasks.update((list) => list.filter((t) => t.id !== tempId)); // rollback
		throw e;
	}
}

export async function editTask(id: string, fields: Partial<Task>): Promise<void> {
	const before = get(tasks).find((t) => t.id === id);
	tasks.update((list) => list.map((t) => (t.id === id ? { ...t, ...fields } : t)));
	try {
		const saved = await api.updateTask(token(), id, fields as any);
		tasks.update((list) => list.map((t) => (t.id === id ? saved : t)));
	} catch (e) {
		if (before) tasks.update((list) => list.map((t) => (t.id === id ? before : t)));
		throw e;
	}
}

export async function moveTask(
	id: string, status: TaskStatus, beforeKey: number | null, afterKey: number | null
): Promise<void> {
	const sort_key = midpoint(beforeKey, afterKey);
	await editTask(id, { status, sort_key });
}

export async function removeTask(id: string): Promise<void> {
	const before = get(tasks);
	tasks.update((list) => list.filter((t) => t.id !== id));
	if (get(selectedTaskId) === id) selectedTaskId.set(null);
	try {
		await api.deleteTask(token(), id);
	} catch (e) {
		tasks.set(before); // rollback
		throw e;
	}
}

/** Reconcile a realtime event into local state. Exported for tests + the socket wiring. */
export function applyTaskEvent(event: string, payload: any): void {
	const ws = get(currentWorkstreamId);
	if (!payload || payload.workstream_id !== ws) return;
	if (event === 'workos:task.created') {
		tasks.update((list) => (list.some((t) => t.id === payload.id) ? list : [...list, payload]));
	} else if (event === 'workos:task.updated') {
		tasks.update((list) => list.map((t) => (t.id === payload.id ? payload : t)));
	} else if (event === 'workos:task.deleted') {
		tasks.update((list) => list.filter((t) => t.id !== payload.id));
		if (get(selectedTaskId) === payload.id) selectedTaskId.set(null);
	}
}

// ──────────────────────────── socket wiring ────────────────────────────

const TASK_EVENTS = ['workos:task.created', 'workos:task.updated', 'workos:task.deleted'];

function subscribeRoom(workstreamId: string): void {
	const s = get(socket);
	if (!s || !browser) return;
	s.emit('workos:subscribe', { auth: { token: token() }, workstream_id: workstreamId });
}

function unsubscribeRoom(workstreamId: string): void {
	const s = get(socket);
	if (!s || !browser) return;
	s.emit('workos:unsubscribe', { workstream_id: workstreamId });
}

let bound = false;
const handlers: Record<string, (p: any) => void> = {};

export function connectRealtime(): void {
	const s = get(socket);
	if (!s || bound) return;
	for (const ev of TASK_EVENTS) {
		handlers[ev] = (payload: any) => applyTaskEvent(ev, payload);
		s.on(ev, handlers[ev]);
	}
	// Re-subscribe on reconnect so the room is rejoined.
	handlers['connect'] = () => {
		const ws = get(currentWorkstreamId);
		if (ws) subscribeRoom(ws);
	};
	s.on('connect', handlers['connect']);
	bound = true;
	const ws = get(currentWorkstreamId);
	if (ws) subscribeRoom(ws);
}

export function disconnectRealtime(): void {
	const s = get(socket);
	if (!s) {
		bound = false;
		return;
	}
	for (const ev of [...TASK_EVENTS, 'connect']) {
		if (handlers[ev]) s.off(ev, handlers[ev]);
	}
	const ws = get(currentWorkstreamId);
	if (ws) unsubscribeRoom(ws);
	bound = false;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test:frontend -- src/lib/components/workos/lib/store.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/store.ts src/lib/components/workos/lib/store.test.ts
git commit -m "feat(workos): add store with optimistic updates and realtime reconcile"
```

---

### Task 17: App shell, icon helper, and rail gate

**Files:**
- Create: `src/lib/components/workos/ui/Icon.svelte`
- Modify: `src/lib/components/workos/WorkOSApp.svelte` (replace placeholder)
- Modify: `src/lib/components/app/railItems.ts` (gate the workos item)
- Modify: `src/lib/components/workos/styles.css` (create minimal; expanded in Task 23)

**Interfaces:**
- Consumes: store (Task 16), chrome components (Task 18 — imported but created next; this task's smoke is deferred until Task 18 exists, so implement Task 18 immediately after).
- Produces: `Icon` component `<Icon name="plus" size={16} />` rendering Lucide paths; `WorkOSApp` mounting the tool; rail visibility gated by `features.workos`.

- [ ] **Step 1: Create `ui/Icon.svelte`** (Lucide paths ported from the prototype)

```svelte
<script lang="ts">
	// Lucide (ISC) path data, ported from the prototype's icon set. 24px grid, 2px stroke.
	const LUCIDE: Record<string, string> = {
		plus: '<path d="M5 12h14M12 5v14"/>',
		search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
		'chevron-right': '<path d="m9 18 6-6-6-6"/>',
		'chevron-down': '<path d="m6 9 6 6 6-6"/>',
		'chevrons-up-down': '<path d="m7 15 5 5 5-5"/><path d="m7 9 5-5 5 5"/>',
		'more-horizontal': '<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>',
		calendar: '<path d="M8 2v4M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/>',
		'message-square': '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
		paperclip: '<path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/>',
		columns: '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M9 3v18M15 3v18"/>',
		list: '<line x1="8" x2="21" y1="6" y2="6"/><line x1="8" x2="21" y1="12" y2="12"/><line x1="8" x2="21" y1="18" y2="18"/><line x1="3" x2="3.01" y1="6" y2="6"/><line x1="3" x2="3.01" y1="12" y2="12"/><line x1="3" x2="3.01" y1="18" y2="18"/>',
		layers: '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 12.5-9.17 4.16a2 2 0 0 1-1.66 0L2 12.5"/><path d="m22 17.5-9.17 4.16a2 2 0 0 1-1.66 0L2 17.5"/>',
		settings: '<circle cx="12" cy="12" r="3"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2"/>',
		x: '<path d="M18 6 6 18M6 6l12 12"/>',
		check: '<path d="M20 6 9 17l-5-5"/>',
		users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
		trash: '<path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
	};

	export let name: string;
	export let size: number = 16;
	export let strokeWidth: number = 2;
</script>

<svg
	width={size}
	height={size}
	viewBox="0 0 24 24"
	fill="none"
	stroke="currentColor"
	stroke-width={strokeWidth}
	stroke-linecap="round"
	stroke-linejoin="round"
	style="flex:none;display:block"
	aria-hidden="true"
>
	{@html LUCIDE[name] ?? ''}
</svg>
```

- [ ] **Step 2: Create a minimal `styles.css`**

Create `src/lib/components/workos/styles.css`:

```css
/* WorkOS tool-local tokens. Expanded in Task 23. */
.workos-root {
	height: 100%;
	width: 100%;
	display: flex;
	min-height: 0;
}
```

- [ ] **Step 3: Replace `WorkOSApp.svelte`**

Overwrite `src/lib/components/workos/WorkOSApp.svelte`:

```svelte
<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import './styles.css';
	import Sidebar from './chrome/Sidebar.svelte';
	import Topbar from './chrome/Topbar.svelte';
	import BoardView from './views/BoardView.svelte';
	import ListView from './views/ListView.svelte';
	import TaskDetail from './views/TaskDetail.svelte';
	import AdminApp from './views/admin/AdminApp.svelte';
	import { canUseAdmin } from './lib/roles';
	import { user } from '$lib/stores';
	import {
		loadBootstrap, connectRealtime, disconnectRealtime,
		view, currentWorkstream, selectedTask, teams, loading
	} from './lib/store';

	// Guard: snap non-admins away from the admin view.
	$: if ($view === 'admin' && !canUseAdmin($user)) view.set('board');

	onMount(async () => {
		await loadBootstrap();
		connectRealtime();
	});
	onDestroy(() => disconnectRealtime());
</script>

<div class="workos-root text-gray-800 dark:text-gray-100">
	<Sidebar />
	<div class="flex-1 flex flex-col min-w-0">
		<Topbar />
		<div class="flex-1 relative min-h-0 bg-gray-50 dark:bg-gray-900">
			{#if $loading && !$teams.length}
				<div class="h-full flex items-center justify-center text-sm text-gray-400">Loading…</div>
			{:else if $view === 'admin'}
				<AdminApp />
			{:else if !$teams.length}
				<div class="h-full flex flex-col items-center justify-center gap-2 text-center px-6">
					<div class="text-lg font-medium">You're not in any teams yet</div>
					<div class="text-sm text-gray-500">Create a team from the sidebar to get started.</div>
				</div>
			{:else if $view === 'list'}
				<ListView />
			{:else}
				<BoardView />
			{/if}
			{#if $selectedTask}
				<TaskDetail />
			{/if}
		</div>
	</div>
</div>
```

- [ ] **Step 4: Gate the rail item**

In `src/lib/components/app/railItems.ts`, change the `workos` item's `visible` predicate from `() => true` to:

```typescript
		visible: ({ user }) =>
			user?.role === 'admin' || (user?.permissions?.features?.workos ?? true)
```

- [ ] **Step 5: Type-check (will report missing chrome/views until Task 18–22)**

Run: `npm run check`
Expected: errors only for not-yet-created `./chrome/*` and `./views/*` imports. These resolve as Tasks 18–22 land. (Do not commit until Step 6.)

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/workos/ui/Icon.svelte src/lib/components/workos/styles.css src/lib/components/workos/WorkOSApp.svelte src/lib/components/app/railItems.ts
git commit -m "feat(workos): app shell, Lucide icon helper, and rail gate"
```

---

### Task 18: Chrome — Sidebar + Topbar

**Files:**
- Create: `src/lib/components/workos/chrome/Sidebar.svelte`, `src/lib/components/workos/chrome/Topbar.svelte`

**Interfaces:**
- Consumes: store; `canUseAdmin`, `canCreateWorkspace` from `roles`; `Icon`; `ThemeSwitcher` from `$lib/components/app/ThemeSwitcher.svelte` (existing). Dispatches modal-open events handled in Task 21 via store flags `openModal`.
- Produces: in `store.ts` add a modal-control store `openModal: Writable<{kind: 'team'|'workspace'|'workstream'|'members'; id?: string} | null>` (add this small store now). Sidebar uses it to trigger create flows; Topbar uses store `view` for Board/List tabs.

- [ ] **Step 1: Add the `openModal` store**

In `src/lib/components/workos/lib/store.ts`, add near the other stores:

```typescript
export type ModalRequest =
	| { kind: 'team' }
	| { kind: 'workspace'; teamId: string }
	| { kind: 'workstream'; workspaceId: string }
	| { kind: 'members'; teamId: string };
export const openModal: Writable<ModalRequest | null> = writable(null);
```

- [ ] **Step 2: Create `chrome/Sidebar.svelte`**

```svelte
<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import ThemeSwitcher from '$lib/components/app/ThemeSwitcher.svelte';
	import { user } from '$lib/stores';
	import { canUseAdmin, canCreateWorkspace } from '../lib/roles';
	import {
		teams, workspaces, workstreams, roles, currentTeam, currentTeamId, currentWorkstreamId,
		selectTeam, selectWorkstream, view, openModal
	} from '../lib/store';

	let teamMenuOpen = false;
	let expanded: Record<string, boolean> = {};

	$: teamWorkspaces = $workspaces.filter((w) => w.team_id === $currentTeamId);
	$: streamsByWs = (wsId: string) => $workstreams.filter((s) => s.workspace_id === wsId);
	$: myRole = $currentTeamId ? $roles[$currentTeamId] : undefined;
</script>

<aside class="w-64 flex-none h-full flex flex-col border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
	<!-- Team switcher -->
	<div class="p-2.5 relative">
		<button
			class="flex items-center gap-2 w-full h-10 px-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-900"
			onclick={() => (teamMenuOpen = !teamMenuOpen)}
		>
			<div class="flex-1 text-left min-w-0">
				<div class="text-sm font-semibold truncate">{$currentTeam?.name ?? 'No team'}</div>
				<div class="text-[11px] text-gray-400">{$currentTeam?.key ?? ''}</div>
			</div>
			<Icon name="chevrons-up-down" size={15} />
		</button>
		{#if teamMenuOpen}
			<div class="absolute left-2.5 right-2.5 mt-1 z-20 rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-lg p-1">
				{#each $teams as t (t.id)}
					<button
						class="flex items-center gap-2 w-full px-2 h-8 rounded text-sm hover:bg-gray-100 dark:hover:bg-gray-800"
						onclick={() => { selectTeam(t.id); teamMenuOpen = false; }}
					>
						<span class="flex-1 text-left truncate">{t.name}</span>
						{#if t.id === $currentTeamId}<Icon name="check" size={14} />{/if}
					</button>
				{/each}
				<button
					class="flex items-center gap-2 w-full px-2 h-8 rounded text-sm text-teal-600 hover:bg-gray-100 dark:hover:bg-gray-800"
					onclick={() => { openModal.set({ kind: 'team' }); teamMenuOpen = false; }}
				>
					<Icon name="plus" size={14} /> New team
				</button>
			</div>
		{/if}
	</div>

	<!-- Workspaces -->
	<div class="flex-1 overflow-y-auto px-2 pb-2">
		<div class="flex items-center justify-between px-2 py-1.5">
			<span class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold">Workspaces</span>
			{#if canCreateWorkspace(myRole) && $currentTeamId}
				<button class="text-gray-400 hover:text-gray-600" onclick={() => openModal.set({ kind: 'workspace', teamId: $currentTeamId })}>
					<Icon name="plus" size={14} />
				</button>
			{/if}
		</div>
		{#each teamWorkspaces as ws (ws.id)}
			<div>
				<button
					class="flex items-center gap-1.5 w-full h-8 px-2 rounded text-sm hover:bg-gray-100 dark:hover:bg-gray-900"
					onclick={() => (expanded[ws.id] = !expanded[ws.id])}
				>
					<Icon name={expanded[ws.id] ? 'chevron-down' : 'chevron-right'} size={14} />
					<span class="flex-1 text-left truncate">{ws.name}</span>
				</button>
				{#if expanded[ws.id]}
					{#each streamsByWs(ws.id) as s (s.id)}
						<button
							class="flex items-center gap-2 w-full h-8 pl-8 pr-2 rounded text-sm hover:bg-gray-100 dark:hover:bg-gray-900"
							class:bg-teal-50={$currentWorkstreamId === s.id}
							onclick={() => { selectWorkstream(s.id); view.set('board'); }}
						>
							<span class="w-1.5 h-1.5 rounded-sm bg-teal-500 flex-none"></span>
							<span class="flex-1 text-left truncate">{s.name}</span>
						</button>
					{/each}
					{#if canCreateWorkspace(myRole)}
						<button
							class="flex items-center gap-2 w-full h-7 pl-8 pr-2 rounded text-xs text-gray-400 hover:text-gray-600"
							onclick={() => openModal.set({ kind: 'workstream', workspaceId: ws.id })}
						>
							<Icon name="plus" size={12} /> New workstream
						</button>
					{/if}
				{/if}
			</div>
		{/each}
	</div>

	<!-- Footer -->
	<div class="border-t border-gray-200 dark:border-gray-800 p-2 flex items-center gap-2">
		<div class="flex-1 min-w-0 text-sm font-medium truncate">{$user?.name ?? ''}</div>
		{#if canUseAdmin($user)}
			<button class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-900" title="WorkOS admin" onclick={() => view.set('admin')}>
				<Icon name="settings" size={16} />
			</button>
		{/if}
		<ThemeSwitcher />
	</div>
</aside>
```

> If `ThemeSwitcher.svelte` requires props, check its signature (`src/lib/components/app/ThemeSwitcher.svelte`) and pass what it needs; otherwise mount as-is.

- [ ] **Step 3: Create `chrome/Topbar.svelte`**

```svelte
<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import { currentWorkstream, currentTeam, workspaces, view, addTask } from '../lib/store';

	let creating = false;
	let title = '';

	$: ws = $currentWorkstream;
	$: parentWorkspace = ws ? $workspaces.find((w) => w.id === ws.workspace_id) : null;

	async function submitNew() {
		if (!title.trim() || !ws) return;
		await addTask(ws.id, { title: title.trim() });
		title = '';
		creating = false;
	}
</script>

<header class="h-12 flex-none flex items-center gap-3 px-3.5 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
	<div class="flex items-center gap-1.5 min-w-0">
		<Icon name="layers" size={16} />
		<span class="text-sm font-semibold truncate">
			{parentWorkspace ? `${parentWorkspace.name} · ` : ''}{ws?.name ?? $currentTeam?.name ?? 'WorkOS'}
		</span>
	</div>

	{#if ws}
		<div class="ml-2 flex items-center gap-1 text-xs">
			<button class="px-2 py-1 rounded {$view === 'board' ? 'bg-gray-100 dark:bg-gray-800 font-medium' : 'text-gray-500'}" onclick={() => view.set('board')}>
				<span class="inline-flex items-center gap-1"><Icon name="columns" size={13} /> Board</span>
			</button>
			<button class="px-2 py-1 rounded {$view === 'list' ? 'bg-gray-100 dark:bg-gray-800 font-medium' : 'text-gray-500'}" onclick={() => view.set('list')}>
				<span class="inline-flex items-center gap-1"><Icon name="list" size={13} /> List</span>
			</button>
		</div>
	{/if}

	<div class="flex-1"></div>

	{#if ws}
		{#if creating}
			<input
				class="text-sm px-2 py-1 rounded border border-gray-300 dark:border-gray-700 bg-transparent w-56"
				placeholder="Task title…"
				bind:value={title}
				onkeydown={(e) => { if (e.key === 'Enter') submitNew(); if (e.key === 'Escape') { creating = false; title = ''; } }}
				autofocus
			/>
			<button class="text-sm px-3 py-1 rounded bg-teal-600 text-white disabled:opacity-50" disabled={!title.trim()} onclick={submitNew}>Add</button>
		{:else}
			<button class="text-sm px-3 py-1 rounded bg-teal-600 text-white inline-flex items-center gap-1" onclick={() => (creating = true)}>
				<Icon name="plus" size={15} /> New task
			</button>
		{/if}
	{/if}
</header>
```

- [ ] **Step 4: Type-check**

Run: `npm run check`
Expected: errors only for not-yet-created `./views/*` imports referenced by `WorkOSApp.svelte`.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/chrome/ src/lib/components/workos/lib/store.ts
git commit -m "feat(workos): add sidebar (team/workspace nav) and topbar"
```

---

### Task 19: Board view (kanban + drag-and-drop)

**Files:**
- Create: `src/lib/components/workos/views/BoardView.svelte`
- Create: `src/lib/components/workos/ui/Pills.svelte` (priority/label/status visuals, reused by List + Detail)

**Interfaces:**
- Consumes: `tasksByStatus`, `currentWorkstream`, `openTask`, `moveTask`, `addTask`, `labels`; `STATUS_ORDER`, `STATUS_LABEL`. Uses `sortablejs` for cross-column DnD; `data-status` on columns, `data-task-id`/`data-sort-key` on cards.
- Produces: `Pills.svelte` exporting components `PriorityPill`, `StatusDot`, `LabelChip` via named `<script context="module">`... (simpler: a single `Pills.svelte` with props `kind`). To keep it simple, `Pills.svelte` takes `{ priority }` OR `{ status }` OR `{ label }` and renders the right pill.

- [ ] **Step 1: Create `ui/Pills.svelte`**

```svelte
<script lang="ts">
	import type { TaskPriority, TaskStatus, Label } from '../lib/types';
	export let priority: TaskPriority | null | undefined = undefined;
	export let status: TaskStatus | undefined = undefined;
	export let label: Label | undefined = undefined;

	const PRIORITY_COLOR: Record<string, string> = {
		urgent: '#dc2626', high: '#ea580c', medium: '#ca8a04', low: '#6b7280'
	};
	const STATUS_COLOR: Record<string, string> = {
		backlog: '#9ca3af', todo: '#6b7280', in_progress: '#2563eb',
		in_review: '#7c3aed', done: '#16a34a', canceled: '#9ca3af'
	};
</script>

{#if priority !== undefined && priority !== null}
	<span class="inline-flex items-center gap-1 text-[11px]" style="color:{PRIORITY_COLOR[priority]}">
		<span class="w-2 h-2 rounded-full" style="background:{PRIORITY_COLOR[priority]}"></span>{priority}
	</span>
{/if}
{#if status}
	<span class="w-2.5 h-2.5 rounded-full inline-block" style="background:{STATUS_COLOR[status]}"></span>
{/if}
{#if label}
	<span class="inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800">
		<span class="w-2 h-2 rounded-full" style="background:{label.color}"></span>{label.name}
	</span>
{/if}
```

- [ ] **Step 2: Create `views/BoardView.svelte`**

```svelte
<script lang="ts">
	import Sortable from 'sortablejs';
	import { onDestroy, tick } from 'svelte';
	import Icon from '../ui/Icon.svelte';
	import Pills from '../ui/Pills.svelte';
	import { STATUS_ORDER, STATUS_LABEL, type TaskStatus } from '../lib/types';
	import { tasksByStatus, currentWorkstream, labels, openTask, moveTask, addTask } from '../lib/store';

	let columnEls: Record<string, HTMLElement> = {};
	let sortables: Sortable[] = [];
	let adding: TaskStatus | null = null;
	let newTitle = '';

	$: byStatus = $tasksByStatus;
	$: labelById = Object.fromEntries($labels.map((l) => [l.id, l]));

	function destroySortables() {
		sortables.forEach((s) => s.destroy());
		sortables = [];
	}

	async function initSortables() {
		destroySortables();
		await tick();
		for (const status of STATUS_ORDER) {
			const el = columnEls[status];
			if (!el) continue;
			sortables.push(
				new Sortable(el, {
					group: 'workos-tasks',
					animation: 150,
					ghostClass: 'opacity-40',
					onEnd: handleEnd
				})
			);
		}
	}

	async function handleEnd(evt: Sortable.SortableEvent) {
		const taskId = evt.item.getAttribute('data-task-id');
		const toStatus = (evt.to as HTMLElement).getAttribute('data-status') as TaskStatus | null;
		if (!taskId || !toStatus) return;
		const newIndex = evt.newIndex ?? 0;

		// Target column from the store, excluding the moved task; insert at newIndex.
		const col = (byStatus[toStatus] ?? []).filter((t) => t.id !== taskId);
		const before = newIndex > 0 ? col[newIndex - 1] : null;
		const after = col[newIndex] ?? null;

		// Revert the DOM move so the Svelte-rendered store stays the source of truth.
		const origin = evt.from as HTMLElement;
		origin.insertBefore(evt.item, origin.children[evt.oldIndex ?? 0] ?? null);

		await moveTask(taskId, toStatus, before ? before.sort_key : null, after ? after.sort_key : null);
	}

	// Re-init when the workstream changes (column nodes are recreated).
	let initedFor: string | null = null;
	$: if ($currentWorkstream && initedFor !== $currentWorkstream.id) {
		initedFor = $currentWorkstream.id;
		initSortables();
	}

	onDestroy(destroySortables);

	async function submitAdd(status: TaskStatus) {
		if (!newTitle.trim() || !$currentWorkstream) return;
		await addTask($currentWorkstream.id, { title: newTitle.trim(), status });
		newTitle = '';
		adding = null;
		await initSortables(); // attach the new card to the sortable list
	}
</script>

<div class="h-full overflow-x-auto flex gap-4 p-4 box-border">
	{#each STATUS_ORDER as status (status)}
		<div class="w-72 flex-none flex flex-col h-full">
			<div class="flex items-center gap-2 px-1 pb-2">
				<Pills {status} />
				<span class="text-sm font-semibold">{STATUS_LABEL[status]}</span>
				<span class="text-xs text-gray-400">{(byStatus[status] ?? []).length}</span>
				<div class="flex-1"></div>
				<button class="text-gray-400 hover:text-gray-600" onclick={() => (adding = status)}><Icon name="plus" size={15} /></button>
			</div>

			<div bind:this={columnEls[status]} data-status={status} class="flex flex-col gap-2 overflow-y-auto flex-1 pb-4 min-h-[8px]">
				{#each byStatus[status] ?? [] as task (task.id)}
					<div
						data-task-id={task.id}
						data-sort-key={task.sort_key}
						class="bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 rounded-lg p-2.5 cursor-pointer hover:shadow-sm"
						onclick={() => openTask(task.id)}
						role="button"
						tabindex="0"
					>
						<div class="flex items-center justify-between mb-1.5">
							<span class="text-[11px] text-gray-400 font-mono">{task.key}</span>
							<Pills priority={task.priority} />
						</div>
						<div class="text-sm font-medium mb-2 leading-snug">{task.title}</div>
						{#if task.labels.length}
							<div class="flex flex-wrap gap-1 mb-2">
								{#each task.labels as lid (lid)}
									{#if labelById[lid]}<Pills label={labelById[lid]} />{/if}
								{/each}
							</div>
						{/if}
						<div class="flex items-center gap-3 text-[11px] text-gray-400">
							{#if task.due_date}
								<span class="inline-flex items-center gap-1"><Icon name="calendar" size={12} />{new Date(task.due_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
							{/if}
							{#if task.progress > 0}<span>{task.progress}%</span>{/if}
						</div>
					</div>
				{/each}
			</div>

			{#if adding === status}
				<input
					class="mt-2 text-sm px-2 py-1.5 rounded border border-gray-300 dark:border-gray-700 bg-transparent"
					placeholder="Task title…"
					bind:value={newTitle}
					onkeydown={(e) => { if (e.key === 'Enter') submitAdd(status); if (e.key === 'Escape') { adding = null; newTitle = ''; } }}
					autofocus
				/>
			{/if}
		</div>
	{/each}
</div>
```

> **DnD verification note:** the revert-then-store-update pattern (mirrors `src/lib/components/admin/Settings/Models/ModelList.svelte`) keeps Svelte authoritative. During the browser smoke (Task 23), drag a card across columns and within a column and confirm: (a) it lands and persists after refresh, (b) no ghost/duplicate node remains. If ghosting appears, ensure the keyed `{#each (task.id)}` and the `insertBefore` revert both run before `moveTask`.

- [ ] **Step 3: Type-check**

Run: `npm run check`
Expected: errors only for the still-missing `./views/ListView.svelte`, `./views/TaskDetail.svelte`, `./views/admin/AdminApp.svelte`.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/views/BoardView.svelte src/lib/components/workos/ui/Pills.svelte
git commit -m "feat(workos): add board view with sortablejs drag-and-drop"
```

---

### Task 20: People directory, List view, Task detail

**Files:**
- Modify: `backend/open_webui/routers/workos.py` (add `GET /directory`)
- Test: `backend/open_webui/test/workos/test_router_directory.py`
- Modify: `src/lib/components/workos/lib/api.ts` (add `getDirectory`), `src/lib/components/workos/lib/store.ts` (add `directory` store + load)
- Create: `src/lib/components/workos/views/ListView.svelte`, `src/lib/components/workos/views/TaskDetail.svelte`

**Interfaces:**
- Produces backend: `GET /directory` → `[{id: str, name: str}]` for users who are members of any team the requester can see (all users for system admins).
- Produces frontend: `getDirectory(token) -> {id,name}[]`; store `directory: Writable<Record<string,{name:string}>>`, helper `displayName(id)`, `initials(id)`. `ListView` (dense grouped rows) and `TaskDetail` (editable slide-over).

- [ ] **Step 1: Write the failing backend test**

Create `backend/open_webui/test/workos/test_router_directory.py`:

```python
import pytest

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_teams import _client, U1


@pytest.mark.asyncio
async def test_directory_returns_team_member_names(monkeypatch):
    async def _fake_names(ids):
        return [{'id': i, 'name': f'User {i}'} for i in ids]

    monkeypatch.setattr(wr, 'resolve_user_names', _fake_names)
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        r = await c.get('/api/v1/workos/directory')
        assert r.status_code == 200
        ids = {row['id'] for row in r.json()}
        assert {'u1', 'u2'} <= ids
```

- [ ] **Step 2: Run it to verify failure**

Run: `cd backend && python -m pytest open_webui/test/workos/test_router_directory.py -v`
Expected: FAIL — route not defined.

- [ ] **Step 3: Implement `GET /directory`** (append to `routers/workos.py`)

```python
async def resolve_user_names(ids: list) -> list:
    # Wrapper around the Users DAO so tests can monkeypatch a fast stub.
    from open_webui.models.users import Users

    out = []
    for uid in ids:
        u = await Users.get_user_by_id(uid)
        if u:
            out.append({'id': u.id, 'name': u.name})
    return out


@router.get('/directory')
async def directory(request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)):
    await _require_workos(request, user, db)
    teams = await (Teams.list_all(db=db) if user.role == 'admin' else Teams.list_for_user(user.id, db=db))
    ids: set = set()
    for t in teams:
        for m in await TeamMembers.list_for_team(t.id, db=db):
            ids.add(m.user_id)
    ids.add(user.id)
    return await resolve_user_names(sorted(ids))
```

> `Users.get_user_by_id` is the existing per-id accessor used in `socket/main.py`. If a batch accessor `Users.get_users_by_user_ids(ids)` exists in `models/users.py`, prefer it inside `resolve_user_names` for fewer round-trips.

- [ ] **Step 4: Run backend test to verify pass**

Run: `cd backend && python -m pytest open_webui/test/workos/test_router_directory.py -v`
Expected: PASS.

- [ ] **Step 5: Add frontend directory api + store**

In `lib/api.ts` add:

```typescript
export const getDirectory = (token: string) => request<{ id: string; name: string }[]>(token, '/directory');
```

In `lib/store.ts` add a store + helpers, and load it inside `loadBootstrap()`:

```typescript
export const directory: Writable<Record<string, { name: string }>> = writable({});

export function displayName(id: string | null | undefined): string {
	if (!id) return 'Unassigned';
	return get(directory)[id]?.name ?? id;
}
export function initials(id: string | null | undefined): string {
	const n = displayName(id);
	return n === 'Unassigned' ? '–' : n.split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase();
}
```

Inside `loadBootstrap()`, after setting teams, add:

```typescript
		const dir = await api.getDirectory(token()).catch(() => []);
		directory.set(Object.fromEntries(dir.map((u) => [u.id, { name: u.name }])));
```

- [ ] **Step 6: Create `views/ListView.svelte`**

```svelte
<script lang="ts">
	import Pills from '../ui/Pills.svelte';
	import { STATUS_ORDER, STATUS_LABEL } from '../lib/types';
	import { tasksByStatus, openTask, directory, initials } from '../lib/store';

	$: byStatus = $tasksByStatus;
	$: void $directory; // re-render when names load
</script>

<div class="h-full overflow-y-auto py-2">
	{#each STATUS_ORDER as status (status)}
		{#if (byStatus[status] ?? []).length}
			<div class="mb-2">
				<div class="flex items-center gap-2 px-3.5 py-2 sticky top-0 bg-gray-50 dark:bg-gray-900 z-[1]">
					<Pills {status} />
					<span class="text-sm font-semibold">{STATUS_LABEL[status]}</span>
					<span class="text-xs text-gray-400">{byStatus[status].length}</span>
				</div>
				{#each byStatus[status] as task (task.id)}
					<div
						class="grid items-center gap-2.5 h-10 px-3.5 cursor-pointer border-b border-gray-100 dark:border-gray-800 hover:bg-gray-100/60 dark:hover:bg-gray-800/40"
						style="grid-template-columns: 18px 70px 1fr 90px 90px 28px"
						onclick={() => openTask(task.id)}
						role="button"
						tabindex="0"
					>
						<Pills status={task.status} />
						<span class="text-xs text-gray-400 font-mono">{task.key}</span>
						<span class="text-sm font-medium truncate">{task.title}</span>
						<span class="text-xs"><Pills priority={task.priority} /></span>
						<span class="text-xs text-gray-500">
							{task.due_date ? new Date(task.due_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '—'}
						</span>
						<span class="w-6 h-6 rounded-full bg-teal-100 text-teal-800 text-[10px] flex items-center justify-center" title={task.assignee_id ?? ''}>
							{initials(task.assignee_id)}
						</span>
					</div>
				{/each}
			</div>
		{/if}
	{/each}
</div>
```

- [ ] **Step 7: Create `views/TaskDetail.svelte`**

```svelte
<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import Pills from '../ui/Pills.svelte';
	import { STATUS_ORDER, STATUS_LABEL, PRIORITY_ORDER, type TaskStatus, type TaskPriority } from '../lib/types';
	import { user } from '$lib/stores';
	import { canDeleteTask } from '../lib/roles';
	import {
		selectedTask, closeTask, editTask, removeTask, labels, directory, displayName, roles, currentTeam
	} from '../lib/store';

	$: t = $selectedTask;
	$: labelById = Object.fromEntries($labels.map((l) => [l.id, l]));
	$: myRole = $currentTeam ? $roles[$currentTeam.id] : undefined;
	$: void $directory;

	let descDraft = '';
	let editingDesc = false;
	$: if (t && !editingDesc) descDraft = t.description ?? '';

	function toggleLabel(id: string) {
		if (!t) return;
		const has = t.labels.includes(id);
		editTask(t.id, { labels: has ? t.labels.filter((x) => x !== id) : [...t.labels, id] });
	}
</script>

{#if t}
	<div class="absolute inset-0 z-30 flex justify-end">
		<div class="absolute inset-0 bg-black/30" onclick={closeTask} role="presentation"></div>
		<div class="relative w-[460px] max-w-[92%] h-full bg-white dark:bg-gray-950 border-l border-gray-200 dark:border-gray-800 shadow-xl flex flex-col">
			<div class="flex items-center gap-2 px-3 h-11 border-b border-gray-200 dark:border-gray-800">
				<span class="text-xs text-gray-400 font-mono">{t.key}</span>
				<div class="flex-1"></div>
				{#if canDeleteTask(t, $user?.id ?? '', myRole)}
					<button class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-900 text-red-500" title="Delete" onclick={() => removeTask(t.id)}>
						<Icon name="trash" size={15} />
					</button>
				{/if}
				<button class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-900" onclick={closeTask}><Icon name="x" size={16} /></button>
			</div>

			<div class="flex-1 overflow-y-auto p-4">
				<input
					class="w-full text-lg font-semibold bg-transparent mb-4 focus:outline-none"
					value={t.title}
					onchange={(e) => editTask(t.id, { title: (e.target as HTMLInputElement).value })}
				/>

				<div class="space-y-2.5 pb-4 border-b border-gray-200 dark:border-gray-800">
					<div class="flex items-center min-h-8">
						<span class="w-24 text-sm text-gray-400">Status</span>
						<select class="text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded px-2 py-1" value={t.status} onchange={(e) => editTask(t.id, { status: (e.target as HTMLSelectElement).value as TaskStatus })}>
							{#each STATUS_ORDER as s (s)}<option value={s}>{STATUS_LABEL[s]}</option>{/each}
							<option value="canceled">Canceled</option>
						</select>
					</div>
					<div class="flex items-center min-h-8">
						<span class="w-24 text-sm text-gray-400">Priority</span>
						<select class="text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded px-2 py-1" value={t.priority ?? ''} onchange={(e) => { const v = (e.target as HTMLSelectElement).value; editTask(t.id, { priority: (v || null) as TaskPriority | null }); }}>
							<option value="">No priority</option>
							{#each PRIORITY_ORDER as p (p)}<option value={p}>{p}</option>{/each}
						</select>
					</div>
					<div class="flex items-center min-h-8">
						<span class="w-24 text-sm text-gray-400">Assignee</span>
						<select class="text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded px-2 py-1" value={t.assignee_id ?? ''} onchange={(e) => { const v = (e.target as HTMLSelectElement).value; editTask(t.id, { assignee_id: v || null }); }}>
							<option value="">Unassigned</option>
							{#each Object.entries($directory) as [id, u] (id)}<option value={id}>{u.name}</option>{/each}
						</select>
					</div>
					<div class="flex items-center min-h-8">
						<span class="w-24 text-sm text-gray-400">Due date</span>
						<input
							type="date"
							class="text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded px-2 py-1"
							value={t.due_date ? new Date(t.due_date).toISOString().slice(0, 10) : ''}
							onchange={(e) => { const v = (e.target as HTMLInputElement).value; editTask(t.id, { due_date: v ? new Date(v).getTime() : null }); }}
						/>
					</div>
					<div class="flex items-start min-h-8">
						<span class="w-24 text-sm text-gray-400 pt-1">Labels</span>
						<div class="flex flex-wrap gap-1.5">
							{#each $labels as l (l.id)}
								<button class="text-[11px] px-1.5 py-0.5 rounded border {t.labels.includes(l.id) ? 'border-teal-500 bg-teal-50 dark:bg-teal-900/30' : 'border-gray-200 dark:border-gray-700'}" onclick={() => toggleLabel(l.id)}>
									<Pills label={l} />
								</button>
							{/each}
						</div>
					</div>
					<div class="flex items-center min-h-8">
						<span class="w-24 text-sm text-gray-400">Progress</span>
						<input type="range" min="0" max="100" step="5" value={t.progress} onchange={(e) => editTask(t.id, { progress: parseInt((e.target as HTMLInputElement).value, 10) })} />
						<span class="ml-2 text-sm">{t.progress}%</span>
					</div>
				</div>

				<div class="pt-4">
					<div class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold mb-2">Description</div>
					{#if editingDesc}
						<textarea class="w-full text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded p-2 min-h-24" bind:value={descDraft}></textarea>
						<div class="flex gap-2 mt-2">
							<button class="text-sm px-3 py-1 rounded bg-teal-600 text-white" onclick={() => { editTask(t.id, { description: descDraft }); editingDesc = false; }}>Save</button>
							<button class="text-sm px-3 py-1 rounded border border-gray-300 dark:border-gray-700" onclick={() => (editingDesc = false)}>Cancel</button>
						</div>
					{:else}
						<button class="text-sm text-left text-gray-600 dark:text-gray-300 whitespace-pre-wrap w-full" onclick={() => (editingDesc = true)}>
							{t.description || 'Add a description…'}
						</button>
					{/if}
				</div>

				<div class="pt-6 text-xs text-gray-400">Comments &amp; activity arrive in Phase 2.</div>
			</div>
		</div>
	</div>
{/if}
```

- [ ] **Step 8: Type-check + run full frontend tests**

Run: `npm run check && npm run test:frontend -- src/lib/components/workos/`
Expected: type-check passes (only `./views/admin/AdminApp.svelte` may still be missing → create in Task 22; if `npm run check` fails solely on that import, proceed). vitest passes.

- [ ] **Step 9: Commit**

```bash
git add backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_directory.py src/lib/components/workos/lib/api.ts src/lib/components/workos/lib/store.ts src/lib/components/workos/views/ListView.svelte src/lib/components/workos/views/TaskDetail.svelte
git commit -m "feat(workos): add people directory, list view, and task detail slide-over"
```

---

### Task 21: Modals — create entities + manage members

**Files:**
- Create: `src/lib/components/workos/views/ModalHost.svelte`
- Modify: `src/lib/components/workos/WorkOSApp.svelte` (mount `<ModalHost />`)

**Interfaces:**
- Consumes: `openModal` store, api create functions, `loadBootstrap`, `directory`, `currentTeam`, `roles`.
- Produces: a single host driven by `$openModal` rendering Team / Workspace / Workstream create forms and a Members manager; on success it calls `loadBootstrap()` to refresh the nav and closes.

- [ ] **Step 1: Create `views/ModalHost.svelte`**

```svelte
<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import * as api from '../lib/api';
	import {
		openModal, token, loadBootstrap, directory, currentTeam, roles, members
	} from '../lib/store';
	import { canManageMembers } from '../lib/roles';
	import type { TeamRole } from '../lib/types';

	let name = '';
	let key = '';
	let visibility: 'team' | 'restricted' = 'team';
	let busy = false;
	let err = '';

	// Members manager state
	let teamMembers: { user_id: string; role: string }[] = [];
	let addUserId = '';
	let addRole: TeamRole = 'member';

	$: req = $openModal;
	$: if (req) reset(req);

	async function reset(r: NonNullable<typeof req>) {
		name = '';
		key = '';
		visibility = 'team';
		err = '';
		if (r.kind === 'members') {
			teamMembers = (await api.listTeamMembers(token(), r.teamId).catch(() => [])).map((m) => ({ user_id: m.user_id, role: m.role }));
		}
	}

	function close() {
		openModal.set(null);
	}

	async function submit() {
		if (!req) return;
		busy = true;
		err = '';
		try {
			if (req.kind === 'team') {
				await api.createTeam(token(), { name, key: key.toUpperCase() });
			} else if (req.kind === 'workspace') {
				await api.createWorkspace(token(), req.teamId, { name, visibility });
			} else if (req.kind === 'workstream') {
				await api.createWorkstream(token(), req.workspaceId, { name });
			}
			await loadBootstrap();
			close();
		} catch (e: any) {
			err = typeof e === 'string' ? e : (e?.detail ?? 'Something went wrong.');
		} finally {
			busy = false;
		}
	}

	async function addMember(teamId: string) {
		if (!addUserId) return;
		try {
			await api.addTeamMember(token(), teamId, { user_id: addUserId, role: addRole });
			teamMembers = (await api.listTeamMembers(token(), teamId)).map((m) => ({ user_id: m.user_id, role: m.role }));
			addUserId = '';
		} catch (e: any) {
			err = typeof e === 'string' ? e : (e?.detail ?? 'Could not add member.');
		}
	}

	async function changeRole(teamId: string, userId: string, role: TeamRole) {
		await api.updateTeamMember(token(), teamId, userId, { role }).catch(() => {});
		teamMembers = (await api.listTeamMembers(token(), teamId)).map((m) => ({ user_id: m.user_id, role: m.role }));
	}

	async function removeMember(teamId: string, userId: string) {
		await api.removeTeamMember(token(), teamId, userId).catch(() => {});
		teamMembers = teamMembers.filter((m) => m.user_id !== userId);
	}

	const TITLES = { team: 'New team', workspace: 'New workspace', workstream: 'New workstream', members: 'Team members' };
</script>

{#if req}
	<div class="fixed inset-0 z-40 flex items-center justify-center">
		<div class="absolute inset-0 bg-black/40" onclick={close} role="presentation"></div>
		<div class="relative w-[420px] max-w-[92%] rounded-xl bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 shadow-2xl p-5">
			<div class="flex items-center mb-4">
				<h2 class="text-base font-semibold flex-1">{TITLES[req.kind]}</h2>
				<button class="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-900" onclick={close}><Icon name="x" size={16} /></button>
			</div>

			{#if err}<div class="mb-3 text-sm text-red-600">{err}</div>{/if}

			{#if req.kind === 'members'}
				<div class="space-y-2 max-h-72 overflow-y-auto">
					{#each teamMembers as m (m.user_id)}
						<div class="flex items-center gap-2">
							<span class="flex-1 text-sm truncate">{$directory[m.user_id]?.name ?? m.user_id}</span>
							<select class="text-xs border border-gray-200 dark:border-gray-700 rounded px-1 py-0.5 bg-transparent" value={m.role} onchange={(e) => changeRole(req.teamId, m.user_id, (e.target as HTMLSelectElement).value as TeamRole)}>
								<option value="owner">owner</option>
								<option value="admin">admin</option>
								<option value="member">member</option>
							</select>
							<button class="text-red-500 p-1" onclick={() => removeMember(req.teamId, m.user_id)}><Icon name="x" size={14} /></button>
						</div>
					{/each}
				</div>
				<div class="flex items-center gap-2 mt-4 pt-3 border-t border-gray-200 dark:border-gray-800">
					<select class="flex-1 text-sm border border-gray-200 dark:border-gray-700 rounded px-2 py-1 bg-transparent" bind:value={addUserId}>
						<option value="">Add a user…</option>
						{#each Object.entries($directory) as [id, u] (id)}<option value={id}>{u.name}</option>{/each}
					</select>
					<select class="text-sm border border-gray-200 dark:border-gray-700 rounded px-2 py-1 bg-transparent" bind:value={addRole}>
						<option value="member">member</option>
						<option value="admin">admin</option>
						<option value="owner">owner</option>
					</select>
					<button class="text-sm px-3 py-1 rounded bg-teal-600 text-white" onclick={() => addMember(req.teamId)}>Add</button>
				</div>
			{:else}
				<div class="space-y-3">
					<input class="w-full text-sm px-3 py-2 rounded border border-gray-300 dark:border-gray-700 bg-transparent" placeholder="Name" bind:value={name} autofocus />
					{#if req.kind === 'team'}
						<input class="w-full text-sm px-3 py-2 rounded border border-gray-300 dark:border-gray-700 bg-transparent font-mono uppercase" placeholder="Key (e.g. OSL)" bind:value={key} maxlength="6" />
						<p class="text-xs text-gray-400">The key prefixes task numbers, e.g. {(key || 'OSL').toUpperCase()}-1.</p>
					{:else if req.kind === 'workspace'}
						<select class="w-full text-sm px-3 py-2 rounded border border-gray-300 dark:border-gray-700 bg-transparent" bind:value={visibility}>
							<option value="team">Visible to whole team</option>
							<option value="restricted">Restricted to members</option>
						</select>
					{/if}
				</div>
				<div class="flex justify-end gap-2 mt-5">
					<button class="text-sm px-3 py-1.5 rounded border border-gray-300 dark:border-gray-700" onclick={close}>Cancel</button>
					<button class="text-sm px-3 py-1.5 rounded bg-teal-600 text-white disabled:opacity-50" disabled={busy || !name.trim() || (req.kind === 'team' && !key.trim())} onclick={submit}>Create</button>
				</div>
			{/if}
		</div>
	</div>
{/if}
```

- [ ] **Step 2: Mount `<ModalHost />` in `WorkOSApp.svelte`**

Add the import and place `<ModalHost />` just inside the root `<div class="workos-root ...">` (after the closing of the main flex layout, before the root div closes):

```svelte
	import ModalHost from './views/ModalHost.svelte';
```
and just before the final `</div>` of `.workos-root`:
```svelte
	<ModalHost />
```

Also add a "Manage members" entry: in `chrome/Sidebar.svelte`, in the team menu dropdown (after the team list, before "New team"), add when `canManageMembers(myRole)`:

```svelte
				{#if $currentTeamId}
					<button class="flex items-center gap-2 w-full px-2 h-8 rounded text-sm hover:bg-gray-100 dark:hover:bg-gray-800" onclick={() => { openModal.set({ kind: 'members', teamId: $currentTeamId }); teamMenuOpen = false; }}>
						<Icon name="users" size={14} /> Manage members
					</button>
				{/if}
```
(import `canManageMembers` from `../lib/roles` in Sidebar.)

- [ ] **Step 3: Type-check**

Run: `npm run check`
Expected: errors only for the still-missing `./views/admin/AdminApp.svelte`.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/views/ModalHost.svelte src/lib/components/workos/WorkOSApp.svelte src/lib/components/workos/chrome/Sidebar.svelte
git commit -m "feat(workos): add modals for entity creation and member management"
```

---

### Task 22: Admin center UI

**Files:**
- Create: `src/lib/components/workos/views/admin/AdminApp.svelte`, `AccessTab.svelte`, `TeamsTab.svelte`, `RulesTab.svelte`

**Interfaces:**
- Consumes: `adminListTeams`, `getAdminSettings`, `updateAdminSettings`, `deleteTeam`; `view`, `directory`.
- Produces: tabbed admin view (Access / Teams / Rules) gated already by `WorkOSApp`/`canUseAdmin`.

- [ ] **Step 1: Create `views/admin/AccessTab.svelte`** (mirrors Policy Review's AccessTab)

```svelte
<script lang="ts">
	const ROLES = [
		{ perm: 'workos', name: 'WorkOS user', desc: 'Use the WorkOS tool; see and act within teams you belong to.' },
		{ perm: 'workos_admin', name: 'WorkOS admin', desc: 'Open this admin center; oversee all teams and global rules.' }
	];
</script>

<div class="space-y-4">
	<p class="text-sm text-gray-500 max-w-prose">
		Access is controlled by two group permissions, granted per group in the Admin Panel.
		Membership within WorkOS (team/workspace roles) is managed inside each team.
	</p>
	<div class="grid gap-3" style="grid-template-columns: repeat(auto-fit, minmax(220px, 1fr))">
		{#each ROLES as r (r.perm)}
			<div class="border border-gray-200 dark:border-gray-800 rounded-lg p-3.5">
				<div class="text-sm font-semibold">{r.name}</div>
				<code class="text-[11px] text-teal-600 bg-teal-50 dark:bg-teal-900/30 px-1.5 py-0.5 rounded inline-block my-1.5">features.{r.perm}</code>
				<div class="text-xs text-gray-500">{r.desc}</div>
			</div>
		{/each}
	</div>
	<a class="text-sm text-teal-600" href="/admin/users/groups">Manage groups &amp; permissions in the Admin Panel →</a>
	<p class="text-xs text-gray-400">System administrators always have both.</p>
</div>
```

- [ ] **Step 2: Create `views/admin/TeamsTab.svelte`**

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import * as api from '../../lib/api';
	import { token, directory } from '../../lib/store';

	let rows: { team: any; owner_ids: string[]; member_count: number }[] = [];
	let loading = true;

	async function load() {
		rows = await api.adminListTeams(token()).catch(() => []);
		loading = false;
	}
	onMount(load);

	async function archive(id: string) {
		await api.updateTeam(token(), id, { archived: true }).catch(() => {});
		await load();
	}
	async function del(id: string) {
		if (!confirm('Delete this team and everything in it?')) return;
		await api.deleteTeam(token(), id).catch(() => {});
		await load();
	}
</script>

{#if loading}
	<div class="text-sm text-gray-400">Loading…</div>
{:else}
	<table class="w-full text-sm">
		<thead class="text-xs text-gray-400 text-left">
			<tr><th class="py-2">Team</th><th>Key</th><th>Owners</th><th>Members</th><th></th></tr>
		</thead>
		<tbody>
			{#each rows as r (r.team.id)}
				<tr class="border-t border-gray-100 dark:border-gray-800">
					<td class="py-2">{r.team.name}{r.team.archived ? ' (archived)' : ''}</td>
					<td class="font-mono text-xs">{r.team.key}</td>
					<td class="text-xs">{r.owner_ids.map((id) => $directory[id]?.name ?? id).join(', ')}</td>
					<td>{r.member_count}</td>
					<td class="text-right">
						<button class="text-xs text-gray-500 mr-2" onclick={() => archive(r.team.id)}>Archive</button>
						<button class="text-xs text-red-500" onclick={() => del(r.team.id)}>Delete</button>
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
{/if}
```

- [ ] **Step 3: Create `views/admin/RulesTab.svelte`**

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import * as api from '../../lib/api';
	import { token } from '../../lib/store';
	import type { WorkosRules } from '../../lib/types';

	let rules: WorkosRules = { team_creation: 'all_users', default_workspace_visibility: 'team' };
	let toast = '';

	onMount(async () => {
		rules = await api.getAdminSettings(token()).catch(() => rules);
	});

	async function save() {
		rules = await api.updateAdminSettings(token(), rules);
		toast = 'Saved';
		setTimeout(() => (toast = ''), 2000);
	}
</script>

<div class="space-y-4 max-w-md">
	<div>
		<label class="text-sm font-medium" for="tc">Who can create teams</label>
		<select id="tc" class="mt-1 w-full text-sm border border-gray-200 dark:border-gray-700 rounded px-2 py-1.5 bg-transparent" bind:value={rules.team_creation}>
			<option value="all_users">All WorkOS users</option>
			<option value="admins_only">Admins only</option>
		</select>
	</div>
	<div>
		<label class="text-sm font-medium" for="vis">Default workspace visibility</label>
		<select id="vis" class="mt-1 w-full text-sm border border-gray-200 dark:border-gray-700 rounded px-2 py-1.5 bg-transparent" bind:value={rules.default_workspace_visibility}>
			<option value="team">Team</option>
			<option value="restricted">Restricted</option>
		</select>
	</div>
	<div class="pt-2 border-t border-gray-200 dark:border-gray-800">
		<div class="text-sm font-medium mb-1">Fixed sets (Phase 1)</div>
		<div class="text-xs text-gray-500">Statuses: Backlog, Todo, In Progress, In Review, Done, Canceled.</div>
		<div class="text-xs text-gray-500">Priorities: Urgent, High, Medium, Low.</div>
		<div class="text-xs text-gray-400 mt-1">Customization and notification settings arrive in later phases.</div>
	</div>
	<div class="flex items-center gap-3">
		<button class="text-sm px-3 py-1.5 rounded bg-teal-600 text-white" onclick={save}>Save</button>
		{#if toast}<span class="text-sm text-green-600">{toast}</span>{/if}
	</div>
</div>
```

- [ ] **Step 4: Create `views/admin/AdminApp.svelte`**

```svelte
<script lang="ts">
	import AccessTab from './AccessTab.svelte';
	import TeamsTab from './TeamsTab.svelte';
	import RulesTab from './RulesTab.svelte';
	import { view } from '../../lib/store';

	type Tab = 'teams' | 'rules' | 'access';
	let tab: Tab = 'teams';
	const TABS: { id: Tab; label: string }[] = [
		{ id: 'teams', label: 'Teams' },
		{ id: 'rules', label: 'Rules & defaults' },
		{ id: 'access', label: 'Access' }
	];
</script>

<div class="max-w-3xl mx-auto px-6 py-6">
	<div class="flex items-end justify-between mb-4">
		<div>
			<div class="text-[11px] uppercase tracking-wide text-gray-400">WorkOS · Admin</div>
			<h1 class="text-xl font-semibold mt-1">Administration</h1>
		</div>
		<button class="text-sm text-gray-500" onclick={() => view.set('board')}>← Back to board</button>
	</div>
	<nav class="flex gap-1 border-b border-gray-200 dark:border-gray-800 mb-5">
		{#each TABS as t (t.id)}
			<button class="px-3 py-2 text-sm border-b-2 {tab === t.id ? 'border-teal-500 font-medium' : 'border-transparent text-gray-500'}" onclick={() => (tab = t.id)}>{t.label}</button>
		{/each}
	</nav>
	{#if tab === 'teams'}<TeamsTab />{:else if tab === 'rules'}<RulesTab />{:else}<AccessTab />{/if}
</div>
```

- [ ] **Step 5: Type-check + frontend tests**

Run: `npm run check && npm run test:frontend -- src/lib/components/workos/`
Expected: type-check passes with no WorkOS errors; vitest passes.

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/workos/views/admin/
git commit -m "feat(workos): add admin center (access, teams, rules tabs)"
```

---

### Task 23: Integration verification + style polish

**Files:**
- Modify: `src/lib/components/workos/styles.css` (optional polish)

**Interfaces:**
- Consumes: everything. This task has no new code paths — it is the end-to-end gate.

- [ ] **Step 1: Run the full backend suite**

Run: `cd backend && python -m pytest open_webui/test/workos/ -v`
Expected: all WorkOS backend tests pass.

- [ ] **Step 2: Run the full frontend WorkOS tests + type-check + lint**

Run:
```bash
npm run test:frontend -- src/lib/components/workos/
npm run check
npm run lint:frontend
```
Expected: vitest green; `npm run check` reports no errors under `src/lib/components/workos/`; lint clean (fix any reported issues).

> If `lint:frontend` is not a script, use the repo's frontend lint command from `package.json` (e.g. `npm run lint`).

- [ ] **Step 3: Manual browser smoke (use the preview workflow)**

Start the dev server and verify against a real browser:
1. Set `WORKOS_SEED_DEMO=true` (optional) to get demo data, or start empty.
2. Log in, click the **WorkOS** rail item → `/workos` loads the tool (not the placeholder).
3. Empty state → create a team (e.g. `Acme`, key `OSL`) → create a workspace → create a workstream.
4. Add a task from the topbar and from a board column; confirm key is `OSL-1`, `OSL-2`.
5. Drag a card between columns and within a column; refresh — order/status persist.
6. Open a task → change status/priority/assignee/due/labels/progress and edit description → reopen to confirm persistence.
7. Switch to List view → rows grouped by status with the same data.
8. **Realtime:** open `/workos` in a second browser/profile logged in as another member of the same team viewing the same workstream; create/move/edit a task in one and confirm it appears in the other without refresh.
9. As an admin (or a user with `features.workos_admin`), open the admin center (sidebar gear) → Teams/Rules/Access tabs load; change a rule and save.
10. As a user without `features.workos`, confirm the rail item is hidden.

Capture a screenshot of the board with the task detail open as proof.

- [ ] **Step 4: Optional style polish**

Tighten `styles.css` / Tailwind classes to better match the prototype (`Osool Task App.html`) — teal accents (`#026c80` brand), card density, status colors. No behavior changes.

- [ ] **Step 5: Commit**

```bash
git add -A src/lib/components/workos/ backend/open_webui/
git commit -m "test(workos): phase 1 integration verification + style polish"
```

---

## Plan Self-Review

**Spec coverage (spec §-by-§):**
- §3 Decisions — identity (real users via `assignee_id`/`user_id`, WorkOS-owned tables) ✓ Tasks 2–4; membership+roles ✓ Tasks 2–3, 6–7; team+workspace membership ✓ Tasks 3, 7; hybrid visuals ✓ Tasks 17–22; sortablejs DnD ✓ Task 19; realtime ✓ Task 11/16; notifications reserved ✓ Task 4 (reserved tables note) / no build; admin center ✓ Tasks 10, 22; fixed enums ✓ Task 9; per-team labels ✓ Tasks 4, 9; task keys ✓ Tasks 2, 4.
- §4 Layout — backend model/router/migration/seeder/config ✓ Tasks 1–6, 12; frontend structure ✓ Tasks 13–23.
- §5 Data model — 7 tables ✓ Tasks 2–5; reserved Phase 2 tables NOT created ✓.
- §6 Authorization — visibility + mutation matrix ✓ Tasks 6–9 (backend) + Task 14 (frontend mirror).
- §7 API — bootstrap/teams/workspaces/workstreams/tasks/labels/admin + user picker (directory) ✓ Tasks 6–10, 20.
- §8 Realtime — subscribe handler + per-mutation emits + optimistic client patch ✓ Tasks 11, 16.
- §9 Admin center — Access/Teams/Rules + config flags + PersistentConfig ✓ Tasks 1, 10, 22.
- §10 Testing — vitest (roles, key, store) + pytest (router membership, keys, emits, subscribe auth) ✓ Tasks 2–4, 6–12, 14–16, 20.
- §11 Migration & seeding ✓ Tasks 5, 12.

**Deviations from spec, noted intentionally:**
- Added `GET /directory` (Task 20) — not in §7's list but required to render assignee/member names for non-admins (§7 only named the admin-only user list). Scoped to teammates; safe for all WorkOS users.
- `Labels` fetch-by-id uses `update_fields(id, {})` as a read (Task 9) — a clean `Labels.get_by_id` is offered as the preferred alternative.

**Placeholder scan:** no `TBD`/`TODO`/"implement later"; every code step contains full code; commands have expected output. The only "stub" is the TaskDetail comments/activity note, which is intentional Phase-1 scope (comments are Phase 2).

**Type/name consistency:** api fn names ↔ store/component calls verified (`getBootstrap`, `addTask`, `editTask`, `moveTask`, `removeTask`, `applyTaskEvent`, `openModal`, `directory`, `displayName`, `initials`). Backend DAO singletons (`Teams`, `TeamMembers`, `Workspaces`, `WorkspaceMembers`, `Workstreams`, `Labels`, `Tasks`) match across Tasks 2–12. Socket event names (`workos:task.created/updated/deleted`, `workos:workstream.*`, `workos:workspace.*`) and rooms (`workos:workstream:{id}`, `workos:team:{id}`) match between Task 11 (emit) and Task 16 (listen). Status/priority sets match between backend (`STATUSES`/`PRIORITIES`, Task 9) and frontend (`STATUS_ORDER`/`PRIORITY_ORDER`, Task 13).

**Scope:** single cohesive Phase 1 (spine + realtime + admin). Comments/attachments/notifications/dashboard/timeline are explicitly Phase 2/3 and out of every task here.

