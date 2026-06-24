import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.internal.db import get_async_session
from open_webui.utils.auth import get_verified_user
from open_webui.utils.access_control import has_permission
from open_webui.models.workos import (
    Teams, TeamMembers, Workspaces, WorkspaceMembers, Workstreams,
    Labels, Tasks, Comments, Activity, Attachments, Notifications,
    TeamModel, WorkspaceModel, WorkstreamModel, TaskModel, LabelModel,
    CommentModel, ActivityModel, AttachmentModel, NotificationModel,
    parse_mentions, task_change_activities, can_see_workstream,
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


router = APIRouter()

TEAM_ROLES = {'owner', 'admin', 'member'}


# ──────────────────────────── permission / access helpers ────────────────────────────


async def _require_workos(request: Request, user, db: AsyncSession) -> None:
    if user.role != 'admin' and not await has_permission(
        user.id, 'features.workos', request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='WorkOS access required.')


async def _require_workos_admin(request: Request, user, db: AsyncSession) -> None:
    if user.role != 'admin' and not await has_permission(
        user.id, 'features.workos_admin', request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='WorkOS admin required.')


async def team_role(user, team_id: str, db: AsyncSession) -> Optional[str]:
    if user.role == 'admin':
        return 'admin'
    m = await TeamMembers.get(team_id, user.id, db=db)
    return m.role if m else None


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


async def resolve_user_names(ids: list) -> list:
    # Wrapper around the Users DAO so tests can monkeypatch a fast stub.
    from open_webui.models.users import Users

    out = []
    for uid in ids:
        u = await Users.get_user_by_id(uid)
        if u:
            out.append({'id': u.id, 'name': u.name})
    return out


@router.get('/directory')
async def directory(request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)):
    await _require_workos(request, user, db)
    teams = await (Teams.list_all(db=db) if user.role == 'admin' else Teams.list_for_user(user.id, db=db))
    ids: set = set()
    for t in teams:
        for m in await TeamMembers.list_for_team(t.id, db=db):
            ids.add(m.user_id)
    ids.add(user.id)
    return await resolve_user_names(sorted(ids))


# ──────────────────────────────── bootstrap ────────────────────────────────


@router.get('/bootstrap')
async def bootstrap(request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)):
    await _require_workos(request, user, db)
    teams = await Teams.list_for_user(user.id, db=db) if user.role != 'admin' else await Teams.list_all(db=db)
    roles: dict = {}
    workspaces = []
    workstreams = []
    for t in teams:
        roles[t.id] = await team_role(user, t.id, db)
        for w in await Workspaces.list_for_team(t.id, db=db):
            if w.visibility == 'team' or user.role == 'admin' or await WorkspaceMembers.get(w.id, user.id, db=db):
                workspaces.append(w)
                workstreams.extend(await Workstreams.list_for_workspace(w.id, db=db))
    return {'teams': teams, 'workspaces': workspaces, 'workstreams': workstreams, 'roles': roles}


# ──────────────────────────────── teams ────────────────────────────────


@router.get('/teams')
async def list_teams(request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)):
    await _require_workos(request, user, db)
    return await (Teams.list_all(db=db) if user.role == 'admin' else Teams.list_for_user(user.id, db=db))


@router.post('/teams')
async def create_team(
    request: Request, form: TeamForm, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
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
    await _require_workos(request, user, db)
    return await require_team_visible(user, team_id, db)


@router.patch('/teams/{team_id}')
async def update_team(
    request: Request, team_id: str, form: TeamUpdateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    await require_team_role(user, team_id, db, {'owner'})
    fields = {k: v for k, v in form.model_dump(exclude_none=True).items()}
    return await Teams.update_fields(team_id, fields, db=db)


@router.delete('/teams/{team_id}')
async def delete_team(
    request: Request, team_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    await require_team_role(user, team_id, db, {'owner'})
    return {'deleted': await Teams.delete(team_id, db=db)}


@router.get('/teams/{team_id}/members')
async def list_members(
    request: Request, team_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    await require_team_visible(user, team_id, db)
    return await TeamMembers.list_for_team(team_id, db=db)


@router.post('/teams/{team_id}/members')
async def add_member(
    request: Request, team_id: str, form: MemberForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    await require_team_role(user, team_id, db, {'owner', 'admin'})
    if form.role not in TEAM_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid role.')
    if await TeamMembers.get(team_id, form.user_id, db=db):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Already a member.')
    return await TeamMembers.add(team_id, form.user_id, form.role, db=db)


@router.patch('/teams/{team_id}/members/{user_id}')
async def update_member(
    request: Request, team_id: str, user_id: str, form: MemberRoleForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    # Only owners may grant/revoke owner or admin; admins may manage members.
    await require_team_role(user, team_id, db, {'owner'} if form.role in {'owner', 'admin'} else {'owner', 'admin'})
    if form.role not in TEAM_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid role.')
    updated = await TeamMembers.update_role(team_id, user_id, form.role, db=db)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Member not found.')
    return updated


@router.delete('/teams/{team_id}/members/{user_id}')
async def remove_member(
    request: Request, team_id: str, user_id: str,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    await require_team_role(user, team_id, db, {'owner', 'admin'})
    return {'removed': await TeamMembers.remove(team_id, user_id, db=db)}


# ──────────────────────────────── workspace schemas ────────────────────────────────


WORKSPACE_ROLES = {'admin', 'member'}


class WorkspaceForm(BaseModel):
    name: str
    icon: Optional[str] = None
    visibility: str = 'team'


class WorkspaceUpdateForm(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    visibility: Optional[str] = None
    archived: Optional[bool] = None


# ──────────────────────────── workspace permission helpers ────────────────────────────


async def workspace_visible(user, workspace, db: AsyncSession) -> bool:
    if await team_role(user, workspace.team_id, db) is None:
        return False
    if workspace.visibility == 'team' or user.role == 'admin':
        return True
    return (await WorkspaceMembers.get(workspace.id, user.id, db=db)) is not None


async def require_workspace_visible(user, workspace_id: str, db: AsyncSession):
    ws = await Workspaces.get_by_id(workspace_id, db=db)
    if not ws or not await workspace_visible(user, ws, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Workspace not found.')
    return ws


async def require_workspace_manage(user, workspace_id: str, db: AsyncSession):
    ws = await require_workspace_visible(user, workspace_id, db)
    if (await team_role(user, ws.team_id, db)) in {'owner', 'admin'}:
        return ws
    wm = await WorkspaceMembers.get(ws.id, user.id, db=db)
    if wm and wm.role == 'admin':
        return ws
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Workspace management requires admin.')


# ──────────────────────────────── workspace endpoints ────────────────────────────────


@router.get('/teams/{team_id}/workspaces')
async def list_workspaces(
    request: Request, team_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    await require_team_visible(user, team_id, db)
    out = []
    for ws in await Workspaces.list_for_team(team_id, db=db):
        if await workspace_visible(user, ws, db):
            out.append(ws)
    return out


@router.post('/teams/{team_id}/workspaces')
async def create_workspace(
    request: Request, team_id: str, form: WorkspaceForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    await require_team_role(user, team_id, db, {'owner', 'admin'})
    if form.visibility not in {'team', 'restricted'}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid visibility.')
    ws = await Workspaces.insert(team_id, form.name, form.icon, form.visibility, user.id, db=db)
    if form.visibility == 'restricted':
        await WorkspaceMembers.add(ws.id, user.id, 'admin', db=db)
    await emit_event('workos:workspace.created', f'workos:team:{team_id}', ws.model_dump())
    return ws


@router.get('/workspaces/{workspace_id}')
async def get_workspace(
    request: Request, workspace_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    return await require_workspace_visible(user, workspace_id, db)


@router.patch('/workspaces/{workspace_id}')
async def update_workspace(
    request: Request, workspace_id: str, form: WorkspaceUpdateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    await require_workspace_manage(user, workspace_id, db)
    fields = form.model_dump(exclude_none=True)
    if 'visibility' in fields and fields['visibility'] not in {'team', 'restricted'}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid visibility.')
    updated = await Workspaces.update_fields(workspace_id, fields, db=db)
    await emit_event('workos:workspace.updated', f'workos:team:{updated.team_id}', updated.model_dump())
    return updated


@router.delete('/workspaces/{workspace_id}')
async def delete_workspace(
    request: Request, workspace_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    ws = await require_workspace_visible(user, workspace_id, db)
    await require_team_role(user, ws.team_id, db, {'owner', 'admin'})
    deleted = await Workspaces.delete(workspace_id, db=db)
    await emit_event('workos:workspace.deleted', f'workos:team:{ws.team_id}', {'id': workspace_id})
    return {'deleted': deleted}


# ──────────────────────────────── workspace member endpoints ────────────────────────────────


@router.get('/workspaces/{workspace_id}/members')
async def list_workspace_members(
    request: Request, workspace_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    await require_workspace_visible(user, workspace_id, db)
    return await WorkspaceMembers.list_for_workspace(workspace_id, db=db)


@router.post('/workspaces/{workspace_id}/members')
async def add_workspace_member(
    request: Request, workspace_id: str, form: MemberForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    await require_workspace_manage(user, workspace_id, db)
    if form.role not in WORKSPACE_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid role.')
    if await WorkspaceMembers.get(workspace_id, form.user_id, db=db):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Already a member.')
    return await WorkspaceMembers.add(workspace_id, form.user_id, form.role, db=db)


@router.patch('/workspaces/{workspace_id}/members/{user_id}')
async def update_workspace_member(
    request: Request, workspace_id: str, user_id: str, form: MemberRoleForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
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
    await _require_workos(request, user, db)
    await require_workspace_manage(user, workspace_id, db)
    return {'removed': await WorkspaceMembers.remove(workspace_id, user_id, db=db)}


# ──────────────────────────────── workstream schemas ────────────────────────────────


class WorkstreamForm(BaseModel):
    name: str
    icon: Optional[str] = None


class WorkstreamUpdateForm(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    archived: Optional[bool] = None


# ──────────────────────────── workstream permission helpers ────────────────────────────


async def require_workstream_visible(user, workstream_id: str, db: AsyncSession):
    stream = await Workstreams.get_by_id(workstream_id, db=db)
    if not stream:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Workstream not found.')
    ws = await require_workspace_visible(user, stream.workspace_id, db)
    return stream, ws


# ──────────────────────────────── workstream endpoints ────────────────────────────────


@router.get('/workspaces/{workspace_id}/workstreams')
async def list_workstreams(
    request: Request, workspace_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    await require_workspace_visible(user, workspace_id, db)
    return await Workstreams.list_for_workspace(workspace_id, db=db)


@router.post('/workspaces/{workspace_id}/workstreams')
async def create_workstream(
    request: Request, workspace_id: str, form: WorkstreamForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    await require_workspace_manage(user, workspace_id, db)
    stream = await Workstreams.insert(workspace_id, form.name, form.icon, user.id, db=db)
    ws_row = await Workspaces.get_by_id(workspace_id, db=db)
    await emit_event('workos:workstream.created', f'workos:team:{ws_row.team_id}', stream.model_dump())
    return stream


@router.patch('/workstreams/{workstream_id}')
async def update_workstream(
    request: Request, workstream_id: str, form: WorkstreamUpdateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    stream, _ = await require_workstream_visible(user, workstream_id, db)
    await require_workspace_manage(user, stream.workspace_id, db)
    updated = await Workstreams.update_fields(workstream_id, form.model_dump(exclude_none=True), db=db)
    ws_row = await Workspaces.get_by_id(stream.workspace_id, db=db)
    await emit_event('workos:workstream.updated', f'workos:team:{ws_row.team_id}', updated.model_dump())
    return updated


@router.delete('/workstreams/{workstream_id}')
async def delete_workstream(
    request: Request, workstream_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    stream, _ = await require_workstream_visible(user, workstream_id, db)
    await require_workspace_manage(user, stream.workspace_id, db)
    deleted = await Workstreams.delete(workstream_id, db=db)
    ws_row = await Workspaces.get_by_id(stream.workspace_id, db=db)
    await emit_event('workos:workstream.deleted', f'workos:team:{ws_row.team_id}', {'id': workstream_id, 'workspace_id': stream.workspace_id})
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
    assignee_id: Optional[str] = None
    due_date: Optional[int] = None
    labels: Optional[list] = None


class TaskUpdateForm(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee_id: Optional[str] = None
    due_date: Optional[int] = None
    progress: Optional[int] = None
    labels: Optional[list] = None
    sort_key: Optional[float] = None


class LabelForm(BaseModel):
    name: str
    color: str


class LabelUpdateForm(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None


# ──────────────────────────── task permission helpers ────────────────────────────


async def require_task_visible(user, task_id: str, db: AsyncSession):
    task = await Tasks.get_by_id(task_id, db=db)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Task not found.')
    stream, _ = await require_workstream_visible(user, task.workstream_id, db)
    return task, stream


def _validate_task_fields(fields: dict) -> None:
    if fields.get('status') is not None and fields['status'] not in STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid status.')
    if fields.get('priority') is not None and fields['priority'] not in PRIORITIES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid priority.')
    if fields.get('progress') is not None and not (0 <= fields['progress'] <= 100):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Progress out of range.')


# ──────────────────────────────── task endpoints ────────────────────────────────


@router.get('/workstreams/{workstream_id}/tasks')
async def list_tasks(
    request: Request, workstream_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    await require_workstream_visible(user, workstream_id, db)
    return await Tasks.list_for_workstream(workstream_id, db=db)


@router.post('/workstreams/{workstream_id}/tasks')
async def create_task(
    request: Request, workstream_id: str, form: TaskCreateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    stream, _ = await require_workstream_visible(user, workstream_id, db)
    _validate_task_fields(form.model_dump())
    team = await require_team_visible(user, (await Workspaces.get_by_id(stream.workspace_id, db=db)).team_id, db)
    task = await Tasks.insert(
        workstream_id, team.id, team.key, form.title, user.id,
        description=form.description, status=form.status, priority=form.priority,
        assignee_id=form.assignee_id, due_date=form.due_date, labels=form.labels, db=db,
    )
    await emit_event('workos:task.created', f'workos:workstream:{workstream_id}', task.model_dump())
    return task


@router.get('/tasks/{task_id}')
async def get_task(
    request: Request, task_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    task, _ = await require_task_visible(user, task_id, db)
    return task


@router.patch('/tasks/{task_id}')
async def update_task(
    request: Request, task_id: str, form: TaskUpdateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    task, _ = await require_task_visible(user, task_id, db)
    fields = form.model_dump(exclude_none=True)
    _validate_task_fields(fields)
    updated = await Tasks.update_fields(task_id, fields, db=db)
    await emit_event('workos:task.updated', f'workos:workstream:{updated.workstream_id}', updated.model_dump())
    return updated


@router.delete('/tasks/{task_id}')
async def delete_task(
    request: Request, task_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    task, stream = await require_task_visible(user, task_id, db)
    ws = await Workspaces.get_by_id(stream.workspace_id, db=db)
    is_admin = (await team_role(user, ws.team_id, db)) in {'owner', 'admin'}
    if not is_admin and task.created_by_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Only the creator or an admin may delete.')
    deleted = await Tasks.delete(task_id, db=db)
    await emit_event('workos:task.deleted', f'workos:workstream:{task.workstream_id}', {'id': task_id, 'workstream_id': task.workstream_id})
    return {'deleted': deleted}


# ──────────────────────────────── label endpoints ────────────────────────────────


@router.get('/teams/{team_id}/labels')
async def list_labels(
    request: Request, team_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    await require_team_visible(user, team_id, db)
    return await Labels.list_for_team(team_id, db=db)


@router.post('/teams/{team_id}/labels')
async def create_label(
    request: Request, team_id: str, form: LabelForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    await require_team_role(user, team_id, db, {'owner', 'admin'})
    return await Labels.insert(team_id, form.name, form.color, db=db)


@router.patch('/labels/{label_id}')
async def update_label(
    request: Request, label_id: str, form: LabelUpdateForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    existing = await Labels.update_fields(label_id, {}, db=db)  # fetch-only to read team_id
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Label not found.')
    await require_team_role(user, existing.team_id, db, {'owner', 'admin'})
    return await Labels.update_fields(label_id, form.model_dump(exclude_none=True), db=db)


@router.delete('/labels/{label_id}')
async def delete_label(
    request: Request, label_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    existing = await Labels.update_fields(label_id, {}, db=db)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Label not found.')
    await require_team_role(user, existing.team_id, db, {'owner', 'admin'})
    return {'deleted': await Labels.delete(label_id, db=db)}


# ──────────────────────────────── admin settings schema ────────────────────────────────


class SettingsForm(BaseModel):
    team_creation: Optional[str] = None
    default_workspace_visibility: Optional[str] = None


# ──────────────────────────────── admin endpoints ────────────────────────────────


@router.get('/admin/teams')
async def admin_list_teams(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos_admin(request, user, db)
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
    await _require_workos_admin(request, user, db)
    return request.app.state.config.WORKOS_RULES


@router.patch('/admin/settings')
async def admin_update_settings(
    request: Request, form: SettingsForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos_admin(request, user, db)
    if form.team_creation is not None and form.team_creation not in {'all_users', 'admins_only'}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid team_creation.')
    if form.default_workspace_visibility is not None and form.default_workspace_visibility not in {'team', 'restricted'}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid default_workspace_visibility.')
    rules = dict(request.app.state.config.WORKOS_RULES or {})
    rules.update(form.model_dump(exclude_none=True))
    request.app.state.config.WORKOS_RULES = rules
    return request.app.state.config.WORKOS_RULES


# ──────────────────────────────── collaboration: schemas ────────────────────────────────


class CommentForm(BaseModel):
    body: str


# ──────────────────────────────── collaboration: helpers ────────────────────────────────


def _notif_enabled(request: Request, type: str) -> bool:
    rules = request.app.state.config.WORKOS_RULES or {}
    cfg = rules.get('notifications') or {}
    return cfg.get(type, True)


async def _actor_name(user) -> str:
    return getattr(user, 'name', None) or user.id


async def notify(
    request: Request, db, *, recipients: set, actor, type: str, task, comment_id=None, snippet=None, extra=None,
):
    """Create + deliver one notification per recipient (minus the actor)."""
    if not _notif_enabled(request, type):
        return []
    targets = {r for r in recipients if r and r != actor.id}
    if not targets:
        return []
    data = {
        'task_id': task.id, 'task_key': task.key, 'task_title': task.title,
        'workstream_id': task.workstream_id, 'actor_name': await _actor_name(actor),
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
    """Creator + assignee + distinct comment authors + users mentioned on existing comments."""
    out: set = set()
    if task.created_by_id:
        out.add(task.created_by_id)
    if task.assignee_id:
        out.add(task.assignee_id)
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
    await _require_workos(request, user, db)
    await require_task_visible(user, task_id, db)
    return await Comments.list_for_task(task_id, db=db)


@router.post('/tasks/{task_id}/comments')
async def create_comment(
    request: Request, task_id: str, form: CommentForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    task, _ = await require_task_visible(user, task_id, db)
    body = (form.body or '').strip()
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Comment body required.')
    mentions = parse_mentions(body)
    comment = await Comments.insert(task_id, user.id, body, mentions, db=db)
    activity = await Activity.insert(task_id, task.team_id, user.id, 'comment_added', {}, db=db)
    payload = {**comment.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id}
    await _emit_task_room('workos:comment.created', task, payload)
    await _emit_task_room('workos:activity.created',
                          task, {**activity.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id})
    # Notification fan-out: mentioned first, then commented (minus those mentioned).
    mentioned = {m for m in mentions if await can_see_workstream(m, False, task.workstream_id, db=db)}
    await notify(request, db, recipients=mentioned, actor=user, type='mentioned', task=task,
                 comment_id=comment.id, snippet=body)
    participants = await _participants(task, db) - mentioned
    await notify(request, db, recipients=participants, actor=user, type='commented', task=task,
                 comment_id=comment.id, snippet=body)
    return comment


@router.patch('/comments/{comment_id}')
async def update_comment(
    request: Request, comment_id: str, form: CommentForm,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session),
):
    await _require_workos(request, user, db)
    existing = await Comments.get_by_id(comment_id, db=db)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Comment not found.')
    task, _ = await require_task_visible(user, existing.task_id, db)
    if existing.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Only the author may edit.')
    body = (form.body or '').strip()
    if not body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Comment body required.')
    new_mentions = parse_mentions(body)
    updated = await Comments.update_body(comment_id, body, new_mentions, db=db)
    payload = {**updated.model_dump(), 'workstream_id': task.workstream_id, 'actor_id': user.id}
    await _emit_task_room('workos:comment.updated', task, payload)
    # Only notify mentions that are newly added on this edit.
    fresh = {m for m in new_mentions if m not in (existing.mentions or [])
             and await can_see_workstream(m, False, task.workstream_id, db=db)}
    await notify(request, db, recipients=fresh, actor=user, type='mentioned', task=task,
                 comment_id=comment_id, snippet=body)
    return updated


@router.delete('/comments/{comment_id}')
async def delete_comment(
    request: Request, comment_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    existing = await Comments.get_by_id(comment_id, db=db)
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Comment not found.')
    task, stream = await require_task_visible(user, existing.task_id, db)
    ws = await Workspaces.get_by_id(stream.workspace_id, db=db)
    is_admin = (await team_role(user, ws.team_id, db)) in {'owner', 'admin'}
    if not is_admin and existing.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Only the author or an admin may delete.')
    deleted = await Comments.delete(comment_id, db=db)
    await _emit_task_room('workos:comment.deleted',
                          task, {'id': comment_id, 'task_id': task.id, 'workstream_id': task.workstream_id,
                                 'actor_id': user.id})
    return {'deleted': deleted}


@router.get('/tasks/{task_id}/activity')
async def list_activity(
    request: Request, task_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    await require_task_visible(user, task_id, db)
    return await Activity.list_for_task(task_id, db=db)
