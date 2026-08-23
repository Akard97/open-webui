from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

import open_webui.routers.analytics as ar
from open_webui.models.groups import Groups
from open_webui.models.usage import UsageEvents, _now
from open_webui.utils.auth import get_admin_user

ADMIN = SimpleNamespace(id='admin1', name='Admin', role='admin')


def _make_app(admin=True):
    app = FastAPI()
    app.include_router(ar.router, prefix='/api/v1/analytics')
    if admin:
        app.dependency_overrides[get_admin_user] = lambda: ADMIN
    return app


def _client(admin=True):
    return httpx.AsyncClient(
        transport=ASGITransport(app=_make_app(admin)), base_url='http://test'
    )


def _stub_group(monkeypatch, members):
    async def _get_group_by_id(id, db=None):
        return SimpleNamespace(id=id, name='G') if id == 'g1' else None

    async def _get_group_user_ids_by_id(id, db=None):
        return members

    monkeypatch.setattr(Groups, 'get_group_by_id', staticmethod(_get_group_by_id))
    monkeypatch.setattr(
        Groups, 'get_group_user_ids_by_id', staticmethod(_get_group_user_ids_by_id)
    )


async def _seed():
    await UsageEvents.insert_client_batch('u1', [
        {'name': 'page.view', 'properties': {'tool': 'workos', 'view': 'board'}, 'session_id': 's1'},
    ])
    await UsageEvents.emit('u2', 'chat.message.sent', {'model': 'm1'})


@pytest.mark.asyncio
async def test_overview_group_filter(monkeypatch):
    await _seed()
    _stub_group(monkeypatch, ['u1'])
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/overview?days=30&group_id=g1')
    assert r.status_code == 200
    tools = {t['tool'] for t in r.json()['tools']}
    assert tools == {'workos'}


@pytest.mark.asyncio
async def test_overview_includes_prev_active_users():
    await _seed()
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/overview?days=30')
    assert r.status_code == 200
    assert all('prev_active_users' in t for t in r.json()['tools'])


@pytest.mark.asyncio
async def test_unknown_group_404(monkeypatch):
    _stub_group(monkeypatch, [])
    async with _client() as c:
        for path in (
            'usage/overview?group_id=nope',
            'usage/daily?group_id=nope',
            'usage/events?group_id=nope',
            'usage/users?group_id=nope',
        ):
            r = await c.get(f'/api/v1/analytics/{path}')
            assert r.status_code == 404, path


@pytest.mark.asyncio
async def test_users_group_filter(monkeypatch):
    await _seed()
    _stub_group(monkeypatch, ['u2'])

    async def _fake_get_users_by_user_ids(ids, db=None):
        return []

    from open_webui.models.users import Users
    monkeypatch.setattr(
        Users, 'get_users_by_user_ids', staticmethod(_fake_get_users_by_user_ids)
    )
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/users?days=30&group_id=g1')
    assert r.status_code == 200
    data = r.json()
    assert data['total'] == 1
    assert data['users'][0]['user_id'] == 'u2'
