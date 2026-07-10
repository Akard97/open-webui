# AI avatar generation: reference photo -> stylized corporate avatar via OpenAI
# gpt-image-2. Self-contained (policy_review.py pattern). Photos stay in memory only.
import io
import logging
from datetime import datetime, timezone

import aiohttp
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from open_webui.env import AIOHTTP_CLIENT_SESSION_SSL
from open_webui.models.avatar import AvatarGenerations
from open_webui.utils.auth import get_verified_user
from open_webui.utils.session_pool import get_session

log = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_TYPES = {'image/png', 'image/jpeg', 'image/webp'}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_SOURCE_EDGE = 1024


def _utc_date() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d')


def _require_enabled(request: Request) -> None:
    if not request.app.state.config.AVATAR_GENERATION_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Avatar generation is disabled.',
        )


def _api_key(request: Request) -> str:
    key = (
        request.app.state.config.AVATAR_OPENAI_API_KEY
        or request.app.state.config.IMAGES_OPENAI_API_KEY
    )
    if not key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='No OpenAI API key is configured for avatar generation.',
        )
    return key


def _downscale(data: bytes) -> tuple[bytes, str]:
    # Cap the reference photo at 1024px on its longest edge to bound input-token
    # cost; normalize EXIF rotation so portraits arrive upright.
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    img = img.convert('RGB')
    if max(img.size) > MAX_SOURCE_EDGE:
        img.thumbnail((MAX_SOURCE_EDGE, MAX_SOURCE_EDGE), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=90)
    return buf.getvalue(), 'image/jpeg'


@router.get('/quota')
async def get_quota(request: Request, user=Depends(get_verified_user)):
    _require_enabled(request)
    limit = int(request.app.state.config.AVATAR_DAILY_LIMIT)
    used = await AvatarGenerations.get_count(user.id, _utc_date())
    return {'remaining': max(0, limit - used), 'limit': limit}


@router.post('/generate')
async def generate_avatar(
    request: Request,
    photo: UploadFile = File(...),
    user=Depends(get_verified_user),
):
    _require_enabled(request)
    key = _api_key(request)

    if photo.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Unsupported image type. Use PNG, JPEG or WebP.',
        )
    data = await photo.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Image is too large (max 10 MB).',
        )

    limit = int(request.app.state.config.AVATAR_DAILY_LIMIT)
    today = _utc_date()
    used = await AvatarGenerations.get_count(user.id, today)
    if used >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f'Daily avatar limit reached ({limit}/day). Resets at midnight UTC.',
        )

    try:
        source, mime = _downscale(data)
    except Exception:
        # Content-Type is client-supplied; garbage bytes labeled as an image
        # must be a clean upload-validation 400, not an unhandled PIL error.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid or corrupted image file.',
        )

    form = aiohttp.FormData()
    form.add_field('model', 'gpt-image-2')
    form.add_field('prompt', request.app.state.config.AVATAR_STYLE_PROMPT)
    form.add_field('size', '1024x1024')
    form.add_field('quality', 'medium')
    form.add_field('output_format', 'webp')
    form.add_field('image', source, filename='photo.jpg', content_type=mime)

    url = f'{request.app.state.config.AVATAR_OPENAI_API_BASE_URL}/images/edits'
    session = await get_session()
    async with session.post(
        url,
        data=form,
        headers={'Authorization': f'Bearer {key}'},
        ssl=AIOHTTP_CLIENT_SESSION_SSL,
    ) as r:
        try:
            body = await r.json(content_type=None)
        except Exception:
            body = None
        if r.status >= 400:
            msg = None
            if isinstance(body, dict):
                msg = (body.get('error') or {}).get('message')
            log.warning(f'avatar generation failed ({r.status}): {msg}')
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=msg or 'Avatar generation failed.',
            )

    try:
        b64 = body['data'][0]['b64_json']
        if not isinstance(b64, str) or not b64:
            raise KeyError('b64_json')
    except (KeyError, IndexError, TypeError):
        # 200 from OpenAI but not the shape we asked for (or a non-JSON body).
        # Bail out with 502 BEFORE consuming quota.
        log.warning('avatar generation returned an unexpected response shape')
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail='Avatar generation returned an unexpected response.',
        )

    new_count = await AvatarGenerations.increment(user.id, today)
    return {
        'image': f'data:image/webp;base64,{b64}',
        'remaining': max(0, limit - new_count),
    }
