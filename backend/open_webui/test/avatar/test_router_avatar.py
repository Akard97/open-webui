import base64
import io
from types import SimpleNamespace

import aiohttp
import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport
from PIL import Image

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


def _form_field(form: aiohttp.FormData, name: str):
    # aiohttp.FormData._fields entries are (type_options, headers, value);
    # the field name lives in type_options['name'].
    for type_options, _headers, value in form._fields:
        if type_options.get('name') == name:
            return value
    raise KeyError(name)


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
    # locked style prompt + model + cost-bound params reach the API call
    url, kwargs = session.calls[0]
    assert url.endswith('/images/edits')
    form = kwargs['data']
    assert _form_field(form, 'model') == 'gpt-image-2'
    assert _form_field(form, 'quality') == 'medium'
    assert _form_field(form, 'output_format') == 'webp'
    assert _form_field(form, 'prompt') == 'style prompt'


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


@pytest.mark.asyncio
async def test_generate_rejects_undecodable_image_bytes(monkeypatch):
    # Content-Type says PNG but the bytes are garbage — must be a clean 400,
    # not an unhandled PIL.UnidentifiedImageError (raw 500).
    session = _patch_openai(monkeypatch)
    async with _client() as c:
        r = await c.post(
            '/api/v1/avatar/generate',
            files={'photo': ('p.png', b'not really a png', 'image/png')},
        )
    assert r.status_code == 400
    assert r.json()['detail'] == 'Invalid or corrupted image file.'
    assert session.calls == []
    assert await AvatarGenerations.get_count('u1', avatar_router._utc_date()) == 0


@pytest.mark.asyncio
async def test_generate_rejects_oversized_upload(monkeypatch):
    session = _patch_openai(monkeypatch)
    big = PNG_BYTES + b'0' * (10 * 1024 * 1024)
    async with _client() as c:
        r = await c.post(
            '/api/v1/avatar/generate',
            files={'photo': ('p.png', big, 'image/png')},
        )
    assert r.status_code == 400
    assert session.calls == []


@pytest.mark.asyncio
async def test_generate_unexpected_success_payload_returns_502(monkeypatch):
    # 200 from OpenAI but no data[0].b64_json — must map to 502, never a raw
    # KeyError/IndexError 500, and must not consume quota.
    _patch_openai(monkeypatch, response=_FakeResponse(status=200, payload={'data': []}))
    async with _client() as c:
        r = await c.post('/api/v1/avatar/generate', files=_files())
    assert r.status_code == 502
    assert r.json()['detail'] == 'Avatar generation returned an unexpected response.'
    assert await AvatarGenerations.get_count('u1', avatar_router._utc_date()) == 0


def test_downscale_caps_longest_edge_and_preserves_aspect():
    buf = io.BytesIO()
    Image.new('RGB', (2048, 1536), 'teal').save(buf, format='PNG')
    out, mime = avatar_router._downscale(buf.getvalue())
    assert mime == 'image/jpeg'
    img = Image.open(io.BytesIO(out))
    assert img.format == 'JPEG'
    assert max(img.size) <= 1024
    w, h = img.size
    assert abs(w / h - 2048 / 1536) < 0.01


def test_downscale_leaves_small_image_unscaled():
    buf = io.BytesIO()
    Image.new('RGB', (200, 200), 'teal').save(buf, format='PNG')
    out, mime = avatar_router._downscale(buf.getvalue())
    assert mime == 'image/jpeg'
    img = Image.open(io.BytesIO(out))
    assert img.size == (200, 200)
