import pytest
from types import SimpleNamespace

import open_webui.routers.workos as wr
from open_webui.models.workos import Teams, TeamMembers, Workspaces, Workstreams
from open_webui.utils.workos_access import can_see_team, can_see_workstream
from open_webui.test.workos.test_router_teams import _client, U1, U2


@pytest.mark.asyncio
async def test_can_see_helpers():
    team = await Teams.insert('Acme', 'OSL', None, 'u1')
    await TeamMembers.add(team.id, 'u1', 'owner')
    ws = await Workspaces.insert(team.id, 'Eng', None, 'team', 'u1')
    s = await Workstreams.insert(ws.id, 'Platform', None, 'u1')
    assert await can_see_team('u1', False, team.id) is True
    assert await can_see_team('u2', False, team.id) is False
    assert await can_see_workstream('u1', False, s.id) is True
    assert await can_see_workstream('u2', False, s.id) is False
    assert await can_see_workstream('u2', True, s.id) is True  # admin override


@pytest.mark.asyncio
async def test_task_create_emits_event(monkeypatch):
    events = []

    async def _rec(event, room, payload):
        events.append((event, room))

    monkeypatch.setattr(wr, 'emit_event', _rec)
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                          json={'name': 'Eng', 'visibility': 'team'})).json()
        s = (await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'P'})).json()
        await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'X'})
    assert ('workos:task.created', f"workos:workstream:{s['id']}") in events
