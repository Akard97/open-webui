import logging
import os
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.internal.db import get_async_db_context
from open_webui.models.users import User
from open_webui.models.workos import Teams, TeamMembers, Workspaces, Workstreams, Labels, Tasks

log = logging.getLogger(__name__)

LABELS = [
    ('frontend', 'teal'), ('backend', 'cyan'), ('bug', 'red'),
    ('research', 'purple'), ('design', 'orange'), ('infra', 'green'),
]

DEMO_TASKS = [
    ('Migrate billing service to new ledger', 'in_progress', 'urgent', 60),
    ('Redesign task detail side panel', 'in_review', 'high', 85),
    ('Add keyboard shortcuts to board view', 'todo', 'medium', 0),
    ('Investigate slow workspace switching', 'in_progress', 'high', 35),
    ('Spec out Workstream templates', 'backlog', 'low', 0),
    ('Audit notification email deliverability', 'todo', 'medium', 0),
    ('Ship comment @mentions', 'done', 'high', 100),
    ('Roll out SSO for enterprise tier', 'done', 'urgent', 100),
    ('Empty states for new Workspaces', 'in_review', 'low', 70),
    ('Rate-limit the public API', 'backlog', 'medium', 0),
]


async def _first_admin_id(db: Optional[AsyncSession] = None) -> Optional[str]:
    async with get_async_db_context(db) as db:
        res = await db.execute(select(User).filter_by(role='admin').order_by(User.created_at.asc()))
        row = res.scalars().first()
        return row.id if row else None


async def seed_workos_demo() -> None:
    if os.environ.get('WORKOS_SEED_DEMO', 'false').lower() != 'true':
        return
    if await Teams.list_all():
        return  # idempotent: only seed an empty WorkOS
    owner_id = await _first_admin_id()
    if not owner_id:
        log.info('WorkOS seed skipped: no admin user yet.')
        return

    team = await Teams.insert('Acme', 'OSL', 'briefcase', owner_id)
    await TeamMembers.add(team.id, owner_id, 'owner')
    for name, color in LABELS:
        await Labels.insert(team.id, name, color)

    eng = await Workspaces.insert(team.id, 'Engineering', 'briefcase', 'team', owner_id)
    await Workspaces.insert(team.id, 'Design', 'palette', 'team', owner_id)
    platform = await Workstreams.insert(eng.id, 'Platform', 'layers', owner_id)
    await Workstreams.insert(eng.id, 'Mobile', 'smartphone', owner_id)
    await Workstreams.insert(eng.id, 'Growth', 'trending-up', owner_id)

    for title, st, prio, prog in DEMO_TASKS:
        t = await Tasks.insert(
            platform.id, team.id, team.key, title, owner_id, status=st, priority=prio, assignee_ids=[owner_id]
        )
        if prog:
            await Tasks.update_fields(t.id, {'progress': prog})
    log.info('WorkOS demo data seeded.')
