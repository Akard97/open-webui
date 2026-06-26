import pytest
import pytest_asyncio
from types import SimpleNamespace

import httpx
from httpx import ASGITransport
from fastapi import FastAPI

import open_webui.routers.workos as wr
from open_webui.utils.auth import get_verified_user


def _make_app(user, rules=None):
    app = FastAPI()
    app.state.config = SimpleNamespace(
        USER_PERMISSIONS={},
        WORKOS_RULES=rules or {'team_creation': 'all_users', 'default_workspace_visibility': 'team'},
    )
    app.include_router(wr.router, prefix='/api/v1/workos')
    app.dependency_overrides[get_verified_user] = lambda: user
    return app


def _client(monkeypatch, *, user, allow=True, rules=None):
    async def _hp(user_id, key, permissions, db=None):
        return allow
    monkeypatch.setattr(wr, 'has_permission', _hp)
    return httpx.AsyncClient(transport=ASGITransport(app=_make_app(user, rules)), base_url='http://test')


U1 = SimpleNamespace(id='u1', name='Lara', role='user')
U2 = SimpleNamespace(id='u2', name='Yusuf', role='user')


@pytest.mark.asyncio
async def test_create_team_makes_creator_owner_and_lists(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        r = await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})
        assert r.status_code == 200, r.text
        team = r.json()
        assert team['key'] == 'OSL'

        r = await c.get('/api/v1/workos/teams')
        assert [t['id'] for t in r.json()] == [team['id']]

        r = await c.get('/api/v1/workos/bootstrap')
        body = r.json()
        assert body['roles'][team['id']] == 'owner'


@pytest.mark.asyncio
async def test_non_member_cannot_see_team(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
    async with _client(monkeypatch, user=U2) as c:
        r = await c.get(f"/api/v1/workos/teams/{team['id']}")
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_only_owner_can_add_members(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        r = await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        assert r.status_code == 200
    # u2 is now a member but not owner/admin -> cannot add a third member
    async with _client(monkeypatch, user=U2) as c:
        r = await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u3', 'role': 'member'})
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_gate_denied_returns_401(monkeypatch):
    async with _client(monkeypatch, user=U1, allow=False) as c:
        r = await c.get('/api/v1/workos/teams')
        assert r.status_code == 401


ADMIN = SimpleNamespace(id='admin1', name='Root', role='admin')


@pytest.mark.asyncio
async def test_system_admin_can_edit_and_delete_any_team(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
    async with _client(monkeypatch, user=ADMIN) as c:
        r = await c.patch(f"/api/v1/workos/teams/{team['id']}", json={'name': 'Renamed'})
        assert r.status_code == 200, r.text
        assert r.json()['name'] == 'Renamed'
        r = await c.delete(f"/api/v1/workos/teams/{team['id']}")
        assert r.json()['deleted'] is True
