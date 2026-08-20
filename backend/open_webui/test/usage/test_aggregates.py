from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

import open_webui.routers.analytics as ar
from open_webui.models.usage import UsageEvents, _now
from open_webui.models.users import Users
from open_webui.utils.auth import get_admin_user, get_current_user


async def _seed():
    # u1: workos page + task create; u2: chat message
    await UsageEvents.insert_client_batch('u1', [
        {'name': 'page.view', 'properties': {'tool': 'workos', 'view': 'board'}, 'session_id': 's1'},
        {'name': 'page.leave', 'properties': {'tool': 'workos', 'view': 'board', 'duration_ms': 4000}, 'session_id': 's1'},
    ])
    await UsageEvents.emit('u1', 'workos.task.create', {'task_id': 't1'})
    await UsageEvents.emit('u2', 'chat.message.sent', {'model': 'm1'})


@pytest.mark.asyncio
async def test_overview():
    await _seed()
    tools = {t['tool']: t for t in await UsageEvents.overview(since_ms=0)}
    assert tools['workos']['active_users'] == 1
    assert tools['workos']['events'] == 3
    assert tools['workos']['avg_page_ms'] == 4000
    assert tools['chat']['active_users'] == 1


@pytest.mark.asyncio
async def test_daily_and_event_counts():
    await _seed()
    days = await UsageEvents.daily(since_ms=0)
    assert len(days) == 1
    assert days[0]['tools']['workos'] == 1
    assert days[0]['events'] == 4
    counts = {e['event_name']: e for e in await UsageEvents.event_counts(since_ms=0)}
    assert counts['workos.task.create']['count'] == 1
    assert counts['page.view']['unique_users'] == 1


@pytest.mark.asyncio
async def test_user_rollup_and_sort():
    await _seed()
    res = await UsageEvents.user_rollup(since_ms=0, sort='events', page=1, limit=10)
    assert res['total'] == 2
    assert res['users'][0]['user_id'] == 'u1'  # 3 events > 1
    assert res['users'][0]['tools']['workos'] == 3


@pytest.mark.asyncio
async def test_delete_before():
    await _seed()
    deleted = await UsageEvents.delete_before(_now() + 1000)
    assert deleted == 4
    assert (await UsageEvents.user_rollup(since_ms=0))['total'] == 0


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


@pytest.mark.asyncio
async def test_usage_endpoint_requires_admin():
    # No get_admin_user override: real auth dependency runs with no
    # credentials on the request and must reject before reaching the DAO.
    async with _client(admin=False) as c:
        r = await c.get('/api/v1/analytics/usage/overview')
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_usage_endpoint_requires_admin_role():
    # Authenticated as a real (non-admin) user: get_current_user is
    # overridden so auth succeeds, but get_admin_user is NOT overridden,
    # so its own role check must reject a non-admin user.
    app = FastAPI()
    app.include_router(ar.router, prefix='/api/v1/analytics')
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id='u1', name='User', role='user'
    )
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url='http://test'
    ) as c:
        r = await c.get('/api/v1/analytics/usage/overview')
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_usage_overview_endpoint():
    await _seed()
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/overview?days=30')
    assert r.status_code == 200
    tools = {t['tool']: t for t in r.json()['tools']}
    assert tools['workos']['active_users'] == 1
    assert tools['workos']['events'] == 3
    assert tools['workos']['avg_page_ms'] == 4000


@pytest.mark.asyncio
async def test_usage_daily_endpoint():
    await _seed()
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/daily?days=30')
    assert r.status_code == 200
    data = r.json()
    assert len(data['days']) == 1
    assert data['days'][0]['tools']['workos'] == 1
    assert data['days'][0]['events'] == 4


@pytest.mark.asyncio
async def test_usage_events_endpoint():
    await _seed()
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/events?days=30')
    assert r.status_code == 200
    counts = {e['event_name']: e for e in r.json()['events']}
    assert counts['workos.task.create']['count'] == 1
    assert counts['page.view']['unique_users'] == 1


@pytest.mark.asyncio
async def test_usage_users_endpoint(monkeypatch):
    await _seed()
    stub = {'u1': SimpleNamespace(id='u1', name='Lara')}

    async def _fake_get_users_by_user_ids(ids, db=None):
        return [stub[i] for i in ids if i in stub]

    monkeypatch.setattr(
        Users, 'get_users_by_user_ids', staticmethod(_fake_get_users_by_user_ids)
    )
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/users?days=30&sort=events&page=1')
    assert r.status_code == 200
    data = r.json()
    assert data['total'] == 2
    assert data['users'][0]['user_id'] == 'u1'
    assert data['users'][0]['name'] == 'Lara'
    assert data['users'][0]['tools']['workos'] == 3
    assert data['users'][1]['name'] == 'removed user'


@pytest.mark.asyncio
async def test_usage_user_activity_endpoint():
    await _seed()
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/users/u1/activity?days=30&page=1')
    assert r.status_code == 200
    data = r.json()
    assert data['total'] == 3
    assert {e['event_name'] for e in data['events']} == {
        'page.view', 'page.leave', 'workos.task.create'
    }
