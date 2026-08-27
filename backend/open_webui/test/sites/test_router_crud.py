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


@pytest.mark.asyncio
async def test_size_limits(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path, user=USER) as c:
        big = b'x' * (sites_router.MAX_FILE_SIZE + 1)
        res = await c.post('/api/v1/sites/', data=_form(slug='too-big'),
                           files=[('files', ('index.html', big, 'text/html'))])
        assert res.status_code == 400

        ok = b'x' * (9 * 1024 * 1024)
        parts = [('files', (f'f{i}.html', ok, 'text/html')) for i in range(4)]  # 36MB total > 30MB
        res = await c.post('/api/v1/sites/', data=_form(slug='too-much'), files=parts)
        assert res.status_code == 400

        exact = b'x' * sites_router.MAX_FILE_SIZE  # exactly at the per-file limit: allowed if total fits
        res = await c.post('/api/v1/sites/', data=_form(slug='at-limit'),
                           files=[('files', ('index.html', exact, 'text/html'))])
        assert res.status_code == 200


@pytest.mark.asyncio
async def test_create_cleans_up_on_write_failure(monkeypatch, tmp_path):
    async with _client(monkeypatch, tmp_path, user=USER) as c:
        def _boom(site_id, validated):
            raise OSError('disk full')

        monkeypatch.setattr(sites_router, '_stage_site_dir', _boom)
        with pytest.raises(OSError):
            await c.post('/api/v1/sites/', data=_form(slug='doomed'), files=[_upload()])

    assert await Sites.get_site_by_slug('doomed') is None
