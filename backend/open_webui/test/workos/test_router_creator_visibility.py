"""Workspace creators keep visibility into their own restricted workspaces even
without a member row (2026-07-02 rule) — but only while they pass the team gate."""
import pytest

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_teams import _client, U1, U2


async def _team_ws(c, *, visibility='team'):
    team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
    ws = (await c.post(
        f"/api/v1/workos/teams/{team['id']}/workspaces", json={'name': 'Eng', 'visibility': visibility}
    )).json()
    return team, ws


@pytest.mark.asyncio
async def test_creator_still_sees_workspace_after_restricted_flip(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws = await _team_ws(c)
        # u2 becomes a team admin and flips the workspace to restricted; u1
        # (creator) is NOT an explicit workspace member.
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'admin'})
    async with _client(monkeypatch, user=U2) as c:
        r = await c.patch(f"/api/v1/workos/workspaces/{ws['id']}", json={'visibility': 'restricted'})
        assert r.status_code == 200

    async with _client(monkeypatch, user=U1) as c:
        assert (await c.get(f"/api/v1/workos/workspaces/{ws['id']}")).status_code == 200
        listed = (await c.get(f"/api/v1/workos/teams/{team['id']}/workspaces")).json()
        assert [w['id'] for w in listed] == [ws['id']]
        rows = (await c.get('/api/v1/workos/access/overview')).json()
        row = next(x for x in rows if x['team']['id'] == team['id'])
        assert [w['id'] for w in row['workspaces']] == [ws['id']]

    # u2 flipped it but is neither creator nor explicit member -> loses sight of it
    async with _client(monkeypatch, user=U2) as c:
        assert (await c.get(f"/api/v1/workos/workspaces/{ws['id']}")).status_code == 404


@pytest.mark.asyncio
async def test_creator_not_evicted_when_removed_as_workspace_member(monkeypatch):
    evictions = []

    async def _evict(user_id, rooms):
        evictions.append((user_id, rooms))

    monkeypatch.setattr(wr, 'evict_user', _evict)
    async with _client(monkeypatch, user=U1) as c:
        team, ws = await _team_ws(c, visibility='restricted')  # creator auto-added as ws admin
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        await c.post(f"/api/v1/workos/workspaces/{ws['id']}/members", json={'user_id': 'u2', 'role': 'member'})

        # Removing the creator's member row must not evict them (creator rule)...
        r = await c.delete(f"/api/v1/workos/workspaces/{ws['id']}/members/u1")
        assert r.json()['removed'] is True
        assert evictions == []
        # ...and they can still open the workspace.
        assert (await c.get(f"/api/v1/workos/workspaces/{ws['id']}")).status_code == 200

        # Removing a plain member still evicts.
        r = await c.delete(f"/api/v1/workos/workspaces/{ws['id']}/members/u2")
        assert r.json()['removed'] is True
        assert [uid for uid, _ in evictions] == ['u2']


@pytest.mark.asyncio
async def test_restricted_nav_events_reach_creator_without_member_row(monkeypatch):
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

    async with _client(monkeypatch, user=U1) as c:
        team, ws = await _team_ws(c)  # team-visible, u1 = creator
        s = (await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'P'})).json()
        log.clear()
        # Flip to restricted with NO explicit members: the rebuild fan-out must
        # still include the creator.
        r = await c.patch(f"/api/v1/workos/workspaces/{ws['id']}", json={'visibility': 'restricted'})
        assert r.status_code == 200
    assert log == [
        ('room', 'workos:workspace.deleted', f"workos:team:{team['id']}"),
        ('users', 'workos:workspace.updated', ['u1']),
        ('users', 'workos:workstream.created', ['u1']),
        ('evict', s['id']),
    ]
