# AI Avatar Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Account-tab "AI Avatar" option: user uploads a reference photo, backend calls OpenAI `gpt-image-2` (images/edits) with a locked corporate style prompt, user previews/regenerates and applies the result as their profile image.

**Architecture:** New self-contained backend router `/api/v1/avatar` (mirrors `policy_review.py` pattern) + `avatar_generation` quota table (10/user/day) + PersistentConfig keys (feature default OFF). Frontend: new `AIAvatarDialog.svelte` opened from a fourth hover action in `UserProfileImage.svelte`; result flows into the existing `profileImageUrl` → Save path. Spec: `docs/superpowers/specs/2026-07-11-ai-avatar-generation-design.md`.

**Tech Stack:** FastAPI + SQLAlchemy async + Alembic + aiohttp + Pillow (backend); Svelte 4 + existing `Modal.svelte` + vitest (frontend).

## Global Constraints

- Feature default OFF: `AVATAR_GENERATION_ENABLED` env/PersistentConfig defaults `false`.
- Daily cap: `AVATAR_DAILY_LIMIT` default `10`; quota consumed only on successful generation.
- OpenAI call: model `gpt-image-2`, endpoint `POST {base}/images/edits`, `size=1024x1024`, `quality=medium`, `output_format=webp`.
- Key resolution: `AVATAR_OPENAI_API_KEY` → fallback `IMAGES_OPENAI_API_KEY` (which itself defaults to `OPENAI_API_KEY` in config.py). No key → 400.
- Reference photos processed in memory only — never written to disk, DB, or logs.
- Feature disabled → API returns 403; frontend hides the action via `$config?.features?.enable_avatar_generation`.
- Backend tests run with the backend venv python: `backend\.venv\Scripts\python.exe -m pytest ...` (plain `python` lacks deps).
- NEVER delegate Svelte file edits to a haiku-model agent (cp1252 corruption history in this repo).
- Copy (user-facing strings) uses `$i18n.t('English key')`; add each new key to `src/lib/i18n/locales/en-US/translation.json` with value `""`.
- Commit after each task; commit only the task's files (other work is pre-staged in this repo — always `git commit -- <paths>` style or precise `git add`, never bare `git add .`).

---

### Task 1: Quota model, DAO, and migration

**Files:**
- Create: `backend/open_webui/models/avatar.py`
- Create: `backend/open_webui/migrations/versions/e7f8a9b0c1d2_add_avatar_generation_table.py`
- Create: `backend/open_webui/test/avatar/conftest.py` (copied from policy_review suite)
- Test: `backend/open_webui/test/avatar/test_models_avatar.py`

**Interfaces:**
- Consumes: `open_webui.internal.db.Base`, `get_async_db_context` (existing).
- Produces: `AvatarGenerations` singleton with `async get_count(user_id: str, date: str, db=None) -> int` and `async increment(user_id: str, date: str, db=None) -> int` (returns the new count). Table `avatar_generation(user_id Text PK, date Text PK, count BigInteger)`. Migration revision `e7f8a9b0c1d2` (down: `d6e7f8a9b0c1`, the current head).

- [ ] **Step 1: Create the test package by mirroring the policy suite's harness**

```powershell
New-Item -ItemType Directory -Force backend\open_webui\test\avatar
Copy-Item backend\open_webui\test\policy_review\conftest.py backend\open_webui\test\avatar\conftest.py
```

Also check `ls backend\open_webui\test\policy_review\` — if an `__init__.py` exists there, create an empty `backend\open_webui\test\avatar\__init__.py` too. The copied conftest is generic: it points `DATABASE_URL` at a temp SQLite file, disables migrations, pre-creates the `config` table, and `create_all`/`drop_all`s the schema per test. Read it after copying; if it imports anything policy-specific (e.g. a policy models module purely to register tables), replace that import with `import open_webui.models.avatar  # noqa: F401` so the `avatar_generation` table registers on `Base.metadata`. Keep everything else identical.

- [ ] **Step 2: Write the failing DAO test**

Create `backend/open_webui/test/avatar/test_models_avatar.py`:

```python
import pytest

from open_webui.models.avatar import AvatarGenerations


@pytest.mark.asyncio
async def test_get_count_defaults_to_zero():
    assert await AvatarGenerations.get_count('u1', '2026-07-11') == 0


@pytest.mark.asyncio
async def test_increment_creates_then_counts_up():
    assert await AvatarGenerations.increment('u1', '2026-07-11') == 1
    assert await AvatarGenerations.increment('u1', '2026-07-11') == 2
    assert await AvatarGenerations.get_count('u1', '2026-07-11') == 2


@pytest.mark.asyncio
async def test_counts_are_per_user_and_per_day():
    await AvatarGenerations.increment('u1', '2026-07-11')
    assert await AvatarGenerations.get_count('u2', '2026-07-11') == 0
    assert await AvatarGenerations.get_count('u1', '2026-07-12') == 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/open_webui/test/avatar/test_models_avatar.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'open_webui.models.avatar'`

- [ ] **Step 4: Write the model + DAO**

Create `backend/open_webui/models/avatar.py`:

```python
# Daily quota bookkeeping for AI avatar generation. One row per (user, UTC day).
from typing import Optional

from sqlalchemy import BigInteger, Column, Text, select
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.internal.db import Base, get_async_db_context


class AvatarGeneration(Base):
    __tablename__ = 'avatar_generation'

    user_id = Column(Text, primary_key=True)
    date = Column(Text, primary_key=True)  # UTC day, 'YYYY-MM-DD'
    count = Column(BigInteger, nullable=False, default=0)


class AvatarGenerationTable:
    async def get_count(
        self, user_id: str, date: str, db: Optional[AsyncSession] = None
    ) -> int:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(AvatarGeneration).filter_by(user_id=user_id, date=date)
            )
            row = res.scalars().first()
            return row.count if row else 0

    async def increment(
        self, user_id: str, date: str, db: Optional[AsyncSession] = None
    ) -> int:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(AvatarGeneration).filter_by(user_id=user_id, date=date)
            )
            row = res.scalars().first()
            if row:
                row.count = row.count + 1
            else:
                row = AvatarGeneration(user_id=user_id, date=date, count=1)
                db.add(row)
            await db.commit()
            return row.count


AvatarGenerations = AvatarGenerationTable()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/open_webui/test/avatar/test_models_avatar.py -v`
Expected: 3 PASSED

- [ ] **Step 6: Write the migration**

Create `backend/open_webui/migrations/versions/e7f8a9b0c1d2_add_avatar_generation_table.py`:

```python
"""add avatar_generation table

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-07-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, None] = 'd6e7f8a9b0c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'avatar_generation',
        sa.Column('user_id', sa.Text(), primary_key=True),
        sa.Column('date', sa.Text(), primary_key=True),
        sa.Column('count', sa.BigInteger(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_table('avatar_generation')
```

- [ ] **Step 7: Sanity-check the migration chain**

Run: `Select-String -Path backend\open_webui\migrations\versions\*.py -Pattern "down_revision.*d6e7f8a9b0c1"`
Expected: exactly one hit — the new file. (Confirms `d6e7f8a9b0c1` was still head and we didn't fork the chain.)

- [ ] **Step 8: Commit**

```bash
git add backend/open_webui/models/avatar.py backend/open_webui/migrations/versions/e7f8a9b0c1d2_add_avatar_generation_table.py backend/open_webui/test/avatar/
git commit -m "feat(avatar): quota table + DAO for AI avatar generation" -- backend/open_webui/models/avatar.py backend/open_webui/migrations/versions/e7f8a9b0c1d2_add_avatar_generation_table.py backend/open_webui/test/avatar/
```

---

### Task 2: Config keys

**Files:**
- Modify: `backend/open_webui/config.py` (append a new section near the image-generation config, after ~line 3990)

**Interfaces:**
- Consumes: `PersistentConfig` class (config.py), `os` (imported at top already).
- Produces: module-level `AVATAR_GENERATION_ENABLED` (bool), `AVATAR_OPENAI_API_BASE_URL` (str), `AVATAR_OPENAI_API_KEY` (str), `AVATAR_DAILY_LIMIT` (int), `AVATAR_STYLE_PROMPT` (str), `DEFAULT_AVATAR_STYLE_PROMPT` (plain str constant). Task 4 imports all five PersistentConfigs in `main.py`.

- [ ] **Step 1: Add the config block**

In `backend/open_webui/config.py`, directly after the existing image-generation config block (search for `IMAGES_OPENAI_API_KEY = PersistentConfig` around line 3935 and scroll past that section's end), insert:

```python
####################################
# AI Avatar Generation (Osool)
####################################

AVATAR_GENERATION_ENABLED = PersistentConfig(
    'AVATAR_GENERATION_ENABLED',
    'avatar.enable',
    os.environ.get('AVATAR_GENERATION_ENABLED', 'false').lower() == 'true',
)

AVATAR_OPENAI_API_BASE_URL = PersistentConfig(
    'AVATAR_OPENAI_API_BASE_URL',
    'avatar.openai.api_base_url',
    os.getenv('AVATAR_OPENAI_API_BASE_URL', 'https://api.openai.com/v1'),
)

AVATAR_OPENAI_API_KEY = PersistentConfig(
    'AVATAR_OPENAI_API_KEY',
    'avatar.openai.api_key',
    os.getenv('AVATAR_OPENAI_API_KEY', ''),
)

AVATAR_DAILY_LIMIT = PersistentConfig(
    'AVATAR_DAILY_LIMIT',
    'avatar.daily_limit',
    int(os.getenv('AVATAR_DAILY_LIMIT', '10')),
)

DEFAULT_AVATAR_STYLE_PROMPT = (
    'Professional corporate avatar portrait of this person: clean modern flat vector '
    'illustration, simplified stylized features that resemble but do not exactly '
    'replicate them, head-and-shoulders composition, confident friendly expression, '
    'business attire, plain soft muted-teal background, subtle teal accents. '
    'No text, no logos, no photorealism.'
)

AVATAR_STYLE_PROMPT = PersistentConfig(
    'AVATAR_STYLE_PROMPT',
    'avatar.style_prompt',
    os.getenv('AVATAR_STYLE_PROMPT', DEFAULT_AVATAR_STYLE_PROMPT),
)
```

- [ ] **Step 2: Verify the module still imports**

Run: `backend\.venv\Scripts\python.exe -c "import os; os.environ['ENABLE_DB_MIGRATIONS']='false'; from open_webui.config import AVATAR_GENERATION_ENABLED, AVATAR_DAILY_LIMIT, AVATAR_STYLE_PROMPT; print(AVATAR_GENERATION_ENABLED.value, AVATAR_DAILY_LIMIT.value)"`
(from the `backend/` directory)
Expected: `False 10`

- [ ] **Step 3: Commit**

```bash
git add backend/open_webui/config.py
git commit -m "feat(avatar): config keys for AI avatar generation (default off)" -- backend/open_webui/config.py
```

---

### Task 3: Avatar router (generate + quota) with mocked-OpenAI tests

**Files:**
- Create: `backend/open_webui/routers/avatar.py`
- Test: `backend/open_webui/test/avatar/test_router_avatar.py`

**Interfaces:**
- Consumes: `AvatarGenerations` (Task 1: `get_count(user_id, date)`, `increment(user_id, date)` → new count), config attrs on `request.app.state.config` (Task 2 names), `open_webui.utils.auth.get_verified_user`, `open_webui.utils.session_pool.get_session` (aiohttp pooled session — same helper `routers/images.py:26` uses), `AIOHTTP_CLIENT_SESSION_SSL` (mirror the exact import `routers/images.py` uses for it).
- Produces: `router` (APIRouter) with `POST /generate` (multipart field `photo`) → `{"image": "data:image/webp;base64,...", "remaining": int}` and `GET /quota` → `{"remaining": int, "limit": int}`. Module-level `_utc_date()` helper. Task 4 mounts it at `/api/v1/avatar`.

- [ ] **Step 1: Write the failing router tests**

Create `backend/open_webui/test/avatar/test_router_avatar.py`:

```python
import base64
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

import open_webui.routers.avatar as avatar_router
from open_webui.models.avatar import AvatarGenerations
from open_webui.utils.auth import get_verified_user

USER = SimpleNamespace(id='u1', role='user', name='Test User', email='t@example.com')

# 1x1 red PNG — a real decodable image so the Pillow downscale path runs.
PNG_BYTES = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
)


def _make_app(user=USER, **overrides):
    config = SimpleNamespace(
        AVATAR_GENERATION_ENABLED=True,
        AVATAR_DAILY_LIMIT=10,
        AVATAR_OPENAI_API_KEY='sk-test',
        IMAGES_OPENAI_API_KEY='',
        AVATAR_OPENAI_API_BASE_URL='https://fake.test/v1',
        AVATAR_STYLE_PROMPT='style prompt',
    )
    for k, v in overrides.items():
        setattr(config, k, v)
    app = FastAPI()
    app.state.config = config
    app.include_router(avatar_router.router, prefix='/api/v1/avatar')
    app.dependency_overrides[get_verified_user] = lambda: user
    return app


def _client(**overrides):
    return httpx.AsyncClient(
        transport=ASGITransport(app=_make_app(**overrides)), base_url='http://test'
    )


class _FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status = status
        self._payload = (
            payload
            if payload is not None
            else {'data': [{'b64_json': base64.b64encode(b'avatar-bytes').decode()}]}
        )

    async def json(self, content_type=None):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _FakeSession:
    def __init__(self, response):
        self._response = response
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self._response


def _patch_openai(monkeypatch, response=None):
    session = _FakeSession(response if response is not None else _FakeResponse())

    async def _get_session():
        return session

    monkeypatch.setattr(avatar_router, 'get_session', _get_session)
    return session


def _files():
    return {'photo': ('p.png', PNG_BYTES, 'image/png')}


@pytest.mark.asyncio
async def test_generate_disabled_returns_403(monkeypatch):
    session = _patch_openai(monkeypatch)
    async with _client(AVATAR_GENERATION_ENABLED=False) as c:
        r = await c.post('/api/v1/avatar/generate', files=_files())
    assert r.status_code == 403
    assert session.calls == []


@pytest.mark.asyncio
async def test_quota_disabled_returns_403():
    async with _client(AVATAR_GENERATION_ENABLED=False) as c:
        r = await c.get('/api/v1/avatar/quota')
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_quota_reports_limit_and_remaining():
    today = avatar_router._utc_date()
    await AvatarGenerations.increment('u1', today)
    async with _client(AVATAR_DAILY_LIMIT=5) as c:
        r = await c.get('/api/v1/avatar/quota')
    assert r.status_code == 200
    assert r.json() == {'remaining': 4, 'limit': 5}


@pytest.mark.asyncio
async def test_generate_happy_path(monkeypatch):
    session = _patch_openai(monkeypatch)
    async with _client() as c:
        r = await c.post('/api/v1/avatar/generate', files=_files())
    assert r.status_code == 200
    body = r.json()
    assert body['image'].startswith('data:image/webp;base64,')
    assert body['remaining'] == 9
    assert await AvatarGenerations.get_count('u1', avatar_router._utc_date()) == 1
    # locked style prompt + model reach the API call
    url, kwargs = session.calls[0]
    assert url.endswith('/images/edits')


@pytest.mark.asyncio
async def test_generate_quota_exhausted_returns_429(monkeypatch):
    session = _patch_openai(monkeypatch)
    async with _client(AVATAR_DAILY_LIMIT=0) as c:
        r = await c.post('/api/v1/avatar/generate', files=_files())
    assert r.status_code == 429
    assert session.calls == []


@pytest.mark.asyncio
async def test_generate_rejects_bad_content_type(monkeypatch):
    session = _patch_openai(monkeypatch)
    async with _client() as c:
        r = await c.post(
            '/api/v1/avatar/generate',
            files={'photo': ('x.txt', b'not an image', 'text/plain')},
        )
    assert r.status_code == 400
    assert session.calls == []


@pytest.mark.asyncio
async def test_generate_openai_error_returns_502_and_keeps_quota(monkeypatch):
    _patch_openai(
        monkeypatch,
        response=_FakeResponse(
            status=400, payload={'error': {'message': 'moderation blocked'}}
        ),
    )
    async with _client() as c:
        r = await c.post('/api/v1/avatar/generate', files=_files())
    assert r.status_code == 502
    assert 'moderation blocked' in r.json()['detail']
    assert await AvatarGenerations.get_count('u1', avatar_router._utc_date()) == 0


@pytest.mark.asyncio
async def test_generate_missing_key_returns_400(monkeypatch):
    session = _patch_openai(monkeypatch)
    async with _client(AVATAR_OPENAI_API_KEY='', IMAGES_OPENAI_API_KEY='') as c:
        r = await c.post('/api/v1/avatar/generate', files=_files())
    assert r.status_code == 400
    assert session.calls == []


@pytest.mark.asyncio
async def test_generate_key_falls_back_to_images_key(monkeypatch):
    session = _patch_openai(monkeypatch)
    async with _client(AVATAR_OPENAI_API_KEY='', IMAGES_OPENAI_API_KEY='sk-img') as c:
        r = await c.post('/api/v1/avatar/generate', files=_files())
    assert r.status_code == 200
    _, kwargs = session.calls[0]
    assert kwargs['headers']['Authorization'] == 'Bearer sk-img'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/open_webui/test/avatar/test_router_avatar.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'open_webui.routers.avatar'`

- [ ] **Step 3: Write the router**

First check how `routers/images.py` imports `AIOHTTP_CLIENT_SESSION_SSL` (grep the import line) and mirror it. Create `backend/open_webui/routers/avatar.py`:

```python
# AI avatar generation: reference photo -> stylized corporate avatar via OpenAI
# gpt-image-2. Self-contained (policy_review.py pattern). Photos stay in memory only.
import io
import logging
from datetime import datetime, timezone

import aiohttp
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from open_webui.env import AIOHTTP_CLIENT_SESSION_SSL
from open_webui.models.avatar import AvatarGenerations
from open_webui.utils.auth import get_verified_user
from open_webui.utils.session_pool import get_session

log = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_TYPES = {'image/png', 'image/jpeg', 'image/webp'}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_SOURCE_EDGE = 1024


def _utc_date() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def _require_enabled(request: Request) -> None:
    if not request.app.state.config.AVATAR_GENERATION_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Avatar generation is disabled.',
        )


def _api_key(request: Request) -> str:
    key = (
        request.app.state.config.AVATAR_OPENAI_API_KEY
        or request.app.state.config.IMAGES_OPENAI_API_KEY
    )
    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='No OpenAI API key is configured for avatar generation.',
        )
    return key


def _downscale(data: bytes) -> tuple[bytes, str]:
    # Cap the reference photo at 1024px on its longest edge to bound input-token
    # cost; normalize EXIF rotation so portraits arrive upright.
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    img = img.convert('RGB')
    if max(img.size) > MAX_SOURCE_EDGE:
        img.thumbnail((MAX_SOURCE_EDGE, MAX_SOURCE_EDGE), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=90)
    return buf.getvalue(), 'image/jpeg'


@router.get('/quota')
async def get_quota(request: Request, user=Depends(get_verified_user)):
    _require_enabled(request)
    limit = int(request.app.state.config.AVATAR_DAILY_LIMIT)
    used = await AvatarGenerations.get_count(user.id, _utc_date())
    return {'remaining': max(0, limit - used), 'limit': limit}


@router.post('/generate')
async def generate_avatar(
    request: Request,
    photo: UploadFile = File(...),
    user=Depends(get_verified_user),
):
    _require_enabled(request)
    key = _api_key(request)

    if photo.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Unsupported image type. Use PNG, JPEG or WebP.',
        )
    data = await photo.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Image is too large (max 10 MB).',
        )

    limit = int(request.app.state.config.AVATAR_DAILY_LIMIT)
    today = _utc_date()
    used = await AvatarGenerations.get_count(user.id, today)
    if used >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f'Daily avatar limit reached ({limit}/day). Resets at midnight UTC.',
        )

    source, mime = _downscale(data)

    form = aiohttp.FormData()
    form.add_field('model', 'gpt-image-2')
    form.add_field('prompt', request.app.state.config.AVATAR_STYLE_PROMPT)
    form.add_field('size', '1024x1024')
    form.add_field('quality', 'medium')
    form.add_field('output_format', 'webp')
    form.add_field('image', source, filename='photo.jpg', content_type=mime)

    url = f'{request.app.state.config.AVATAR_OPENAI_API_BASE_URL}/images/edits'
    session = await get_session()
    async with session.post(
        url,
        data=form,
        headers={'Authorization': f'Bearer {key}'},
        ssl=AIOHTTP_CLIENT_SESSION_SSL,
    ) as r:
        body = await r.json(content_type=None)
        if r.status >= 400:
            msg = None
            if isinstance(body, dict):
                msg = (body.get('error') or {}).get('message')
            log.warning(f'avatar generation failed ({r.status}): {msg}')
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=msg or 'Avatar generation failed.',
            )

    b64 = body['data'][0]['b64_json']
    new_count = await AvatarGenerations.increment(user.id, today)
    return {
        'image': f'data:image/webp;base64,{b64}',
        'remaining': max(0, limit - new_count),
    }
```

If images.py imports `AIOHTTP_CLIENT_SESSION_SSL` from somewhere other than `open_webui.env`, use that module instead.

- [ ] **Step 4: Run tests to verify they pass**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/open_webui/test/avatar/ -v`
Expected: all 12 tests PASS (3 model + 9 router)

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/avatar.py backend/open_webui/test/avatar/test_router_avatar.py
git commit -m "feat(avatar): /api/v1/avatar router — gpt-image-2 generation + quota" -- backend/open_webui/routers/avatar.py backend/open_webui/test/avatar/test_router_avatar.py
```

---

### Task 4: Wire into main.py (state, router, feature flag)

**Files:**
- Modify: `backend/open_webui/main.py` — four spots: routers import (~line 91), config imports (~line 184 area), `app.state.config` assignments (~line 1283-1286, next to the IMAGES ones), `include_router` block (~line 1462), `features` dict in `get_app_config` (~line 2383).

**Interfaces:**
- Consumes: `avatar` router module (Task 3), five `AVATAR_*` PersistentConfigs (Task 2).
- Produces: `/api/v1/avatar/*` mounted; `app.state.config.AVATAR_*` attributes the router reads; `features.enable_avatar_generation` flag consumed by the frontend (Task 6).

- [ ] **Step 1: Make the edits**

1. In the `from open_webui.routers import (...)` block (around line 91, where `policy_review` is listed) add `avatar,` in alphabetical position.
2. In the `from open_webui.config import (...)` block add:

```python
    AVATAR_GENERATION_ENABLED,
    AVATAR_OPENAI_API_BASE_URL,
    AVATAR_OPENAI_API_KEY,
    AVATAR_DAILY_LIMIT,
    AVATAR_STYLE_PROMPT,
```

3. Next to the `app.state.config.IMAGES_OPENAI_API_KEY = ...` assignments (~line 1285) add:

```python
app.state.config.AVATAR_GENERATION_ENABLED = AVATAR_GENERATION_ENABLED
app.state.config.AVATAR_OPENAI_API_BASE_URL = AVATAR_OPENAI_API_BASE_URL
app.state.config.AVATAR_OPENAI_API_KEY = AVATAR_OPENAI_API_KEY
app.state.config.AVATAR_DAILY_LIMIT = AVATAR_DAILY_LIMIT
app.state.config.AVATAR_STYLE_PROMPT = AVATAR_STYLE_PROMPT
```

4. Next to `app.include_router(policy_review.router, ...)` (~line 1462) add:

```python
app.include_router(avatar.router, prefix='/api/v1/avatar', tags=['avatar'])
```

5. In `get_app_config`'s `features` dict (opens ~line 2382, entries like `'enable_api_keys': app.state.config.ENABLE_API_KEYS,`) add:

```python
        'enable_avatar_generation': app.state.config.AVATAR_GENERATION_ENABLED,
```

- [ ] **Step 2: Verify the app imports**

Run (from `backend/`): `backend\.venv\Scripts\python.exe -c "import os; os.environ['ENABLE_DB_MIGRATIONS']='false'; from open_webui.main import app; print([r.path for r in app.routes if 'avatar' in r.path])"`
Expected: prints `['/api/v1/avatar/quota', '/api/v1/avatar/generate']` (order may vary). If importing `main` cold-starts too much on this machine, fall back to: `backend\.venv\Scripts\python.exe -m pytest backend/open_webui/test/avatar/ -q` plus a `Select-String` check that all five edits landed.

- [ ] **Step 3: Commit**

```bash
git add backend/open_webui/main.py
git commit -m "feat(avatar): mount avatar router + expose enable_avatar_generation flag" -- backend/open_webui/main.py
```

---

### Task 5: Frontend API module + dialog helpers (with vitest)

**Files:**
- Create: `src/lib/apis/avatar/index.ts`
- Create: `src/lib/components/chat/Settings/Account/aiAvatar.ts`
- Test: `src/lib/components/chat/Settings/Account/aiAvatar.test.ts`

**Interfaces:**
- Consumes: `WEBUI_API_BASE_URL` from `$lib/constants`.
- Produces: `generateAvatar(token: string, photo: Blob, filename?: string) -> Promise<{image: string; remaining: number}>`, `getAvatarQuota(token: string) -> Promise<{remaining: number; limit: number}>`, `isReusablePhoto(profileImageUrl: string, initialsImageUrl: string) -> boolean`, `dataUrlToBlob(dataUrl: string) -> Blob`. Task 6's dialog imports all four.

- [ ] **Step 1: Write the failing helper test**

Create `src/lib/components/chat/Settings/Account/aiAvatar.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { isReusablePhoto, dataUrlToBlob } from './aiAvatar';

const INITIALS = 'data:image/png;base64,aW5pdGlhbHM=';

describe('isReusablePhoto', () => {
	it('accepts an uploaded data-URL photo', () => {
		expect(isReusablePhoto('data:image/webp;base64,Zm9v', INITIALS)).toBe(true);
	});
	it('rejects the generated-initials image', () => {
		expect(isReusablePhoto(INITIALS, INITIALS)).toBe(false);
	});
	it('rejects remote URLs, the default image, and empty values', () => {
		expect(isReusablePhoto('https://example.com/a.png', INITIALS)).toBe(false);
		expect(isReusablePhoto('/static/user.png', INITIALS)).toBe(false);
		expect(isReusablePhoto('', INITIALS)).toBe(false);
	});
});

describe('dataUrlToBlob', () => {
	it('decodes mime type and bytes', async () => {
		const blob = dataUrlToBlob('data:image/webp;base64,' + btoa('hello'));
		expect(blob.type).toBe('image/webp');
		expect(await blob.text()).toBe('hello');
	});
	it('falls back to octet-stream for a bare data URL', () => {
		const blob = dataUrlToBlob('data:;base64,' + btoa('x'));
		expect(blob.type).toBe('application/octet-stream');
	});
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- aiAvatar`
Expected: FAIL — cannot resolve `./aiAvatar`

- [ ] **Step 3: Write the helpers**

Create `src/lib/components/chat/Settings/Account/aiAvatar.ts`:

```ts
// Pure helpers for the AI avatar dialog — kept in .ts so they're unit-testable
// (fork convention: logic in lib .ts files, .svelte stays thin).

/**
 * True when the current profile image can be reused as the generation reference:
 * a data-URL photo that isn't the generated-initials image (remote URLs like
 * gravatar or /static/user.png can't be re-uploaded without a CORS fetch).
 */
export const isReusablePhoto = (
	profileImageUrl: string,
	initialsImageUrl: string
): boolean => {
	return (
		typeof profileImageUrl === 'string' &&
		profileImageUrl.startsWith('data:image/') &&
		profileImageUrl !== initialsImageUrl
	);
};

/** Convert a data URL into a Blob for multipart upload. */
export const dataUrlToBlob = (dataUrl: string): Blob => {
	const [head, b64] = dataUrl.split(',');
	const mime = head.match(/data:(.*?);base64/)?.[1] || 'application/octet-stream';
	const bytes = atob(b64);
	const arr = new Uint8Array(bytes.length);
	for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
	return new Blob([arr], { type: mime });
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test:frontend -- aiAvatar`
Expected: 5 tests PASS

- [ ] **Step 5: Write the API module**

Create `src/lib/apis/avatar/index.ts`:

```ts
import { WEBUI_API_BASE_URL } from '$lib/constants';

export const generateAvatar = async (
	token: string,
	photo: Blob,
	filename = 'photo.png'
): Promise<{ image: string; remaining: number }> => {
	const data = new FormData();
	data.append('photo', photo, filename);

	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/avatar/generate`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			authorization: `Bearer ${token}`
		},
		body: data
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail ?? err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getAvatarQuota = async (
	token: string
): Promise<{ remaining: number; limit: number }> => {
	let error = null;

	const res = await fetch(`${WEBUI_API_BASE_URL}/avatar/quota`, {
		method: 'GET',
		headers: {
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error(err);
			error = err.detail ?? err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};
```

- [ ] **Step 6: Commit**

```bash
git add src/lib/apis/avatar/index.ts src/lib/components/chat/Settings/Account/aiAvatar.ts src/lib/components/chat/Settings/Account/aiAvatar.test.ts
git commit -m "feat(avatar): frontend api module + dialog helpers" -- src/lib/apis/avatar/index.ts src/lib/components/chat/Settings/Account/aiAvatar.ts src/lib/components/chat/Settings/Account/aiAvatar.test.ts
```

---

### Task 6: AIAvatarDialog + Account-tab integration

**Files:**
- Create: `src/lib/components/chat/Settings/Account/AIAvatarDialog.svelte`
- Modify: `src/lib/components/chat/Settings/Account/UserProfileImage.svelte` (add fourth hover action + mount dialog)
- Modify: `src/lib/i18n/locales/en-US/translation.json` (new keys, `""` values)

**Interfaces:**
- Consumes: `generateAvatar`, `getAvatarQuota` (Task 5 api module), `isReusablePhoto`, `dataUrlToBlob` (Task 5 helpers), `Modal.svelte` (`bind:show`, `size`), `Spinner.svelte`, `generateInitialsImage` from `$lib/utils`, `config` store flag `enable_avatar_generation` (Task 4).
- Produces: `<AIAvatarDialog bind:show currentImage user on:apply>` where the `apply` event detail is the final ≤512px webp data URL.

- [ ] **Step 1: Create the dialog component**

Create `src/lib/components/chat/Settings/Account/AIAvatarDialog.svelte`:

```svelte
<script lang="ts">
	import { createEventDispatcher, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';

	import { generateAvatar, getAvatarQuota } from '$lib/apis/avatar';
	import { generateInitialsImage } from '$lib/utils';
	import Modal from '$lib/components/common/Modal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { isReusablePhoto, dataUrlToBlob } from './aiAvatar';

	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	export let show = false;
	export let currentImage = '';
	export let user = null;

	let photoInputElement: HTMLInputElement;
	let sourceDataUrl = '';
	let resultDataUrl = '';
	let generating = false;
	let remaining: number | null = null;
	let limit: number | null = null;

	$: initialsImage = user?.name ? generateInitialsImage(user.name) : '';
	$: canUseCurrent = isReusablePhoto(currentImage, initialsImage);

	let wasShown = false;
	$: if (show && !wasShown) {
		wasShown = true;
		init();
	} else if (!show && wasShown) {
		wasShown = false;
		sourceDataUrl = '';
		resultDataUrl = '';
		generating = false;
	}

	const init = async () => {
		try {
			const quota = await getAvatarQuota(localStorage.token);
			remaining = quota.remaining;
			limit = quota.limit;
		} catch (err) {
			toast.error(`${err}`);
		}
	};

	const onPhotoSelected = () => {
		const file = photoInputElement.files?.[0];
		if (!file) {
			return;
		}
		if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
			toast.error($i18n.t('Unsupported image type. Use PNG, JPEG or WebP.'));
			return;
		}
		const reader = new FileReader();
		reader.onload = (event) => {
			sourceDataUrl = `${event.target?.result ?? ''}`;
			resultDataUrl = '';
		};
		reader.readAsDataURL(file);
	};

	const generate = async () => {
		if (!sourceDataUrl || generating) {
			return;
		}
		generating = true;
		try {
			const res = await generateAvatar(localStorage.token, dataUrlToBlob(sourceDataUrl));
			resultDataUrl = res.image;
			remaining = res.remaining;
		} catch (err) {
			toast.error(`${err}`);
		} finally {
			generating = false;
		}
	};

	// Shrink the 1024px result to <=512px webp so the stored profile_image_url stays small.
	const resizeResult = (src: string): Promise<string> =>
		new Promise((resolve) => {
			const img = new Image();
			img.onload = () => {
				const canvas = document.createElement('canvas');
				const edge = Math.min(512, img.width);
				canvas.width = edge;
				canvas.height = edge;
				canvas.getContext('2d')?.drawImage(img, 0, 0, edge, edge);
				resolve(canvas.toDataURL('image/webp', 0.85));
			};
			img.onerror = () => resolve(src);
			img.src = src;
		});

	const apply = async () => {
		dispatch('apply', await resizeResult(resultDataUrl));
		show = false;
	};
</script>

<input
	bind:this={photoInputElement}
	type="file"
	hidden
	accept="image/png,image/jpeg,image/webp"
	on:change={onPhotoSelected}
/>

<Modal bind:show size="sm">
	<div class="px-5 pt-4 pb-5">
		<div class="flex justify-between items-center dark:text-gray-300">
			<div class="text-lg font-medium self-center">{$i18n.t('AI Avatar')}</div>
			<button
				class="self-center"
				type="button"
				aria-label={$i18n.t('Close')}
				on:click={() => {
					show = false;
				}}
			>
				<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5">
					<path
						d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z"
					/>
				</svg>
			</button>
		</div>

		<div class="text-xs text-gray-500 mt-1">
			{$i18n.t('Create a stylized professional avatar from a photo.')}
		</div>

		<div class="flex justify-center gap-6 my-5">
			<div class="flex flex-col items-center gap-2">
				<button
					type="button"
					class="size-24 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden flex items-center justify-center border border-dashed border-gray-300 dark:border-gray-600"
					on:click={() => photoInputElement.click()}
					aria-label={$i18n.t('Upload a photo')}
				>
					{#if sourceDataUrl}
						<img src={sourceDataUrl} alt="" class="size-24 object-cover" />
					{:else}
						<span class="text-xs text-gray-500 px-2 text-center">{$i18n.t('Upload a photo')}</span>
					{/if}
				</button>
				{#if canUseCurrent && sourceDataUrl !== currentImage}
					<button
						type="button"
						class="text-xs text-gray-500 hover:text-gray-800 dark:hover:text-gray-300"
						on:click={() => {
							sourceDataUrl = currentImage;
							resultDataUrl = '';
						}}>{$i18n.t('Use current photo')}</button
					>
				{/if}
			</div>

			<div class="flex flex-col items-center gap-2">
				<div
					class="size-24 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden flex items-center justify-center"
				>
					{#if generating}
						<Spinner className="size-5" />
					{:else if resultDataUrl}
						<img src={resultDataUrl} alt="" class="size-24 object-cover" />
					{:else}
						<span class="text-xs text-gray-400 px-2 text-center">{$i18n.t('Preview')}</span>
					{/if}
				</div>
			</div>
		</div>

		<div class="text-xs text-gray-500 mb-4">
			{$i18n.t('Your photo is sent to OpenAI to create the avatar. It is not stored.')}
			{#if remaining !== null && limit !== null}
				· {remaining}/{limit} {$i18n.t('generations left today')}
			{/if}
		</div>

		<div class="flex justify-end gap-2">
			<button
				class="px-3.5 py-1.5 text-sm font-medium rounded-full bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition disabled:opacity-50"
				type="button"
				disabled={!sourceDataUrl || generating || remaining === 0}
				on:click={generate}
			>
				{resultDataUrl ? $i18n.t('Regenerate') : $i18n.t('Generate')}
			</button>
			{#if resultDataUrl && !generating}
				<button
					class="px-3.5 py-1.5 text-sm font-medium rounded-full bg-emerald-700 hover:bg-emerald-800 text-white transition"
					type="button"
					on:click={apply}
				>
					{$i18n.t('Use avatar')}
				</button>
			{/if}
		</div>
	</div>
</Modal>
```

- [ ] **Step 2: Wire it into UserProfileImage.svelte**

In `src/lib/components/chat/Settings/Account/UserProfileImage.svelte`:

1. Extend the script imports/state:

```ts
import { config } from '$lib/stores';
import AIAvatarDialog from './AIAvatarDialog.svelte';

let showAIAvatarDialog = false;
```

2. After the Gravatar `<button>` (the last one in the hover action column, ends line ~149), add:

```svelte
{#if $config?.features?.enable_avatar_generation}
	<button
		class=" text-xs text-center text-gray-800 dark:text-gray-400 rounded-lg py-0.5 opacity-0 group-hover:opacity-100 transition-all"
		type="button"
		on:click={() => {
			showAIAvatarDialog = true;
		}}>{$i18n.t('AI Avatar')}</button
	>
{/if}
```

3. At the end of the file (after the closing `</div>` of the component markup):

```svelte
<AIAvatarDialog
	bind:show={showAIAvatarDialog}
	currentImage={profileImageUrl}
	{user}
	on:apply={(e) => {
		profileImageUrl = e.detail;
	}}
/>
```

- [ ] **Step 3: Add i18n keys**

In `src/lib/i18n/locales/en-US/translation.json`, add (alphabetical placement, `""` values — the key text itself is the English copy):

```json
"AI Avatar": "",
"Create a stylized professional avatar from a photo.": "",
"generations left today": "",
"Generate": "",
"Regenerate": "",
"Unsupported image type. Use PNG, JPEG or WebP.": "",
"Upload a photo": "",
"Use avatar": "",
"Use current photo": "",
"Your photo is sent to OpenAI to create the avatar. It is not stored.": ""
```

Check first — some keys (`Generate`, `Close`, `Preview`) may already exist; skip duplicates. (`Close` and `Preview` are near-certainly present.)

- [ ] **Step 4: Static verification**

Run: `npm run test:frontend -- aiAvatar` → 5 PASS (unchanged).
Run: `npx svelte-check --threshold error --output human 2>&1 | Select-String -Pattern "AIAvatarDialog|UserProfileImage|aiAvatar|avatar/index"` → no errors in the new/modified files (repo may have pre-existing errors elsewhere; only the touched files must be clean).

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/chat/Settings/Account/AIAvatarDialog.svelte src/lib/components/chat/Settings/Account/UserProfileImage.svelte src/lib/i18n/locales/en-US/translation.json
git commit -m "feat(avatar): AI Avatar dialog in Account tab" -- src/lib/components/chat/Settings/Account/AIAvatarDialog.svelte src/lib/components/chat/Settings/Account/UserProfileImage.svelte src/lib/i18n/locales/en-US/translation.json
```

---

### Task 7: Full verification pass

**Files:** none (verification only)

- [ ] **Step 1: Backend suite**

Run: `backend\.venv\Scripts\python.exe -m pytest backend/open_webui/test/avatar/ -v`
Expected: 12 PASS.

- [ ] **Step 2: Frontend suite**

Run: `npm run test:frontend`
Expected: all suites pass (incl. the 5 new aiAvatar tests; pre-existing workos/policy suites unaffected).

- [ ] **Step 3: Confirm nothing unrelated was committed**

Run: `git log --stat osool@{u}..HEAD -- . 2>$null` (or `git log --stat -7`)
Expected: each avatar commit touches only its own task's files; the pre-staged workos palette files remain staged-but-uncommitted.

- [ ] **Step 4: Manual smoke (user-driven, needs real key)**

Not automatable here. Preconditions, for whoever runs it:
1. Set on the Docker container (`osool-ai-open-webui-1`): `AVATAR_GENERATION_ENABLED=true` and `AVATAR_OPENAI_API_KEY=sk-...`, then restart the container. Caveat: PersistentConfig — once a value is saved into the config DB (e.g. via admin UI), the DB value wins over env on later boots.
2. Frontend is live via the user's own Vite hot-reload server — do NOT start a Vite server without asking (standing rule).
3. Smoke: Settings → Account → hover avatar → "AI Avatar" → upload photo → Generate (expect ~10-20s) → Regenerate (quota counter drops) → Use avatar → Save → avatar shows in sidebar/topbar. Tune `AVATAR_STYLE_PROMPT` env if the look isn't right.
