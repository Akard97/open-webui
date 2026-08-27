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
        # Bare slug redirects to the canonical trailing-slash URL so the
        # page's relative assets resolve inside /sites/demo/.
        bare = await c.get('/sites/demo')
        assert bare.status_code == 308
        assert bare.headers['location'] == '/sites/demo/'

        res = await c.get('/sites/demo/')
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
        res = await c.get('/sites/demo/')
        assert res.status_code == 302
        assert res.headers['location'].startswith('/auth?redirect=')
        assert res.headers['location'].endswith('/sites/demo/')
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
        assert (await c.get('/sites/internal/')).status_code == 200
        assert (await c.get('/sites/granted/')).status_code == 200
        assert (await c.get('/sites/locked/')).status_code == 404  # no leak
    async with _client(monkeypatch, tmp_path, viewer=OWNER) as c:
        assert (await c.get('/sites/locked/')).status_code == 200  # owner
    async with _client(monkeypatch, tmp_path, viewer=ADMIN) as c:
        assert (await c.get('/sites/locked/')).status_code == 200  # admin


@pytest.mark.asyncio
async def test_unknown_slug_and_unknown_file(monkeypatch, tmp_path):
    await _seed(tmp_path, public=True)
    async with _client(monkeypatch, tmp_path, viewer=None) as c:
        assert (await c.get('/sites/nope/')).status_code == 404
        assert (await c.get('/sites/demo/ghost.png')).status_code == 404


@pytest.mark.asyncio
async def test_traversal_rejected(monkeypatch, tmp_path):
    await _seed(tmp_path, public=True)
    (tmp_path / 'secret.txt').write_text('nope')
    async with _client(monkeypatch, tmp_path, viewer=None) as c:
        # not in manifest -> 404 regardless of encoding tricks
        assert (await c.get('/sites/demo/..%2Fsecret.txt')).status_code == 404
        assert (await c.get('/sites/demo/%2e%2e/secret.txt')).status_code == 404


@pytest.mark.asyncio
async def test_optional_user_role_gate(monkeypatch):
    monkeypatch.setattr(sites_router, 'decode_token', lambda t: {'id': 'x1'})

    async def _user_with_role(role):
        async def _get(id, db=None):
            return SimpleNamespace(id='x1', role=role)
        return _get

    req = SimpleNamespace(headers={'authorization': 'Bearer tok'}, cookies={})

    monkeypatch.setattr(sites_router.Users, 'get_user_by_id', await _user_with_role('pending'))
    assert await sites_router._get_optional_user(req) is None

    monkeypatch.setattr(sites_router.Users, 'get_user_by_id', await _user_with_role('user'))
    assert (await sites_router._get_optional_user(req)).role == 'user'

    monkeypatch.setattr(sites_router.Users, 'get_user_by_id', await _user_with_role('admin'))
    assert (await sites_router._get_optional_user(req)).role == 'admin'


@pytest.mark.asyncio
async def test_optional_user_rejects_revoked_token(monkeypatch):
    """A revoked JWT (sign-out / back-channel logout) must resolve to anonymous."""
    monkeypatch.setattr(sites_router, 'decode_token', lambda t: {'id': 'x1', 'jti': 'j1'})

    async def _get_user(id, db=None):
        return SimpleNamespace(id='x1', role='user', email='x@x.io')

    monkeypatch.setattr(sites_router.Users, 'get_user_by_id', _get_user)
    req = SimpleNamespace(headers={'authorization': 'Bearer tok'}, cookies={})

    async def _revoked(request, decoded):
        return False

    monkeypatch.setattr(sites_router, 'is_valid_token', _revoked)
    assert await sites_router._get_optional_user(req) is None

    async def _valid(request, decoded):
        return True

    monkeypatch.setattr(sites_router, 'is_valid_token', _valid)
    assert (await sites_router._get_optional_user(req)).id == 'x1'
