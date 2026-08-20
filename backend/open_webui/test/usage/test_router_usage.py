from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

import open_webui.routers.usage as ur
from open_webui.models.usage import UsageEvents
from open_webui.utils.auth import get_verified_user

U1 = SimpleNamespace(id='u1', name='Lara', role='user')


def _make_app(user, enabled=True):
    app = FastAPI()
    app.state.config = SimpleNamespace(ENABLE_USAGE_TRACKING=enabled)
    app.include_router(ur.router, prefix='/api/v1/usage')
    app.dependency_overrides[get_verified_user] = lambda: user
    return app


def _client(*, user=U1, enabled=True):
    return httpx.AsyncClient(
        transport=ASGITransport(app=_make_app(user, enabled)), base_url='http://test'
    )


def _ev(name='page.view', **props):
    return {'name': name, 'properties': {'tool': 'workos', 'view': 'board', **props}, 'session_id': 's1'}


@pytest.mark.asyncio
async def test_ingest_accepts_valid_batch():
    async with _client() as c:
        r = await c.post('/api/v1/usage/events', json={'events': [_ev(), _ev()]})
    assert r.status_code == 200
    assert r.json() == {'accepted': 2, 'rejected': 0}


@pytest.mark.asyncio
async def test_ingest_rejects_server_kind_and_unknown_names():
    async with _client() as c:
        r = await c.post(
            '/api/v1/usage/events',
            json={'events': [{'name': 'workos.task.create', 'properties': {}, 'session_id': 's1'},
                             {'name': 'nope', 'properties': {}, 'session_id': 's1'}]},
        )
    assert r.status_code == 200
    assert r.json() == {'accepted': 0, 'rejected': 2}


@pytest.mark.asyncio
async def test_ingest_batch_cap():
    async with _client() as c:
        r = await c.post('/api/v1/usage/events', json={'events': [_ev()] * 51})
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_ingest_disabled_flag_drops_everything():
    async with _client(enabled=False) as c:
        r = await c.post('/api/v1/usage/events', json={'events': [_ev()]})
    assert r.status_code == 200
    assert r.json() == {'accepted': 0, 'rejected': 1}


@pytest.mark.asyncio
async def test_ingest_user_id_comes_from_token_not_payload(monkeypatch):
    seen = {}
    real = UsageEvents.insert_client_batch

    async def spy(user_id, events, db=None):
        seen['user_id'] = user_id
        return await real(user_id, events, db=db)

    monkeypatch.setattr(UsageEvents, 'insert_client_batch', spy)
    async with _client() as c:
        await c.post('/api/v1/usage/events', json={'events': [_ev(user_id='attacker')]})
    assert seen['user_id'] == 'u1'


@pytest.mark.asyncio
async def test_ingest_rate_limited(monkeypatch):
    monkeypatch.setattr(ur.ingest_rate_limiter, 'is_limited', lambda key: True)
    async with _client() as c:
        r = await c.post('/api/v1/usage/events', json={'events': [_ev()]})
    assert r.status_code == 429
