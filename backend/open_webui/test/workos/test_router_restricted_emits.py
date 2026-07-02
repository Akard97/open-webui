"""Restricted-workspace event routing: nav events for restricted workspaces
never reach the team-wide room — they go to member user rooms — and the
team<->restricted visibility flips emit the documented sequences in order."""
import pytest

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_teams import _client, U1


def _record(monkeypatch):
    """One ordered log across both channels: ('room', event, room) / ('users', event, ids)."""
    log = []

    async def _ee(event, room, payload):
        log.append(('room', event, room))

    async def _eu(event, payload, user_ids):
        log.append(('users', event, sorted(user_ids)))

    async def _evict(workstream_id):
        log.append(('evict', workstream_id))

    monkeypatch.setattr(wr, 'emit_event', _ee)
    monkeypatch.setattr(wr, 'emit_users', _eu)
    monkeypatch.setattr(wr, 'evict_workstream_room_non_members', _evict)
    return log


async def _team(c):
    return (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()


def _team_room_events(log):
    return [e for kind, e, room in log if kind == 'room' and str(room).startswith('workos:team:')]


@pytest.mark.asyncio
async def test_restricted_workspace_crud_never_hits_team_room(monkeypatch):
    log = _record(monkeypatch)
    async with _client(monkeypatch, user=U1) as c:
        team = await _team(c)
        ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                           json={'name': 'Secret', 'visibility': 'restricted'})).json()
        s = (await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'P'})).json()
        await c.patch(f"/api/v1/workos/workstreams/{s['id']}", json={'name': 'P2'})
        await c.patch(f"/api/v1/workos/workspaces/{ws['id']}", json={'name': 'Secret2'})
        await c.delete(f"/api/v1/workos/workstreams/{s['id']}")
        await c.delete(f"/api/v1/workos/workspaces/{ws['id']}")
    assert _team_room_events(log) == []
    # every nav event went to the member (creator was auto-added as ws admin)
    user_events = [(e, ids) for kind, e, ids in log if kind == 'users']
    assert ('workos:workspace.created', ['u1']) in user_events
    assert ('workos:workstream.created', ['u1']) in user_events
    assert ('workos:workstream.updated', ['u1']) in user_events
    assert ('workos:workspace.updated', ['u1']) in user_events
    assert ('workos:workstream.deleted', ['u1']) in user_events
    assert ('workos:workspace.deleted', ['u1']) in user_events


@pytest.mark.asyncio
async def test_team_visible_workspace_still_uses_team_room(monkeypatch):
    log = _record(monkeypatch)
    async with _client(monkeypatch, user=U1) as c:
        team = await _team(c)
        ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                           json={'name': 'Eng', 'visibility': 'team'})).json()
        await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'P'})
    assert _team_room_events(log) == ['workos:workspace.created', 'workos:workstream.created']
    assert [x for x in log if x[0] == 'users'] == []


@pytest.mark.asyncio
async def test_flip_team_to_restricted_sequence_and_eviction(monkeypatch):
    log = _record(monkeypatch)
    async with _client(monkeypatch, user=U1) as c:
        team = await _team(c)
        ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                           json={'name': 'Eng', 'visibility': 'team'})).json()
        s = (await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'P'})).json()
        # u1 (team owner) must be an explicit member to keep seeing it after the flip
        await c.post(f"/api/v1/workos/workspaces/{ws['id']}/members", json={'user_id': 'u1', 'role': 'admin'})
        log.clear()
        r = await c.patch(f"/api/v1/workos/workspaces/{ws['id']}", json={'visibility': 'restricted'})
        assert r.status_code == 200, r.text
    # order is load-bearing: team-room deleted first, then member rebuild, then eviction
    assert log == [
        ('room', 'workos:workspace.deleted', f"workos:team:{team['id']}"),
        ('users', 'workos:workspace.updated', ['u1']),
        ('users', 'workos:workstream.created', ['u1']),
        ('evict', s['id']),
    ]


@pytest.mark.asyncio
async def test_flip_restricted_to_team_broadcasts_subtree(monkeypatch):
    log = _record(monkeypatch)
    async with _client(monkeypatch, user=U1) as c:
        team = await _team(c)
        ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                           json={'name': 'Secret', 'visibility': 'restricted'})).json()
        s = (await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'P'})).json()
        log.clear()
        r = await c.patch(f"/api/v1/workos/workspaces/{ws['id']}", json={'visibility': 'team'})
        assert r.status_code == 200, r.text
    room = f"workos:team:{team['id']}"
    assert log == [
        ('room', 'workos:workspace.updated', room),
        ('room', 'workos:workstream.created', room),
    ]
