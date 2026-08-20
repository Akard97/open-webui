import asyncio
import logging
import time
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.internal.db import get_async_session
from open_webui.utils.auth import get_verified_user
from open_webui.storage.provider import Storage
from open_webui.models.workos import (
    Teams, TeamMembers, Workspaces, WorkspaceMembers, Workstreams,
    Labels, Tasks, Comments, Reactions, Activity, Attachments, Notifications, Subtasks,
    TeamModel, WorkspaceModel, WorkstreamModel, TaskModel, LabelModel,
    CommentModel, ActivityModel, AttachmentModel, NotificationModel,
    parse_mentions, task_change_activities,
)
from open_webui.models.users import Users
from open_webui.models.usage import UsageEvents
from open_webui.utils.workos_access import (
    TEAM_ROLES, WORKSPACE_ROLES,
    require_workos, require_workos_admin,
    can_see_workspace, can_see_workstream, team_role,
    is_last_owner, is_app_admin,
    require_team_visible, require_team_role,
    require_workspace_visible, require_workspace_manage,
    require_workstream_visible, require_task_visible, require_subtask_visible,
    require_task_writable, require_subtask_writable,
    require_capability, require_team_capability,
    validate_assignees,
)

log = logging.getLogger(__name__)


async def emit_event(event: str, room: str, payload: dict) -> None:
    try:
        from open_webui.socket.main import sio

        await sio.emit(event, payload, room=room)
    except Exception as e:  # pragma: no cover - emit is best-effort
        log.debug(f'workos emit failed for {event}: {e}')


async def emit_users(event: str, payload: dict, user_ids: list) -> None:
    try:
        from open_webui.socket.main import emit_to_users

        await emit_to_users(event, payload, user_ids)
    except Exception as e:  # pragma: no cover - emit is best-effort
        log.debug(f'workos emit_to_users failed for {event}: {e}')


async def evict_user(user_id: str, rooms: list) -> None:
    try:
        from open_webui.socket.main import workos_leave_rooms

        await workos_leave_rooms(user_id, rooms)
    except Exception as e:  # pragma: no cover - eviction is best-effort
        log.debug(f'workos eviction failed for {user_id}: {e}')


async def evict_workstream_room_non_members(workstream_id: str) -> None:
    try:
        from open_webui.socket.main import workos_evict_room_non_members

        await workos_evict_room_non_members(workstream_id)
    except Exception as e:  # pragma: no cover - eviction is best-effort
        log.debug(f'workos room eviction failed for {workstream_id}: {e}')


router = APIRouter()


# Access predicates and require_* gates live in open_webui.utils.workos_access —
# the single source of truth for WorkOS visibility/role policy.


# ──────────────────────────────── schemas ────────────────────────────────


class TeamForm(BaseModel):
    name: str
    key: str
    icon: Optional[str] = None


class TeamUpdateForm(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    archived: Optional[bool] = None


class MemberForm(BaseModel):
    user_id: str
    role: str = 'member'


class MemberRoleForm(BaseModel):
    role: str


# ──────────────────────────────── directory ────────────────────────────────


def sanitize_profile_image_url(url) -> str | None:
    # Only genuine custom images travel to the client: uploaded avatars are
    # data: URLs and OAuth pictures are http(s). The '/user.png' default and
    # the per-user '/api/v1/users/{id}/profile/image' placeholder both mean
    # "no upload" — mapped to None so the UI keeps its initials fallback.
    if url and (url.startswith('data:') or url.startswith('http')):
        return url
    return None


async def resolve_user_names(ids: list) -> list:
    # Wrapper around the Users DAO so tests can monkeypatch a fast stub.
    from open_webui.models.users import Users

    out = []
    for uid in ids:
        u = await Users.get_user_by_id(uid)
        if u:
            out.append({
                'id': u.id,
                'name': u.name,
                'profile_image_url': sanitize_profile_image_url(u.profile_image_url),
            })
    return out


async def list_all_users() -> list:
    # Wrapper around the Users DAO so tests can monkeypatch a fast stub.
    from open_webui.models.users import Users

    result = await Users.get_users()
    return [
        {
            'id': u.id,
            'name': u.name,
            'profile_image_url': sanitize_profile_image_url(u.profile_image_url),
        }
        for u in result['users']
    ]


@router.get('/directory')
async def directory(request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)):
    await require_workos(request, user, db)
    teams = await (Teams.list_all(db=db) if user.role == 'admin' else Teams.list_for_user(user.id, db=db))
    ids: set = set()
    for t in teams:
        for m in await TeamMembers.list_for_team(t.id, db=db):
            ids.add(m.user_id)
    ids.add(user.id)
    return await resolve_user_names(sorted(ids))


@router.get('/users')
async def list_users(
    request: Request, team_id: str,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    # Full app roster for the team "Add a user…" picker — gated to the people who
    # can actually add members (team owners/admins, or a global admin).
    await require_workos(request, user, db)
    await require_team_role(user, team_id, db, {'owner', 'admin'})
    return await list_all_users()


# ──────────────────────────────── bootstrap ────────────────────────────────


async def visible_tree(user, db):
    """Teams the user belongs to (all teams for an app admin) plus every
    workspace/workstream they can see. Shared read model for /bootstrap and
    the internal on-behalf-of API (routers/workos_internal.py)."""
    is_admin = user.role == 'admin'
    teams = await (Teams.list_all(db=db) if is_admin else Teams.list_for_user(user.id, db=db))
    workspaces = []
    workstreams = []
    for t in teams:
        for w in await Workspaces.list_for_team(t.id, db=db):
            if await can_see_workspace(user.id, is_admin, w, db=db):
                workspaces.append(w)
                workstreams.extend(await Workstreams.list_for_workspace(w.id, db=db))
    return teams, workspaces, workstreams


async def visible_my_tasks(user, db):
    """The user's created/assigned tasks, filtered to visible workstreams.
    Shared by GET /me/tasks and the internal on-behalf-of API."""
    is_admin = user.role == 'admin'
    teams = await Teams.list_all(db=db) if is_admin else await Teams.list_for_user(user.id, db=db)
    candidates = await Tasks.list_for_user(user.id, [t.id for t in teams], db=db)
    return [
        t for t in candidates
        if await can_see_workstream(user.id, is_admin, t.workstream_id, db=db)
    ]


@router.get('/bootstrap')
async def bootstrap(request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)):
    await require_workos(request, user, db)
    teams, workspaces, workstreams = await visible_tree(user, db)
    roles: dict = {}
    for t in teams:
        roles[t.id] = await team_role(user, t.id, db)
    return {
        'teams': teams, 'workspaces': workspaces, 'workstreams': workstreams, 'roles': roles,
        'notifications_unread': await Notifications.unread_count(user.id, db=db),
    }


# ──────────────────────────────── teams ────────────────────────────────


@router.get('/teams')
async def list_teams(request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)):
    await require_workos(request, user, db)
    return await (Teams.list_all(db=db) if user.role == 'admin' else Teams.list_for_user(user.id, db=db))


@router.post('/teams')
async def create_team(
    request: Request, form: TeamForm, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    rules = request.app.state.config.WORKOS_RULES or {}
    if rules.get('team_creation') == 'admins_only' and user.role != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Team creation is restricted to admins.')
    key = form.key.strip().upper()
    if not key or await Teams.get_by_key(key, db=db):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Team key missing or already in use.')
    team = await Teams.insert(name=form.name, key=key, icon=form.icon, created_by_id=user.id, db=db)
    await TeamMembers.add(team.id, user.id, 'owner', db=db)
    return team


@router.get('/teams/{team_id}')
async def get_team(
    request: Request, team_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    return await require_team_visible(user, team_id, db)


@router.patch('/teams/{team_id}')
async def update_team(
    request: Request, team_id: str, form: TeamUpdateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    await require_team_role(user, team_id, db, {'owner'})
    fields = {k: v for k, v in form.model_dump(exclude_none=True).items()}
    return await Teams.update_fields(team_id, fields, db=db)


@router.delete('/teams/{team_id}')
async def delete_team(
    request: Request, team_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    await require_team_role(user, team_id, db, {'owner'})
    return {'deleted': await Teams.delete(team_id, db=db)}


@router.get('/teams/{team_id}/members')
async def list_members(
    request: Request, team_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    await require_team_visible(user, team_id, db)
    return await TeamMembers.list_for_team(team_id, db=db)


@router.post('/teams/{team_id}/members')
async def add_member(
    request: Request, team_id: str, form: MemberForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    await require_team_role(user, team_id, db, {'owner', 'admin'})
    if form.role not in TEAM_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid role.')
    if await TeamMembers.get(team_id, form.user_id, db=db):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Already a member.')
    member = await TeamMembers.add(team_id, form.user_id, form.role, db=db)
    await UsageEvents.emit(user.id, 'workos.team.member_add', {'team_id': team_id, 'member_id': form.user_id, 'role': form.role})
    return member


@router.patch('/teams/{team_id}/members/{user_id}')
async def update_member(
    request: Request, team_id: str, user_id: str, form: MemberRoleForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    # Only owners may grant/revoke owner or admin; admins may manage members.
    await require_team_capability(
        user, team_id, db,
        'team.members.grant_privileged' if form.role in {'owner', 'admin'} else 'team.members.manage',
    )
    if form.role not in TEAM_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid role.')
    if form.role != 'owner' and await is_last_owner(team_id, user_id, db):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Cannot demote the last team owner.')
    updated = await TeamMembers.update_role(team_id, user_id, form.role, db=db)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Member not found.')
    return updated


@router.delete('/teams/{team_id}/members/{user_id}')
async def remove_member(
    request: Request, team_id: str, user_id: str,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    await require_team_role(user, team_id, db, {'owner', 'admin'})
    if await is_last_owner(team_id, user_id, db):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Cannot remove the last team owner.')
    removed = await TeamMembers.remove(team_id, user_id, db=db)
    if removed:
        await UsageEvents.emit(user.id, 'workos.team.member_remove', {'team_id': team_id, 'member_id': user_id})
    # Revocation eviction: drop the ex-member's live sockets from every room
    # under this team (app-admins retain access, so leave theirs alone).
    if removed and not await is_app_admin(user_id, db):
        rooms = [f'workos:team:{team_id}']
        for w in await Workspaces.list_for_team(team_id, db=db):
            rooms.extend(f'workos:workstream:{s.id}' for s in await Workstreams.list_for_workspace(w.id, db=db))
        await evict_user(user_id, rooms)
    return {'removed': removed}


# ──────────────────────────────── workspace schemas ────────────────────────────────


class WorkspaceForm(BaseModel):
    name: str
    icon: Optional[str] = None
    visibility: Optional[str] = None


class WorkspaceUpdateForm(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    visibility: Optional[str] = None
    archived: Optional[bool] = None


# ──────────────────────────────── workspace endpoints ────────────────────────────────


def _with_creator(ws, member_ids: list) -> list:
    """Restricted-workspace recipient set: explicit members plus the creator,
    who retains visibility without a member row (see can_see_workspace)."""
    ids = set(member_ids)
    if ws.created_by_id:
        ids.add(ws.created_by_id)
    return sorted(ids)


async def _emit_nav_event(event: str, ws, payload: dict, db, member_ids: Optional[list] = None) -> None:
    """Route a workspace/workstream nav event by the workspace's visibility:
    team-visible -> the team-wide room; restricted -> each member's (and the
    creator's) user room, so plain team members never receive restricted
    names/metadata."""
    if ws.visibility == 'team':
        await emit_event(event, f'workos:team:{ws.team_id}', payload)
        return
    if member_ids is None:
        member_ids = [m.user_id for m in await WorkspaceMembers.list_for_workspace(ws.id, db=db)]
    await emit_users(event, payload, _with_creator(ws, member_ids))


async def _emit_workspace_updated(before, updated, db) -> None:
    """Visibility-aware routing for workspace.updated, including the flips.

    team -> restricted: team-room clients get a deleted event (they drop the
    workspace and its child workstreams), then members rebuild the subtree
    from user-room events — emission order is load-bearing. Finally, sockets
    that can no longer see the child workstreams are evicted from those rooms.
    restricted -> team: the whole team gains the subtree, so it gets the full
    update plus workstream.created events in the team room.
    """
    if before.visibility == 'team' and updated.visibility == 'restricted':
        await emit_event('workos:workspace.deleted', f'workos:team:{updated.team_id}', {'id': updated.id})
        member_ids = _with_creator(
            updated, [m.user_id for m in await WorkspaceMembers.list_for_workspace(updated.id, db=db)]
        )
        streams = await Workstreams.list_for_workspace(updated.id, db=db)
        await emit_users('workos:workspace.updated', updated.model_dump(), member_ids)
        for s in streams:
            await emit_users('workos:workstream.created', s.model_dump(), member_ids)
        for s in streams:
            await evict_workstream_room_non_members(s.id)
    elif before.visibility == 'restricted' and updated.visibility == 'team':
        await emit_event('workos:workspace.updated', f'workos:team:{updated.team_id}', updated.model_dump())
        for s in await Workstreams.list_for_workspace(updated.id, db=db):
            await emit_event('workos:workstream.created', f'workos:team:{updated.team_id}', s.model_dump())
    else:
        await _emit_nav_event('workos:workspace.updated', updated, updated.model_dump(), db)


@router.get('/teams/{team_id}/workspaces')
async def list_workspaces(
    request: Request, team_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    await require_team_visible(user, team_id, db)
    out = []
    for ws in await Workspaces.list_for_team(team_id, db=db):
        if await can_see_workspace(user.id, user.role == 'admin', ws, db=db):
            out.append(ws)
    return out


@router.post('/teams/{team_id}/workspaces')
async def create_workspace(
    request: Request, team_id: str, form: WorkspaceForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    await require_team_role(user, team_id, db, {'owner', 'admin'})
    rules = request.app.state.config.WORKOS_RULES or {}
    visibility = form.visibility or rules.get('default_workspace_visibility') or 'team'
    if visibility not in {'team', 'restricted'}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid visibility.')
    ws = await Workspaces.insert(team_id, form.name, form.icon, visibility, user.id, db=db)
    if visibility == 'restricted':
        await WorkspaceMembers.add(ws.id, user.id, 'admin', db=db)
    await _emit_nav_event('workos:workspace.created', ws, ws.model_dump(), db)
    return ws


@router.get('/workspaces/{workspace_id}')
async def get_workspace(
    request: Request, workspace_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    return await require_workspace_visible(user, workspace_id, db)


@router.patch('/workspaces/{workspace_id}')
async def update_workspace(
    request: Request, workspace_id: str, form: WorkspaceUpdateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    before = await require_workspace_manage(user, workspace_id, db)
    fields = form.model_dump(exclude_none=True)
    if 'visibility' in fields and fields['visibility'] not in {'team', 'restricted'}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid visibility.')
    updated = await Workspaces.update_fields(workspace_id, fields, db=db)
    if before.visibility != updated.visibility:
        await UsageEvents.emit(user.id, 'workos.workspace.visibility_change',
                               {'workspace_id': workspace_id, 'from': before.visibility, 'to': updated.visibility})
    await _emit_workspace_updated(before, updated, db)
    return updated


@router.delete('/workspaces/{workspace_id}')
async def delete_workspace(
    request: Request, workspace_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    ws = await require_workspace_visible(user, workspace_id, db)
    await require_team_capability(user, ws.team_id, db, 'workspace.delete')
    # Capture the restricted-member list before the delete, then emit after it.
    member_ids = None
    if ws.visibility == 'restricted':
        member_ids = [m.user_id for m in await WorkspaceMembers.list_for_workspace(workspace_id, db=db)]
    deleted = await Workspaces.delete(workspace_id, db=db)
    await _emit_nav_event('workos:workspace.deleted', ws, {'id': workspace_id}, db, member_ids=member_ids)
    return {'deleted': deleted}


# ──────────────────────────────── workspace member endpoints ────────────────────────────────


@router.get('/workspaces/{workspace_id}/members')
async def list_workspace_members(
    request: Request, workspace_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    await require_workspace_visible(user, workspace_id, db)
    return await WorkspaceMembers.list_for_workspace(workspace_id, db=db)


@router.post('/workspaces/{workspace_id}/members')
async def add_workspace_member(
    request: Request, workspace_id: str, form: MemberForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    await require_workspace_manage(user, workspace_id, db)
    if form.role not in WORKSPACE_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid role.')
    if await WorkspaceMembers.get(workspace_id, form.user_id, db=db):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Already a member.')
    member = await WorkspaceMembers.add(workspace_id, form.user_id, form.role, db=db)
    await UsageEvents.emit(user.id, 'workos.workspace.member_add', {'workspace_id': workspace_id, 'member_id': form.user_id})
    return member


@router.patch('/workspaces/{workspace_id}/members/{user_id}')
async def update_workspace_member(
    request: Request, workspace_id: str, user_id: str, form: MemberRoleForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    await require_workspace_manage(user, workspace_id, db)
    if form.role not in WORKSPACE_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid role.')
    updated = await WorkspaceMembers.update_role(workspace_id, user_id, form.role, db=db)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Member not found.')
    return updated


@router.delete('/workspaces/{workspace_id}/members/{user_id}')
async def remove_workspace_member(
    request: Request, workspace_id: str, user_id: str,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    ws = await require_workspace_manage(user, workspace_id, db)
    removed = await WorkspaceMembers.remove(workspace_id, user_id, db=db)
    if removed:
        await UsageEvents.emit(user.id, 'workos.workspace.member_remove', {'workspace_id': workspace_id, 'member_id': user_id})
    # Removal from a restricted workspace revokes visibility -> evict from its
    # workstream rooms (not the team room — the user is still a team member).
    # Removal from a team-visible workspace revokes nothing. The creator and
    # app-admins keep visibility without a member row, so they are never evicted.
    if removed and ws.visibility == 'restricted' and user_id != ws.created_by_id and not await is_app_admin(user_id, db):
        rooms = [f'workos:workstream:{s.id}' for s in await Workstreams.list_for_workspace(workspace_id, db=db)]
        await evict_user(user_id, rooms)
    return {'removed': removed}


# ──────────────────────────────── workstream schemas ────────────────────────────────


class WorkstreamForm(BaseModel):
    name: str
    icon: Optional[str] = None


class WorkstreamUpdateForm(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    archived: Optional[bool] = None


# ──────────────────────────────── workstream endpoints ────────────────────────────────


@router.get('/workspaces/{workspace_id}/workstreams')
async def list_workstreams(
    request: Request, workspace_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    await require_workspace_visible(user, workspace_id, db)
    return await Workstreams.list_for_workspace(workspace_id, db=db)


@router.post('/workspaces/{workspace_id}/workstreams')
async def create_workstream(
    request: Request, workspace_id: str, form: WorkstreamForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    await require_workspace_manage(user, workspace_id, db)
    stream = await Workstreams.insert(workspace_id, form.name, form.icon, user.id, db=db)
    ws_row = await Workspaces.get_by_id(workspace_id, db=db)
    await _emit_nav_event('workos:workstream.created', ws_row, stream.model_dump(), db)
    return stream


@router.patch('/workstreams/{workstream_id}')
async def update_workstream(
    request: Request, workstream_id: str, form: WorkstreamUpdateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    stream, _ = await require_workstream_visible(user, workstream_id, db)
    await require_workspace_manage(user, stream.workspace_id, db)
    updated = await Workstreams.update_fields(workstream_id, form.model_dump(exclude_none=True), db=db)
    ws_row = await Workspaces.get_by_id(stream.workspace_id, db=db)
    await _emit_nav_event('workos:workstream.updated', ws_row, updated.model_dump(), db)
    return updated


@router.delete('/workstreams/{workstream_id}')
async def delete_workstream(
    request: Request, workstream_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    stream, _ = await require_workstream_visible(user, workstream_id, db)
    await require_workspace_manage(user, stream.workspace_id, db)
    deleted = await Workstreams.delete(workstream_id, db=db)
    ws_row = await Workspaces.get_by_id(stream.workspace_id, db=db)
    await _emit_nav_event('workos:workstream.deleted', ws_row,
                          {'id': workstream_id, 'workspace_id': stream.workspace_id}, db)
    return {'deleted': deleted}


# ──────────────────────────────── task + label constants ────────────────────────────────


STATUSES = {'backlog', 'todo', 'in_progress', 'in_review', 'done', 'canceled'}
PRIORITIES = {'urgent', 'high', 'medium', 'low'}


# ──────────────────────────────── task + label schemas ────────────────────────────────


class TaskCreateForm(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = 'backlog'
    priority: Optional[str] = None
    assignee_ids: Optional[list[str]] = None
    start_date: Optional[int] = None
    due_date: Optional[int] = None
    labels: Optional[list] = None
    attachment_required: bool = False


class TaskUpdateForm(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee_ids: Optional[list[str]] = None
    start_date: Optional[int] = None
    due_date: Optional[int] = None
    progress: Optional[int] = None
    labels: Optional[list] = None
    sort_key: Optional[float] = None
    attachment_required: Optional[bool] = None


class SubtaskCreateForm(BaseModel):
    title: str
    assignee_ids: Optional[list[str]] = None
    sort_key: Optional[float] = None


class SubtaskUpdateForm(BaseModel):
    title: Optional[str] = None
    completed: Optional[bool] = None
    assignee_ids: Optional[list[str]] = None
    sort_key: Optional[float] = None


class LabelForm(BaseModel):
    name: str
    color: str


class LabelUpdateForm(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None


# ──────────────────────────── task field validation ────────────────────────────


def _validate_task_fields(fields: dict, *, current: Optional[dict] = None) -> None:
    if fields.get('status') is not None and fields['status'] not in STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid status.')
    if fields.get('priority') is not None and fields['priority'] not in PRIORITIES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid priority.')
    if fields.get('progress') is not None and not (0 <= fields['progress'] <= 100):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Progress out of range.')
    start = fields.get('start_date', (current or {}).get('start_date'))
    due = fields.get('due_date', (current or {}).get('due_date'))
    if start is not None and due is not None and start > due:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Start date must be before due date.')


# ──────────────────────────────── task endpoints ────────────────────────────────


@router.get('/workstreams/{workstream_id}/tasks')
async def list_tasks(
    request: Request, workstream_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    await require_workstream_visible(user, workstream_id, db)
    return await Tasks.list_for_workstream(workstream_id, db=db)


@router.get('/me/tasks')
async def list_my_tasks(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    return await visible_my_tasks(user, db)


@router.post('/workstreams/{workstream_id}/tasks')
async def create_task(
    request: Request, workstream_id: str, form: TaskCreateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    stream, _ = await require_workstream_visible(user, workstream_id, db)
    _validate_task_fields(form.model_dump())
    if not form.assignee_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Task needs at least one assignee.')
    team = await require_team_visible(user, (await Workspaces.get_by_id(stream.workspace_id, db=db)).team_id, db)
    await validate_assignees(form.assignee_ids, workstream_id, db)
    task = await Tasks.insert(
        workstream_id, team.id, team.key, form.title, user.id,
        description=form.description, status=form.status, priority=form.priority,
        assignee_ids=form.assignee_ids, start_date=form.start_date, due_date=form.due_date, labels=form.labels,
        attachment_required=form.attachment_required, db=db,
    )
    await emit_event('workos:task.created', f'workos:workstream:{workstream_id}', task.model_dump())
    if task.assignee_ids:
        await notify(request, db, recipients=set(task.assignee_ids), actor=user, type='assigned', task=task)
    await UsageEvents.emit(user.id, 'workos.task.create', {'task_id': task.id, 'team_id': task.team_id, 'workstream_id': workstream_id})
    return task


@router.get('/tasks/{task_id}')
async def get_task(
    request: Request, task_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    task, _ = await require_task_visible(user, task_id, db)
    return task


@router.patch('/tasks/{task_id}')
async def update_task(
    request: Request, task_id: str, form: TaskUpdateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    task, stream = await require_task_visible(user, task_id, db)
    await require_task_writable(user, task, stream, db)
    fields = form.model_dump(exclude_none=True)
    _validate_task_fields(fields, current=task.model_dump())
    if 'assignee_ids' in fields:
        if not fields['assignee_ids']:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Task needs at least one assignee.')
        await validate_assignees(fields['assignee_ids'], task.workstream_id, db)
    if 'attachment_required' in fields and fields['attachment_required'] != task.attachment_required:
        await require_capability('task.flag.attachment_required', user, db,
                                 task=task, creator_id=task.created_by_id)
    # Hard gate: a flagged task cannot TRANSITION to done without at least one
    # attachment (task-level or comment-level both count). Runs before any field
    # is persisted so a mixed patch fails atomically.
    if fields.get('status') == 'done' and task.status != 'done':
        effective_flag = fields.get('attachment_required', task.attachment_required)
        if effective_flag and not await Attachments.list_for_task(task_id, db=db):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='ATTACHMENT_REQUIRED')
    before = task.model_dump()
    # Parent update + subtask-assignee cascade commit in ONE transaction: the
    # "subtask assignees ⊆ parent assignees" invariant must never half-commit.
    result = await Tasks.update_with_cascade(task_id, fields, db=db)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Task not found.')
    updated, cascaded = result
    # Auto-delete tags that this edit orphaned (removed here and used by no other task).
    deleted_label_ids: list[str] = []
    if 'labels' in fields:
        removed = [l for l in (before.get('labels') or []) if l not in (updated.labels or [])]
        if removed:
            deleted_label_ids = await Labels.prune_unused(updated.team_id, removed, db=db)
    # Realtime only after the transaction committed — clients never see a state
    # the database might roll back.
    await emit_event('workos:task.updated', f'workos:workstream:{updated.workstream_id}', updated.model_dump())
    for st in cascaded:
        await emit_event(
            'workos:subtask.updated', f'workos:workstream:{updated.workstream_id}',
            {**st.model_dump(), 'workstream_id': updated.workstream_id, 'actor_id': user.id},
        )
    # Activity log for the changed fields.
    for act in task_change_activities(user.id, before, updated.model_dump()):
        row = await Activity.insert(task_id, updated.team_id, user.id, act['type'], act['data'], db=db)
        await _emit_task_room('workos:activity.created', updated,
                              {**row.model_dump(), 'workstream_id': updated.workstream_id, 'actor_id': user.id})
    # Notifications: assignment + status change.
    if 'assignee_ids' in fields and (updated.assignee_ids or []) != (before.get('assignee_ids') or []):
        if updated.assignee_ids:
            await notify(request, db, recipients=set(updated.assignee_ids), actor=user, type='assigned', task=updated)
    if 'status' in fields and updated.status != before.get('status'):
        await notify(request, db, recipients={updated.created_by_id, *(updated.assignee_ids or [])}, actor=user,
                     type='status_changed', task=updated,
                     extra={'from': before.get('status'), 'to': updated.status})
        if updated.status == 'done':
            await UsageEvents.emit(user.id, 'workos.task.complete', {'task_id': updated.id, 'team_id': updated.team_id})
    return {**updated.model_dump(), 'deleted_label_ids': deleted_label_ids}


@router.delete('/tasks/{task_id}')
async def delete_task(
    request: Request, task_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    task, stream = await require_task_visible(user, task_id, db)
    ws = await Workspaces.get_by_id(stream.workspace_id, db=db)
    await require_capability('task.delete', user, db, team_id=ws.team_id, creator_id=task.created_by_id)
    deleted = await Tasks.delete(task_id, db=db)
    if deleted:
        await UsageEvents.emit(user.id, 'workos.task.delete', {'task_id': task_id, 'team_id': task.team_id})
    # Auto-delete tags this task held that no surviving task references.
    deleted_label_ids = await Labels.prune_unused(task.team_id, task.labels or [], db=db)
    await emit_event('workos:task.deleted', f'workos:workstream:{task.workstream_id}', {'id': task_id, 'workstream_id': task.workstream_id})
    return {'deleted': deleted, 'deleted_label_ids': deleted_label_ids}


# ──────────────────────────────── label endpoints ────────────────────────────────


@router.get('/teams/{team_id}/labels')
async def list_labels(
    request: Request, team_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    await require_team_visible(user, team_id, db)
    return await Labels.list_for_team(team_id, db=db)


@router.post('/teams/{team_id}/labels')
async def create_label(
    request: Request, team_id: str, form: LabelForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    # Any member who can see the team may create tags (tags are a shared, lightweight resource).
    await require_team_visible(user, team_id, db)
    return await Labels.insert(team_id, form.name, form.color, db=db)


@router.patch('/labels/{label_id}')
async def update_label(
    request: Request, label_id: str, form: LabelUpdateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    existing = await Labels.update_fields(label_id, {}, db=db)  # fetch-only to read team_id
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Label not found.')
    await require_team_capability(user, existing.team_id, db, 'labels.manage')
    return await Labels.update_fields(label_id, form.model_dump(exclude_none=True), db=db)


@router.delete('/labels/{label_id}')
async def delete_label(
    request: Request, label_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    existing = await Labels.update_fields(label_id, {}, db=db)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Label not found.')
    await require_team_capability(user, existing.team_id, db, 'labels.manage')
    return {'deleted': await Labels.delete(label_id, db=db)}


# ──────────────────────────────── admin settings schema ────────────────────────────────


class SettingsForm(BaseModel):
    team_creation: Optional[str] = None
    default_workspace_visibility: Optional[str] = None
    notifications: Optional[dict] = None
    max_attachment_mb: Optional[int] = None


# ──────────────────────────────── admin endpoints ────────────────────────────────


@router.get('/admin/teams')
async def admin_list_teams(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos_admin(request, user, db)
    out = []
    for team in await Teams.list_all(db=db):
        members = await TeamMembers.list_for_team(team.id, db=db)
        out.append({
            'team': team,
            'owner_ids': [m.user_id for m in members if m.role == 'owner'],
            'member_count': len(members),
        })
    return out


@router.get('/admin/settings')
async def admin_get_settings(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos_admin(request, user, db)
    return request.app.state.config.WORKOS_RULES


@router.patch('/admin/settings')
async def admin_update_settings(
    request: Request, form: SettingsForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos_admin(request, user, db)
    if form.team_creation is not None and form.team_creation not in {'all_users', 'admins_only'}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid team_creation.')
    if form.default_workspace_visibility is not None and form.default_workspace_visibility not in {'team', 'restricted'}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid default_workspace_visibility.')
    if form.max_attachment_mb is not None and form.max_attachment_mb < 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid max_attachment_mb.')
    rules = dict(request.app.state.config.WORKOS_RULES or {})
    rules.update(form.model_dump(exclude_none=True))
    request.app.state.config.WORKOS_RULES = rules
    return request.app.state.config.WORKOS_RULES


# ──────────────────────────────── access console ────────────────────────────────


@router.get('/access/overview')
async def access_overview(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    """Teams the caller manages (team_role in {owner, admin}; app-admins: all teams,
    archived included), with the workspaces they can see. Restricted workspaces the
    caller is not a member of are omitted — the console manages only what its user
    can see. Non-managers get an empty list."""
    await require_workos(request, user, db)
    is_admin = user.role == 'admin'
    teams = await (Teams.list_all(db=db) if is_admin else Teams.list_for_user(user.id, db=db))
    out = []
    for team in teams:
        role = await team_role(user, team.id, db)
        if role not in {'owner', 'admin'}:
            continue
        members = await TeamMembers.list_for_team(team.id, db=db)
        workspaces = []
        for ws in await Workspaces.list_for_team(team.id, db=db):
            if not await can_see_workspace(user.id, is_admin, ws, db=db):
                continue
            entry = {
                'id': ws.id,
                'name': ws.name,
                'icon': ws.icon,
                'visibility': ws.visibility,
                'archived': ws.archived,
            }
            if ws.visibility == 'restricted':
                entry['member_count'] = len(await WorkspaceMembers.list_for_workspace(ws.id, db=db))
            workspaces.append(entry)
        out.append({
            'team': team,
            'my_role': role,
            'owner_ids': [m.user_id for m in members if m.role == 'owner'],
            'member_count': len(members),
            'workspaces': workspaces,
        })
    return out


# ──────────────────────────────── collaboration: schemas ────────────────────────────────


class CommentForm(BaseModel):
    body: str
    parent_id: Optional[str] = None  # create-only; ignored on PATCH


# ──────────────────────────────── collaboration: helpers ────────────────────────────────


# Notification types that share another type's WORKOS_RULES.notifications toggle.
_NOTIF_CATEGORY = {'subtask_assigned': 'assigned'}


def _notif_enabled(request: Request, type: str) -> bool:
    rules = request.app.state.config.WORKOS_RULES or {}
    cfg = rules.get('notifications') or {}
    return cfg.get(_NOTIF_CATEGORY.get(type, type), True)


def _actor_name(user) -> str:
    return getattr(user, 'name', None) or user.id


async def notify(
    request: Request, db, *, recipients: set, actor, type: str, task, comment_id=None, snippet=None, extra=None,
):
    """Create + deliver one notification per recipient (minus the actor)."""
    if not _notif_enabled(request, type):
        return []
    targets = {r for r in recipients if r and r != actor.id}
    visible = set()
    for uid in targets:
        if await can_see_workstream(uid, await is_app_admin(uid, db), task.workstream_id, db=db):
            visible.add(uid)
    targets = visible
    if not targets:
        return []
    data = {
        'task_id': task.id, 'task_key': task.key, 'task_title': task.title,
        'workstream_id': task.workstream_id, 'actor_name': _actor_name(actor),
    }
    if snippet is not None:
        data['snippet'] = snippet[:140]
    if extra:
        data.update(extra)
    created = []
    for uid in targets:
        n = await Notifications.insert(uid, actor.id, type, data, task_id=task.id, comment_id=comment_id, db=db)
        created.append(n)
        await emit_users('workos:notification.created', n.model_dump(), [uid])
    return created


async def _participants(task, db) -> set:
    """Creator + assignees + distinct comment authors + users mentioned on existing comments."""
    out: set = set()
    if task.created_by_id:
        out.add(task.created_by_id)
    out.update(task.assignee_ids or [])
    for com in await Comments.list_for_task(task.id, db=db):
        out.add(com.user_id)
        out.update(com.mentions or [])
    return out


async def _emit_task_room(event: str, task, payload: dict) -> None:
    await emit_event(event, f'workos:workstream:{task.workstream_id}', payload)


# ──────────────────────────────── comment endpoints ────────────────────────────────


@router.get('/tasks/{task_id}/comments')
async def list_comments(
    request: Request, task_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    await require_task_visible(user, task_id, db)
    items = await Comments.list_for_task(task_id, db=db)
    reactions = await Reactions.aggregate_for_comments([c.id for c in items], db=db)
    out = []
    for c in items:
        d = c.model_dump()
        d['reactions'] = reactions.get(c.id, [])
        out.append(d)
    return out


@router.post('/tasks/{task_id}/comments')
async def create_comment(
    request: Request, task_id: str, form: CommentForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    task, _ = await require_task_visible(user, task_id, db)
    body = (form.body or '').strip()
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Comment body required.')
    parent = None
    if form.parent_id:
        parent = await Comments.get_by_id(form.parent_id, db=db)
        if not parent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Parent comment not found.')
        if parent.task_id != task_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail='Parent comment belongs to another task.')
        if parent.deleted_at:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail='Cannot reply to a deleted comment.')
    mentions = parse_mentions(body)
    comment = await Comments.insert(task_id, user.id, body, mentions, parent_id=form.parent_id, db=db)
    await UsageEvents.emit(user.id, 'workos.comment.create',
                           {'task_id': task_id, 'team_id': task.team_id, 'is_reply': bool(form.parent_id)})
    activity = await Activity.insert(task_id, task.team_id, user.id, 'comment_added', {}, db=db)
    payload = {**comment.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id}
    await _emit_task_room('workos:comment.created', task, payload)
    await _emit_task_room('workos:activity.created',
                          task, {**activity.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id})
    # Notification fan-out precedence: mentioned > replied > commented — one per recipient.
    mentioned = set()
    for m in mentions:
        if await can_see_workstream(m, await is_app_admin(m, db), task.workstream_id, db=db):
            mentioned.add(m)
    await notify(request, db, recipients=mentioned, actor=user, type='mentioned', task=task,
                 comment_id=comment.id, snippet=body)
    replied_to = set()
    if parent and parent.user_id and parent.user_id not in mentioned:
        replied_to = {parent.user_id}
        await notify(request, db, recipients=replied_to, actor=user, type='replied', task=task,
                     comment_id=comment.id, snippet=body)
    participants = await _participants(task, db) - mentioned - replied_to
    await notify(request, db, recipients=participants, actor=user, type='commented', task=task,
                 comment_id=comment.id, snippet=body)
    return comment


@router.patch('/comments/{comment_id}')
async def update_comment(
    request: Request, comment_id: str, form: CommentForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    existing = await Comments.get_by_id(comment_id, db=db)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Comment not found.')
    if existing.deleted_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Comment was deleted.')
    task, _ = await require_task_visible(user, existing.task_id, db)
    await require_capability('comment.edit', user, db, author_id=existing.user_id)
    body = (form.body or '').strip()
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Comment body required.')
    new_mentions = parse_mentions(body)
    updated = await Comments.update_body(comment_id, body, new_mentions, db=db)
    # update_body's CommentModel never carries reactions (pydantic default []) — reattach the
    # live aggregate so editing a comment doesn't clobber its reaction pills on other clients.
    agg = await Reactions.aggregate_for_comments([comment_id], db=db)
    result = {**updated.model_dump(), 'reactions': agg.get(comment_id, [])}
    payload = {**result, 'workstream_id': task.workstream_id, 'actor_id': user.id}
    await _emit_task_room('workos:comment.updated', task, payload)
    # Only notify mentions that are newly added on this edit.
    fresh = set()
    for m in new_mentions:
        if m not in (existing.mentions or []) and await can_see_workstream(m, False, task.workstream_id, db=db):
            fresh.add(m)
    await notify(request, db, recipients=fresh, actor=user, type='mentioned', task=task,
                 comment_id=comment_id, snippet=body)
    return result


@router.delete('/comments/{comment_id}')
async def delete_comment(
    request: Request, comment_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    existing = await Comments.get_by_id(comment_id, db=db)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Comment not found.')
    task, stream = await require_task_visible(user, existing.task_id, db)
    ws = await Workspaces.get_by_id(stream.workspace_id, db=db)
    await require_capability('comment.delete', user, db, team_id=ws.team_id, author_id=existing.user_id)
    if await Comments.has_children(comment_id, db=db):
        await Reactions.purge_for_comment(comment_id, db=db)
        tomb = await Comments.tombstone(comment_id, db=db)
        payload = {**tomb.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id}
        await _emit_task_room('workos:comment.updated', task, payload)
        return {'deleted': True, 'tombstoned': True}
    await Reactions.purge_for_comment(comment_id, db=db)
    deleted = await Comments.delete(comment_id, db=db)
    await _emit_task_room('workos:comment.deleted',
                          task, {'id': comment_id, 'task_id': task.id, 'workstream_id': task.workstream_id,
                                 'actor_id': user.id})
    return {'deleted': deleted}


REACTION_EMOJI = {'👍', '❤️', '🎉', '👀', '😂', '🚀'}


class ReactionForm(BaseModel):
    emoji: str


@router.post('/comments/{comment_id}/reactions')
async def toggle_reaction(
    request: Request, comment_id: str, form: ReactionForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    """Toggle the caller's emoji reaction. Any task-visible user may react — no
    capability entry (deliberate; reactions are lightweight, like viewing)."""
    await require_workos(request, user, db)
    existing = await Comments.get_by_id(comment_id, db=db)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Comment not found.')
    task, _ = await require_task_visible(user, existing.task_id, db)
    if form.emoji not in REACTION_EMOJI:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unsupported emoji.')
    if existing.deleted_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Comment was deleted.')
    added = await Reactions.toggle(comment_id, user.id, form.emoji, db=db)
    agg = await Reactions.aggregate_for_comments([comment_id], db=db)
    reactions = agg.get(comment_id, [])
    await _emit_task_room('workos:comment.reaction', task,
                          {'comment_id': comment_id, 'task_id': task.id,
                           'workstream_id': task.workstream_id, 'reactions': reactions,
                           'actor_id': user.id})
    return {'added': added, 'reactions': reactions}


@router.get('/tasks/{task_id}/activity')
async def list_activity(
    request: Request, task_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    await require_task_visible(user, task_id, db)
    return await Activity.list_for_task(task_id, db=db)


def _daily_counts(timestamps: list, days: int, tz_offset_minutes: int, now_ms: int) -> list:
    """Bucket epoch-ms timestamps into the viewer's last `days` local calendar days
    (oldest first). tz_offset_minutes is minutes AHEAD of UTC (JS: -getTimezoneOffset())."""
    tz = timezone(timedelta(minutes=tz_offset_minutes))
    today = datetime.fromtimestamp(now_ms / 1000, tz).date()
    ordered = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
    counts = {d.isoformat(): 0 for d in ordered}
    for ts in timestamps:
        key = datetime.fromtimestamp(ts / 1000, tz).date().isoformat()
        if key in counts:
            counts[key] += 1
    return [{'day': k, 'n': v} for k, v in counts.items()]


@router.get('/workstreams/{workstream_id}/activity')
async def list_workstream_activity(
    request: Request, workstream_id: str, limit: int = 30, days: int = 14, tz_offset_minutes: int = 0,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    await require_workstream_visible(user, workstream_id, db)
    limit = max(1, min(limit, 100))
    days = max(1, min(days, 31))
    tz_offset_minutes = max(-840, min(tz_offset_minutes, 840))
    now_ms = int(time.time() * 1000)
    since = now_ms - (days + 1) * 86_400_000  # one spare day so tz shifting never truncates
    items = await Activity.list_for_workstream(workstream_id, limit=limit, db=db)
    stamps_ms = await Activity.timestamps_for_workstream(workstream_id, since, db=db)
    return {'items': items, 'daily': _daily_counts(stamps_ms, days, tz_offset_minutes, now_ms)}


# ──────────────────────────────── attachment endpoints ────────────────────────────────


ATTACHMENT_MIME_ALLOW = {
    'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/svg+xml',
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'text/plain', 'text/csv', 'text/markdown', 'application/json', 'application/zip',
}


def _max_attachment_bytes(request: Request) -> int:
    rules = request.app.state.config.WORKOS_RULES or {}
    mb = rules.get('max_attachment_mb', 25)
    return int(mb) * 1024 * 1024


@router.post('/tasks/{task_id}/attachments')
async def upload_attachment(
    request: Request, task_id: str, file: UploadFile = File(...), comment_id: Optional[str] = None,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    task, _ = await require_task_visible(user, task_id, db)
    contents = await file.read()
    limit = _max_attachment_bytes(request)
    if len(contents) > limit:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Attachment too large.')
    if file.content_type not in ATTACHMENT_MIME_ALLOW:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Unsupported file type.')
    if comment_id is not None:
        com = await Comments.get_by_id(comment_id, db=db)
        if not com or com.task_id != task_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid comment for this task.')
        if not (file.content_type or '').startswith('image/'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail='Comment attachments must be images.')
    import io as _io

    safe_name = file.filename or 'file'
    storage_name = f'workos/{_uuid.uuid4()}_{safe_name}'
    _data, key = await asyncio.to_thread(
        Storage.upload_file, _io.BytesIO(contents), storage_name,
        {'OpenWebUI-User-Id': user.id, 'WorkOS-Task-Id': task_id},
    )
    att = await Attachments.insert(
        task_id, comment_id, key, safe_name, len(contents), file.content_type, user.id, db=db,
    )
    activity = await Activity.insert(task_id, task.team_id, user.id, 'attachment_added',
                                     {'name': safe_name}, db=db)
    await _emit_task_room('workos:attachment.created',
                          task, {**att.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id})
    await _emit_task_room('workos:activity.created',
                          task, {**activity.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id})
    return att


@router.get('/tasks/{task_id}/attachments')
async def list_attachments(
    request: Request, task_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    await require_task_visible(user, task_id, db)
    return await Attachments.list_for_task(task_id, db=db)


@router.get('/workstreams/{workstream_id}/attachments')
async def list_workstream_attachments(
    request: Request, workstream_id: str,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    await require_workstream_visible(user, workstream_id, db)
    return await Attachments.list_for_workstream(workstream_id, db=db)


@router.get('/attachments/{attachment_id}/content')
async def download_attachment(
    request: Request, attachment_id: str,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    att = await Attachments.get_by_id(attachment_id, db=db)
    if not att:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Attachment not found.')
    await require_task_visible(user, att.task_id, db)  # 404 if the caller can't see the task
    path = await asyncio.to_thread(Storage.get_file, att.storage_key)
    # Serve the provider's file directly, like files.py's download endpoints, and
    # do NOT delete it afterward. Cloud providers hand back a deterministic path
    # shared across concurrent downloads of the same attachment (and the local
    # provider returns the real file), so a post-response unlink would race a
    # sibling download or delete a file we don't own. Cleanup of the cloud cache
    # copy is governed by STORAGE_LOCAL_CACHE at the storage layer.
    return FileResponse(
        path,
        media_type=att.content_type or 'application/octet-stream',
        filename=att.name,
    )


@router.delete('/attachments/{attachment_id}')
async def delete_attachment(
    request: Request, attachment_id: str,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    att = await Attachments.get_by_id(attachment_id, db=db)
    if not att:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Attachment not found.')
    task, stream = await require_task_visible(user, att.task_id, db)
    ws = await Workspaces.get_by_id(stream.workspace_id, db=db)
    await require_capability('attachment.delete', user, db, team_id=ws.team_id, author_id=att.created_by_id)
    try:
        await asyncio.to_thread(Storage.delete_file, att.storage_key)
    except Exception as e:  # pragma: no cover - best-effort
        log.debug(f'workos attachment storage delete failed: {e}')
    deleted = await Attachments.delete(attachment_id, db=db)
    await _emit_task_room('workos:attachment.deleted',
                          task, {'id': attachment_id, 'task_id': task.id,
                                 'workstream_id': task.workstream_id, 'actor_id': user.id})
    return {'deleted': deleted}


# ──────────────────────────────── notification endpoints ────────────────────────────────


class MarkReadForm(BaseModel):
    ids: Optional[list] = None
    all: bool = False


class ArchiveForm(BaseModel):
    ids: Optional[list] = None
    all_read: bool = False
    archived: bool = True


@router.get('/notifications')
async def list_notifications(
    request: Request, unread_only: bool = False, limit: int = 50, before: Optional[int] = None,
    before_id: Optional[str] = None, archived: bool = False,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    limit = max(1, min(limit, 200))
    return await Notifications.list_for_user(
        user.id, unread_only=unread_only, limit=limit, before=before, before_id=before_id,
        archived=archived, db=db
    )


@router.post('/notifications/read')
async def mark_notifications_read(
    request: Request, form: MarkReadForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    await Notifications.mark_read(user.id, ids=form.ids, all=form.all, db=db)
    return {'unread': await Notifications.unread_count(user.id, db=db)}


@router.get('/notifications/counts')
async def notification_counts(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    return await Notifications.counts_for_user(user.id, db=db)


@router.post('/notifications/archive')
async def archive_notifications(
    request: Request, form: ArchiveForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    """Archive implies read. Intrinsically scoped to the caller's rows."""
    await require_workos(request, user, db)
    await Notifications.set_archived(
        user.id, ids=form.ids, all_read=form.all_read, archived=form.archived, db=db
    )
    return {'unread': await Notifications.unread_count(user.id, db=db)}


# ──────────────────────────────── subtask endpoints ────────────────────────────────


async def _emit_parent_after_subtask(task_id: str, db: AsyncSession):
    task = await Tasks.get_by_id(task_id, db=db)
    if task:
        await emit_event('workos:task.updated', f'workos:workstream:{task.workstream_id}', task.model_dump())
    return task


async def _expand_parent_assignees(request: Request, user, task, stream, assignee_ids: list, db: AsyncSession):
    """Auto-add subtask assignees missing from the parent task (subset invariant).

    Expanding the parent list requires task.write: subtask creation is open to
    any task-visible user, and parent assignment itself grants task.write, so an
    ungated auto-add would let any visible user self-assign into edit rights.
    Returns the (possibly updated) parent task.
    """
    missing = [uid for uid in assignee_ids if uid not in (task.assignee_ids or [])]
    if not missing:
        return task
    try:
        await require_task_writable(user, task, stream, db)
    except HTTPException as e:
        if e.status_code != status.HTTP_403_FORBIDDEN:
            raise
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail='Only task editors can add new people to the task.')
    # Atomic union against the row as it is NOW — a concurrent assignee removal
    # committed after this request's snapshot must stay removed, or the auto-add
    # would silently hand edit rights back to a revoked user.
    merged = await Tasks.merge_assignees(task.id, assignee_ids, db=db)
    if merged is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Task not found.')
    before_task, updated = merged
    if (updated.assignee_ids or []) == (before_task.assignee_ids or []):
        return updated
    # No task.updated emit here — both callers emit the final parent state via
    # _emit_parent_after_subtask once the subtask write lands.
    for act in task_change_activities(user.id, before_task.model_dump(), updated.model_dump()):
        row = await Activity.insert(task.id, updated.team_id, user.id, act['type'], act['data'], db=db)
        await _emit_task_room('workos:activity.created', updated,
                              {**row.model_dump(), 'workstream_id': updated.workstream_id, 'actor_id': user.id})
    return updated


@router.get('/tasks/{task_id}/subtasks')
async def list_subtasks(
    request: Request, task_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    await require_task_visible(user, task_id, db)
    return await Subtasks.list_for_task(task_id, db=db)


@router.post('/tasks/{task_id}/subtasks')
async def create_subtask(
    request: Request, task_id: str, form: SubtaskCreateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    task, stream = await require_task_visible(user, task_id, db)
    if not form.title.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Subtask title is required.')
    assignee_ids = list(dict.fromkeys(form.assignee_ids or []))
    if assignee_ids:
        await validate_assignees(assignee_ids, task.workstream_id, db)
        task = await _expand_parent_assignees(request, user, task, stream, assignee_ids, db)
    elif task.assignee_ids:
        assignee_ids = [task.assignee_ids[0]]
    subtask = await Subtasks.insert(
        task_id, form.title.strip(), user.id, assignee_ids=assignee_ids, sort_key=form.sort_key, db=db
    )
    payload = {**subtask.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id}
    await emit_event('workos:subtask.created', f'workos:workstream:{task.workstream_id}', payload)
    await _emit_parent_after_subtask(task_id, db)
    row = await Activity.insert(task_id, task.team_id, user.id, 'subtask_created', {'title': subtask.title}, db=db)
    await _emit_task_room('workos:activity.created', task, {**row.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id})
    if assignee_ids:
        await notify(request, db, recipients=set(assignee_ids), actor=user,
                     type='subtask_assigned', task=task, extra={'subtask_title': subtask.title})
    return subtask


@router.patch('/subtasks/{subtask_id}')
async def update_subtask(
    request: Request, subtask_id: str, form: SubtaskUpdateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await require_workos(request, user, db)
    subtask, task, stream = await require_subtask_visible(user, subtask_id, db)
    await require_subtask_writable(user, subtask, task, stream, db)
    fields = form.model_dump(exclude_none=True)
    if 'title' in fields:
        fields['title'] = fields['title'].strip()
        if not fields['title']:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Subtask title is required.')
    newly_assigned: list = []
    if 'assignee_ids' in fields:
        fields['assignee_ids'] = list(dict.fromkeys(fields['assignee_ids']))
        await validate_assignees(fields['assignee_ids'], task.workstream_id, db)
        task = await _expand_parent_assignees(request, user, task, stream, fields['assignee_ids'], db)
        newly_assigned = [uid for uid in fields['assignee_ids'] if uid not in (subtask.assignee_ids or [])]
    updated = await Subtasks.update_fields(subtask_id, fields, db=db)
    payload = {**updated.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id}
    await emit_event('workos:subtask.updated', f'workos:workstream:{task.workstream_id}', payload)
    await _emit_parent_after_subtask(task.id, db)
    if 'completed' in fields and fields['completed'] != subtask.completed:
        row = await Activity.insert(
            task.id, task.team_id, user.id,
            'subtask_completed' if fields['completed'] else 'subtask_reopened',
            {'title': updated.title},
            db=db,
        )
        await _emit_task_room('workos:activity.created', task, {**row.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id})
    if newly_assigned:
        await notify(request, db, recipients=set(newly_assigned), actor=user,
                     type='subtask_assigned', task=task, extra={'subtask_title': updated.title})
    return updated


@router.delete('/subtasks/{subtask_id}')
async def delete_subtask(
    request: Request, subtask_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    subtask, task, stream = await require_subtask_visible(user, subtask_id, db)
    await require_subtask_writable(user, subtask, task, stream, db)
    deleted = await Subtasks.delete(subtask_id, db=db)
    await emit_event(
        'workos:subtask.deleted',
        f'workos:workstream:{task.workstream_id}',
        {'id': subtask_id, 'task_id': task.id, 'workstream_id': task.workstream_id, 'actor_id': user.id},
    )
    await _emit_parent_after_subtask(task.id, db)
    return {'deleted': deleted}
