import pytest
from types import SimpleNamespace

from open_webui.test.workos.test_router_teams import _client, U1, U2


async def _team(c):
    return (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()


@pytest.mark.asyncio
async def test_create_and_list_workspace(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = await _team(c)
        r = await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                         json={'name': 'Engineering', 'visibility': 'team'})
        assert r.status_code == 200, r.text
        ws = r.json()
        r = await c.get(f"/api/v1/workos/teams/{team['id']}/workspaces")
        assert [w['id'] for w in r.json()] == [ws['id']]


@pytest.mark.asyncio
async def test_restricted_workspace_hidden_from_non_member(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = await _team(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                          json={'name': 'Secret', 'visibility': 'restricted'})).json()
    async with _client(monkeypatch, user=U2) as c:
        # u2 is a team member but not a workspace member -> 404 on the restricted workspace
        r = await c.get(f"/api/v1/workos/workspaces/{ws['id']}")
        assert r.status_code == 404
        # not listed either
        r = await c.get(f"/api/v1/workos/teams/{team['id']}/workspaces")
        assert ws['id'] not in [w['id'] for w in r.json()]


@pytest.mark.asyncio
async def test_member_cannot_create_workspace(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = await _team(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    async with _client(monkeypatch, user=U2) as c:
        r = await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces", json={'name': 'X', 'visibility': 'team'})
        assert r.status_code == 403
