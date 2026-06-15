import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.constants import ERROR_MESSAGES
from open_webui.internal.db import get_async_session
from open_webui.utils.auth import get_verified_user
from open_webui.utils.access_control import has_permission
from open_webui.utils.policy_review.scoring import compute_scores
from open_webui.models.policy_review import (
    PolicyChecklistVersions,
    PolicyReviews,
    PolicyLibrary,
    PolicyAudits,
)

log = logging.getLogger(__name__)

router = APIRouter()


def _audit_now() -> str:
    # Human-readable stamp matching the frontend's display style; stored in `approval`.
    return time.strftime('%d %b, %H:%M', time.gmtime())


# ──────────────────────────── helpers ────────────────────────────


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
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    active = await PolicyChecklistVersions.get_active(db=db)
    if not active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    return active


@router.get('/checklist/versions')
async def list_checklist_versions(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_admin', db)
    return await PolicyChecklistVersions.list_versions(db=db)


@router.get('/checklist/versions/{version_id}')
async def get_checklist_version(
    request: Request, version_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_admin', db)
    version = await PolicyChecklistVersions.get_by_id(version_id, db=db)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    return version


@router.get('/checklist/draft')
async def get_checklist_draft(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_admin', db)
    return await PolicyChecklistVersions.get_draft(db=db)


@router.post('/checklist/draft')
async def start_checklist_draft(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_admin', db)
    draft = await PolicyChecklistVersions.start_draft(db=db)
    if not draft:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='No active version to clone.')
    return draft


@router.put('/checklist/draft')
async def save_checklist_draft(
    request: Request, form: ChecklistDataForm, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_admin', db)
    saved = await PolicyChecklistVersions.save_draft(form.data, db=db)
    if not saved:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No draft to save.')
    return saved


@router.delete('/checklist/draft')
async def discard_checklist_draft(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
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
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
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


# ──────────────────────────── reviews ────────────────────────────


class ReviewCreateForm(BaseModel):
    policy_meta: dict
    strengths: Optional[list] = None


class ResultsForm(BaseModel):
    results: dict


class NoteForm(BaseModel):
    note: Optional[str] = ''


async def _load_owned_or_403(review_id: str, user, db, *, approver_ok: bool = False):
    review = await PolicyReviews.get_by_id(review_id, db=db)
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    is_owner = review.created_by_id is not None and review.created_by_id == user.id
    if is_owner or user.role == 'admin':
        return review
    if approver_ok:
        return review
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.ACCESS_PROHIBITED)


@router.post('/reviews')
async def create_review(
    request: Request, form: ReviewCreateForm, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_checker', db)
    active = await PolicyChecklistVersions.get_active(db=db)
    if not active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='No active checklist version.')
    review = await PolicyReviews.insert_review(
        created_by_id=user.id,
        created_by_name=user.name,
        policy_meta=form.policy_meta,
        active_version=active,
        strengths=form.strengths or [],
        db=db,
    )
    await PolicyAudits.insert('review', review.id, 'created', user.id, user.name, None, db=db)
    return review


@router.get('/reviews/mine')
async def list_my_reviews(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_checker', db)
    return await PolicyReviews.list_by_creator(user.id, db=db)


@router.get('/reviews/queue')
async def list_approval_queue(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_approver', db)
    return await PolicyReviews.list_by_status('pending', db=db)


@router.get('/reviews/{review_id}')
async def get_review(
    request: Request, review_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    # Owner, admin, or any approver may read.
    is_approver = user.role == 'admin' or await has_permission(
        user.id, 'features.policy_approver', request.app.state.config.USER_PERMISSIONS, db=db
    )
    return await _load_owned_or_403(review_id, user, db, approver_ok=is_approver)


@router.patch('/reviews/{review_id}/results')
async def update_review_results(
    request: Request, review_id: str, form: ResultsForm, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_checker', db)
    review = await _load_owned_or_403(review_id, user, db)
    if review.status not in ('draft', 'rejected'):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Review is locked.')
    merged = {**(review.results or {})}
    for item_id, patch in form.results.items():
        merged[item_id] = {**(merged.get(item_id) or {}), **patch}
    fields = {'results': merged}
    if review.status == 'rejected':
        fields['status'] = 'draft'  # editing a returned review reopens it
        await PolicyAudits.insert('review', review_id, 'reopened', user.id, user.name, None, db=db)
    updated = await PolicyReviews.update_fields(review_id, fields, db=db)
    await PolicyAudits.insert('review', review_id, 'updated', user.id, user.name, None, db=db)
    return updated


@router.post('/reviews/{review_id}/submit')
async def submit_review(
    request: Request, review_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_checker', db)
    review = await _load_owned_or_403(review_id, user, db)
    if review.status != 'draft':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Only a draft can be submitted.')
    score = compute_scores(review.checklist_snapshot or {}, review.results or {})
    if score['humanItemsRemain']:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Resolve all items before submitting.')
    approval = {**(review.approval or {}), 'status': 'pending', 'sentAt': _audit_now(), 'note': ''}
    updated = await PolicyReviews.update_fields(review_id, {'status': 'pending', 'approval': approval}, db=db)
    await PolicyAudits.insert('review', review_id, 'submitted', user.id, user.name, None, db=db)
    return updated


@router.post('/reviews/{review_id}/approve')
async def approve_review(
    request: Request, review_id: str, form: NoteForm, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_approver', db)
    review = await PolicyReviews.get_by_id(review_id, db=db)
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    if review.status != 'pending':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Only a pending review can be approved.')
    score = compute_scores(review.checklist_snapshot or {}, review.results or {})
    approval = {
        **(review.approval or {}),
        'status': 'approved',
        'decidedAt': _audit_now(),
        'decidedBy': user.name,
        'note': (form.note or '').strip() or 'Approved for issuance and published to the policy library.',
    }
    updated = await PolicyReviews.update_fields(review_id, {'status': 'approved', 'approval': approval}, db=db)
    # Upsert into the library.
    meta = review.policy_meta or {}
    fn = (meta.get('code', '').split('-')[1] if '-' in meta.get('code', '') else 'GOV')
    library_data = {
        'code': meta.get('code'),
        'title': meta.get('name'),
        'fn': fn,
        'owner': meta.get('owner'),
        'version': str(meta.get('version', '')).lstrip('v'),
        'status': 'approved',
        'score': score['overall'],
        'pages': meta.get('pages'),
        'nextReview': '—',
        'updatedDays': 0,
    }
    await PolicyLibrary.upsert(code=meta.get('code'), data=library_data, source_review_id=review_id, db=db)
    await PolicyAudits.insert('review', review_id, 'approved', user.id, user.name, {'score': score['overall']}, db=db)
    await PolicyAudits.insert('review', review_id, 'published', user.id, user.name, {'code': meta.get('code')}, db=db)
    return updated


@router.post('/reviews/{review_id}/reject')
async def reject_review(
    request: Request, review_id: str, form: NoteForm, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_approver', db)
    review = await PolicyReviews.get_by_id(review_id, db=db)
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    if review.status != 'pending':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Only a pending review can be rejected.')
    if not (form.note or '').strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='A rejection note is required.')
    approval = {
        **(review.approval or {}),
        'status': 'rejected',
        'decidedAt': _audit_now(),
        'decidedBy': user.name,
        'note': form.note.strip(),
    }
    updated = await PolicyReviews.update_fields(review_id, {'status': 'rejected', 'approval': approval}, db=db)
    await PolicyAudits.insert('review', review_id, 'rejected', user.id, user.name, {'note': form.note.strip()}, db=db)
    return updated


# ──────────────────────────── library ────────────────────────────


@router.get('/library')
async def list_library(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    return await PolicyLibrary.list_all(db=db)


@router.get('/library/{code}')
async def get_library_entry(
    request: Request, code: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    entry = await PolicyLibrary.get_by_code(code, db=db)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    return entry
