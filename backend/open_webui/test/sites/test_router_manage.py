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
