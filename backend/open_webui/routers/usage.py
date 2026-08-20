from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.constants import ERROR_MESSAGES
from open_webui.internal.db import get_async_session
from open_webui.models.usage import UsageEvents
from open_webui.utils.auth import get_verified_user
from open_webui.utils.rate_limit import RateLimiter
from open_webui.utils.redis import get_redis_client

router = APIRouter()

# 1000 ingest requests/user/hour -- far above normal use (tracker flushes at
# most every 10s => ~360/hr).
ingest_rate_limiter = RateLimiter(
    redis_client=get_redis_client(), limit=1000, window=3600
)

MAX_BATCH = 50


class ClientEventForm(BaseModel):
    name: str
    properties: dict = Field(default_factory=dict)
    session_id: str | None = None


class IngestForm(BaseModel):
    events: list[ClientEventForm]


class IngestResponse(BaseModel):
    accepted: int
    rejected: int


@router.post('/events', response_model=IngestResponse)
async def ingest_events(
    request: Request,
    form: IngestForm,
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    if not request.app.state.config.ENABLE_USAGE_TRACKING:
        return IngestResponse(accepted=0, rejected=len(form.events))
    if len(form.events) > MAX_BATCH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'batch exceeds {MAX_BATCH} events',
        )
    if ingest_rate_limiter.is_limited(f'usage:{user.id}'):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=ERROR_MESSAGES.RATE_LIMIT_EXCEEDED,
        )
    accepted, rejected = await UsageEvents.insert_client_batch(
        user.id, [e.model_dump() for e in form.events], db=db
    )
    return IngestResponse(accepted=accepted, rejected=rejected)
