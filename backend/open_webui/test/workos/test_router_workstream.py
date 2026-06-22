import pytest

from open_webui.test.workos.test_router_teams import _client, U1, U2


async def _ws(c):
    team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
    ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                       json={'name': 'Engineering', 'visibility': 'team'})).json()
    return team, ws


@pytest.mark.asyncio
async def test_workstream_crud(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws = await _ws(c)
        r = await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'Platform'})
        assert r.status_code == 200, r.text
        s = r.json()
        r = await c.get(f"/api/v1/workos/workspaces/{ws['id']}/workstreams")
        assert [x['id'] for x in r.json()] == [s['id']]
        r = await c.patch(f"/api/v1/workos/workstreams/{s['id']}", json={'name': 'Core'})
        assert r.json()['name'] == 'Core'
        r = await c.delete(f"/api/v1/workos/workstreams/{s['id']}")
        assert r.json()['deleted'] is True


@pytest.mark.asyncio
async def test_non_member_cannot_list_workstreams(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws = await _ws(c)
    async with _client(monkeypatch, user=U2) as c:
        r = await c.get(f"/api/v1/workos/workspaces/{ws['id']}/workstreams")
        assert r.status_code == 404
