import pytest

from open_webui.test.workos.test_router_teams import _client, U1, U2
from open_webui.test.workos.test_router_task import _stream


@pytest.mark.asyncio
async def test_member_cannot_edit_task_they_dont_own(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'T'})).json()
    async with _client(monkeypatch, user=U2) as c:
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'title': 'hijack'})
        assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_assignee_can_edit_task(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                          json={'title': 'T', 'assignee_ids': ['u2']})).json()
    async with _client(monkeypatch, user=U2) as c:
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'status': 'in_progress'})
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_team_admin_can_edit_others_task(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'admin'})
        t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'T'})).json()
    async with _client(monkeypatch, user=U2) as c:
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'title': 'edited'})
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_creator_can_still_edit_own_task(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'T'})).json()
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'priority': 'high'})
        assert r.status_code == 200, r.text


async def _subtask(c):
    team, ws, s = await _stream(c)
    t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'T'})).json()
    st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks", json={'title': 'sub'})).json()
    return team, ws, s, t, st


@pytest.mark.asyncio
async def test_member_cannot_edit_others_subtask(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s, t, st = await _subtask(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    async with _client(monkeypatch, user=U2) as c:
        r = await c.patch(f"/api/v1/workos/subtasks/{st['id']}", json={'completed': True})
        assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_member_cannot_delete_others_subtask(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s, t, st = await _subtask(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    async with _client(monkeypatch, user=U2) as c:
        r = await c.delete(f"/api/v1/workos/subtasks/{st['id']}")
        assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_task_creator_can_modify_and_delete_subtask(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s, t, st = await _subtask(c)
        r = await c.patch(f"/api/v1/workos/subtasks/{st['id']}", json={'completed': True})
        assert r.status_code == 200, r.text
        r = await c.delete(f"/api/v1/workos/subtasks/{st['id']}")
        assert r.json()['deleted'] is True
