import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from open_webui.internal.db import Base, get_async_db_context
from sqlalchemy import BigInteger, Column, JSON, Text, delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)


def _now() -> int:
    return int(time.time() * 1000)


def _id() -> str:
    return str(uuid.uuid4())


TOOLS = {'chat', 'workos', 'policy', 'home', 'admin', 'settings', 'notes', 'other'}

# event_name -> (tool, kind). kind 'client' events may only arrive via the
# ingest endpoint; kind 'server' events may only be written by emit().
# page.view/page.leave carry their real tool in properties['tool'] ('app' here
# is a placeholder, replaced at validation time).
EVENT_ALLOWLIST: dict[str, tuple[str, str]] = {
    # client
    'page.view': ('app', 'client'),
    'page.leave': ('app', 'client'),
    'workos.view.switch': ('workos', 'client'),
    'workos.search.used': ('workos', 'client'),
    # server
    'chat.message.sent': ('chat', 'server'),
    'workos.task.create': ('workos', 'server'),
    'workos.task.complete': ('workos', 'server'),
    'workos.task.delete': ('workos', 'server'),
    'workos.comment.create': ('workos', 'server'),
    'workos.team.member_add': ('workos', 'server'),
    'workos.team.member_remove': ('workos', 'server'),
    'workos.workspace.member_add': ('workos', 'server'),
    'workos.workspace.member_remove': ('workos', 'server'),
    'workos.workspace.visibility_change': ('workos', 'server'),
    'policy.review.submit': ('policy', 'server'),
    'policy.review.approve': ('policy', 'server'),
    'policy.review.reject': ('policy', 'server'),
    'policy.doc.upload': ('policy', 'server'),
}

MAX_PROPERTIES_BYTES = 2048


class UsageEvent(Base):
    __tablename__ = 'usage_event'

    id = Column(Text, primary_key=True, unique=True)
    user_id = Column(Text, nullable=False)
    event_name = Column(Text, nullable=False)
    tool = Column(Text, nullable=False)
    properties = Column(JSON, default=dict)
    session_id = Column(Text, nullable=True)
    source = Column(Text, nullable=False)
    duration_ms = Column(BigInteger, nullable=True)
    created_at = Column(BigInteger, nullable=False)


def _validate_client_event(ev: dict) -> Optional[dict]:
    name = ev.get('name')
    meta = EVENT_ALLOWLIST.get(name)
    if not meta or meta[1] != 'client':
        return None
    props = ev.get('properties') or {}
    if not isinstance(props, dict):
        return None
    try:
        if len(json.dumps(props)) > MAX_PROPERTIES_BYTES:
            return None
    except (TypeError, ValueError):
        return None
    tool = meta[0]
    duration_ms = None
    if name in ('page.view', 'page.leave'):
        tool = props.get('tool')
        if tool not in TOOLS:
            return None
    if name == 'page.leave':
        d = props.get('duration_ms')
        if not isinstance(d, int) or isinstance(d, bool) or d < 0 or d > 86_400_000:
            return None
        duration_ms = d
    session_id = ev.get('session_id')
    if session_id is not None and (not isinstance(session_id, str) or len(session_id) > 64):
        session_id = None
    return {
        'name': name,
        'tool': tool,
        'properties': props,
        'session_id': session_id,
        'duration_ms': duration_ms,
    }


class UsageEventsDao:
    async def insert_client_batch(
        self, user_id: str, events: list[dict], db: Optional[AsyncSession] = None
    ) -> tuple[int, int]:
        rows = []
        rejected = 0
        now = _now()
        for ev in events:
            valid = _validate_client_event(ev)
            if valid is None:
                rejected += 1
                continue
            rows.append(
                UsageEvent(
                    id=_id(),
                    user_id=user_id,
                    event_name=valid['name'],
                    tool=valid['tool'],
                    properties=valid['properties'],
                    session_id=valid['session_id'],
                    source='client',
                    duration_ms=valid['duration_ms'],
                    created_at=now,
                )
            )
        if rows:
            async with get_async_db_context(db) as db:
                db.add_all(rows)
                await db.commit()
        return len(rows), rejected

    async def emit(
        self, user_id: str, event_name: str, properties: Optional[dict] = None
    ) -> None:
        # Own session on purpose: a failed telemetry insert must never poison
        # the caller's transaction, and any exception is swallowed.
        try:
            meta = EVENT_ALLOWLIST.get(event_name)
            if not meta or meta[1] != 'server':
                log.warning(f'usage emit refused for event {event_name}')
                return
            async with get_async_db_context(None) as db:
                db.add(
                    UsageEvent(
                        id=_id(),
                        user_id=user_id,
                        event_name=event_name,
                        tool=meta[0],
                        properties=properties or {},
                        session_id=None,
                        source='server',
                        duration_ms=None,
                        created_at=_now(),
                    )
                )
                await db.commit()
        except Exception:
            log.exception(f'usage emit failed for event {event_name}')

    async def user_activity(
        self,
        user_id: str,
        since_ms: int,
        page: int = 1,
        limit: int = 50,
        tool: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> dict:
        async with get_async_db_context(db) as db:
            q = select(UsageEvent).filter(
                UsageEvent.user_id == user_id, UsageEvent.created_at >= since_ms
            )
            cq = select(func.count(UsageEvent.id)).filter(
                UsageEvent.user_id == user_id, UsageEvent.created_at >= since_ms
            )
            if tool:
                q = q.filter(UsageEvent.tool == tool)
                cq = cq.filter(UsageEvent.tool == tool)
            total = (await db.execute(cq)).scalar() or 0
            res = await db.execute(
                q.order_by(desc(UsageEvent.created_at))
                .limit(limit)
                .offset((page - 1) * limit)
            )
            events = [
                {
                    'event_name': r.event_name,
                    'tool': r.tool,
                    'properties': r.properties or {},
                    'source': r.source,
                    'created_at': r.created_at,
                }
                for r in res.scalars().all()
            ]
            return {'events': events, 'total': total}

    async def overview(self, since_ms: int, db: Optional[AsyncSession] = None) -> list[dict]:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(
                    UsageEvent.tool,
                    func.count(func.distinct(UsageEvent.user_id)),
                    func.count(func.distinct(UsageEvent.session_id)),
                    func.count(UsageEvent.id),
                )
                .filter(UsageEvent.created_at >= since_ms)
                .group_by(UsageEvent.tool)
            )
            rows = res.all()
            dres = await db.execute(
                select(UsageEvent.tool, func.avg(UsageEvent.duration_ms))
                .filter(
                    UsageEvent.created_at >= since_ms,
                    UsageEvent.event_name == 'page.leave',
                )
                .group_by(UsageEvent.tool)
            )
            durations = dict(dres.all())
            return [
                {
                    'tool': t,
                    'active_users': u,
                    'sessions': s,
                    'events': e,
                    'avg_page_ms': int(durations.get(t) or 0),
                }
                for t, u, s, e in rows
            ]

    async def daily(
        self, since_ms: int, tool: Optional[str] = None, db: Optional[AsyncSession] = None
    ) -> list[dict]:
        day = (UsageEvent.created_at.op('/')(86_400_000)).label('day')
        async with get_async_db_context(db) as db:
            q = (
                select(
                    day,
                    UsageEvent.tool,
                    func.count(func.distinct(UsageEvent.user_id)),
                    func.count(UsageEvent.id),
                )
                .filter(UsageEvent.created_at >= since_ms)
                .group_by(day, UsageEvent.tool)
                .order_by(day)
            )
            if tool:
                q = q.filter(UsageEvent.tool == tool)
            out: dict[int, dict] = {}
            for d, t, dau, cnt in (await db.execute(q)).all():
                d = int(d)
                bucket = out.setdefault(
                    d,
                    {
                        'date': datetime.fromtimestamp(d * 86400, tz=timezone.utc).strftime('%Y-%m-%d'),
                        'tools': {},
                        'events': 0,
                    },
                )
                bucket['tools'][t] = dau
                bucket['events'] += cnt
            return [out[k] for k in sorted(out)]

    async def event_counts(
        self, since_ms: int, tool: Optional[str] = None, db: Optional[AsyncSession] = None
    ) -> list[dict]:
        async with get_async_db_context(db) as db:
            q = (
                select(
                    UsageEvent.event_name,
                    UsageEvent.tool,
                    func.count(UsageEvent.id).label('count'),
                    func.count(func.distinct(UsageEvent.user_id)),
                )
                .filter(UsageEvent.created_at >= since_ms)
                .group_by(UsageEvent.event_name, UsageEvent.tool)
                .order_by(desc('count'))
            )
            if tool:
                q = q.filter(UsageEvent.tool == tool)
            return [
                {'event_name': n, 'tool': t, 'count': c, 'unique_users': u}
                for n, t, c, u in (await db.execute(q)).all()
            ]

    async def user_rollup(
        self,
        since_ms: int,
        sort: str = 'events',
        page: int = 1,
        limit: int = 25,
        db: Optional[AsyncSession] = None,
    ) -> dict:
        async with get_async_db_context(db) as db:
            total = (
                await db.execute(
                    select(func.count(func.distinct(UsageEvent.user_id))).filter(
                        UsageEvent.created_at >= since_ms
                    )
                )
            ).scalar() or 0
            base = (
                select(
                    UsageEvent.user_id,
                    func.max(UsageEvent.created_at).label('last_seen'),
                    func.count(func.distinct(UsageEvent.session_id)).label('sessions'),
                    func.count(UsageEvent.id).label('events'),
                )
                .filter(UsageEvent.created_at >= since_ms)
                .group_by(UsageEvent.user_id)
                .order_by(
                    desc('last_seen' if sort == 'last_seen' else 'events'),
                    UsageEvent.user_id,
                )
                .limit(limit)
                .offset((page - 1) * limit)
            )
            rows = (await db.execute(base)).all()
            ids = [r[0] for r in rows]
            tool_counts: dict[str, dict[str, int]] = {}
            if ids:
                tres = await db.execute(
                    select(UsageEvent.user_id, UsageEvent.tool, func.count(UsageEvent.id))
                    .filter(UsageEvent.created_at >= since_ms, UsageEvent.user_id.in_(ids))
                    .group_by(UsageEvent.user_id, UsageEvent.tool)
                )
                for uid, t, c in tres.all():
                    tool_counts.setdefault(uid, {})[t] = c
            return {
                'users': [
                    {
                        'user_id': uid,
                        'last_seen': last_seen,
                        'sessions': sessions,
                        'events': events,
                        'tools': tool_counts.get(uid, {}),
                    }
                    for uid, last_seen, sessions, events in rows
                ],
                'total': total,
            }

    async def delete_before(
        self, cutoff_ms: int, db: Optional[AsyncSession] = None
    ) -> int:
        async with get_async_db_context(db) as db:
            res = await db.execute(delete(UsageEvent).filter(UsageEvent.created_at < cutoff_ms))
            await db.commit()
            return res.rowcount or 0


UsageEvents = UsageEventsDao()
