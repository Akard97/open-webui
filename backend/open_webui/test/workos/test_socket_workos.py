"""Socket-layer tests: workos:subscribe uses the connection's established
session identity (never a payload token), and the eviction helpers leave the
right rooms."""
import pytest

from open_webui.models.workos import Teams, TeamMembers, Workspaces, Workstreams


async def _tree():
    team = await Teams.insert('Acme', 'OSL', None, 'u1')
    await TeamMembers.add(team.id, 'u1', 'owner')
    ws = await Workspaces.insert(team.id, 'Eng', None, 'team', 'u1')
    stream = await Workstreams.insert(ws.id, 'Platform', None, 'u1')
    return team, ws, stream


def _patch_rooms(monkeypatch, sm):
    joined, left = [], []

    async def _enter(sid, room):
        joined.append((sid, room))

    async def _leave(sid, room):
        left.append((sid, room))

    monkeypatch.setattr(sm.sio, 'enter_room', _enter)
    monkeypatch.setattr(sm.sio, 'leave_room', _leave)
    return joined, left


@pytest.mark.asyncio
async def test_subscribe_without_session_joins_nothing_even_with_token(monkeypatch):
    import open_webui.socket.main as sm

    team, _, stream = await _tree()
    joined, _ = _patch_rooms(monkeypatch, sm)
    monkeypatch.setattr(sm, 'SESSION_POOL', {})
    # A payload token must be ignored: no established session -> fail closed.
    await sm.workos_subscribe('sid1', {'auth': {'token': 'whatever'}, 'team_id': team.id,
                                       'workstream_id': stream.id})
    assert joined == []


@pytest.mark.asyncio
async def test_subscribe_uses_session_identity(monkeypatch):
    import open_webui.socket.main as sm

    team, _, stream = await _tree()
    joined, _ = _patch_rooms(monkeypatch, sm)
    monkeypatch.setattr(sm, 'SESSION_POOL', {'sid1': {'id': 'u1', 'role': 'user'}})
    await sm.workos_subscribe('sid1', {'team_id': team.id, 'workstream_id': stream.id})
    assert ('sid1', f'workos:team:{team.id}') in joined
    assert ('sid1', f'workos:workstream:{stream.id}') in joined


@pytest.mark.asyncio
async def test_subscribe_non_member_joins_nothing(monkeypatch):
    import open_webui.socket.main as sm

    team, _, stream = await _tree()
    joined, _ = _patch_rooms(monkeypatch, sm)
    monkeypatch.setattr(sm, 'SESSION_POOL', {'sid2': {'id': 'u2', 'role': 'user'}})
    await sm.workos_subscribe('sid2', {'team_id': team.id, 'workstream_id': stream.id})
    assert joined == []


@pytest.mark.asyncio
async def test_workos_leave_rooms_hits_every_sid_and_room(monkeypatch):
    import open_webui.socket.main as sm

    _, left = _patch_rooms(monkeypatch, sm)
    monkeypatch.setattr(sm, 'get_session_ids_from_room', lambda room: ['sidA', 'sidB'])
    await sm.workos_leave_rooms('u2', ['workos:team:t1', 'workos:workstream:s1'])
    assert set(left) == {
        ('sidA', 'workos:team:t1'), ('sidA', 'workos:workstream:s1'),
        ('sidB', 'workos:team:t1'), ('sidB', 'workos:workstream:s1'),
    }


@pytest.mark.asyncio
async def test_evict_room_non_members_kicks_only_invisible_sockets(monkeypatch):
    import open_webui.socket.main as sm

    team, _, stream = await _tree()  # u1 is a team member; workspace is team-visible
    _, left = _patch_rooms(monkeypatch, sm)
    room = f'workos:workstream:{stream.id}'
    monkeypatch.setattr(sm, 'get_session_ids_from_room', lambda r: ['sid1', 'sid2', 'sid3'])
    monkeypatch.setattr(sm, 'SESSION_POOL', {
        'sid1': {'id': 'u1', 'role': 'user'},  # member -> stays
        'sid2': {'id': 'u9', 'role': 'user'},  # non-member -> evicted
        # sid3 has no session -> evicted
    })
    await sm.workos_evict_room_non_members(stream.id)
    assert set(left) == {('sid2', room), ('sid3', room)}
