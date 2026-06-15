import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.constants import ERROR_MESSAGES
from open_webui.internal.db import get_async_session
from open_webui.models.policy_review import (
    PolicyChecklistVersions,
    PolicyReviews,
    PolicyLibrary,
    PolicyAudits,
)

log = logging.getLogger(__name__)

router = APIRouter()


# ──────────────────────────── lazy auth / access helpers ────────────────────
# Deferred so importing this module does NOT trigger open_webui.config at
# collection time (config queries the DB synchronously; test DBs may not have
# that table yet).  Tests monkeypatch `has_permission` and override
# `get_verified_user` on the dependency directly.


async def get_verified_user(request: Request = None):  # pragma: no cover
    """Thin async shim — resolved lazily so tests can override via dependency_overrides."""
    from open_webui.utils.auth import get_verified_user as _real
    # This function is never actually called in production: FastAPI resolves
    # `get_verified_user` from open_webui.utils.auth directly via the app-level
    # wiring in main.py.  In tests, dependency_overrides replaces this exact
    # function object, so the body never executes in tests either.
    return await _real(request)  # type: ignore[arg-type]


async def has_permission(user_id, key, user_permissions, db=None):
    """Thin async shim — resolved lazily; monkeypatched by tests."""
    from open_webui.utils.access_control import has_permission as _hp
    return await _hp(user_id, key, user_permissions, db=db)


async def _compute_scores(*args, **kwargs):
    """Thin shim for compute_scores — resolved lazily."""
    from open_webui.utils.policy_review.scoring import compute_scores as _fn
    return _fn(*args, **kwargs)


# ──────────────────────────── permission guard ────────────────────────────


async def _require(request: Request, user, key: str, db: AsyncSession) -> None:
    """Raise 401 unless the user is an admin or holds features.<key>."""
    if user.role != 'admin' and not await has_permission(
        user.id, f'features.{key}', request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.UNAUTHORIZED)


# ──────────────────────────── checklist ────────────────────────────


class ChecklistDataForm(BaseModel):
    data: dict


@router.get('/checklist/active')
async def get_active_checklist(
    request: Request,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    active = await PolicyChecklistVersions.get_active(db=db)
    if not active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    return active


@router.get('/checklist/versions')
async def list_checklist_versions(
    request: Request,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require(request, user, 'policy_admin', db)
    return await PolicyChecklistVersions.list_versions(db=db)


@router.get('/checklist/versions/{version_id}')
async def get_checklist_version(
    request: Request,
    version_id: str,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require(request, user, 'policy_admin', db)
    version = await PolicyChecklistVersions.get_by_id(version_id, db=db)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    return version


@router.get('/checklist/draft')
async def get_checklist_draft(
    request: Request,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require(request, user, 'policy_admin', db)
    return await PolicyChecklistVersions.get_draft(db=db)


@router.post('/checklist/draft')
async def start_checklist_draft(
    request: Request,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require(request, user, 'policy_admin', db)
    draft = await PolicyChecklistVersions.start_draft(db=db)
    if not draft:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='No active version to clone.')
    return draft


@router.put('/checklist/draft')
async def save_checklist_draft(
    request: Request,
    form: ChecklistDataForm,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require(request, user, 'policy_admin', db)
    saved = await PolicyChecklistVersions.save_draft(form.data, db=db)
    if not saved:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No draft to save.')
    return saved


@router.delete('/checklist/draft')
async def discard_checklist_draft(
    request: Request,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require(request, user, 'policy_admin', db)
    await PolicyChecklistVersions.discard_draft(db=db)
    return {'success': True}


def _validate_checklist_data(data: dict) -> list[str]:
    """Mirror checklist.ts validateDraft."""
    errors: list[str] = []
    themes = data.get('themes', [])
    sections = data.get('sections', [])
    weight_sum = sum(t.get('weight', 0) for t in themes)
    if round(weight_sum) != 100:
        errors.append(f'Theme weights must sum to 100% (currently {round(weight_sum)}%).')
    for t in themes:
        secs = [s for s in sections if s.get('theme') == t['id']]
        if not secs:
            errors.append(f"Theme {t['id']} has no PRP groups.")
        if sum(len(s.get('items', [])) for s in secs) == 0:
            errors.append(f"Theme {t['id']} has no items.")
    for s in sections:
        if not s.get('items'):
            errors.append(f"Group {s['id']} has no items.")
    return errors


@router.post('/checklist/draft/publish')
async def publish_checklist_draft(
    request: Request,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require(request, user, 'policy_admin', db)
    draft = await PolicyChecklistVersions.get_draft(db=db)
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No draft to publish.')
    errors = _validate_checklist_data(draft.data or {})
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=' '.join(errors))
    published = await PolicyChecklistVersions.publish_draft(by_id=user.id, by_name=user.name, db=db)
    await PolicyAudits.insert('checklist', published.id, 'checklist_published', user.id, user.name, {'label': published.label}, db=db)
    return published
