import pytest

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_teams import _client, U1


@pytest.mark.asyncio
async def test_directory_returns_team_member_names(monkeypatch):
    async def _fake_names(ids):
        return [{'id': i, 'name': f'User {i}'} for i in ids]

    monkeypatch.setattr(wr, 'resolve_user_names', _fake_names)
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        r = await c.get('/api/v1/workos/directory')
        assert r.status_code == 200
        ids = {row['id'] for row in r.json()}
        assert {'u1', 'u2'} <= ids


@pytest.mark.asyncio
async def test_users_roster_returned_to_team_owner(monkeypatch):
    async def _fake_all_users():
        return [{'id': 'u1', 'name': 'Lara'}, {'id': 'u2', 'name': 'Yusuf'}, {'id': 'u3', 'name': 'Mona'}]

    monkeypatch.setattr(wr, 'list_all_users', _fake_all_users)
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        r = await c.get(f"/api/v1/workos/users?team_id={team['id']}")
        assert r.status_code == 200, r.text
        assert {row['id'] for row in r.json()} == {'u1', 'u2', 'u3'}


@pytest.mark.asyncio
async def test_users_denied_to_plain_member(monkeypatch):
    from open_webui.test.workos.test_router_teams import U2

    async def _fake_all_users():
        return []

    monkeypatch.setattr(wr, 'list_all_users', _fake_all_users)
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    async with _client(monkeypatch, user=U2) as c:
        r = await c.get(f"/api/v1/workos/users?team_id={team['id']}")
        assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_users_requires_team_id(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        r = await c.get('/api/v1/workos/users')
        assert r.status_code == 422  # missing required query param


@pytest.mark.asyncio
async def test_users_requires_workos_access(monkeypatch):
    async def _fake_all_users():
        return []

    monkeypatch.setattr(wr, 'list_all_users', _fake_all_users)
    # team_id present so the handler body runs; the feature gate then rejects.
    async with _client(monkeypatch, user=U1, allow=False) as c:
        r = await c.get('/api/v1/workos/users?team_id=anything')
        assert r.status_code == 401
