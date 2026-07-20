"""Service-to-service WorkOS read API for the Osool AI backend.

On-behalf-of endpoints: the caller (osool-api) presents a shared service
secret and names the acting user in the path. Every visibility decision is
delegated to open_webui.utils.workos_access — the single source of truth —
so parity with the UI is structural, not re-implemented.

Read-only by construction: this router registers GET handlers only (a test
asserts this). Mounted by main.py ONLY when WORKOS_SERVICE_SECRET is set,
with include_in_schema=False so the routes never appear in the OpenAPI doc;
the reverse proxy additionally blocks /api/v1/workos/internal/* from outside.
"""

import os
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.internal.db import get_async_session
from open_webui.models.workos import Attachments, Comments, Subtasks, Tasks
from open_webui.routers.workos import resolve_user_names, visible_my_tasks, visible_tree
from open_webui.utils.workos_access import (
    require_task_visible, require_workos, require_workstream_visible,
)

router = APIRouter()


def require_service_token(x_service_token: str = Header(default='')) -> None:
    secret = os.environ.get('WORKOS_SERVICE_SECRET', '')
    # Compare bytes: compare_digest on str raises TypeError (-> 500) if the
    # header smuggles a non-ASCII char; encoded, it stays a clean 401.
    if not secret or not secrets.compare_digest(x_service_token.encode(), secret.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid service token.')


async def _load_user(user_id: str):
    # Wrapper around the Users DAO so tests can monkeypatch a fast stub
    # (same pattern as resolve_user_names in routers/workos.py).
    from open_webui.models.users import Users

    return await Users.get_user_by_id(user_id)


async def _acting_user(request: Request, user_id: str, db: AsyncSession):
    user = await _load_user(user_id)
    # Mirror get_verified_user's role gate on the public routes: only active
    # roles act. 404 (not 401) keeps a pending account indistinguishable
    # from a nonexistent one.
    if not user or user.role not in ('user', 'admin'):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found.')
    await require_workos(request, user, db)
    return user


async def _user_names(*id_groups) -> dict:
    ids: set = set()
    for group in id_groups:
        ids.update(i for i in group if i)
    return {u['id']: u['name'] for u in await resolve_user_names(sorted(ids))}


@router.get('/users/{user_id}/bootstrap', dependencies=[Depends(require_service_token)])
async def internal_bootstrap(
    request: Request, user_id: str, db: AsyncSession = Depends(get_async_session)
):
    user = await _acting_user(request, user_id, db)
    teams, workspaces, workstreams = await visible_tree(user, db)
    return {'teams': teams, 'workspaces': workspaces, 'workstreams': workstreams}


def _task_name_groups(tasks):
    groups = [t.assignee_ids or [] for t in tasks]
    groups.append([t.created_by_id for t in tasks])
    return groups


@router.get('/users/{user_id}/tasks', dependencies=[Depends(require_service_token)])
async def internal_my_tasks(
    request: Request, user_id: str, db: AsyncSession = Depends(get_async_session)
):
    user = await _acting_user(request, user_id, db)
    tasks = await visible_my_tasks(user, db)
    return {'tasks': tasks, 'users': await _user_names(*_task_name_groups(tasks))}


@router.get('/users/{user_id}/workstreams/{workstream_id}/tasks',
            dependencies=[Depends(require_service_token)])
async def internal_workstream_tasks(
    request: Request, user_id: str, workstream_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    user = await _acting_user(request, user_id, db)
    await require_workstream_visible(user, workstream_id, db)
    tasks = await Tasks.list_for_workstream(workstream_id, db=db)
    return {'tasks': tasks, 'users': await _user_names(*_task_name_groups(tasks))}


@router.get('/users/{user_id}/tasks/{task_id}', dependencies=[Depends(require_service_token)])
async def internal_task_detail(
    request: Request, user_id: str, task_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    user = await _acting_user(request, user_id, db)
    task, _ = await require_task_visible(user, task_id, db)
    subtasks = await Subtasks.list_for_task(task_id, db=db)
    comments = await Comments.list_for_task(task_id, db=db)
    attachments = await Attachments.list_for_task(task_id, db=db)
    users = await _user_names(
        task.assignee_ids or [], [task.created_by_id],
        [c.user_id for c in comments],
        [s.created_by_id for s in subtasks],
        [a.created_by_id for a in attachments],
    )
    return {
        'task': task, 'subtasks': subtasks, 'comments': comments,
        # storage_key stays server-side: it is a storage-layer path, useless
        # and mildly leaky outside this process.
        'attachments': [
            {'id': a.id, 'name': a.name, 'size': a.size, 'content_type': a.content_type,
             'created_by_id': a.created_by_id, 'created_at': a.created_at}
            for a in attachments
        ],
        'users': users,
    }


def mount(app) -> bool:
    """Mount the internal API iff WORKOS_SERVICE_SECRET is set (fail closed).
    Hidden from the OpenAPI schema; the reverse proxy also blocks the prefix
    from outside. Returns whether the router was mounted."""
    if not os.environ.get('WORKOS_SERVICE_SECRET'):
        return False
    app.include_router(
        router, prefix='/api/v1/workos/internal',
        include_in_schema=False, tags=['workos-internal'],
    )
    return True
