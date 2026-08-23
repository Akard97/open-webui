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


@pytest.mark.asyncio
async def test_active_endpoint():
    await _seed()
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/active?days=30')
    assert r.status_code == 200
    data = r.json()
    assert set(data) == {'dau', 'wau', 'mau', 'new_users'}
    assert data['dau'] == {'current': 2, 'previous': 0}


@pytest.mark.asyncio
async def test_heatmap_endpoint():
    await _seed()
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/heatmap?days=30')
    assert r.status_code == 200
    m = r.json()['matrix']
    assert len(m) == 7 and all(len(row) == 24 for row in m)
    assert sum(sum(row) for row in m) == 2


@pytest.mark.asyncio
async def test_models_endpoint():
    await _seed()
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/models?days=30')
    assert r.status_code == 200
    assert r.json()['models'] == [{'model': 'm1', 'messages': 1, 'unique_users': 1}]


@pytest.mark.asyncio
async def test_sessions_daily_endpoint():
    await _seed()
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/sessions/daily?days=30')
    assert r.status_code == 200
    data = r.json()
    assert data['days'][0]['sessions'] == 1
    assert data['avg_session_ms'] == 0


@pytest.mark.asyncio
async def test_groups_endpoint(monkeypatch):
    await _seed()

    async def _get_all_groups(db=None):
        return [
            SimpleNamespace(id='g1', name='Engineering'),
            SimpleNamespace(id='g2', name='Empty'),
        ]

    async def _get_group_user_ids_by_ids(ids, db=None):
        return {'g1': ['u1', 'u2', 'u3'], 'g2': []}

    async def _group_rollup(since_ms, db=None):
        return {'g1': {'active_users': 2, 'events': 2, 'top_tool': 'workos'}}

    monkeypatch.setattr(Groups, 'get_all_groups', staticmethod(_get_all_groups))
    monkeypatch.setattr(
        Groups, 'get_group_user_ids_by_ids', staticmethod(_get_group_user_ids_by_ids)
    )
    monkeypatch.setattr(UsageEvents, 'group_rollup', _group_rollup)
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/groups?days=30')
    assert r.status_code == 200
    groups = r.json()['groups']
    assert groups[0] == {
        'group_id': 'g1', 'name': 'Engineering', 'members': 3,
        'active_users': 2, 'events': 2, 'top_tool': 'workos',
    }
    assert groups[1] == {
        'group_id': 'g2', 'name': 'Empty', 'members': 0,
        'active_users': 0, 'events': 0, 'top_tool': None,
    }


@pytest.mark.asyncio
async def test_user_summary_endpoint():
    await _seed()
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/users/u2/summary?days=30')
    assert r.status_code == 200
    data = r.json()
    assert data['tools'] == {'chat': 1}
    assert data['models'] == [{'model': 'm1', 'messages': 1}]
    assert len(data['hours']) == 24


@pytest.mark.asyncio
async def test_new_endpoints_require_admin():
    async with _client(admin=False) as c:
        for path in (
            'usage/active', 'usage/heatmap', 'usage/models',
            'usage/sessions/daily', 'usage/groups', 'usage/users/u1/summary',
        ):
            r = await c.get(f'/api/v1/analytics/{path}')
            assert r.status_code in (401, 403), path


@pytest.mark.asyncio
async def test_new_endpoints_group_filter(monkeypatch):
    # The router→DAO user_ids handoff on each scoped new endpoint — exactly
    # where a copy-paste omission would hide.
    await _seed()
    _stub_group(monkeypatch, ['u1'])
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/active?days=30&group_id=g1')
        assert r.json()['dau']['current'] == 1
        r = await c.get('/api/v1/analytics/usage/heatmap?days=30&group_id=g1')
        assert sum(sum(row) for row in r.json()['matrix']) == 1
        r = await c.get('/api/v1/analytics/usage/models?days=30&group_id=g1')
        assert r.json()['models'] == []  # u2's chat message excluded
        r = await c.get('/api/v1/analytics/usage/sessions/daily?days=30&group_id=g1')
        assert r.json()['days'][0]['sessions'] == 1


@pytest.mark.asyncio
async def test_new_endpoints_unknown_group_404(monkeypatch):
    _stub_group(monkeypatch, [])
    async with _client() as c:
        for path in (
            'usage/active?group_id=nope',
            'usage/heatmap?group_id=nope',
            'usage/models?group_id=nope',
            'usage/sessions/daily?group_id=nope',
        ):
            r = await c.get(f'/api/v1/analytics/{path}')
            assert r.status_code == 404, path


@pytest.mark.asyncio
async def test_empty_group_zeros(monkeypatch):
    # 0-member group must yield zeros, not silently degrade to unscoped data
    # (the None-vs-[] seam in _group_user_ids).
    await _seed()
    _stub_group(monkeypatch, [])
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/overview?days=30&group_id=g1')
        assert r.json()['tools'] == []
        r = await c.get('/api/v1/analytics/usage/active?days=30&group_id=g1')
        assert r.json()['dau'] == {'current': 0, 'previous': 0}
