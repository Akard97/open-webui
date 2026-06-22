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
    TeamModel,
)

log = logging.getLogger(__name__)

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
