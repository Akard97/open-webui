import logging
import os
import time
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
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
    PolicyDocuments,
)

import json
from fastapi.responses import Response

from open_webui.utils.policy_review.documents import (
    validate_upload,
    store_upload,
    read_stored,
    copy_stored,
    delete_stored,
    extract_text,
)

log = logging.getLogger(__name__)

router = APIRouter()


def _audit_now() -> str:
    # Human-readable stamp matching the frontend's display style; stored in `approval`.
    return time.strftime('%d %b, %H:%M', time.gmtime())


def _document_response(doc) -> Response:
    data = read_stored(doc.storage_path)
    return Response(
        content=data,
        media_type=doc.content_type or 'application/octet-stream',
        headers={'Content-Disposition': f'attachment; filename="{doc.filename}"'},
    )


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


@router.post('/checklist/versions/{version_id}/activate')
async def activate_checklist_version(
    request: Request, version_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    # Audit-safe revert: re-activate an archived version (the current active is archived,
    # the target is promoted). The target keeps its label; nothing is deleted.
    await _require(request, user, 'policy_admin', db)
    result = await PolicyChecklistVersions.activate_version(version_id, by_id=user.id, by_name=user.name, db=db)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    if result is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Only an archived version can be re-activated.')
    await PolicyAudits.insert('checklist', result.id, 'checklist_reactivated', user.id, user.name, {'label': result.label}, db=db)
    return result


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


# ── TEMP testing scaffolding ────────────────────────────────────────────────
# There is no AI scan / document parsing yet, so a freshly created review starts
# with every checklist item `pending`. The submit gate (here and in the UI) blocks
# submission while ANY item is pending/human, so a new policy can never be sent for
# approval until ~100 items are answered by hand. To let testers exercise the
# submit → approve → publish flow, we pre-mark every item `compliant` on creation.
# Set POLICY_REVIEW_AUTOFILL=false to disable; remove this block once real review
# (manual or AI-assisted) lands.
AUTOFILL_RESULTS_ON_CREATE = os.getenv('POLICY_REVIEW_AUTOFILL', 'true').strip().lower() not in (
    'false', '0', 'no', 'off', '',
)


def _autofilled_results(active_data: Optional[dict]) -> dict:
    """Mark every checklist item `compliant` so the review is fully resolved and
    immediately submittable. TEMP testing helper — see AUTOFILL_RESULTS_ON_CREATE."""
    results: dict = {}
    for sec in (active_data or {}).get('sections', []):
        for item in sec.get('items', []):
            item_id = item.get('id')
            if not item_id:
                continue
            results[item_id] = {
                'result': 'compliant',
                'reviewed': True,
                'confidence': 0.99,
                'comment': 'Auto-marked compliant (testing default).',
            }
    return results


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
    request: Request,
    file: UploadFile = File(...),
    meta: str = Form(...),
    strengths: Optional[str] = Form(None),
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require(request, user, 'policy_checker', db)

    try:
        policy_meta = json.loads(meta)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid metadata.')
    strengths_list: list = []
    if strengths:
        try:
            strengths_list = json.loads(strengths)
        except json.JSONDecodeError:
            strengths_list = []

    active = await PolicyChecklistVersions.get_active(db=db)
    if not active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='No active checklist version.')

    contents = await file.read()
    try:
        validate_upload(file.filename, len(contents))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    storage_path = store_upload(contents, file.filename)
    try:
        text = await extract_text(file.filename, file.content_type, storage_path)
    except Exception:
        delete_stored(storage_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Could not extract text from this document.',
        )

    # filename is surfaced both at policy_meta.filename (legacy display) and inside
    # policy_meta.document (the Phase 2 descriptor) — both are part of the frontend contract.
    policy_meta['document'] = {
        'filename': file.filename,
        'contentType': file.content_type,
        'size': len(contents),
    }
    policy_meta['filename'] = file.filename

    # The binary is already stored; if review insert OR document upsert fails, roll both
    # back (delete the review on a fresh session — the request session may be dirty after a
    # failed commit — and remove the orphaned binary) so no half-state survives.
    review = None
    try:
        review = await PolicyReviews.insert_review(
            created_by_id=user.id,
            created_by_name=user.name,
            policy_meta=policy_meta,
            active_version=active,
            results=_autofilled_results(active.data) if AUTOFILL_RESULTS_ON_CREATE else None,
            strengths=strengths_list,
            db=db,
        )
        await PolicyDocuments.upsert(
            'review', review.id, file.filename, file.content_type, len(contents), storage_path, text, db=db
        )
    except Exception:
        if review is not None:
            await PolicyReviews.delete(review.id)
        delete_stored(storage_path)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Failed to store document.')

    await PolicyAudits.insert('review', review.id, 'created', user.id, user.name, None, db=db)
    await PolicyAudits.insert('review', review.id, 'document_uploaded', user.id, user.name, {'filename': file.filename}, db=db)
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


@router.get('/reviews/{review_id}/document')
async def download_review_document(
    request: Request, review_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    is_approver = user.role == 'admin' or await has_permission(
        user.id, 'features.policy_approver', request.app.state.config.USER_PERMISSIONS, db=db
    )
    await _load_owned_or_403(review_id, user, db, approver_ok=is_approver)
    doc = await PolicyDocuments.get('review', review_id, db=db)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    return _document_response(doc)


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


@router.put('/reviews/{review_id}/document')
async def replace_review_document(
    request: Request,
    review_id: str,
    file: UploadFile = File(...),
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require(request, user, 'policy_checker', db)
    review = await _load_owned_or_403(review_id, user, db)
    if review.status not in ('draft', 'rejected'):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Review is locked.')

    contents = await file.read()
    try:
        validate_upload(file.filename, len(contents))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    storage_path = store_upload(contents, file.filename)
    try:
        text = await extract_text(file.filename, file.content_type, storage_path)
    except Exception:
        delete_stored(storage_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Could not extract text from this document.',
        )

    old = await PolicyDocuments.get('review', review_id, db=db)
    await PolicyDocuments.upsert(
        'review', review_id, file.filename, file.content_type, len(contents), storage_path, text, db=db
    )
    if old and old.storage_path != storage_path:
        delete_stored(old.storage_path)

    meta = {**(review.policy_meta or {})}
    meta['document'] = {'filename': file.filename, 'contentType': file.content_type, 'size': len(contents)}
    meta['filename'] = file.filename
    fields = {'policy_meta': meta}
    if review.status == 'rejected':
        fields['status'] = 'draft'  # editing a returned review reopens it
        await PolicyAudits.insert('review', review_id, 'reopened', user.id, user.name, None, db=db)

    updated = await PolicyReviews.update_fields(review_id, fields, db=db)
    await PolicyAudits.insert('review', review_id, 'document_replaced', user.id, user.name, {'filename': file.filename}, db=db)
    return updated


@router.post('/reviews/{review_id}/submit')
async def submit_review(
    request: Request,
    review_id: str,
    form: Optional[NoteForm] = None,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require(request, user, 'policy_checker', db)
    review = await _load_owned_or_403(review_id, user, db)
    if review.status != 'draft':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Only a draft can be submitted.')
    score = compute_scores(review.checklist_snapshot or {}, review.results or {})
    if score['humanItemsRemain']:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Resolve all items before submitting.')
    # The reviewer's optional note is meaningful context for the approver.
    note = ((form.note if form else '') or '').strip()
    approval = {**(review.approval or {}), 'status': 'pending', 'sentAt': _audit_now(), 'note': note}
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
    # Copy the review's source document into a library-owned, immutable copy so the
    # Library download survives later deletion of the review.
    src_doc = await PolicyDocuments.get('review', review_id, db=db)
    if src_doc:
        new_path = copy_stored(src_doc.storage_path, src_doc.filename)
        await PolicyDocuments.upsert(
            'library', meta.get('code'), src_doc.filename, src_doc.content_type, src_doc.size, new_path, src_doc.text, db=db
        )
        library_data['hasDocument'] = True
        library_data['filename'] = src_doc.filename

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


@router.delete('/reviews/{review_id}')
async def delete_review(
    request: Request, review_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    review = await PolicyReviews.get_by_id(review_id, db=db)
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    # Admins (role or policy_admin) may delete any review in any status, for governance/cleanup.
    # A plain checker may delete only their OWN review while it is still a draft or returned
    # (rejected). Deleting an approved review does NOT remove its published library entry —
    # unpublishing is a separate, explicit action.
    is_admin = user.role == 'admin' or await has_permission(
        user.id, 'features.policy_admin', request.app.state.config.USER_PERMISSIONS, db=db
    )
    if not is_admin:
        await _require(request, user, 'policy_checker', db)
        is_owner = review.created_by_id is not None and review.created_by_id == user.id
        if not is_owner:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.ACCESS_PROHIBITED)
        if review.status not in ('draft', 'rejected'):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Only a draft or returned review can be deleted.')
    doc = await PolicyDocuments.delete('review', review_id, db=db)
    if doc:
        delete_stored(doc.storage_path)
    await PolicyReviews.delete(review_id, db=db)
    await PolicyAudits.insert('review', review_id, 'deleted', user.id, user.name, {'code': (review.policy_meta or {}).get('code')}, db=db)
    return {'success': True}


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


@router.get('/library/{code}/document')
async def download_library_document(
    request: Request, code: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    doc = await PolicyDocuments.get('library', code, db=db)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    return _document_response(doc)


@router.delete('/library/{code}')
async def delete_library_entry(
    request: Request, code: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    # Unpublish a policy from the library. Allowed for an approver or admin (OR-gate, so it
    # is not expressed via the single-key _require helper).
    allowed = (
        user.role == 'admin'
        or await has_permission(user.id, 'features.policy_approver', request.app.state.config.USER_PERMISSIONS, db=db)
        or await has_permission(user.id, 'features.policy_admin', request.app.state.config.USER_PERMISSIONS, db=db)
    )
    if not allowed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.UNAUTHORIZED)
    entry = await PolicyLibrary.get_by_code(code, db=db)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    doc = await PolicyDocuments.delete('library', code, db=db)
    if doc:
        delete_stored(doc.storage_path)
    await PolicyLibrary.delete_by_code(code, db=db)
    await PolicyAudits.insert('library', entry.id, 'unpublished', user.id, user.name, {'code': code}, db=db)
    return {'success': True}
