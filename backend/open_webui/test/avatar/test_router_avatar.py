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
