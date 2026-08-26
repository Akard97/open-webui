import json
import logging
import mimetypes
import re
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.constants import ERROR_MESSAGES
from open_webui.env import DATA_DIR
from open_webui.internal.db import get_async_session
from open_webui.models.access_grants import AccessGrants
from open_webui.models.sites import SiteModel, Sites
from open_webui.models.users import Users
from open_webui.utils.access_control import has_permission
from open_webui.utils.auth import get_verified_user

log = logging.getLogger(__name__)

SITES_DIR = DATA_DIR / 'sites'
SITES_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILES_PER_SITE = 30
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_SITE_SIZE = 30 * 1024 * 1024  # 30 MB

SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]{1,58}[a-z0-9]$')
FILENAME_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._ -]{0,127}$')

router = APIRouter()


class SiteResponse(SiteModel):
    access_grants: list = []
    user_name: Optional[str] = None


class SiteAccessForm(BaseModel):
    public: bool
    access_grants: list[dict] = []


async def _require_publisher(request: Request, user, db: AsyncSession) -> None:
    """Raise 401 unless the user is an admin or holds features.site_publisher."""
    if user.role != 'admin' and not await has_permission(
        user.id, 'features.site_publisher', request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.UNAUTHORIZED)


def _bad(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


async def _validate_files(uploads: list[UploadFile]) -> list[tuple[str, bytes, str]]:
    """Validate names/sizes/limits; return [(name, content, content_type)]."""
    if not uploads:
        raise _bad('At least one file is required.')
    if len(uploads) > MAX_FILES_PER_SITE:
        raise _bad(f'A site can have at most {MAX_FILES_PER_SITE} files.')

    validated: list[tuple[str, bytes, str]] = []
    seen: set[str] = set()
    total = 0
    for upload in uploads:
        name = (upload.filename or '').strip()
        if not FILENAME_RE.match(name):
            raise _bad(f'Invalid file name: {name!r}')
        if name in seen:
            raise _bad(f'Duplicate file name: {name!r}')
        seen.add(name)
        content = await upload.read()
        if len(content) > MAX_FILE_SIZE:
            raise _bad(f'{name!r} exceeds the {MAX_FILE_SIZE // (1024 * 1024)} MB per-file limit.')
        total += len(content)
        if total > MAX_SITE_SIZE:
            raise _bad(f'Site exceeds the {MAX_SITE_SIZE // (1024 * 1024)} MB total size limit.')
        content_type = mimetypes.guess_type(name)[0] or 'application/octet-stream'
        validated.append((name, content, content_type))
    return validated


def _pick_entry(names: list[str], requested: Optional[str]) -> str:
    htmls = [n for n in names if n.lower().endswith(('.html', '.htm'))]
    if not htmls:
        raise _bad('A site must contain at least one HTML file.')
    if requested:
        if requested not in htmls:
            raise _bad('entry_file must be one of the uploaded HTML files.')
        return requested
    if len(htmls) == 1:
        return htmls[0]
    if 'index.html' in htmls:
        return 'index.html'
    raise _bad('Multiple HTML files uploaded — specify entry_file.')


def _parse_grants(raw: str) -> list[dict]:
    try:
        grants = json.loads(raw)
    except json.JSONDecodeError:
        raise _bad('access_grants must be valid JSON.')
    if not isinstance(grants, list):
        raise _bad('access_grants must be a JSON list.')
    return grants


def _write_site_dir(site_id: str, validated: list[tuple[str, bytes, str]]) -> None:
    site_dir = SITES_DIR / site_id
    if site_dir.exists():
        shutil.rmtree(site_dir)
    site_dir.mkdir(parents=True)
    for name, content, _ in validated:
        (site_dir / name).write_bytes(content)


def _manifest(validated: list[tuple[str, bytes, str]]) -> list[dict]:
    return [{'name': n, 'size': len(c), 'content_type': t} for n, c, t in validated]


async def _site_response(site: SiteModel, db: AsyncSession, *, with_user: bool = False) -> SiteResponse:
    grants = await AccessGrants.get_grants_by_resource('site', site.id, db=db)
    user_name = None
    if with_user:
        owner = await Users.get_user_by_id(site.user_id)
        user_name = owner.name if owner else None
    return SiteResponse(
        **site.model_dump(),
        access_grants=[
            {'principal_type': g.principal_type, 'principal_id': g.principal_id, 'permission': g.permission}
            for g in grants
        ],
        user_name=user_name,
    )


@router.get('/', response_model=list[SiteResponse])
async def list_sites(
    request: Request,
    all: bool = False,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require_publisher(request, user, db)
    if all and user.role == 'admin':
        sites = await Sites.get_all_sites(db=db)
        return [await _site_response(s, db, with_user=True) for s in sites]
    sites = await Sites.get_sites_by_user_id(user.id, db=db)
    return [await _site_response(s, db) for s in sites]


@router.post('/', response_model=SiteResponse)
async def create_site(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    public: bool = Form(False),
    entry_file: Optional[str] = Form(None),
    access_grants: str = Form('[]'),
    files: list[UploadFile] = File(...),
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require_publisher(request, user, db)

    name = name.strip()
    if not name:
        raise _bad('Name is required.')
    if not SLUG_RE.match(slug):
        raise _bad('Slug must be 3-60 characters: lowercase letters, digits, hyphens; no leading/trailing hyphen.')
    grants = _parse_grants(access_grants)
    if await Sites.get_site_by_slug(slug, db=db):
        raise _bad('This link is already taken.')

    validated = await _validate_files(files)
    entry = _pick_entry([v[0] for v in validated], entry_file)

    site = await Sites.insert_new_site(
        user.id, name=name, slug=slug, public=public, files=_manifest(validated), entry_file=entry, db=db
    )
    if site is None:
        raise _bad('This link is already taken.')

    try:
        _write_site_dir(site.id, validated)
        await AccessGrants.set_access_grants('site', site.id, grants, db=db)
    except Exception:
        # Roll back to a consistent state: no half-created site may remain.
        shutil.rmtree(SITES_DIR / site.id, ignore_errors=True)
        await Sites.delete_site_by_id(site.id, db=db)
        raise
    return await _site_response(site, db)


@router.get('/{id}', response_model=SiteResponse)
async def get_site(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require_publisher(request, user, db)
    site = await Sites.get_site_by_id(id, db=db)
    if not site or (site.user_id != user.id and user.role != 'admin'):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    return await _site_response(site, db, with_user=user.role == 'admin')
