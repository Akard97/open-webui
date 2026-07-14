import pytest

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_teams import _client, U1, U2
from open_webui.test.workos.test_router_task import _stream


async def _restricted_task(c):
    """U1 owns a restricted workspace (auto workspace-admin) with one stream + task."""
    team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
    ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                       json={'name': 'Eng', 'visibility': 'restricted'})).json()
    s = (await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'P'})).json()
    t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                      json={'title': 'T', 'assignee_ids': ['u1']})).json()
    return team, ws, s, t


@pytest.mark.asyncio
async def test_commented_notification_skips_participant_who_lost_visibility(monkeypatch):
    sent = []

    async def _eu(event, payload, user_ids):
        if payload.get('type') == 'commented':
            sent.extend(user_ids)

    monkeypatch.setattr(wr, 'emit_users', _eu)
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s, t = await _restricted_task(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        await c.post(f"/api/v1/workos/workspaces/{ws['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    async with _client(monkeypatch, user=U2) as c2:
        # u2 can see the stream now, so becomes a comment participant.
        await c2.post(f"/api/v1/workos/tasks/{t['id']}/comments", json={'body': 'u2 here'})
    async with _client(monkeypatch, user=U1) as c:
        await c.delete(f"/api/v1/workos/workspaces/{ws['id']}/members/u2")  # u2 loses visibility
        await c.post(f"/api/v1/workos/tasks/{t['id']}/comments", json={'body': 'reply'})
    assert 'u2' not in sent


@pytest.mark.asyncio
async def test_commented_notification_reaches_visible_participant(monkeypatch):
    sent = []

    async def _eu(event, payload, user_ids):
        if payload.get('type') == 'commented':
            sent.extend(user_ids)

    monkeypatch.setattr(wr, 'emit_users', _eu)
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s, t = await _restricted_task(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        await c.post(f"/api/v1/workos/workspaces/{ws['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    async with _client(monkeypatch, user=U2) as c2:
        await c2.post(f"/api/v1/workos/tasks/{t['id']}/comments", json={'body': 'u2 here'})
    async with _client(monkeypatch, user=U1) as c:
        await c.post(f"/api/v1/workos/tasks/{t['id']}/comments", json={'body': 'reply'})
    assert 'u2' in sent


@pytest.mark.asyncio
async def test_create_task_rejects_assignee_who_cannot_see_workstream(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)  # team-visible; u2 is NOT a member
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                         json={'title': 'T', 'assignee_ids': ['u2']})
        assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_create_task_allows_assignee_who_is_team_member(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                         json={'title': 'T', 'assignee_ids': ['u2']})
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_update_task_rejects_unseeable_assignee(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                          json={'title': 'T', 'assignee_ids': ['u1']})).json()
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_ids': ['u2']})
        assert r.status_code == 400, r.text
