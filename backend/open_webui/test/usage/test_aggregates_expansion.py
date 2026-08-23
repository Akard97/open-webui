import pytest

from open_webui.internal.db import get_async_db_context
from open_webui.models.usage import UsageEvent, UsageEvents, _id, _now


async def _insert(
    user_id,
    created_at,
    name='page.view',
    tool='chat',
    session_id=None,
    properties=None,
    source='client',
):
    """Insert a raw event row with full control over the timestamp."""
    async with get_async_db_context(None) as db:
        db.add(
            UsageEvent(
                id=_id(),
                user_id=user_id,
                event_name=name,
                tool=tool,
                properties=properties or {},
                session_id=session_id,
                source=source,
                duration_ms=None,
                created_at=created_at,
            )
        )
        await db.commit()


async def _seed_two_users():
    now = _now()
    await _insert('u1', now - 1000, tool='workos', session_id='s1')
    await _insert('u1', now - 900, tool='workos', session_id='s1')
    await _insert('u2', now - 800, tool='chat', session_id='s2')


@pytest.mark.asyncio
async def test_overview_user_ids_filter():
    await _seed_two_users()
    tools = {t['tool']: t for t in await UsageEvents.overview(0, user_ids=['u1'])}
    assert set(tools) == {'workos'}
    assert tools['workos']['active_users'] == 1
    assert tools['workos']['events'] == 2
    assert await UsageEvents.overview(0, user_ids=[]) == []


@pytest.mark.asyncio
async def test_daily_user_ids_filter():
    await _seed_two_users()
    days = await UsageEvents.daily(0, user_ids=['u2'])
    assert len(days) == 1
    assert days[0]['tools'] == {'chat': 1}
    assert days[0]['events'] == 1


@pytest.mark.asyncio
async def test_event_counts_user_ids_filter():
    await _seed_two_users()
    counts = await UsageEvents.event_counts(0, user_ids=['u1'])
    assert [(e['tool'], e['count']) for e in counts] == [('workos', 2)]


@pytest.mark.asyncio
async def test_user_rollup_user_ids_filter():
    await _seed_two_users()
    res = await UsageEvents.user_rollup(0, user_ids=['u2'])
    assert res['total'] == 1
    assert [u['user_id'] for u in res['users']] == ['u2']
    assert res['users'][0]['tools'] == {'chat': 1}
