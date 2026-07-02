import pytest
from types import SimpleNamespace

from open_webui.test.workos.test_router_teams import _client, U1, U2

ADMIN = SimpleNamespace(id='admin1', name='Root', role='admin')
U3 = SimpleNamespace(id='u3', name='Nadia', role='user')


async def _setup_team(c, *, key='OSL'):
    team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': key})).json()
    return team


@pytest.mark.asyncio
async def test_owner_sees_own_team_with_role_and_counts(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = await _setup_team(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces", json={'name': 'Open', 'visibility': 'team'})

        r = await c.get('/api/v1/workos/access/overview')
        assert r.status_code == 200
        rows = r.json()
        row = next(x for x in rows if x['team']['id'] == team['id'])
        assert row['my_role'] == 'owner'
        assert row['member_count'] == 2
        assert row['owner_ids'] == ['u1']
        assert [w['name'] for w in row['workspaces']] == ['Open']
        assert row['workspaces'][0]['visibility'] == 'team'
        assert 'member_count' not in row['workspaces'][0]


@pytest.mark.asyncio
async def test_plain_member_gets_empty_list(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = await _setup_team(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    async with _client(monkeypatch, user=U2) as c:
        r = await c.get('/api/v1/workos/access/overview')
        assert r.status_code == 200
        assert r.json() == []


@pytest.mark.asyncio
async def test_team_admin_sees_team_but_not_hidden_restricted_workspace(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = await _setup_team(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'admin'})
        # restricted workspace created by u1 (owner) -> u1 auto-added as workspace admin, u2 is not a member
        r = await c.post(
            f"/api/v1/workos/teams/{team['id']}/workspaces", json={'name': 'Secret', 'visibility': 'restricted'}
        )
        assert r.status_code == 200

    async with _client(monkeypatch, user=U2) as c:
        rows = (await c.get('/api/v1/workos/access/overview')).json()
        row = next(x for x in rows if x['team']['id'] == team['id'])
        assert row['my_role'] == 'admin'
        # deliberate 2026-06-26 decision: team admin gets no bypass into restricted workspaces
        assert [w['name'] for w in row['workspaces']] == []

    async with _client(monkeypatch, user=U1) as c:
        rows = (await c.get('/api/v1/workos/access/overview')).json()
        row = next(x for x in rows if x['team']['id'] == team['id'])
        ws = next(w for w in row['workspaces'] if w['name'] == 'Secret')
        assert ws['visibility'] == 'restricted'
        assert ws['member_count'] == 1


@pytest.mark.asyncio
async def test_app_admin_sees_all_teams_including_archived_and_restricted(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = await _setup_team(c)
        await c.post(
            f"/api/v1/workos/teams/{team['id']}/workspaces", json={'name': 'Secret', 'visibility': 'restricted'}
        )
        await c.patch(f"/api/v1/workos/teams/{team['id']}", json={'archived': True})

    async with _client(monkeypatch, user=ADMIN) as c:
        rows = (await c.get('/api/v1/workos/access/overview')).json()
        row = next(x for x in rows if x['team']['id'] == team['id'])
        assert row['team']['archived'] is True
        assert row['my_role'] == 'admin'
        ws = next(w for w in row['workspaces'] if w['name'] == 'Secret')
        assert ws['visibility'] == 'restricted'
        assert ws['member_count'] == 1


@pytest.mark.asyncio
async def test_gate_denied_returns_401(monkeypatch):
    async with _client(monkeypatch, user=U3, allow=False) as c:
        r = await c.get('/api/v1/workos/access/overview')
        assert r.status_code == 401
