"""Membership-revocation eviction: removing a member drops their live sockets
from the rooms that removal makes invisible — and nothing more."""
import pytest

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_teams import _client, U1


def _record_evictions(monkeypatch):
    calls = []

    async def _rec(user_id, rooms):
        calls.append((user_id, list(rooms)))

    monkeypatch.setattr(wr, 'evict_user', _rec)
    return calls


async def _team_with_member(c, *, visibility='team'):
    team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
    await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                       json={'name': 'Eng', 'visibility': visibility})).json()
    s = (await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'P'})).json()
    return team, ws, s


@pytest.mark.asyncio
async def test_team_removal_evicts_team_and_stream_rooms(monkeypatch):
    calls = _record_evictions(monkeypatch)
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _team_with_member(c)
        r = await c.delete(f"/api/v1/workos/teams/{team['id']}/members/u2")
        assert r.json()['removed'] is True
    assert calls == [('u2', [f"workos:team:{team['id']}", f"workos:workstream:{s['id']}"])]


@pytest.mark.asyncio
async def test_team_removal_skips_eviction_for_app_admin_target(monkeypatch):
    calls = _record_evictions(monkeypatch)

    async def _yes(uid, db=None):
        return True

    monkeypatch.setattr(wr, 'is_app_admin', _yes)
    async with _client(monkeypatch, user=U1) as c:
        team, _, _ = await _team_with_member(c)
        r = await c.delete(f"/api/v1/workos/teams/{team['id']}/members/u2")
        assert r.json()['removed'] is True
    assert calls == []


@pytest.mark.asyncio
async def test_restricted_workspace_removal_evicts_stream_rooms_only(monkeypatch):
    calls = _record_evictions(monkeypatch)
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _team_with_member(c, visibility='restricted')
        await c.post(f"/api/v1/workos/workspaces/{ws['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        r = await c.delete(f"/api/v1/workos/workspaces/{ws['id']}/members/u2")
        assert r.json()['removed'] is True
    assert calls == [('u2', [f"workos:workstream:{s['id']}"])]


@pytest.mark.asyncio
async def test_team_visible_workspace_removal_does_not_evict(monkeypatch):
    calls = _record_evictions(monkeypatch)
    async with _client(monkeypatch, user=U1) as c:
        team, ws, _ = await _team_with_member(c, visibility='team')
        await c.post(f"/api/v1/workos/workspaces/{ws['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        r = await c.delete(f"/api/v1/workos/workspaces/{ws['id']}/members/u2")
        assert r.json()['removed'] is True
    assert calls == []


@pytest.mark.asyncio
async def test_failed_removal_does_not_evict(monkeypatch):
    calls = _record_evictions(monkeypatch)
    async with _client(monkeypatch, user=U1) as c:
        team, _, _ = await _team_with_member(c)
        r = await c.delete(f"/api/v1/workos/teams/{team['id']}/members/ghost")
        assert r.json()['removed'] is False
    assert calls == []
