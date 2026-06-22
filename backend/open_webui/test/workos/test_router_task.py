import pytest

from open_webui.test.workos.test_router_teams import _client, U1, U2


async def _stream(c):
    team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
    ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                       json={'name': 'Eng', 'visibility': 'team'})).json()
    s = (await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'Platform'})).json()
    return team, ws, s


@pytest.mark.asyncio
async def test_task_create_patch_delete(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'Migrate billing'})
        assert r.status_code == 200, r.text
        t = r.json()
        assert t['key'] == 'OSL-1' and t['status'] == 'backlog'
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}",
                          json={'status': 'in_progress', 'priority': 'high', 'sort_key': 5.0})
        assert r.json()['status'] == 'in_progress' and r.json()['priority'] == 'high'
        r = await c.get(f"/api/v1/workos/workstreams/{s['id']}/tasks")
        assert len(r.json()) == 1
        assert (await c.delete(f"/api/v1/workos/tasks/{t['id']}")).json()['deleted'] is True


@pytest.mark.asyncio
async def test_task_patch_rejects_bad_status(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'X'})).json()
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'status': 'bogus'})
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_labels_crud(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        r = await c.post(f"/api/v1/workos/teams/{team['id']}/labels", json={'name': 'backend', 'color': 'cyan'})
        assert r.status_code == 200
        lab = r.json()
        assert [x['id'] for x in (await c.get(f"/api/v1/workos/teams/{team['id']}/labels")).json()] == [lab['id']]
        assert (await c.delete(f"/api/v1/workos/labels/{lab['id']}")).json()['deleted'] is True


@pytest.mark.asyncio
async def test_non_member_cannot_create_task(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
    async with _client(monkeypatch, user=U2) as c:
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'X'})
        assert r.status_code == 404
