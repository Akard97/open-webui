"""Direct unit tests for the access-policy module (utils/workos_access).

Pins the predicate matrix and the exact HTTPException status/detail strings
the frontend may rely on.
"""
import pytest
from types import SimpleNamespace

from fastapi import HTTPException

import open_webui.utils.workos_access as wa
from open_webui.models.workos import Teams, TeamMembers, Workspaces, WorkspaceMembers, Workstreams, Tasks, Subtasks


def _user(uid, role='user'):
    return SimpleNamespace(id=uid, role=role)


async def _tree(visibility='team'):
    team = await Teams.insert('Acme', 'OSL', None, 'u1')
    await TeamMembers.add(team.id, 'u1', 'owner')
    ws = await Workspaces.insert(team.id, 'Eng', None, visibility, 'u1')
    stream = await Workstreams.insert(ws.id, 'Platform', None, 'u1')
    return team, ws, stream


@pytest.mark.asyncio
async def test_can_see_workspace_matrix():
    team, ws, _ = await _tree('team')
    await TeamMembers.add(team.id, 'u2', 'member')
    # team-visible: any team member; outsiders never; app-admin yes.
    assert await wa.can_see_workspace('u1', False, ws) is True
    assert await wa.can_see_workspace('u2', False, ws) is True
    assert await wa.can_see_workspace('u3', False, ws) is False
    assert await wa.can_see_workspace('u3', True, ws) is True

    rws = await Workspaces.insert(team.id, 'Secret', None, 'restricted', 'u1')
    await WorkspaceMembers.add(rws.id, 'u2', 'member')
    # restricted: explicit workspace members only (+ app-admin); a plain team member is out.
    assert await wa.can_see_workspace('u2', False, rws) is True
    assert await wa.can_see_workspace('u1', False, rws) is False
    assert await wa.can_see_workspace('u1', True, rws) is True
    # non-team-member workspace member row alone is not enough (team gate first).
    await WorkspaceMembers.add(rws.id, 'u9', 'member')
    assert await wa.can_see_workspace('u9', False, rws) is False


@pytest.mark.asyncio
async def test_can_see_workspace_orphaned_team_blocks_admin():
    # An app-admin cannot see a workspace whose parent team row is gone.
    team, ws, stream = await _tree('team')
    await Teams.delete(team.id)
    assert await wa.can_see_workspace('u9', True, ws) is False
    assert await wa.can_see_workstream('u9', True, stream.id) is False


@pytest.mark.asyncio
async def test_is_workspace_manager():
    team, _, _ = await _tree('team')
    await TeamMembers.add(team.id, 'u2', 'member')
    rws = await Workspaces.insert(team.id, 'Secret', None, 'restricted', 'u1')
    await WorkspaceMembers.add(rws.id, 'u2', 'admin')
    await WorkspaceMembers.add(rws.id, 'u3', 'member')
    assert await wa.is_workspace_manager(_user('u1'), rws, None) is True   # team owner
    assert await wa.is_workspace_manager(_user('u2'), rws, None) is True   # workspace admin
    assert await wa.is_workspace_manager(_user('u3'), rws, None) is False  # workspace member


@pytest.mark.asyncio
async def test_is_last_owner():
    team, _, _ = await _tree('team')
    await TeamMembers.add(team.id, 'u2', 'member')
    assert await wa.is_last_owner(team.id, 'u1', None) is True
    assert await wa.is_last_owner(team.id, 'u2', None) is False
    await TeamMembers.add(team.id, 'u3', 'owner')
    assert await wa.is_last_owner(team.id, 'u1', None) is False


async def _detail(coro):
    with pytest.raises(HTTPException) as exc:
        await coro
    return exc.value.status_code, exc.value.detail


@pytest.mark.asyncio
async def test_require_visible_404_details():
    outsider = _user('u9')
    assert await _detail(wa.require_team_visible(outsider, 'missing', None)) == (404, 'Team not found.')
    assert await _detail(wa.require_workspace_visible(outsider, 'missing', None)) == (404, 'Workspace not found.')
    assert await _detail(wa.require_workstream_visible(outsider, 'missing', None)) == (404, 'Workstream not found.')
    assert await _detail(wa.require_task_visible(outsider, 'missing', None)) == (404, 'Task not found.')
    assert await _detail(wa.require_subtask_visible(outsider, 'missing', None)) == (404, 'Subtask not found.')

    # Existing-but-invisible is also a 404 (never a 403).
    team, ws, stream = await _tree('team')
    assert await _detail(wa.require_team_visible(outsider, team.id, None)) == (404, 'Team not found.')
    assert await _detail(wa.require_workspace_visible(outsider, ws.id, None)) == (404, 'Workspace not found.')
    # An existing-but-invisible workstream 404s at the parent workspace gate.
    assert await _detail(wa.require_workstream_visible(outsider, stream.id, None)) == (404, 'Workspace not found.')


@pytest.mark.asyncio
async def test_require_role_and_manage_403_details():
    team, ws, _ = await _tree('team')
    await TeamMembers.add(team.id, 'u2', 'member')
    member = _user('u2')
    assert await _detail(wa.require_team_role(member, team.id, None, {'owner', 'admin'})) == (403, 'Insufficient role.')
    assert await _detail(wa.require_workspace_manage(member, ws.id, None)) == (
        403, 'Workspace management requires admin.')


@pytest.mark.asyncio
async def test_write_gate_403_details():
    team, ws, stream = await _tree('team')
    await TeamMembers.add(team.id, 'u2', 'member')
    task = await Tasks.insert(stream.id, team.id, team.key, 'T', 'u1')
    subtask = await Subtasks.insert(task.id, 'S', 'u1')
    member = _user('u2')
    assert await _detail(wa.require_task_writable(member, task, stream, None)) == (
        403, 'You do not have permission to edit this task.')
    assert await _detail(wa.require_subtask_writable(member, subtask, task, stream, None)) == (
        403, 'You do not have permission to modify this subtask.')
    # creator, assignee, app-admin all pass
    assert await wa.require_task_writable(_user('u1'), task, stream, None) is None
    assert await wa.require_subtask_writable(_user('u1'), subtask, task, stream, None) is None
    assert await wa.require_task_writable(_user('u9', role='admin'), task, stream, None) is None


@pytest.mark.asyncio
async def test_validate_assignees_rejects_invisible(monkeypatch):
    team, ws, stream = await _tree('team')

    async def _not_admin(uid, db=None):
        return False

    monkeypatch.setattr(wa, 'is_app_admin', _not_admin)
    code, detail = await _detail(wa.validate_assignees(['u2'], stream.id, None))
    assert (code, detail) == (400, 'One or more assignees cannot access this workstream.')
    await TeamMembers.add(team.id, 'u2', 'member')
    assert await wa.validate_assignees(['u2'], stream.id, None) is None
