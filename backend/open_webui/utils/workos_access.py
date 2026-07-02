"""WorkOS access-control policy module.

Single source of truth for who can see and do what in the WorkOS
Team → Workspace → Workstream → Task containment tree. Keep
docs/superpowers/specs/2026-06-26-workos-access-control.md in sync with
any change here.

Two families of callables:

- Pure predicates (``can_see_*``, ``is_*``) return bools and never raise.
  They are safe outside the request path (notification fan-out, socket
  room joins).
- ``require_*`` wrappers are the request-path twins: they raise
  HTTPException — 404 when a row is missing OR invisible (so non-members
  cannot distinguish "doesn't exist" from "you can't see it"), 403 for
  role/write failures.

App-level admins (``user.role == 'admin'``) are super-users across all
teams and workspaces, including restricted ones. A *team* owner/admin role
grants no bypass of a restricted-workspace gate.
"""

from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.models.workos import (
    Teams, TeamMembers, Workspaces, WorkspaceMembers, Workstreams,
    Tasks, Subtasks, TeamModel,
    TEAM_ROLES, WORKSPACE_ROLES,  # re-exported: policy callers import role sets from here
)
from open_webui.models.users import Users
from open_webui.utils.access_control import has_permission


# ──────────────────────────────── feature gates ────────────────────────────────


async def require_workos(request: Request, user, db: AsyncSession) -> None:
    if user.role != 'admin' and not await has_permission(
        user.id, 'features.workos', request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='WorkOS access required.')


async def require_workos_admin(request: Request, user, db: AsyncSession) -> None:
    if user.role != 'admin' and not await has_permission(
        user.id, 'features.workos_admin', request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='WorkOS admin required.')


# ──────────────────────────────── pure predicates ────────────────────────────────


async def can_see_team(user_id: str, is_admin: bool, team_id: str, db: Optional[AsyncSession] = None) -> bool:
    if is_admin:
        return (await Teams.get_by_id(team_id, db=db)) is not None
    return (await TeamMembers.get(team_id, user_id, db=db)) is not None


async def can_see_workspace(user_id: str, is_admin: bool, workspace, db: Optional[AsyncSession] = None) -> bool:
    """Canonical workspace visibility: team gate first, then the per-workspace switch.

    Note the admin branch still requires the parent team row to exist (an
    app-admin cannot see a workspace orphaned by a deleted team).
    """
    if not await can_see_team(user_id, is_admin, workspace.team_id, db=db):
        return False
    if workspace.visibility == 'team' or is_admin:
        return True
    return (await WorkspaceMembers.get(workspace.id, user_id, db=db)) is not None


async def can_see_workstream(
    user_id: str, is_admin: bool, workstream_id: str, db: Optional[AsyncSession] = None
) -> bool:
    stream = await Workstreams.get_by_id(workstream_id, db=db)
    if not stream:
        return False
    ws = await Workspaces.get_by_id(stream.workspace_id, db=db)
    if not ws:
        return False
    return await can_see_workspace(user_id, is_admin, ws, db=db)


async def team_role(user, team_id: str, db: AsyncSession) -> Optional[str]:
    if user.role == 'admin':
        return 'admin'
    m = await TeamMembers.get(team_id, user.id, db=db)
    return m.role if m else None


async def is_workspace_manager(user, workspace, db: AsyncSession) -> bool:
    if (await team_role(user, workspace.team_id, db)) in {'owner', 'admin'}:
        return True
    wm = await WorkspaceMembers.get(workspace.id, user.id, db=db)
    return bool(wm and wm.role == 'admin')


async def is_last_owner(team_id: str, user_id: str, db: AsyncSession) -> bool:
    members = await TeamMembers.list_for_team(team_id, db=db)
    owners = [m for m in members if m.role == 'owner']
    return len(owners) == 1 and owners[0].user_id == user_id


async def is_app_admin(user_id: str, db=None) -> bool:
    u = await Users.get_user_by_id(user_id, db=db)
    return bool(u and u.role == 'admin')


# ──────────────────────────────── visibility wrappers ────────────────────────────────


async def require_team_visible(user, team_id: str, db: AsyncSession) -> TeamModel:
    team = await Teams.get_by_id(team_id, db=db)
    if not team or await team_role(user, team_id, db) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Team not found.')
    return team


async def require_team_role(user, team_id: str, db: AsyncSession, allowed: set) -> TeamModel:
    team = await require_team_visible(user, team_id, db)
    if user.role == 'admin':
        return team
    if (await team_role(user, team_id, db)) not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Insufficient role.')
    return team


async def require_workspace_visible(user, workspace_id: str, db: AsyncSession):
    ws = await Workspaces.get_by_id(workspace_id, db=db)
    if not ws or not await can_see_workspace(user.id, user.role == 'admin', ws, db=db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Workspace not found.')
    return ws


async def require_workspace_manage(user, workspace_id: str, db: AsyncSession):
    ws = await require_workspace_visible(user, workspace_id, db)
    if await is_workspace_manager(user, ws, db):
        return ws
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Workspace management requires admin.')


async def require_workstream_visible(user, workstream_id: str, db: AsyncSession):
    stream = await Workstreams.get_by_id(workstream_id, db=db)
    if not stream:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Workstream not found.')
    ws = await require_workspace_visible(user, stream.workspace_id, db)
    return stream, ws


async def require_task_visible(user, task_id: str, db: AsyncSession):
    task = await Tasks.get_by_id(task_id, db=db)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Task not found.')
    stream, _ = await require_workstream_visible(user, task.workstream_id, db)
    return task, stream


async def require_subtask_visible(user, subtask_id: str, db: AsyncSession):
    subtask = await Subtasks.get_by_id(subtask_id, db=db)
    if not subtask:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Subtask not found.')
    task, stream = await require_task_visible(user, subtask.task_id, db)
    return subtask, task, stream


# ──────────────────────────────── write gates ────────────────────────────────


async def require_task_writable(user, task, stream, db: AsyncSession) -> None:
    if user.role == 'admin':
        return
    if task.created_by_id == user.id:
        return
    if user.id in (task.assignee_ids or []):
        return
    ws = await Workspaces.get_by_id(stream.workspace_id, db=db)
    if await is_workspace_manager(user, ws, db):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                        detail='You do not have permission to edit this task.')


async def require_subtask_writable(user, subtask, task, stream, db: AsyncSession) -> None:
    if user.role == 'admin':
        return
    if subtask.created_by_id == user.id:
        return
    if task.created_by_id == user.id or user.id in (task.assignee_ids or []):
        return
    ws = await Workspaces.get_by_id(stream.workspace_id, db=db)
    if await is_workspace_manager(user, ws, db):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                        detail='You do not have permission to modify this subtask.')


# ──────────────────────────────── input validation ────────────────────────────────


async def validate_assignees(assignee_ids, workstream_id, db):
    for uid in assignee_ids or []:
        if not await can_see_workstream(uid, await is_app_admin(uid, db), workstream_id, db=db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='One or more assignees cannot access this workstream.',
            )
