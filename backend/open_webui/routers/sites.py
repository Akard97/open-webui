import asyncio
import hashlib
import hmac
import json
import logging
import mimetypes
import os
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote
from uuid import uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.constants import ERROR_MESSAGES
from open_webui.env import (
    DATA_DIR,
    UVICORN_WORKERS,
    WEBUI_AUTH_COOKIE_SAME_SITE,
    WEBUI_AUTH_TRUSTED_EMAIL_HEADER,
    WEBUI_SECRET_KEY,
)
from open_webui.internal.db import get_async_session
from open_webui.models.access_grants import AccessGrants
from open_webui.models.sites import SiteModel, Sites, SiteViews
from open_webui.models.users import Users
from open_webui.utils.access_control import has_permission
from open_webui.utils.auth import decode_token, get_verified_user, is_valid_token

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
        # casefold: Index.html and index.html collide on a case-insensitive
        # filesystem while the manifest would list both.
        if name.casefold() in seen:
            raise _bad(f'Duplicate file name: {name!r}')
        seen.add(name.casefold())
        content = bytearray()
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            content.extend(chunk)
            if len(content) > MAX_FILE_SIZE:
                raise _bad(f'{name!r} exceeds the {MAX_FILE_SIZE // (1024 * 1024)} MB per-file limit.')
            if total + len(content) > MAX_SITE_SIZE:
                raise _bad(f'Site exceeds the {MAX_SITE_SIZE // (1024 * 1024)} MB total size limit.')
        content = bytes(content)
        total += len(content)
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


# In-process per-site write serialization. Sufficient for the single-worker
# deployment this app runs as (SQLite has the same constraint elsewhere).
# NOT safe across processes: with UVICORN_WORKERS > 1 (or multiple nodes)
# concurrent publishes to the same site can interleave dir swaps and DB
# commits — hence the startup warning below.
_site_locks: dict[str, asyncio.Lock] = {}

if UVICORN_WORKERS > 1:
    log.warning(
        'UVICORN_WORKERS=%s: Site Publisher serializes writes per-process only; '
        'concurrent publishes to the same site from different workers can corrupt '
        'site files. Run a single worker or avoid concurrent site updates.',
        UVICORN_WORKERS,
    )


def _site_lock(site_id: str) -> asyncio.Lock:
    lock = _site_locks.get(site_id)
    if lock is None:
        lock = _site_locks[site_id] = asyncio.Lock()
    return lock


def _rmtree_logged(path: Path) -> None:
    """Best-effort recursive delete: a failure must not break the request,
    but an orphaned directory must not vanish silently from the logs either."""
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass
    except OSError:
        log.warning('Failed to remove site dir %s; orphaned files remain', path, exc_info=True)


def _stage_site_dir(site_id: str, validated: list[tuple[str, bytes, str]]) -> Optional[Path]:
    """Install the uploaded files as the live dir; return the previous dir (or None).

    Files are written to a unique temp dir first, so nothing live changes until
    every write has succeeded. The previous version is renamed aside — never
    deleted — so a failed install, or a failed DB commit after it, can be
    undone with _restore_site_dir. The caller removes the returned backup once
    the whole operation has committed.
    """
    site_dir = SITES_DIR / site_id
    tmp_dir = SITES_DIR / f'{site_id}.tmp-{uuid4().hex}'
    tmp_dir.mkdir(parents=True)
    try:
        for name, content, _ in validated:
            (tmp_dir / name).write_bytes(content)
        backup = None
        if site_dir.exists():
            backup = SITES_DIR / f'{site_id}.bak-{uuid4().hex}'
            site_dir.rename(backup)
        try:
            tmp_dir.rename(site_dir)
        except Exception:
            if backup is not None:
                backup.rename(site_dir)  # put the previous version back
            raise
        return backup
    except Exception:
        _rmtree_logged(tmp_dir)
        raise


def _restore_site_dir(site_id: str, backup: Optional[Path]) -> None:
    """Undo _stage_site_dir: discard the new dir and reinstate the backup."""
    site_dir = SITES_DIR / site_id
    _rmtree_logged(site_dir)
    if backup is not None and backup.exists():
        try:
            backup.rename(site_dir)
        except OSError:
            log.exception('Failed to restore previous site dir for %s', site_id)


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

    async with _site_lock(site.id):
        try:
            _stage_site_dir(site.id, validated)
            await AccessGrants.set_access_grants('site', site.id, grants, db=db)
        except BaseException:
            # Roll back to a consistent state: no half-created site may remain.
            # BaseException: asyncio.CancelledError (client disconnect / shutdown)
            # must also trigger cleanup, and it is not an Exception.
            _rmtree_logged(SITES_DIR / site.id)
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
    site = await _get_owned_site(id, user, db)
    return await _site_response(site, db, with_user=user.role == 'admin')


async def _get_owned_site(id: str, user, db: AsyncSession) -> SiteModel:
    site = await Sites.get_site_by_id(id, db=db)
    if not site or (site.user_id != user.id and user.role != 'admin'):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    return site


ANALYTICS_WINDOWS = (7, 30, 90)


@router.get('/{id}/analytics')
async def get_site_analytics(
    request: Request,
    id: str,
    days: int = 30,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    if days not in ANALYTICS_WINDOWS:
        raise _bad(f'days must be one of {ANALYTICS_WINDOWS}')
    await _require_publisher(request, user, db)
    site = await _get_owned_site(id, user, db)
    return await SiteViews.get_analytics(site.id, days, db=db)


@router.post('/{id}/update', response_model=SiteResponse)
async def update_site(
    request: Request,
    id: str,
    name: Optional[str] = Form(None),
    slug: Optional[str] = Form(None),
    entry_file: Optional[str] = Form(None),
    files: list[UploadFile] = File(default=[]),
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require_publisher(request, user, db)
    site = await _get_owned_site(id, user, db)

    updates: dict = {}
    if name is not None:
        name = name.strip()
        if not name:
            raise _bad('Name cannot be empty.')
        updates['name'] = name
    if slug is not None and slug != site.slug:
        if not SLUG_RE.match(slug):
            raise _bad('Slug must be 3-60 characters: lowercase letters, digits, hyphens; no leading/trailing hyphen.')
        if await Sites.get_site_by_slug(slug, db=db):
            raise _bad('This link is already taken.')
        updates['slug'] = slug

    validated = None
    if files:
        validated = await _validate_files(files)
        updates['files'] = _manifest(validated)
        updates['entry_file'] = _pick_entry([v[0] for v in validated], entry_file)
    elif entry_file is not None:
        current_names = [f['name'] for f in site.files]
        updates['entry_file'] = _pick_entry(current_names, entry_file)

    if validated is not None:
        async with _site_lock(site.id):
            # Stage files BEFORE the DB commit so metadata never points at
            # files that were not installed; the previous version is kept
            # until both the install and the commit succeed.
            backup = _stage_site_dir(site.id, validated)
            try:
                updated = await Sites.update_site_by_id(site.id, updates, db=db)
                if updated is None:
                    raise _bad('This link is already taken.')
            except BaseException:
                # BaseException: a cancelled request (client disconnect) must
                # also restore the previous version, and CancelledError is not
                # an Exception. Restore is synchronous, so it completes even
                # while the task is being cancelled.
                _restore_site_dir(site.id, backup)
                raise
            if backup is not None:
                _rmtree_logged(backup)
    else:
        updated = await Sites.update_site_by_id(site.id, updates, db=db)
        if updated is None:
            raise _bad('This link is already taken.')
    return await _site_response(updated, db, with_user=user.role == 'admin')


@router.post('/{id}/access', response_model=SiteResponse)
async def update_site_access(
    request: Request,
    id: str,
    form_data: SiteAccessForm,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require_publisher(request, user, db)
    site = await _get_owned_site(id, user, db)
    # Grants and the public flag commit atomically: a partial write could
    # otherwise leave a private site readable by newly granted principals.
    updated = await Sites.update_site_access(
        site.id, public=form_data.public, access_grants=form_data.access_grants, db=db
    )
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
    return await _site_response(updated, db, with_user=user.role == 'admin')


@router.delete('/{id}')
async def delete_site(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require_publisher(request, user, db)
    site = await _get_owned_site(id, user, db)
    async with _site_lock(site.id):
        # delete_site_by_id removes the site row, its grant rows AND its view
        # rows in one transaction, so a crash mid-delete cannot orphan grants
        # or leave analytics rows behind for a site that no longer exists.
        deleted = await Sites.delete_site_by_id(site.id, db=db)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found')
        _rmtree_logged(SITES_DIR / site.id)
    return {'deleted': True}


serve_router = APIRouter()


# SECURITY: the sandbox CSP gives served pages an opaque origin, which keeps
# the viewer's token cookie off any fetch a page makes ONLY while the auth
# cookie stays SameSite=lax/strict (this app's default). If
# WEBUI_AUTH_COOKIE_SAME_SITE is set to 'none', a published page's scripts
# could call the API with the viewer's cookie via credentialed CORS (ACAO
# reflects origin 'null') — so in that configuration scripts are disabled
# entirely rather than trusting deployers to have read this comment.
def _sandbox_csp(same_site: Optional[str]) -> str:
    # Case/whitespace-insensitive: Starlette accepts any casing of the
    # samesite value ('None', 'NONE', ...), all of which yield SameSite=None
    # cookies, so all of them must disable scripts here.
    if (same_site or '').strip().lower() == 'none':
        log.warning(
            'WEBUI_AUTH_COOKIE_SAME_SITE=none: Site Publisher pages are served with '
            'scripts disabled to block credentialed API access from sandboxed pages.'
        )
        return 'sandbox'
    return 'sandbox allow-scripts'


_SANDBOX_CSP = _sandbox_csp(WEBUI_AUTH_COOKIE_SAME_SITE)

SERVE_HEADERS = {
    # Opaque origin: scripts (when allowed) cannot reach the app's
    # localStorage, cookies, or API with the viewer's credentials.
    'Content-Security-Policy': _SANDBOX_CSP,
    'X-Content-Type-Options': 'nosniff',
    'Cache-Control': 'no-cache',
}

BOT_UA_RE = re.compile(r'bot|crawl|spider|slurp|headless|curl|wget|python-requests', re.IGNORECASE)

HTML_EXT_RE = re.compile(r'\.html?$', re.IGNORECASE)


def _visitor_key(site_id: str, ip: str, user_agent: str, *, now_ms: Optional[int] = None) -> str:
    """A per-site, per-day pseudonym for a visitor.

    The UTC date inside the message rotates the salt daily, so the same person
    on two days yields unrelated keys and the table cannot reconstruct anyone's
    browsing history. The site id scopes the key, so the same person on two
    sites also yields unrelated keys. HMAC under WEBUI_SECRET_KEY means an
    attacker holding the database still cannot brute-force the small IP+UA
    space back to a raw address.
    """
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    day = datetime.fromtimestamp(now_ms / 1000, tz=timezone.utc).strftime('%Y-%m-%d')
    msg = f'{day}|{site_id}|{ip}|{user_agent}'
    digest = hmac.new(WEBUI_SECRET_KEY.encode(), msg.encode(), hashlib.sha256).digest()
    return digest[:16].hex()


def _is_bot(user_agent: str) -> bool:
    """Empty or automated User-Agents must not inflate a site's view count."""
    ua = (user_agent or '').strip()
    return not ua or bool(BOT_UA_RE.search(ua))


def _is_html(filename: str) -> bool:
    """Only documents count as views. Assets are requests, not pageviews."""
    return bool(HTML_EXT_RE.search(filename or ''))


async def _record_view(
    *,
    site_id: str,
    owner_id: str,
    filename: str,
    method: str,
    user_agent: str,
    ip: str,
    has_credentials: bool,
    request: Request,
    viewer,
) -> None:
    """Record a pageview. Runs as a background task, AFTER the response is sent.

    Nothing in here is on the response path: the filters, the HMAC, the
    token decode and the INSERT all happen once the visitor already has their
    page. Best-effort throughout — analytics must never take a published page
    down, so every failure is swallowed and logged.

    `request` comes along only because `_get_optional_user` needs
    `app.state.redis` to check token revocation, and it is touched only when
    the request actually carried credentials. Reading it here is sound:
    Starlette runs background tasks inside the still-open ASGI scope, and the
    scalars this function filters on were captured before the response anyway.
    """
    try:
        # Only a GET displays a page. HEAD (link-preview fetchers, uptime
        # monitors — often sending browser-shaped User-Agents the bot filter
        # will not catch) transfers no body and renders nothing.
        # Today these are FastAPI APIRoutes, which unlike Starlette's plain
        # Route do NOT auto-add HEAD, so such a request is already rejected
        # with 405 before reaching here. This guard is what keeps that true
        # if the routes are ever declared with methods=['GET', 'HEAD'] or
        # mounted as Starlette routes; it must not be removed as dead code.
        if method != 'GET':
            return
        if not _is_html(filename):
            return
        if _is_bot(user_agent):
            return
        if viewer is None and has_credentials:
            # Only a public site reaches here with viewer None: a private one
            # required valid credentials to resolve, and that user was passed
            # in. This is where a logged-in owner viewing their own public site
            # is recognised — and anonymous traffic, carrying no credentials,
            # pays neither a token decode nor a user lookup.
            viewer = await _get_optional_user(request)
        await SiteViews.record_view(
            site_id,
            filename,
            _visitor_key(site_id, ip, user_agent),
            bool(viewer is not None and viewer.id == owner_id),
        )
    except Exception:
        log.warning('Failed to record site view for %s', site_id, exc_info=True)


def _queue_view(site, filename: str, request: Request, background: BackgroundTasks, *, viewer=None) -> None:
    """Queue a pageview for a document that has already been served.

    Callers must invoke this only AFTER access resolution succeeded AND
    _serve_file returned: a visitor bounced to the login page is never counted,
    and neither is a request for a file the site does not have.

    This is the whole cost analytics adds to the response path: a handful of
    dict lookups off the already-parsed request, and an append to the response's
    background-task list. Everything else is deferred to `_record_view`.

    `viewer` is whoever access resolution already resolved. It is None for a
    public site, which is readable without credentials and so resolves nobody.
    """
    try:
        background.add_task(
            _record_view,
            site_id=site.id,
            owner_id=site.user_id,
            filename=filename,
            method=request.method,
            user_agent=request.headers.get('user-agent', ''),
            # SECURITY: the peer address only, never a forwarded header — those
            # are caller-controlled and would let anyone mint unlimited
            # visitor keys and inflate unique_visitors at will.
            ip=request.client.host if request.client else '',
            has_credentials=bool(request.headers.get('authorization') or request.cookies.get('token')),
            request=request,
            viewer=viewer,
        )
    except Exception:
        log.warning('Failed to queue site view for %s', getattr(site, 'id', '?'), exc_info=True)


async def _get_optional_user(request: Request):
    """Resolve the requester from bearer header or token cookie; None if anonymous/invalid."""
    token = None
    auth_header = request.headers.get('authorization') or ''
    if auth_header.lower().startswith('bearer '):
        token = auth_header[7:].strip()
    if not token:
        token = request.cookies.get('token')
    if not token:
        return None
    try:
        data = decode_token(token)
    except Exception:
        return None
    if not data or 'id' not in data:
        return None
    # Mirror get_current_user: revoked tokens (sign-out / OIDC back-channel
    # logout) must not keep granting access to private sites.
    if data.get('jti') and not await is_valid_token(request, data):
        return None
    user = await Users.get_user_by_id(data['id'])
    if user is None or user.role not in ('user', 'admin'):
        return None
    if WEBUI_AUTH_TRUSTED_EMAIL_HEADER:
        trusted_email = request.headers.get(WEBUI_AUTH_TRUSTED_EMAIL_HEADER, '').lower()
        if trusted_email and user.email != trusted_email:
            return None
    return user


def _serve_404() -> HTTPException:
    # Error responses carry the same CSP/nosniff/no-cache headers as served
    # pages: they leave through the same public routes.
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Not found', headers=SERVE_HEADERS)


async def _resolve_site_for_view(slug: str, request: Request, db: AsyncSession, *, is_entry: bool):
    """Resolve the site to serve, and the viewer allowed to see it.

    Returns `(site, viewer)` when the view is allowed, or `(RedirectResponse,
    None)` when an anonymous visitor must be bounced to the login page (entry
    route only — the file route raises 401 instead). Every other outcome
    raises. `viewer` is None for a public site: those are readable without
    credentials, so no token is decoded and no user is looked up.

    The viewer is returned rather than discarded so the caller can flag an
    owner's own pageview without decoding the same token a second time.
    """
    site = await Sites.get_site_by_slug(slug, db=db)
    if not site:
        raise _serve_404()
    if site.public:
        return site, None
    user = await _get_optional_user(request)
    if user is None:
        if is_entry:
            # Direct navigation: send the browser to login and back.
            redirect = RedirectResponse(
                url=f'/auth?redirect={quote(f"/sites/{slug}/")}', status_code=302, headers=SERVE_HEADERS
            )
            return redirect, None
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated', headers=SERVE_HEADERS)
    if user.role == 'admin' or site.user_id == user.id:
        return site, user
    if await AccessGrants.has_access(
        user_id=user.id, resource_type='site', resource_id=site.id, permission='read', db=db
    ):
        return site, user
    # Authenticated but not allowed: do not reveal that the site exists.
    raise _serve_404()


def _serve_file(site, filename: str) -> FileResponse:
    manifest = {f['name']: f for f in site.files}
    entry = manifest.get(filename)
    if not entry:
        raise _serve_404()
    site_dir = (SITES_DIR / site.id).resolve()
    file_path = (site_dir / filename).resolve()
    # Defense in depth: the manifest check above should already exclude traversal.
    if not str(file_path).startswith(str(site_dir) + os.sep):
        raise _serve_404()
    if not file_path.is_file():
        raise _serve_404()
    return FileResponse(file_path, media_type=entry['content_type'], headers=SERVE_HEADERS)


@serve_router.get('/sites/{slug}')
async def redirect_site_entry(slug: str):
    # The canonical entry URL ends with a slash so a page's relative assets
    # (href="style.css") resolve to /sites/{slug}/style.css, not /sites/style.css.
    return RedirectResponse(url=f'/sites/{quote(slug)}/', status_code=308, headers=SERVE_HEADERS)


@serve_router.get('/sites/{slug}/')
async def serve_site_entry(
    slug: str,
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_async_session),
):
    site, viewer = await _resolve_site_for_view(slug, request, db, is_entry=True)
    if isinstance(site, RedirectResponse):
        return site
    # Serve first, record second: _serve_file raises 404 for a file the site
    # does not have, so only a document that actually exists is counted.
    response = _serve_file(site, site.entry_file)
    _queue_view(site, site.entry_file, request, background, viewer=viewer)
    return response


@serve_router.get('/sites/{slug}/{filename}')
async def serve_site_file(
    slug: str,
    filename: str,
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_async_session),
):
    site, viewer = await _resolve_site_for_view(slug, request, db, is_entry=False)
    response = _serve_file(site, filename)
    _queue_view(site, filename, request, background, viewer=viewer)
    return response
