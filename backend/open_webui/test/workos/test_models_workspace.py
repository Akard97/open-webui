import pytest

from open_webui.models.workos import Teams, Workspaces, WorkspaceMembers, Workstreams


@pytest.mark.asyncio
async def test_workspace_crud_and_listing():
    team = await Teams.insert('Acme', 'OSL', None, 'u1')
    ws = await Workspaces.insert(team.id, 'Engineering', 'briefcase', 'team', 'u1')
    assert ws.visibility == 'team'
    assert [w.id for w in await Workspaces.list_for_team(team.id)] == [ws.id]
    ws2 = await Workspaces.update_fields(ws.id, {'name': 'Eng', 'visibility': 'restricted'})
    assert ws2.name == 'Eng' and ws2.visibility == 'restricted'
    assert await Workspaces.delete(ws.id) is True
    assert await Workspaces.get_by_id(ws.id) is None


@pytest.mark.asyncio
async def test_workspace_membership():
    team = await Teams.insert('Acme', 'OSL', None, 'u1')
    ws = await Workspaces.insert(team.id, 'Engineering', None, 'restricted', 'u1')
    await WorkspaceMembers.add(ws.id, 'u2', 'member')
    assert (await WorkspaceMembers.get(ws.id, 'u2')).role == 'member'
    await WorkspaceMembers.update_role(ws.id, 'u2', 'admin')
    assert (await WorkspaceMembers.get(ws.id, 'u2')).role == 'admin'
    assert {m.user_id for m in await WorkspaceMembers.list_for_workspace(ws.id)} == {'u2'}
    assert await WorkspaceMembers.remove(ws.id, 'u2') is True


@pytest.mark.asyncio
async def test_workstream_crud():
    team = await Teams.insert('Acme', 'OSL', None, 'u1')
    ws = await Workspaces.insert(team.id, 'Engineering', None, 'team', 'u1')
    s = await Workstreams.insert(ws.id, 'Platform', 'layers', 'u1')
    assert [x.id for x in await Workstreams.list_for_workspace(ws.id)] == [s.id]
    s2 = await Workstreams.update_fields(s.id, {'name': 'Core'})
    assert s2.name == 'Core'
    assert await Workstreams.delete(s.id) is True
