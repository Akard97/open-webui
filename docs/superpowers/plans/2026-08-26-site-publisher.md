# Site Publisher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let permission-granted users publish small static websites (HTML + assets) at `/sites/<slug>` with per-site access control (public / all users / specific people / private).

**Architecture:** One new `site` table (file manifest as JSON column, bytes on disk under `DATA_DIR/sites/<site_id>/`), sharing via the existing `access_grant` table (`resource_type='site'`), one backend router serving both the `/api/v1/sites` CRUD API and the unauthenticated-capable `/sites/{slug}` serving routes. Served HTML is isolated with `Content-Security-Policy: sandbox allow-scripts`. Frontend: gated rail item + `/sites` manager page reusing the existing `AccessControl` picker.

**Tech Stack:** FastAPI + SQLAlchemy async (backend), Alembic, SvelteKit (Svelte 5 runes for new components), pytest + httpx ASGITransport, vitest.

**Spec:** `docs/superpowers/specs/2026-08-26-site-publisher-design.md` (commit 5a27e5ed8). Read it first.

## Global Constraints

- Timestamps: **milliseconds** epoch — `def _now() -> int: return int(time.time() * 1000)`, columns `BigInteger`. (Newer-table convention; do NOT copy policy_review's nanoseconds.)
- Migration `down_revision` MUST be `'d3e4f5a6b7c8'` (current head, verified 2026-08-26).
- Slug rule: `^[a-z0-9][a-z0-9-]{1,58}[a-z0-9]$` (3–60 chars, no leading/trailing hyphen), globally unique.
- Filename rule: `^[A-Za-z0-9][A-Za-z0-9._ -]{0,127}$`.
- Limits: 30 files/site, 10 MB/file, 30 MB/site total.
- Served-file headers (every response): `Content-Security-Policy: sandbox allow-scripts`, `X-Content-Type-Options: nosniff`, `Cache-Control: no-cache`.
- Unauthorized (logged-in but no grant) on serving routes → **404**, never 403 (no existence leak).
- Backend tests run from `C:\Projects\open-webui\backend`: `.venv/Scripts/python.exe -m pytest open_webui/test/sites -q`
- Frontend check from repo root: `npm run check` (no NEW errors vs. baseline); vitest: `npx vitest run <file>`.
- **Dirty working tree:** unrelated uncommitted changes exist in `src/lib/constants.ts`, `src/lib/components/chat/Chat.svelte`, `src/lib/components/chat/MessageInput.svelte`, `src/lib/apis/analytics/index.ts`, and BOTH i18n translation.json files. `git add` ONLY the exact files each task's commit step lists. Never `git add -A` or `git add .`.
- New Svelte components use Svelte 5 runes (`$state`, `$derived`, `$effect`, `$props`) — same idiom as `src/lib/components/policy-review/`.
- Commit messages: normal prose, end with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.

---

### Task 1: `site` table — model, DAO, migration

**Files:**
- Create: `backend/open_webui/models/sites.py`
- Create: `backend/open_webui/migrations/versions/e4f5a6b7c8d9_site_publisher.py`
- Create: `backend/open_webui/test/sites/__init__.py` (empty)
- Create: `backend/open_webui/test/sites/conftest.py`
- Test: `backend/open_webui/test/sites/test_models.py`

**Interfaces:**
- Consumes: `open_webui.internal.db` (`Base`, `get_async_db_context`).
- Produces: `Sites` singleton (`from open_webui.models.sites import Sites, SiteModel`) with async methods:
  - `insert_new_site(user_id: str, *, name: str, slug: str, public: bool, files: list[dict], entry_file: str, db=None) -> Optional[SiteModel]` (None on duplicate slug)
  - `get_site_by_id(id: str, db=None) -> Optional[SiteModel]`
  - `get_site_by_slug(slug: str, db=None) -> Optional[SiteModel]`
  - `get_sites_by_user_id(user_id: str, db=None) -> list[SiteModel]` (newest first)
  - `get_all_sites(db=None) -> list[SiteModel]` (newest first)
  - `update_site_by_id(id: str, updates: dict, db=None) -> Optional[SiteModel]` (None on duplicate slug or missing row)
  - `delete_site_by_id(id: str, db=None) -> bool`
- `SiteModel` fields: `id, user_id, name, slug, public: bool, files: list, entry_file, created_at: int, updated_at: int`.

- [ ] **Step 1: Write conftest** (copy of the policy_review pattern, registering the sites + access_grant tables)

`backend/open_webui/test/sites/conftest.py`:

```python
import os
import tempfile

# Must run before importing open_webui.* — these configure the engine at import time.
_DB_FILE = tempfile.mktemp(suffix='.db')
os.environ['DATABASE_URL'] = f'sqlite:///{_DB_FILE}'
os.environ['ENABLE_DB_MIGRATIONS'] = 'false'

import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402

from open_webui.internal.db import Base, async_engine, engine  # noqa: E402
import open_webui.models.sites  # noqa: E402,F401  (register tables on Base)
import open_webui.models.access_grants  # noqa: E402,F401
import open_webui.models.groups  # noqa: E402,F401

# Pre-create the config table read at import time by open_webui.config
# (migrations are disabled for tests). Same workaround as test/policy_review.
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

Also create empty `backend/open_webui/test/sites/__init__.py`.

- [ ] **Step 2: Write failing model tests**

`backend/open_webui/test/sites/test_models.py`:

```python
import pytest

from open_webui.models.sites import Sites


def _files():
    return [{'name': 'index.html', 'size': 120, 'content_type': 'text/html'}]


@pytest.mark.asyncio
async def test_insert_and_get():
    site = await Sites.insert_new_site(
        'u1', name='My Page', slug='my-page', public=False, files=_files(), entry_file='index.html'
    )
    assert site is not None
    assert site.slug == 'my-page'
    assert site.public is False
    assert site.files[0]['name'] == 'index.html'
    assert site.created_at > 10**12  # ms epoch, not seconds

    by_id = await Sites.get_site_by_id(site.id)
    by_slug = await Sites.get_site_by_slug('my-page')
    assert by_id.id == site.id and by_slug.id == site.id


@pytest.mark.asyncio
async def test_duplicate_slug_returns_none():
    a = await Sites.insert_new_site('u1', name='A', slug='taken', public=False, files=_files(), entry_file='index.html')
    b = await Sites.insert_new_site('u2', name='B', slug='taken', public=False, files=_files(), entry_file='index.html')
    assert a is not None
    assert b is None


@pytest.mark.asyncio
async def test_update_and_slug_conflict():
    a = await Sites.insert_new_site('u1', name='A', slug='site-a', public=False, files=_files(), entry_file='index.html')
    b = await Sites.insert_new_site('u1', name='B', slug='site-b', public=False, files=_files(), entry_file='index.html')

    updated = await Sites.update_site_by_id(a.id, {'name': 'A2', 'public': True})
    assert updated.name == 'A2' and updated.public is True
    assert updated.updated_at >= a.updated_at

    conflict = await Sites.update_site_by_id(a.id, {'slug': 'site-b'})
    assert conflict is None
    assert (await Sites.get_site_by_id(a.id)).slug == 'site-a'
    assert b is not None


@pytest.mark.asyncio
async def test_list_and_delete():
    await Sites.insert_new_site('u1', name='A', slug='aaa', public=False, files=_files(), entry_file='index.html')
    s2 = await Sites.insert_new_site('u1', name='B', slug='bbb', public=False, files=_files(), entry_file='index.html')
    await Sites.insert_new_site('u2', name='C', slug='ccc', public=False, files=_files(), entry_file='index.html')

    mine = await Sites.get_sites_by_user_id('u1')
    assert [s.slug for s in mine] == ['bbb', 'aaa']  # newest first
    assert len(await Sites.get_all_sites()) == 3

    assert await Sites.delete_site_by_id(s2.id) is True
    assert await Sites.get_site_by_id(s2.id) is None
    assert await Sites.delete_site_by_id('nope') is False
```

- [ ] **Step 3: Run tests, verify they fail**

From `backend/`: `.venv/Scripts/python.exe -m pytest open_webui/test/sites -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'open_webui.models.sites'`

- [ ] **Step 4: Write the model**

`backend/open_webui/models/sites.py`:

```python
import time
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, JSON, Text, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.internal.db import Base, get_async_db_context


def _now() -> int:
    return int(time.time() * 1000)


class Site(Base):
    __tablename__ = 'site'

    id = Column(Text, primary_key=True)
    user_id = Column(Text, nullable=False, index=True)
    name = Column(Text, nullable=False)
    slug = Column(Text, nullable=False, unique=True, index=True)
    public = Column(Boolean, nullable=False, default=False)
    files = Column(JSON, nullable=False)  # [{"name","size","content_type"}]
    entry_file = Column(Text, nullable=False)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


class SiteModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    name: str
    slug: str
    public: bool
    files: list
    entry_file: str
    created_at: int
    updated_at: int


class SitesTable:
    async def insert_new_site(
        self,
        user_id: str,
        *,
        name: str,
        slug: str,
        public: bool,
        files: list[dict],
        entry_file: str,
        db: Optional[AsyncSession] = None,
    ) -> Optional[SiteModel]:
        async with get_async_db_context(db) as db:
            now = _now()
            site = Site(
                id=str(uuid.uuid4()),
                user_id=user_id,
                name=name,
                slug=slug,
                public=public,
                files=files,
                entry_file=entry_file,
                created_at=now,
                updated_at=now,
            )
            db.add(site)
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
                return None
            await db.refresh(site)
            return SiteModel.model_validate(site)

    async def get_site_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[SiteModel]:
        async with get_async_db_context(db) as db:
            site = (await db.execute(select(Site).filter_by(id=id))).scalars().first()
            return SiteModel.model_validate(site) if site else None

    async def get_site_by_slug(self, slug: str, db: Optional[AsyncSession] = None) -> Optional[SiteModel]:
        async with get_async_db_context(db) as db:
            site = (await db.execute(select(Site).filter_by(slug=slug))).scalars().first()
            return SiteModel.model_validate(site) if site else None

    async def get_sites_by_user_id(self, user_id: str, db: Optional[AsyncSession] = None) -> list[SiteModel]:
        async with get_async_db_context(db) as db:
            result = await db.execute(
                select(Site).filter_by(user_id=user_id).order_by(Site.updated_at.desc())
            )
            return [SiteModel.model_validate(s) for s in result.scalars().all()]

    async def get_all_sites(self, db: Optional[AsyncSession] = None) -> list[SiteModel]:
        async with get_async_db_context(db) as db:
            result = await db.execute(select(Site).order_by(Site.updated_at.desc()))
            return [SiteModel.model_validate(s) for s in result.scalars().all()]

    async def update_site_by_id(
        self, id: str, updates: dict, db: Optional[AsyncSession] = None
    ) -> Optional[SiteModel]:
        async with get_async_db_context(db) as db:
            site = (await db.execute(select(Site).filter_by(id=id))).scalars().first()
            if not site:
                return None
            for key in ('name', 'slug', 'public', 'files', 'entry_file'):
                if key in updates:
                    setattr(site, key, updates[key])
            site.updated_at = _now()
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
                return None
            await db.refresh(site)
            return SiteModel.model_validate(site)

    async def delete_site_by_id(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            result = await db.execute(delete(Site).filter_by(id=id))
            await db.commit()
            return result.rowcount > 0


Sites = SitesTable()
```

- [ ] **Step 5: Run tests, verify they pass**

`.venv/Scripts/python.exe -m pytest open_webui/test/sites -q`
Expected: 4 passed

- [ ] **Step 6: Write the migration**

`backend/open_webui/migrations/versions/e4f5a6b7c8d9_site_publisher.py`:

```python
"""site table for the Site Publisher bonus tool

Spec: docs/superpowers/specs/2026-08-26-site-publisher-design.md

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'site',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('slug', sa.Text(), nullable=False),
        sa.Column('public', sa.Boolean(), nullable=False),
        sa.Column('files', sa.JSON(), nullable=False),
        sa.Column('entry_file', sa.Text(), nullable=False),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug', name='uq_site_slug'),
    )
    op.create_index('ix_site_user_id', 'site', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_site_user_id', table_name='site')
    op.drop_table('site')
```

- [ ] **Step 7: Commit**

```bash
git add backend/open_webui/models/sites.py backend/open_webui/migrations/versions/e4f5a6b7c8d9_site_publisher.py backend/open_webui/test/sites/
git commit -m "feat(sites): site table, DAO, and migration for Site Publisher"
```

---

### Task 2: permission flag + CRUD router (create / list / get)

**Files:**
- Modify: `backend/open_webui/config.py` (~line 1568: add env bool after `USER_PERMISSIONS_FEATURES_POLICY_ADMIN`; ~line 1663: add `'site_publisher'` to the `features` dict after `'workos_admin'`)
- Create: `backend/open_webui/routers/sites.py`
- Modify: `backend/open_webui/main.py` (import `sites` in the router import block ~line 420 area; add `app.include_router(sites.router, prefix='/api/v1/sites', tags=['sites'])` next to `usage`/`avatar` at ~line 1500)
- Test: `backend/open_webui/test/sites/test_router_crud.py`

**Interfaces:**
- Consumes: `Sites`/`SiteModel` from Task 1; `AccessGrants.set_access_grants('site', id, grants, db=db)`, `AccessGrants.get_grants_by_resource('site', id, db=db)`; `has_permission` from `open_webui.utils.access_control`; `get_verified_user`, `get_async_session`.
- Produces (used by Tasks 3, 4, 5):
  - module constants `SITES_DIR` (Path), `MAX_FILES_PER_SITE = 30`, `MAX_FILE_SIZE = 10 * 1024 * 1024`, `MAX_SITE_SIZE = 30 * 1024 * 1024`, `SLUG_RE`, `FILENAME_RE`
  - `router` (APIRouter for `/api/v1/sites`)
  - helpers `_require_publisher(request, user, db)`, `_validate_files(uploads) -> list[tuple[str, bytes, str]]`, `_pick_entry(names, requested) -> str`, `_write_site_dir(site_id, validated)`, `_site_response(site, grants) -> SiteResponse`
  - `SiteResponse` pydantic model: all `SiteModel` fields + `access_grants: list = []` + `user_name: Optional[str] = None`
- API contract (Task 5's client): `GET /api/v1/sites/` → `list[SiteResponse]` (`?all=true` admin-only, includes `user_name`); `POST /api/v1/sites/` multipart fields `name`, `slug`, `public` ('true'/'false'), `entry_file` (optional), `access_grants` (JSON string), `files` (repeated) → `SiteResponse`; `GET /api/v1/sites/{id}` → `SiteResponse` with grants.

- [ ] **Step 1: Add the permission flag to config.py**

After the `USER_PERMISSIONS_FEATURES_POLICY_ADMIN` block (~line 1576):

```python
USER_PERMISSIONS_FEATURES_SITE_PUBLISHER = (
    os.environ.get('USER_PERMISSIONS_FEATURES_SITE_PUBLISHER', 'False').lower() == 'true'
)
```

In `DEFAULT_USER_PERMISSIONS['features']` (~line 1663), after `'workos_admin'`:

```python
        'site_publisher': USER_PERMISSIONS_FEATURES_SITE_PUBLISHER,
```

- [ ] **Step 2: Write failing router tests**

`backend/open_webui/test/sites/test_router_crud.py`. Pattern: build a minimal FastAPI app, override `get_verified_user`, monkeypatch `has_permission`, monkeypatch `SITES_DIR` to `tmp_path`. Multipart via httpx `files=` / `data=`.

```python
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

import open_webui.routers.sites as sites_router
from open_webui.models.sites import Sites
from open_webui.models.access_grants import AccessGrants
from open_webui.utils.auth import get_verified_user

USER = SimpleNamespace(id='u1', role='user', name='Pub', email='p@x.io')
OTHER = SimpleNamespace(id='u2', role='user', name='Other', email='o@x.io')
ADMIN = SimpleNamespace(id='a1', role='admin', name='Admin', email='a@x.io')


class _AsyncReturn:
    def __init__(self, value):
        self.value = value

    async def __call__(self, *args, **kwargs):
        return self.value


def _make_app(user):
    app = FastAPI()
    app.state.config = SimpleNamespace(USER_PERMISSIONS={})
    app.include_router(sites_router.router, prefix='/api/v1/sites')
    app.dependency_overrides[get_verified_user] = lambda: user
    return app


def _client(monkeypatch, tmp_path, *, user, allow=True):
    monkeypatch.setattr(sites_router, 'has_permission', _AsyncReturn(allow))
    monkeypatch.setattr(sites_router, 'SITES_DIR', tmp_path)
    return httpx.AsyncClient(transport=ASGITransport(app=_make_app(user)), base_url='http://test')


def _upload(name='index.html', content=b'<h1>hi</h1>'):
    return ('files', (name, content, 'text/html'))


def _form(slug='my-page', **overrides):
    data = {'name': 'My Page', 'slug': slug, 'public': 'false', 'access_grants': '[]'}
    data.update(overrides)
    return data


@pytest.mark.asyncio
async def test_permission_gate(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path, user=USER, allow=False) as c:
        assert (await c.get('/api/v1/sites/')).status_code == 401
        assert (await c.post('/api/v1/sites/', data=_form(), files=[_upload()])).status_code == 401


@pytest.mark.asyncio
async def test_admin_bypasses_permission(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path, user=ADMIN, allow=False) as c:
        assert (await c.get('/api/v1/sites/')).status_code == 200


@pytest.mark.asyncio
async def test_create_site_writes_files_and_grants(monkeypatch, tmp_path):
    grants = [{'principal_type': 'user', 'principal_id': 'u9', 'permission': 'read'}]
    async with _client(monkeypatch, tmp_path, user=USER) as c:
        res = await c.post(
            '/api/v1/sites/',
            data=_form(access_grants=json.dumps(grants)),
            files=[_upload(), _upload('logo.png', b'\x89PNG')],
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body['slug'] == 'my-page'
    assert body['entry_file'] == 'index.html'  # single html auto-picked
    assert {f['name'] for f in body['files']} == {'index.html', 'logo.png'}

    site_dir = tmp_path / body['id']
    assert (site_dir / 'index.html').read_bytes() == b'<h1>hi</h1>'
    stored = await AccessGrants.get_grants_by_resource('site', body['id'])
    assert [(g.principal_type, g.principal_id, g.permission) for g in stored] == [('user', 'u9', 'read')]


@pytest.mark.asyncio
async def test_create_validation_errors(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path, user=USER) as c:
        # bad slug
        assert (await c.post('/api/v1/sites/', data=_form(slug='Bad_Slug'), files=[_upload()])).status_code == 400
        # no html file
        assert (await c.post('/api/v1/sites/', data=_form(slug='no-html'), files=[_upload('a.png', b'x')])).status_code == 400
        # bad filename
        assert (
            await c.post('/api/v1/sites/', data=_form(slug='bad-name'), files=[_upload('../evil.html')])
        ).status_code == 400
        # multiple htmls without entry_file and without index.html
        res = await c.post(
            '/api/v1/sites/', data=_form(slug='two-htmls'), files=[_upload('a.html'), _upload('b.html')]
        )
        assert res.status_code == 400
        # multiple htmls WITH index.html defaults to it
        res = await c.post(
            '/api/v1/sites/', data=_form(slug='with-index'), files=[_upload('index.html'), _upload('b.html')]
        )
        assert res.status_code == 200 and res.json()['entry_file'] == 'index.html'
        # duplicate slug
        assert (await c.post('/api/v1/sites/', data=_form(slug='with-index'), files=[_upload()])).status_code == 400
        # too many files
        many = [_upload(f'f{i}.html') for i in range(31)]
        assert (await c.post('/api/v1/sites/', data=_form(slug='too-many'), files=many)).status_code == 400
        # duplicate filenames in one upload
        assert (
            await c.post('/api/v1/sites/', data=_form(slug='dupes'), files=[_upload(), _upload()])
        ).status_code == 400


@pytest.mark.asyncio
async def test_list_scoping_and_get(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path, user=USER) as c:
        created = (await c.post('/api/v1/sites/', data=_form(), files=[_upload()])).json()
    await Sites.insert_new_site('u2', name='X', slug='other-site', public=False,
                                files=[{'name': 'index.html', 'size': 1, 'content_type': 'text/html'}],
                                entry_file='index.html')

    async with _client(monkeypatch, tmp_path, user=USER) as c:
        mine = (await c.get('/api/v1/sites/')).json()
        assert [s['slug'] for s in mine] == ['my-page']
        # non-admin cannot use ?all=true
        assert [s['slug'] for s in (await c.get('/api/v1/sites/?all=true')).json()] == ['my-page']
        # owner can fetch detail (includes grants key)
        detail = (await c.get(f"/api/v1/sites/{created['id']}")).json()
        assert detail['id'] == created['id'] and 'access_grants' in detail
        # non-owner gets 404
    async with _client(monkeypatch, tmp_path, user=OTHER) as c:
        assert (await c.get(f"/api/v1/sites/{created['id']}")).status_code == 404
    async with _client(monkeypatch, tmp_path, user=ADMIN) as c:
        assert len((await c.get('/api/v1/sites/?all=true')).json()) == 2
        assert (await c.get(f"/api/v1/sites/{created['id']}")).status_code == 200
```

- [ ] **Step 3: Run tests, verify they fail**

`.venv/Scripts/python.exe -m pytest open_webui/test/sites/test_router_crud.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'open_webui.routers.sites'`

- [ ] **Step 4: Write the router (constants, helpers, create/list/get)**

`backend/open_webui/routers/sites.py`:

```python
import json
import logging
import mimetypes
import re
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.constants import ERROR_MESSAGES
from open_webui.env import DATA_DIR
from open_webui.internal.db import get_async_session
from open_webui.models.access_grants import AccessGrants
from open_webui.models.sites import SiteModel, Sites
from open_webui.models.users import Users
from open_webui.utils.access_control import has_permission
from open_webui.utils.auth import get_verified_user

log = logging.getLogger(__name__)

SITES_DIR = DATA_DIR / 'sites'
SITES_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILES_PER_SITE = 30
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_SITE_SIZE = 30 * 1024 * 1024  # 30 MB

SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]{1,58}[a-z0-9]$')
FILENAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._ -]{0,127}$')

router = APIRouter()


class SiteResponse(SiteModel):
    access_grants: list = []
    user_name: Optional[str] = None


class SiteAccessForm(BaseModel):
    public: bool
    access_grants: list[dict] = []


async def _require_publisher(request: Request, user, db: AsyncSession) -> None:
    """Raise 401 unless the user is an admin or holds features.site_publisher."""
    if user.role != 'admin' and not await has_permission(
        user.id, 'features.site_publisher', request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.UNAUTHORIZED)


def _bad(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


async def _validate_files(uploads: list[UploadFile]) -> list[tuple[str, bytes, str]]:
    """Validate names/sizes/limits; return [(name, content, content_type)]."""
    if not uploads:
        raise _bad('At least one file is required.')
    if len(uploads) > MAX_FILES_PER_SITE:
        raise _bad(f'A site can have at most {MAX_FILES_PER_SITE} files.')

    validated: list[tuple[str, bytes, str]] = []
    seen: set[str] = set()
    total = 0
    for upload in uploads:
        name = (upload.filename or '').strip()
        if not FILENAME_RE.match(name):
            raise _bad(f'Invalid file name: {name!r}')
        if name in seen:
            raise _bad(f'Duplicate file name: {name!r}')
        seen.add(name)
        content = await upload.read()
        if len(content) > MAX_FILE_SIZE:
            raise _bad(f'{name!r} exceeds the {MAX_FILE_SIZE // (1024 * 1024)} MB per-file limit.')
        total += len(content)
        if total > MAX_SITE_SIZE:
            raise _bad(f'Site exceeds the {MAX_SITE_SIZE // (1024 * 1024)} MB total size limit.')
        content_type = mimetypes.guess_type(name)[0] or 'application/octet-stream'
        validated.append((name, content, content_type))
    return validated


def _pick_entry(names: list[str], requested: Optional[str]) -> str:
    htmls = [n for n in names if n.lower().endswith(('.html', '.htm'))]
    if not htmls:
        raise _bad('A site must contain at least one HTML file.')
    if requested:
        if requested not in htmls:
            raise _bad('entry_file must be one of the uploaded HTML files.')
        return requested
    if len(htmls) == 1:
        return htmls[0]
    if 'index.html' in htmls:
        return 'index.html'
    raise _bad('Multiple HTML files uploaded — specify entry_file.')


def _parse_grants(raw: str) -> list[dict]:
    try:
        grants = json.loads(raw)
    except json.JSONDecodeError:
        raise _bad('access_grants must be valid JSON.')
    if not isinstance(grants, list):
        raise _bad('access_grants must be a JSON list.')
    return grants


def _write_site_dir(site_id: str, validated: list[tuple[str, bytes, str]]) -> None:
    site_dir = SITES_DIR / site_id
    if site_dir.exists():
        shutil.rmtree(site_dir)
    site_dir.mkdir(parents=True)
    for name, content, _ in validated:
        (site_dir / name).write_bytes(content)


def _manifest(validated: list[tuple[str, bytes, str]]) -> list[dict]:
    return [{'name': n, 'size': len(c), 'content_type': t} for n, c, t in validated]


async def _site_response(site: SiteModel, db: AsyncSession, *, with_user: bool = False) -> SiteResponse:
    grants = await AccessGrants.get_grants_by_resource('site', site.id, db=db)
    user_name = None
    if with_user:
        owner = await Users.get_user_by_id(site.user_id)
        user_name = owner.name if owner else None
    return SiteResponse(
        **site.model_dump(),
        access_grants=[
            {'principal_type': g.principal_type, 'principal_id': g.principal_id, 'permission': g.permission}
            for g in grants
        ],
        user_name=user_name,
    )


@router.get('/', response_model=list[SiteResponse])
async def list_sites(
    request: Request,
    all: bool = False,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require_publisher(request, user, db)
    if all and user.role == 'admin':
        sites = await Sites.get_all_sites(db=db)
        return [await _site_response(s, db, with_user=True) for s in sites]
    sites = await Sites.get_sites_by_user_id(user.id, db=db)
    return [await _site_response(s, db) for s in sites]


@router.post('/', response_model=SiteResponse)
async def create_site(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    public: bool = Form(False),
    entry_file: Optional[str] = Form(None),
    access_grants: str = Form('[]'),
    files: list[UploadFile] = File(...),
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require_publisher(request, user, db)

    name = name.strip()
    if not name:
        raise _bad('Name is required.')
    if not SLUG_RE.match(slug):
        raise _bad('Slug must be 3-60 characters: lowercase letters, digits, hyphens; no leading/trailing hyphen.')
    grants = _parse_grants(access_grants)
    if await Sites.get_site_by_slug(slug, db=db):
        raise _bad('This link is already taken.')

    validated = await _validate_files(files)
    entry = _pick_entry([v[0] for v in validated], entry_file)

    site = await Sites.insert_new_site(
        user.id, name=name, slug=slug, public=public, files=_manifest(validated), entry_file=entry, db=db
    )
    if site is None:
        raise _bad('This link is already taken.')

    _write_site_dir(site.id, validated)
    await AccessGrants.set_access_grants('site', site.id, grants, db=db)
    return await _site_response(site, db)


@router.get('/{id}', response_model=SiteResponse)
async def get_site(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require_publisher(request, user, db)
    site = await Sites.get_site_by_id(id, db=db)
    if not site or (site.user_id != user.id and user.role != 'admin'):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    return await _site_response(site, db, with_user=user.role == 'admin')
```

- [ ] **Step 5: Run tests, verify they pass**

`.venv/Scripts/python.exe -m pytest open_webui/test/sites -q`
Expected: all pass (Task 1's 4 + this module's 6)

- [ ] **Step 6: Register the router in main.py**

In the router import block (search `from open_webui.routers import` — add `sites` to the list). Then next to `app.include_router(usage.router, ...)` (~line 1500):

```python
app.include_router(sites.router, prefix='/api/v1/sites', tags=['sites'])
```

Verify import works: `.venv/Scripts/python.exe -c "from open_webui.routers import sites"` (run from `backend/`; expect no output).

- [ ] **Step 7: Commit**

```bash
git add backend/open_webui/config.py backend/open_webui/routers/sites.py backend/open_webui/main.py backend/open_webui/test/sites/test_router_crud.py
git commit -m "feat(sites): site_publisher permission and sites CRUD API (create/list/get)"
```

---

### Task 3: update / access / delete endpoints

**Files:**
- Modify: `backend/open_webui/routers/sites.py` (append endpoints)
- Test: `backend/open_webui/test/sites/test_router_manage.py`

**Interfaces:**
- Consumes: everything Task 2 produced.
- Produces (Task 5's client):
  - `POST /api/v1/sites/{id}/update` — multipart, ALL fields optional: `name`, `slug`, `entry_file`, `files` (if present → full replace) → `SiteResponse`
  - `POST /api/v1/sites/{id}/access` — JSON `{"public": bool, "access_grants": [...]}` → `SiteResponse`
  - `DELETE /api/v1/sites/{id}` → `{"deleted": true}`

- [ ] **Step 1: Write failing tests**

`backend/open_webui/test/sites/test_router_manage.py` (reuses helpers — copy `_AsyncReturn`, `_make_app`, `_client`, `_upload`, `_form`, `USER`, `OTHER`, `ADMIN` from `test_router_crud.py` verbatim; they are small):

```python
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

import open_webui.routers.sites as sites_router
from open_webui.models.access_grants import AccessGrants
from open_webui.utils.auth import get_verified_user

USER = SimpleNamespace(id='u1', role='user', name='Pub', email='p@x.io')
OTHER = SimpleNamespace(id='u2', role='user', name='Other', email='o@x.io')
ADMIN = SimpleNamespace(id='a1', role='admin', name='Admin', email='a@x.io')


class _AsyncReturn:
    def __init__(self, value):
        self.value = value

    async def __call__(self, *args, **kwargs):
        return self.value


def _make_app(user):
    app = FastAPI()
    app.state.config = SimpleNamespace(USER_PERMISSIONS={})
    app.include_router(sites_router.router, prefix='/api/v1/sites')
    app.dependency_overrides[get_verified_user] = lambda: user
    return app


def _client(monkeypatch, tmp_path, *, user, allow=True):
    monkeypatch.setattr(sites_router, 'has_permission', _AsyncReturn(allow))
    monkeypatch.setattr(sites_router, 'SITES_DIR', tmp_path)
    return httpx.AsyncClient(transport=ASGITransport(app=_make_app(user)), base_url='http://test')


def _upload(name='index.html', content=b'<h1>hi</h1>'):
    return ('files', (name, content, 'text/html'))


async def _create(c, slug='my-page'):
    res = await c.post(
        '/api/v1/sites/',
        data={'name': 'My Page', 'slug': slug, 'public': 'false', 'access_grants': '[]'},
        files=[_upload()],
    )
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.asyncio
async def test_update_metadata_only(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path, user=USER) as c:
        site = await _create(c)
        res = await c.post(f"/api/v1/sites/{site['id']}/update", data={'name': 'Renamed', 'slug': 'new-link'})
        assert res.status_code == 200
        body = res.json()
        assert body['name'] == 'Renamed' and body['slug'] == 'new-link'
        # files untouched
        assert (tmp_path / site['id'] / 'index.html').exists()


@pytest.mark.asyncio
async def test_update_replaces_files(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path, user=USER) as c:
        site = await _create(c)
        res = await c.post(
            f"/api/v1/sites/{site['id']}/update",
            data={},
            files=[_upload('main.html', b'<p>new</p>'), _upload('pic.png', b'\x89PNG')],
        )
        assert res.status_code == 200
        body = res.json()
        assert {f['name'] for f in body['files']} == {'main.html', 'pic.png'}
        assert body['entry_file'] == 'main.html'
        assert not (tmp_path / site['id'] / 'index.html').exists()
        assert (tmp_path / site['id'] / 'main.html').read_bytes() == b'<p>new</p>'


@pytest.mark.asyncio
async def test_update_slug_conflict_and_bad_entry(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path, user=USER) as c:
        a = await _create(c, 'site-a')
        await _create(c, 'site-b')
        assert (await c.post(f"/api/v1/sites/{a['id']}/update", data={'slug': 'site-b'})).status_code == 400
        assert (await c.post(f"/api/v1/sites/{a['id']}/update", data={'entry_file': 'nope.html'})).status_code == 400


@pytest.mark.asyncio
async def test_owner_only_unless_admin(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path, user=USER) as c:
        site = await _create(c)
    async with _client(monkeypatch, tmp_path, user=OTHER) as c:
        assert (await c.post(f"/api/v1/sites/{site['id']}/update", data={'name': 'X'})).status_code == 404
        assert (await c.delete(f"/api/v1/sites/{site['id']}")).status_code == 404
    async with _client(monkeypatch, tmp_path, user=ADMIN) as c:
        assert (await c.post(f"/api/v1/sites/{site['id']}/update", data={'name': 'X'})).status_code == 200


@pytest.mark.asyncio
async def test_access_update(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path, user=USER) as c:
        site = await _create(c)
        res = await c.post(
            f"/api/v1/sites/{site['id']}/access",
            json={'public': True, 'access_grants': [{'principal_type': 'user', 'principal_id': '*', 'permission': 'read'}]},
        )
        assert res.status_code == 200
        body = res.json()
        assert body['public'] is True
        grants = await AccessGrants.get_grants_by_resource('site', site['id'])
        assert [(g.principal_id, g.permission) for g in grants] == [('*', 'read')]


@pytest.mark.asyncio
async def test_delete_removes_row_grants_and_folder(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path, user=USER) as c:
        site = await _create(c)
        await c.post(
            f"/api/v1/sites/{site['id']}/access",
            json={'public': False, 'access_grants': [{'principal_type': 'user', 'principal_id': 'u9', 'permission': 'read'}]},
        )
        assert (tmp_path / site['id']).exists()
        res = await c.delete(f"/api/v1/sites/{site['id']}")
        assert res.status_code == 200 and res.json() == {'deleted': True}
        assert not (tmp_path / site['id']).exists()
        assert await AccessGrants.get_grants_by_resource('site', site['id']) == []
        assert (await c.get(f"/api/v1/sites/{site['id']}")).status_code == 404
```

- [ ] **Step 2: Run tests, verify they fail**

`.venv/Scripts/python.exe -m pytest open_webui/test/sites/test_router_manage.py -q`
Expected: FAIL — 404s / 405s (endpoints don't exist)

- [ ] **Step 3: Implement the endpoints** (append to `routers/sites.py`)

```python
async def _get_owned_site(id: str, user, db: AsyncSession) -> SiteModel:
    site = await Sites.get_site_by_id(id, db=db)
    if not site or (site.user_id != user.id and user.role != 'admin'):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    return site


@router.post('/{id}/update', response_model=SiteResponse)
async def update_site(
    request: Request,
    id: str,
    name: Optional[str] = Form(None),
    slug: Optional[str] = Form(None),
    entry_file: Optional[str] = Form(None),
    files: list[UploadFile] = File(default=[]),
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require_publisher(request, user, db)
    site = await _get_owned_site(id, user, db)

    updates: dict = {}
    if name is not None:
        name = name.strip()
        if not name:
            raise _bad('Name cannot be empty.')
        updates['name'] = name
    if slug is not None and slug != site.slug:
        if not SLUG_RE.match(slug):
            raise _bad('Slug must be 3-60 characters: lowercase letters, digits, hyphens; no leading/trailing hyphen.')
        if await Sites.get_site_by_slug(slug, db=db):
            raise _bad('This link is already taken.')
        updates['slug'] = slug

    if files:
        validated = await _validate_files(files)
        updates['files'] = _manifest(validated)
        updates['entry_file'] = _pick_entry([v[0] for v in validated], entry_file)
        _write_site_dir(site.id, validated)
    elif entry_file is not None:
        current_names = [f['name'] for f in site.files]
        updates['entry_file'] = _pick_entry(current_names, entry_file)

    updated = await Sites.update_site_by_id(site.id, updates, db=db)
    if updated is None:
        raise _bad('This link is already taken.')
    return await _site_response(updated, db)


@router.post('/{id}/access', response_model=SiteResponse)
async def update_site_access(
    request: Request,
    id: str,
    form_data: SiteAccessForm,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require_publisher(request, user, db)
    site = await _get_owned_site(id, user, db)
    updated = await Sites.update_site_by_id(site.id, {'public': form_data.public}, db=db)
    await AccessGrants.set_access_grants('site', site.id, form_data.access_grants, db=db)
    return await _site_response(updated, db)


@router.delete('/{id}')
async def delete_site(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require_publisher(request, user, db)
    site = await _get_owned_site(id, user, db)
    await AccessGrants.revoke_all_access('site', site.id, db=db)
    await Sites.delete_site_by_id(site.id, db=db)
    shutil.rmtree(SITES_DIR / site.id, ignore_errors=True)
    return {'deleted': True}
```

- [ ] **Step 4: Run the full sites test suite**

`.venv/Scripts/python.exe -m pytest open_webui/test/sites -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/sites.py backend/open_webui/test/sites/test_router_manage.py
git commit -m "feat(sites): update, access, and delete endpoints"
```

---

### Task 4: serving routes (`/sites/{slug}`)

**Files:**
- Modify: `backend/open_webui/routers/sites.py` (append `serve_router` + optional-auth helper)
- Modify: `backend/open_webui/main.py` (register `serve_router`)
- Test: `backend/open_webui/test/sites/test_serving.py`

**Interfaces:**
- Consumes: `Sites`, `AccessGrants.has_access`, `decode_token` from `open_webui.utils.auth`, `Users` from `open_webui.models.users`.
- Produces: `serve_router` (APIRouter, no prefix) with `GET /sites/{slug}` and `GET /sites/{slug}/{filename}`; helper `_get_optional_user(request) -> Optional[UserModel]`.

- [ ] **Step 1: Write failing tests**

`backend/open_webui/test/sites/test_serving.py`. Auth here is NOT dependency-injected (cookie/bearer, optional), so tests monkeypatch `sites_router._get_optional_user` (module-global lookup happens at call time). The AccessGrant table is real (created by conftest).

```python
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

import open_webui.routers.sites as sites_router
from open_webui.models.access_grants import AccessGrants
from open_webui.models.sites import Sites

VIEWER = SimpleNamespace(id='v1', role='user', name='Viewer', email='v@x.io')
OWNER = SimpleNamespace(id='o1', role='user', name='Owner', email='o@x.io')
ADMIN = SimpleNamespace(id='a1', role='admin', name='Admin', email='a@x.io')


def _app():
    app = FastAPI()
    app.include_router(sites_router.serve_router)
    return app


def _client(monkeypatch, tmp_path, *, viewer):
    async def _fake_optional_user(request):
        return viewer

    monkeypatch.setattr(sites_router, '_get_optional_user', _fake_optional_user)
    monkeypatch.setattr(sites_router, 'SITES_DIR', tmp_path)
    return httpx.AsyncClient(transport=ASGITransport(app=_app()), base_url='http://test')


async def _seed(tmp_path, *, slug='demo', public=False, grants=None):
    site = await Sites.insert_new_site(
        OWNER.id,
        name='Demo',
        slug=slug,
        public=public,
        files=[
            {'name': 'index.html', 'size': 12, 'content_type': 'text/html'},
            {'name': 'pic.png', 'size': 4, 'content_type': 'image/png'},
        ],
        entry_file='index.html',
    )
    d = tmp_path / site.id
    d.mkdir(parents=True)
    (d / 'index.html').write_bytes(b'<h1>demo</h1>')
    (d / 'pic.png').write_bytes(b'\x89PNG')
    if grants:
        await AccessGrants.set_access_grants('site', site.id, grants, db=None)
    return site


@pytest.mark.asyncio
async def test_public_site_served_without_login(monkeypatch, tmp_path):
    await _seed(tmp_path, public=True)
    async with _client(monkeypatch, tmp_path, viewer=None) as c:
        res = await c.get('/sites/demo')
        assert res.status_code == 200
        assert b'demo' in res.content
        assert res.headers['content-security-policy'] == 'sandbox allow-scripts'
        assert res.headers['x-content-type-options'] == 'nosniff'
        assert res.headers['content-type'].startswith('text/html')
        asset = await c.get('/sites/demo/pic.png')
        assert asset.status_code == 200
        assert asset.headers['content-security-policy'] == 'sandbox allow-scripts'


@pytest.mark.asyncio
async def test_anonymous_on_private_site(monkeypatch, tmp_path):
    await _seed(tmp_path)
    async with _client(monkeypatch, tmp_path, viewer=None) as c:
        res = await c.get('/sites/demo')
        assert res.status_code == 302
        assert res.headers['location'].startswith('/auth?redirect=')
        assert (await c.get('/sites/demo/pic.png')).status_code == 401


@pytest.mark.asyncio
async def test_access_matrix(monkeypatch, tmp_path):
    # everyone-logged-in via user:* grant
    await _seed(tmp_path, slug='internal',
                grants=[{'principal_type': 'user', 'principal_id': '*', 'permission': 'read'}])
    # specific user grant
    await _seed(tmp_path, slug='granted',
                grants=[{'principal_type': 'user', 'principal_id': VIEWER.id, 'permission': 'read'}])
    # private
    await _seed(tmp_path, slug='locked')

    async with _client(monkeypatch, tmp_path, viewer=VIEWER) as c:
        assert (await c.get('/sites/internal')).status_code == 200
        assert (await c.get('/sites/granted')).status_code == 200
        assert (await c.get('/sites/locked')).status_code == 404  # no leak
    async with _client(monkeypatch, tmp_path, viewer=OWNER) as c:
        assert (await c.get('/sites/locked')).status_code == 200  # owner
    async with _client(monkeypatch, tmp_path, viewer=ADMIN) as c:
        assert (await c.get('/sites/locked')).status_code == 200  # admin


@pytest.mark.asyncio
async def test_unknown_slug_and_unknown_file(monkeypatch, tmp_path):
    await _seed(tmp_path, public=True)
    async with _client(monkeypatch, tmp_path, viewer=None) as c:
        assert (await c.get('/sites/nope')).status_code == 404
        assert (await c.get('/sites/demo/ghost.png')).status_code == 404


@pytest.mark.asyncio
async def test_traversal_rejected(monkeypatch, tmp_path):
    await _seed(tmp_path, public=True)
    (tmp_path / 'secret.txt').write_text('nope')
    async with _client(monkeypatch, tmp_path, viewer=None) as c:
        # not in manifest -> 404 regardless of encoding tricks
        assert (await c.get('/sites/demo/..%2Fsecret.txt')).status_code == 404
        assert (await c.get('/sites/demo/%2e%2e/secret.txt')).status_code == 404
```

- [ ] **Step 2: Run tests, verify they fail**

`.venv/Scripts/python.exe -m pytest open_webui/test/sites/test_serving.py -q`
Expected: FAIL — `AttributeError: ... has no attribute 'serve_router'`

- [ ] **Step 3: Implement serving** (append to `routers/sites.py`; add imports `os`, `FileResponse`, `RedirectResponse`, `quote`, `decode_token`)

Add to the import block at the top of the file:

```python
import os
from urllib.parse import quote

from fastapi.responses import FileResponse, RedirectResponse

from open_webui.utils.auth import decode_token, get_verified_user  # extend existing line
```

Append:

```python
serve_router = APIRouter()

SERVE_HEADERS = {
    # Opaque origin: scripts run but cannot reach the app's localStorage,
    # cookies, or API with the viewer's credentials.
    'Content-Security-Policy': 'sandbox allow-scripts',
    'X-Content-Type-Options': 'nosniff',
    'Cache-Control': 'no-cache',
}


async def _get_optional_user(request: Request):
    """Resolve the requester from bearer header or token cookie; None if anonymous/invalid."""
    token = None
    auth_header = request.headers.get('authorization') or ''
    if auth_header.lower().startswith('bearer '):
        token = auth_header[7:].strip()
    if not token:
        token = request.cookies.get('token')
    if not token:
        return None
    try:
        data = decode_token(token)
    except Exception:
        return None
    if not data or 'id' not in data:
        return None
    return await Users.get_user_by_id(data['id'])


async def _resolve_site_for_view(slug: str, request: Request, db: AsyncSession, *, is_entry: bool):
    site = await Sites.get_site_by_slug(slug, db=db)
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    if site.public:
        return site
    user = await _get_optional_user(request)
    if user is None:
        if is_entry:
            # Direct navigation: send the browser to login and back.
            return RedirectResponse(url=f'/auth?redirect={quote(f"/sites/{slug}")}', status_code=302)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')
    if user.role == 'admin' or site.user_id == user.id:
        return site
    if await AccessGrants.has_access(
        user_id=user.id, resource_type='site', resource_id=site.id, permission='read', db=db
    ):
        return site
    # Authenticated but not allowed: do not reveal that the site exists.
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')


def _serve_file(site, filename: str) -> FileResponse:
    manifest = {f['name']: f for f in site.files}
    entry = manifest.get(filename)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    site_dir = (SITES_DIR / site.id).resolve()
    file_path = (site_dir / filename).resolve()
    # Defense in depth: the manifest check above should already exclude traversal.
    if not str(file_path).startswith(str(site_dir) + os.sep):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    if not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    return FileResponse(file_path, media_type=entry['content_type'], headers=SERVE_HEADERS)


@serve_router.get('/sites/{slug}')
async def serve_site_entry(
    slug: str, request: Request, db: AsyncSession = Depends(get_async_session)
):
    site = await _resolve_site_for_view(slug, request, db, is_entry=True)
    if isinstance(site, RedirectResponse):
        return site
    return _serve_file(site, site.entry_file)


@serve_router.get('/sites/{slug}/{filename}')
async def serve_site_file(
    slug: str, filename: str, request: Request, db: AsyncSession = Depends(get_async_session)
):
    site = await _resolve_site_for_view(slug, request, db, is_entry=False)
    return _serve_file(site, filename)
```

- [ ] **Step 4: Run tests, verify they pass**

`.venv/Scripts/python.exe -m pytest open_webui/test/sites -q`
Expected: all pass

- [ ] **Step 5: Register serve_router in main.py**

Directly under the Task 2 line:

```python
app.include_router(sites.serve_router, tags=['sites'])
```

(Any `include_router` runs before the `/` SPA mount at the bottom of main.py, so `/sites/{slug}` wins over the catch-all; the bare `/sites` path still falls through to the SPA.)

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/routers/sites.py backend/open_webui/main.py backend/open_webui/test/sites/test_serving.py
git commit -m "feat(sites): public serving routes with CSP sandbox isolation"
```

---

### Task 5: frontend plumbing — API client, visibility, rail item, route shell

**Files:**
- Create: `src/lib/apis/sites/index.ts`
- Create: `src/lib/components/sites/lib/visibility.ts`
- Create: `src/lib/components/sites/lib/visibility.test.ts`
- Modify: `src/lib/components/app/railItems.ts` (add import + one entry)
- Create: `src/routes/(app)/sites/+layout.svelte`
- Create: `src/routes/(app)/sites/+page.svelte`
- Create: `src/lib/components/sites/SitesPage.svelte` (placeholder shell this task; real UI in Task 6)

**Interfaces:**
- Consumes: `WEBUI_API_BASE_URL` from `$lib/constants`; `GlobeAlt` icon (`$lib/components/icons/GlobeAlt.svelte`, exists); rail `RailItem` type; `user` store.
- Produces (Task 6 consumes):
  - `canSeeSites(ctx: {user: any}) : boolean`
  - API functions (token first arg, `localStorage.token` caller-side):
    - `getSites(token: string, all?: boolean): Promise<any[]>`
    - `getSiteById(token: string, id: string): Promise<any>`
    - `createSite(token: string, formData: FormData): Promise<any>`
    - `updateSite(token: string, id: string, formData: FormData): Promise<any>`
    - `updateSiteAccess(token: string, id: string, body: {public: boolean; access_grants: any[]}): Promise<any>`
    - `deleteSite(token: string, id: string): Promise<any>`

- [ ] **Step 1: Write the visibility predicate + test**

`src/lib/components/sites/lib/visibility.ts`:

```ts
/**
 * Single source of truth for who can see the Site Publisher tool.
 * Admins always; otherwise the admin-granted site_publisher permission.
 * Used by the rail (railItems.ts) and the route guard
 * (routes/(app)/sites/+layout.svelte) so they cannot disagree.
 */
export function canSeeSites({ user }: { user: any }): boolean {
	return user?.role === 'admin' || !!user?.permissions?.features?.site_publisher;
}
```

`src/lib/components/sites/lib/visibility.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { canSeeSites } from './visibility';

describe('canSeeSites', () => {
	it.each([
		[{ user: { role: 'admin' } }, true],
		[{ user: { role: 'user', permissions: { features: { site_publisher: true } } } }, true],
		[{ user: { role: 'user', permissions: { features: { site_publisher: false } } } }, false],
		[{ user: { role: 'user', permissions: { features: {} } } }, false],
		[{ user: { role: 'user' } }, false],
		[{ user: undefined }, false]
	])('%j -> %s', (ctx, expected) => {
		expect(canSeeSites(ctx as any)).toBe(expected);
	});
});
```

- [ ] **Step 2: Run the test**

`npx vitest run src/lib/components/sites/lib/visibility.test.ts`
Expected: 6 passed

- [ ] **Step 3: Write the API client**

`src/lib/apis/sites/index.ts` (repo's standard fetch idiom; multipart calls must NOT set Content-Type — the browser adds the boundary):

```ts
import { WEBUI_API_BASE_URL } from '$lib/constants';

const jsonHeaders = (token: string) => ({
	Accept: 'application/json',
	'Content-Type': 'application/json',
	authorization: `Bearer ${token}`
});

const handle = async (res: Response) => {
	if (!res.ok) throw await res.json();
	return res.json();
};

export const getSites = async (token: string = '', all: boolean = false) => {
	let error = null;
	const res = await fetch(`${WEBUI_API_BASE_URL}/sites/${all ? '?all=true' : ''}`, {
		method: 'GET',
		headers: jsonHeaders(token)
	})
		.then(handle)
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});
	if (error) throw error;
	return res;
};

export const getSiteById = async (token: string = '', id: string) => {
	let error = null;
	const res = await fetch(`${WEBUI_API_BASE_URL}/sites/${encodeURIComponent(id)}`, {
		method: 'GET',
		headers: jsonHeaders(token)
	})
		.then(handle)
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});
	if (error) throw error;
	return res;
};

export const createSite = async (token: string = '', formData: FormData) => {
	let error = null;
	const res = await fetch(`${WEBUI_API_BASE_URL}/sites/`, {
		method: 'POST',
		headers: { Accept: 'application/json', authorization: `Bearer ${token}` },
		body: formData
	})
		.then(handle)
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});
	if (error) throw error;
	return res;
};

export const updateSite = async (token: string = '', id: string, formData: FormData) => {
	let error = null;
	const res = await fetch(`${WEBUI_API_BASE_URL}/sites/${encodeURIComponent(id)}/update`, {
		method: 'POST',
		headers: { Accept: 'application/json', authorization: `Bearer ${token}` },
		body: formData
	})
		.then(handle)
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});
	if (error) throw error;
	return res;
};

export const updateSiteAccess = async (
	token: string = '',
	id: string,
	body: { public: boolean; access_grants: any[] }
) => {
	let error = null;
	const res = await fetch(`${WEBUI_API_BASE_URL}/sites/${encodeURIComponent(id)}/access`, {
		method: 'POST',
		headers: jsonHeaders(token),
		body: JSON.stringify(body)
	})
		.then(handle)
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});
	if (error) throw error;
	return res;
};

export const deleteSite = async (token: string = '', id: string) => {
	let error = null;
	const res = await fetch(`${WEBUI_API_BASE_URL}/sites/${encodeURIComponent(id)}`, {
		method: 'DELETE',
		headers: jsonHeaders(token)
	})
		.then(handle)
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});
	if (error) throw error;
	return res;
};
```

- [ ] **Step 4: Rail item**

In `src/lib/components/app/railItems.ts`: add imports

```ts
import GlobeAlt from '$lib/components/icons/GlobeAlt.svelte';
import { canSeeSites } from '$lib/components/sites/lib/visibility';
```

and append to the items array (after the policy-review entry):

```ts
	{
		// Site Publisher bonus tool. Visible to admins and users the admin
		// has granted the site_publisher permission.
		id: 'sites',
		label: 'Sites',
		href: '/sites',
		icon: GlobeAlt,
		segments: ['sites'],
		visible: ({ user }) => canSeeSites({ user })
	},
```

- [ ] **Step 5: Route shell + guard**

`src/routes/(app)/sites/+layout.svelte`:

```svelte
<script lang="ts">
	import { goto } from '$app/navigation';
	import { user } from '$lib/stores';
	import { canSeeSites } from '$lib/components/sites/lib/visibility';

	let { children } = $props();

	// Route guard: same predicate as the rail item, so a deep link can't
	// reach a tool the rail wouldn't show.
	let allowed = $derived(canSeeSites({ user: $user }));
	$effect(() => {
		if (!allowed) goto('/home');
	});
</script>

{#if allowed}
	{@render children()}
{/if}
```

`src/routes/(app)/sites/+page.svelte`:

```svelte
<script lang="ts">
	import SitesPage from '$lib/components/sites/SitesPage.svelte';
	import { WEBUI_NAME } from '$lib/stores';
</script>

<svelte:head>
	<title>Sites • {$WEBUI_NAME}</title>
</svelte:head>

<SitesPage />
```

`src/lib/components/sites/SitesPage.svelte` (shell only this task):

```svelte
<script lang="ts">
	// Real UI lands in the next task.
</script>

<div class="w-full h-full flex items-center justify-center text-gray-500">Sites</div>
```

- [ ] **Step 6: Type check**

`npm run check` — expect no NEW errors (repo baseline may not be zero; compare against a run on the unmodified tree if unsure).

- [ ] **Step 7: Commit**

```bash
git add src/lib/apis/sites/ src/lib/components/sites/ src/lib/components/app/railItems.ts "src/routes/(app)/sites/"
git commit -m "feat(sites): frontend plumbing - API client, rail item, gated route"
```

---

### Task 6: manager page UI

**Files:**
- Modify: `src/lib/components/sites/SitesPage.svelte` (replace shell with real UI)
- Create: `src/lib/components/sites/SiteEditor.svelte`

**Interfaces:**
- Consumes: Task 5 API functions; `AccessControl` from `$lib/components/workspace/common/AccessControl.svelte` (props: `bind:accessGrants` — flat `{principal_type, principal_id, permission}[]`, `accessRoles={['read']}`, `sharePublic={false}` hides its public toggle); `Modal` + `ConfirmDialog` from `$lib/components/common/`; `copyToClipboard` from `$lib/utils`; `toast` from `svelte-sonner`; `user` store.
- Produces: complete `/sites` page.

**Access-level mapping (single source of truth for the UI):**

| UI level                 | `public` | `access_grants` sent                                        |
| ------------------------ | -------- | ----------------------------------------------------------- |
| Public (no login)        | `true`   | `[]`                                                        |
| Everyone in Osool        | `false`  | `[{principal_type:'user', principal_id:'*', permission:'read'}]` |
| Specific people          | `false`  | the AccessControl picker's grants (strip any `*` entries)   |
| Private (only me)        | `false`  | `[]`                                                        |

Derive the level when opening the editor: `public` → 'public'; any `user:*` read grant → 'internal'; non-empty grants → 'specific'; else 'private'.

- [ ] **Step 1: Write `SiteEditor.svelte`** (create + edit modal)

`src/lib/components/sites/SiteEditor.svelte`:

```svelte
<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { getContext } from 'svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import AccessControl from '$lib/components/workspace/common/AccessControl.svelte';
	import { createSite, updateSite, updateSiteAccess } from '$lib/apis/sites';

	const i18n = getContext('i18n');

	let {
		show = $bindable(false),
		site = null, // null => create mode
		onSaved = () => {}
	} = $props();

	let name = $state('');
	let slug = $state('');
	let slugTouched = $state(false);
	let level = $state('private'); // 'public' | 'internal' | 'specific' | 'private'
	let accessGrants = $state<any[]>([]);
	let files = $state<File[]>([]);
	let entryFile = $state('');
	let saving = $state(false);
	let dragging = $state(false);

	const slugify = (v: string) =>
		v
			.toLowerCase()
			.replace(/[^a-z0-9]+/g, '-')
			.replace(/^-+|-+$/g, '')
			.slice(0, 60);

	$effect(() => {
		if (show) {
			name = site?.name ?? '';
			slug = site?.slug ?? '';
			slugTouched = !!site;
			files = [];
			entryFile = site?.entry_file ?? '';
			if (site?.public) level = 'public';
			else if ((site?.access_grants ?? []).some((g: any) => g.principal_id === '*')) level = 'internal';
			else if ((site?.access_grants ?? []).length > 0) level = 'specific';
			else level = 'private';
			accessGrants = (site?.access_grants ?? []).filter((g: any) => g.principal_id !== '*');
		}
	});

	$effect(() => {
		if (!slugTouched) slug = slugify(name);
	});

	let htmlNames = $derived(
		files.length > 0
			? files.filter((f) => /\.html?$/i.test(f.name)).map((f) => f.name)
			: (site?.files ?? []).filter((f: any) => /\.html?$/i.test(f.name)).map((f: any) => f.name)
	);

	$effect(() => {
		if (htmlNames.length > 0 && !htmlNames.includes(entryFile)) {
			entryFile = htmlNames.includes('index.html') ? 'index.html' : htmlNames[0];
		}
	});

	const addFiles = (list: FileList | File[] | null) => {
		if (!list) return;
		const next = [...files];
		for (const f of Array.from(list)) {
			if (!next.some((x) => x.name === f.name)) next.push(f);
		}
		files = next;
	};

	const grantsForLevel = () => {
		if (level === 'internal') return [{ principal_type: 'user', principal_id: '*', permission: 'read' }];
		if (level === 'specific') return accessGrants.filter((g) => g.principal_id !== '*');
		return [];
	};

	const submit = async () => {
		saving = true;
		try {
			if (!site) {
				const fd = new FormData();
				fd.append('name', name);
				fd.append('slug', slug);
				fd.append('public', level === 'public' ? 'true' : 'false');
				fd.append('access_grants', JSON.stringify(grantsForLevel()));
				if (entryFile) fd.append('entry_file', entryFile);
				for (const f of files) fd.append('files', f);
				await createSite(localStorage.token, fd);
			} else {
				const fd = new FormData();
				fd.append('name', name);
				fd.append('slug', slug);
				if (entryFile) fd.append('entry_file', entryFile);
				for (const f of files) fd.append('files', f);
				await updateSite(localStorage.token, site.id, fd);
				await updateSiteAccess(localStorage.token, site.id, {
					public: level === 'public',
					access_grants: grantsForLevel()
				});
			}
			toast.success($i18n.t('Site saved'));
			show = false;
			onSaved();
		} catch (err) {
			toast.error(`${err}`);
		} finally {
			saving = false;
		}
	};
</script>

<Modal size="md" bind:show>
	<div class="p-5 flex flex-col gap-4">
		<div class="text-lg font-medium dark:text-gray-100">
			{site ? $i18n.t('Edit Site') : $i18n.t('Publish a Site')}
		</div>

		<div class="flex flex-col gap-1">
			<label class="text-xs font-medium text-gray-500" for="site-name">{$i18n.t('Name')}</label>
			<input
				id="site-name"
				class="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-transparent px-3 py-2 text-sm outline-none dark:text-gray-100"
				bind:value={name}
				placeholder={$i18n.t('My page')}
			/>
		</div>

		<div class="flex flex-col gap-1">
			<label class="text-xs font-medium text-gray-500" for="site-slug">{$i18n.t('Link')}</label>
			<div class="flex items-center gap-1 text-sm">
				<span class="text-gray-400 shrink-0">{window.location.origin}/sites/</span>
				<input
					id="site-slug"
					class="flex-1 min-w-0 rounded-lg border border-gray-200 dark:border-gray-700 bg-transparent px-3 py-2 text-sm outline-none dark:text-gray-100"
					bind:value={slug}
					oninput={() => (slugTouched = true)}
				/>
			</div>
		</div>

		<div class="flex flex-col gap-1">
			<div class="text-xs font-medium text-gray-500">{$i18n.t('Files')}</div>
			<button
				type="button"
				class="rounded-xl border-2 border-dashed px-4 py-6 text-sm text-gray-500 transition
					{dragging ? 'border-gray-500 bg-gray-50 dark:bg-gray-850' : 'border-gray-200 dark:border-gray-700'}"
				ondragover={(e) => {
					e.preventDefault();
					dragging = true;
				}}
				ondragleave={() => (dragging = false)}
				ondrop={(e) => {
					e.preventDefault();
					dragging = false;
					addFiles(e.dataTransfer?.files ?? null);
				}}
				onclick={() => document.getElementById('site-files-input')?.click()}
			>
				{site && files.length === 0
					? $i18n.t('Drop files to replace the current ones, or click to browse')
					: $i18n.t('Drop your HTML and asset files here, or click to browse')}
			</button>
			<input
				id="site-files-input"
				type="file"
				multiple
				hidden
				onchange={(e) => {
					addFiles((e.target as HTMLInputElement).files);
					(e.target as HTMLInputElement).value = '';
				}}
			/>
			{#if files.length > 0}
				<div class="flex flex-col gap-1 mt-1">
					{#each files as f (f.name)}
						<div class="flex items-center justify-between text-xs text-gray-600 dark:text-gray-300">
							<span class="truncate">{f.name}</span>
							<div class="flex items-center gap-2 shrink-0">
								<span class="text-gray-400">{(f.size / 1024).toFixed(1)} KB</span>
								<button
									type="button"
									class="text-gray-400 hover:text-red-500"
									onclick={() => (files = files.filter((x) => x.name !== f.name))}>&times;</button
								>
							</div>
						</div>
					{/each}
				</div>
			{:else if site}
				<div class="text-xs text-gray-400">
					{$i18n.t('{{count}} file(s) currently published', { count: (site.files ?? []).length })}
				</div>
			{/if}
			{#if htmlNames.length > 1}
				<div class="flex items-center gap-2 mt-1 text-xs">
					<span class="text-gray-500">{$i18n.t('Opens with')}</span>
					<select
						class="rounded border border-gray-200 dark:border-gray-700 bg-transparent px-2 py-1 dark:text-gray-100"
						bind:value={entryFile}
					>
						{#each htmlNames as n (n)}
							<option value={n}>{n}</option>
						{/each}
					</select>
				</div>
			{/if}
		</div>

		<div class="flex flex-col gap-2">
			<div class="text-xs font-medium text-gray-500">{$i18n.t('Who can view')}</div>
			<div class="flex flex-col gap-1.5 text-sm dark:text-gray-100">
				{#each [
					['private', $i18n.t('Only me')],
					['specific', $i18n.t('Specific people or groups')],
					['internal', $i18n.t('Everyone with an account')],
					['public', $i18n.t('Public — no login needed')]
				] as [value, label] (value)}
					<label class="flex items-center gap-2">
						<input type="radio" name="site-level" {value} bind:group={level} />
						{label}
					</label>
				{/each}
			</div>
			{#if level === 'specific'}
				<AccessControl bind:accessGrants accessRoles={['read']} sharePublic={false} />
			{/if}
		</div>

		<div class="flex justify-end gap-2 pt-1">
			<button
				type="button"
				class="rounded-lg px-3.5 py-1.5 text-sm text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-850"
				onclick={() => (show = false)}>{$i18n.t('Cancel')}</button
			>
			<button
				type="button"
				class="rounded-lg bg-gray-900 px-3.5 py-1.5 text-sm text-white hover:bg-gray-800 dark:bg-gray-100 dark:text-gray-900 disabled:opacity-50"
				disabled={saving || !name.trim() || !slug || (!site && files.length === 0)}
				onclick={submit}>{saving ? $i18n.t('Saving...') : site ? $i18n.t('Save') : $i18n.t('Publish')}</button
			>
		</div>
	</div>
</Modal>
```

Note: verify `Modal.svelte`'s actual props (`size`, `bind:show`) against an existing consumer (e.g. `ShareChatModal.svelte`) and adjust — some Modal variants use `on:close`.

- [ ] **Step 2: Write the list page**

Replace `src/lib/components/sites/SitesPage.svelte`:

```svelte
<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { user } from '$lib/stores';
	import { copyToClipboard } from '$lib/utils';
	import { getSites, deleteSite } from '$lib/apis/sites';
	import SiteEditor from './SiteEditor.svelte';
	import ConfirmDialog from '$lib/components/common/ConfirmDialog.svelte';

	const i18n = getContext('i18n');

	let sites = $state<any[]>([]);
	let loaded = $state(false);
	let showEditor = $state(false);
	let editing = $state<any>(null);
	let confirmDelete = $state<any>(null);
	let showAll = $state(false);

	const levelBadge = (s: any) => {
		if (s.public) return $i18n.t('Public');
		if ((s.access_grants ?? []).some((g: any) => g.principal_id === '*')) return $i18n.t('Everyone');
		if ((s.access_grants ?? []).length > 0) return $i18n.t('Specific');
		return $i18n.t('Private');
	};

	const load = async () => {
		try {
			sites = (await getSites(localStorage.token, showAll)) ?? [];
		} catch (err) {
			toast.error(`${err}`);
		}
		loaded = true;
	};

	const copyLink = async (s: any) => {
		await copyToClipboard(`${window.location.origin}/sites/${s.slug}`);
		toast.success($i18n.t('Link copied'));
	};

	const remove = async () => {
		try {
			await deleteSite(localStorage.token, confirmDelete.id);
			toast.success($i18n.t('Site deleted'));
			confirmDelete = null;
			await load();
		} catch (err) {
			toast.error(`${err}`);
		}
	};

	onMount(load);
</script>

<div class="mx-auto w-full max-w-3xl px-4 py-6 flex flex-col gap-4">
	<div class="flex items-center justify-between">
		<div>
			<div class="text-xl font-medium dark:text-gray-100">{$i18n.t('Sites')}</div>
			<div class="text-xs text-gray-500">
				{$i18n.t('Publish static pages and share them with a link.')}
			</div>
		</div>
		<div class="flex items-center gap-2">
			{#if $user?.role === 'admin'}
				<button
					type="button"
					class="rounded-lg px-3 py-1.5 text-xs {showAll
						? 'bg-gray-100 dark:bg-gray-850 dark:text-gray-100'
						: 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-850'}"
					onclick={async () => {
						showAll = !showAll;
						await load();
					}}>{$i18n.t('All users')}</button
				>
			{/if}
			<button
				type="button"
				class="rounded-lg bg-gray-900 px-3.5 py-1.5 text-sm text-white hover:bg-gray-800 dark:bg-gray-100 dark:text-gray-900"
				onclick={() => {
					editing = null;
					showEditor = true;
				}}>{$i18n.t('New Site')}</button
			>
		</div>
	</div>

	{#if loaded && sites.length === 0}
		<div class="rounded-xl border border-dashed border-gray-200 dark:border-gray-700 py-14 text-center text-sm text-gray-500">
			{$i18n.t('Nothing published yet. Create your first site.')}
		</div>
	{:else}
		<div class="flex flex-col divide-y divide-gray-100 dark:divide-gray-850 rounded-xl border border-gray-100 dark:border-gray-850">
			{#each sites as s (s.id)}
				<div class="flex items-center gap-3 px-4 py-3">
					<div class="min-w-0 flex-1">
						<div class="flex items-center gap-2">
							<span class="truncate text-sm font-medium dark:text-gray-100">{s.name}</span>
							<span class="shrink-0 rounded bg-gray-100 dark:bg-gray-850 px-1.5 py-0.5 text-[10px] text-gray-500">
								{levelBadge(s)}
							</span>
						</div>
						<a
							class="text-xs text-gray-500 hover:underline truncate block"
							href={`/sites/${s.slug}`}
							target="_blank"
							rel="noopener">/sites/{s.slug}</a
						>
						{#if s.user_name && showAll}
							<div class="text-[10px] text-gray-400">{s.user_name}</div>
						{/if}
					</div>
					<div class="flex shrink-0 items-center gap-1 text-xs">
						<button
							type="button"
							class="rounded px-2 py-1 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-850"
							onclick={() => copyLink(s)}>{$i18n.t('Copy link')}</button
						>
						<button
							type="button"
							class="rounded px-2 py-1 text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-850"
							onclick={() => {
								editing = s;
								showEditor = true;
							}}>{$i18n.t('Edit')}</button
						>
						<button
							type="button"
							class="rounded px-2 py-1 text-red-500 hover:bg-red-50 dark:hover:bg-red-950"
							onclick={() => (confirmDelete = s)}>{$i18n.t('Delete')}</button
						>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</div>

<SiteEditor bind:show={showEditor} site={editing} onSaved={load} />

<ConfirmDialog
	show={confirmDelete !== null}
	title={$i18n.t('Delete site?')}
	message={$i18n.t('The link will stop working immediately. This cannot be undone.')}
	on:confirm={remove}
	on:cancel={() => (confirmDelete = null)}
/>
```

Note: verify `ConfirmDialog.svelte`'s actual prop/event names against an existing consumer and adjust.

- [ ] **Step 3: Type check + vitest**

`npm run check` (no NEW errors) and `npx vitest run src/lib/components/sites` (visibility tests still pass).

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/sites/
git commit -m "feat(sites): manager page - list, editor dialog, access levels, delete"
```

---

### Task 7: admin permission toggle + i18n

**Files:**
- Modify: `src/lib/constants/permissions.ts` (features block ~line 70: add `site_publisher: false` after `policy_admin: false`)
- Modify: `src/lib/components/admin/Users/Groups/Permissions.svelte` (add toggle block after the `policy_admin` block ~line 1020)
- Modify: `src/lib/i18n/locales/en-US/translation.json` + `src/lib/i18n/locales/ar/translation.json` — **see the dirty-tree warning below**

**Interfaces:**
- Consumes: `permissions.features.site_publisher` path (matches backend key from Task 2).
- Produces: admins can grant the permission per group; UI strings translatable.

- [ ] **Step 1: Frontend permission default**

In `src/lib/constants/permissions.ts`, `features` block, after `policy_admin: false`:

```ts
		site_publisher: false
```

(mind the comma on the previous line)

- [ ] **Step 2: Admin toggle**

In `src/lib/components/admin/Users/Groups/Permissions.svelte`, after the `policy_admin` block (~line 1020), copy the sibling pattern:

```svelte
	<div class="flex flex-col w-full">
		<Tooltip
			className="flex w-full justify-between my-1"
			content={$i18n.t(
				'Allows members of this group to publish static sites and share them with custom links.'
			)}
			placement="top-start"
		>
			<div class=" self-center text-xs font-medium">
				{$i18n.t('Site Publisher')}
			</div>
			<Switch bind:state={permissions.features.site_publisher} />
		</Tooltip>
		{#if defaultPermissions?.features?.site_publisher && !permissions.features.site_publisher}
			<div>
				<div class="text-xs text-gray-500">
					{$i18n.t('This is a default user permission and will remain enabled.')}
				</div>
			</div>
		{/if}
	</div>
```

- [ ] **Step 3: i18n keys — CHECK THE TREE FIRST**

Both translation.json files carry unrelated uncommitted edits. Run `git diff --stat src/lib/i18n/locales/en-US/translation.json src/lib/i18n/locales/ar/translation.json`. If they are still dirty with unrelated changes, SKIP this step, leave the keys to i18next fallback (English renders fine), and report the skip in the task summary so it lands in the follow-up backlog. If the user has committed/reverted them, add these keys (alphabetical position, en-US value `""`, ar value = the Arabic below):

| key | ar |
| --- | --- |
| `All users` | `جميع المستخدمين` |
| `Copy link` | `نسخ الرابط` |
| `Delete site?` | `حذف الموقع؟` |
| `Drop your HTML and asset files here, or click to browse` | `أسقط ملفات HTML والملفات المرفقة هنا، أو انقر للاستعراض` |
| `Drop files to replace the current ones, or click to browse` | `أسقط ملفات لاستبدال الحالية، أو انقر للاستعراض` |
| `Edit Site` | `تعديل الموقع` |
| `Everyone` | `الجميع` |
| `Everyone with an account` | `كل من لديه حساب` |
| `Link` | `الرابط` |
| `Link copied` | `تم نسخ الرابط` |
| `My page` | `صفحتي` |
| `New Site` | `موقع جديد` |
| `Nothing published yet. Create your first site.` | `لا يوجد شيء منشور بعد. أنشئ موقعك الأول.` |
| `Only me` | `أنا فقط` |
| `Opens with` | `يفتح بـ` |
| `Public — no login needed` | `عام — لا حاجة لتسجيل الدخول` |
| `Publish` | `نشر` |
| `Publish a Site` | `نشر موقع` |
| `Publish static pages and share them with a link.` | `انشر صفحات ثابتة وشاركها برابط.` |
| `Site Publisher` | `ناشر المواقع` |
| `Site deleted` | `تم حذف الموقع` |
| `Site saved` | `تم حفظ الموقع` |
| `Sites` | `المواقع` |
| `Specific` | `محدد` |
| `Specific people or groups` | `أشخاص أو مجموعات محددة` |
| `The link will stop working immediately. This cannot be undone.` | `سيتوقف الرابط عن العمل فورًا. لا يمكن التراجع عن هذا.` |
| `Who can view` | `من يمكنه المشاهدة` |
| `Allows members of this group to publish static sites and share them with custom links.` | `يسمح لأعضاء هذه المجموعة بنشر مواقع ثابتة ومشاركتها بروابط مخصصة.` |
| `{{count}} file(s) currently published` | `{{count}} ملف/ملفات منشورة حاليًا` |

(Keys already present in the files — e.g. `Cancel`, `Delete`, `Edit`, `Name`, `Private`, `Public`, `Save`, `Saving...` — must NOT be duplicated; check before adding each.)

- [ ] **Step 4: Type check**

`npm run check` — no NEW errors.

- [ ] **Step 5: Commit**

```bash
git add src/lib/constants/permissions.ts src/lib/components/admin/Users/Groups/Permissions.svelte
git commit -m "feat(sites): admin group toggle for the site_publisher permission"
```

If Step 3 ran, add the two translation.json files to the same commit — ONLY after confirming `git diff` shows nothing but the new keys.

---

## Final verification (after all tasks)

1. Full backend suite: `.venv/Scripts/python.exe -m pytest open_webui/test/sites -q` — all green.
2. `npm run check` + `npx vitest run src/lib/components/sites` — green.
3. Restart the Docker container (`osool-ai-open-webui-1`) so Alembic applies migration `e4f5a6b7c8d9`.
4. Browser smoke checklist (user performs, via the container origin — Vite dev origin cannot serve `/sites/*`):
   - [ ] Admin: grant "Site Publisher" to a test group; member sees the "Sites" rail item; ungranted user doesn't and deep-link `/sites` (bare) redirects to /home.
   - [ ] Publish a 2-file site (html + image referenced relatively); open `/sites/<slug>` — page renders, image loads.
   - [ ] Published page JS cannot read localStorage (DevTools console on the page: `localStorage` should throw SecurityError — CSP sandbox working).
   - [ ] Access levels: Private (other user gets 404), Specific (granted user sees it), Everyone (any logged-in user), Public (incognito window, no login).
   - [ ] Anonymous on a non-public link → redirected to login, then back after sign-in.
   - [ ] Edit: replace files, change slug — old link 404s, new link serves.
   - [ ] Delete — link 404s, row gone from list.
   - [ ] Copy-link button + visibility badges correct. RTL/Arabic page sanity if i18n step ran.
