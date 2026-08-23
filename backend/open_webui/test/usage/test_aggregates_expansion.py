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


@pytest.mark.asyncio
async def test_active_counts_windows():
    now = _now()
    await _insert('u1', now - 3_600_000)            # 1h ago: dau current
    await _insert('u2', now - 30 * 3_600_000)       # 30h ago: dau previous, wau current
    await _insert('u3', now - 10 * 86_400_000)      # 10d ago: wau previous, mau current
    res = await UsageEvents.active_counts(days=30)
    assert res['dau'] == {'current': 1, 'previous': 1}
    assert res['wau'] == {'current': 2, 'previous': 1}
    assert res['mau'] == {'current': 3, 'previous': 0}
    assert res['new_users'] == {'current': 3, 'previous': 0}


@pytest.mark.asyncio
async def test_active_counts_new_user_uses_first_ever_event():
    now = _now()
    await _insert('u1', now - 1000)
    # u4's FIRST event is 40d ago (previous window); recent activity must not
    # make them "new" in the current window.
    await _insert('u4', now - 40 * 86_400_000)
    await _insert('u4', now - 5 * 86_400_000)
    res = await UsageEvents.active_counts(days=30)
    assert res['mau']['current'] == 2
    assert res['new_users'] == {'current': 1, 'previous': 1}


@pytest.mark.asyncio
async def test_active_counts_user_ids_filter():
    now = _now()
    await _insert('u1', now - 1000)
    await _insert('u2', now - 1000)
    res = await UsageEvents.active_counts(days=30, user_ids=['u1'])
    assert res['dau'] == {'current': 1, 'previous': 0}
    assert res['new_users']['current'] == 1


@pytest.mark.asyncio
async def test_overview_prev_active_users():
    now = _now()
    await _insert('u1', now - 1000, tool='workos')
    await _insert('u1', now - 40 * 86_400_000, tool='workos')
    await _insert('u2', now - 40 * 86_400_000, tool='workos')
    since = now - 30 * 86_400_000
    tools = {
        t['tool']: t
        for t in await UsageEvents.overview(
            since, prev_since_ms=now - 60 * 86_400_000
        )
    }
    assert tools['workos']['active_users'] == 1
    assert tools['workos']['prev_active_users'] == 2
    # Without prev_since_ms the field defaults to 0.
    tools = {t['tool']: t for t in await UsageEvents.overview(since)}
    assert tools['workos']['prev_active_users'] == 0


@pytest.mark.asyncio
async def test_heatmap_buckets_utc():
    # Epoch day 4 = 1970-01-05, a Monday. With 0=Sunday, Monday = row 1.
    monday_10am = 4 * 86_400_000 + 10 * 3_600_000
    await _insert('u1', monday_10am)
    await _insert('u2', monday_10am + 60_000)   # same hour bucket
    await _insert('u1', monday_10am + 3_600_000)  # 11:00
    matrix = await UsageEvents.heatmap(0)
    assert len(matrix) == 7 and all(len(r) == 24 for r in matrix)
    assert matrix[1][10] == 2
    assert matrix[1][11] == 1
    assert sum(sum(r) for r in matrix) == 3


@pytest.mark.asyncio
async def test_heatmap_user_ids_filter():
    monday_10am = 4 * 86_400_000 + 10 * 3_600_000
    await _insert('u1', monday_10am)
    await _insert('u2', monday_10am)
    matrix = await UsageEvents.heatmap(0, user_ids=['u1'])
    assert matrix[1][10] == 1


@pytest.mark.asyncio
async def test_sessions_daily_counts_and_avg():
    day0 = 10 * 86_400_000
    # s1: two events 60s apart -> length 60_000
    await _insert('u1', day0 + 1000, session_id='s1')
    await _insert('u1', day0 + 61_000, session_id='s1')
    # s2: single event -> length 0, excluded from the average
    await _insert('u2', day0 + 5000, session_id='s2')
    # server event without session_id -> excluded from session counts entirely
    await _insert('u1', day0 + 9000, name='workos.task.create', tool='workos', source='server')
    res = await UsageEvents.sessions_daily(0)
    assert res['days'] == [{'date': '1970-01-11', 'sessions': 2}]
    assert res['avg_session_ms'] == 60_000


@pytest.mark.asyncio
async def test_sessions_daily_empty():
    res = await UsageEvents.sessions_daily(0)
    assert res == {'days': [], 'avg_session_ms': 0}


@pytest.mark.asyncio
async def test_model_counts():
    now = _now()
    for uid in ('u1', 'u2'):
        await _insert(uid, now - 1000, name='chat.message.sent', tool='chat',
                      properties={'model': 'm1'}, source='server')
    await _insert('u1', now - 900, name='chat.message.sent', tool='chat',
                  properties={'model': 'm2'}, source='server')
    await _insert('u1', now - 800, name='chat.message.sent', tool='chat',
                  properties={}, source='server')  # no model -> 'unknown'
    await _insert('u1', now - 700)  # page.view: not a chat message, ignored
    rows = await UsageEvents.model_counts(0)
    assert rows[0] == {'model': 'm1', 'messages': 2, 'unique_users': 2}
    assert {r['model'] for r in rows} == {'m1', 'm2', 'unknown'}


@pytest.mark.asyncio
async def test_model_counts_user_ids_filter():
    now = _now()
    await _insert('u1', now - 1000, name='chat.message.sent', tool='chat',
                  properties={'model': 'm1'}, source='server')
    await _insert('u2', now - 1000, name='chat.message.sent', tool='chat',
                  properties={'model': 'm2'}, source='server')
    rows = await UsageEvents.model_counts(0, user_ids=['u2'])
    assert [r['model'] for r in rows] == ['m2']


@pytest.mark.asyncio
async def test_user_summary():
    day0 = 10 * 86_400_000
    old = day0 - 5 * 86_400_000
    await _insert('u1', old, session_id='old')  # before window: only first_seen
    await _insert('u1', day0 + 10 * 3_600_000, session_id='s1', tool='workos')
    await _insert('u1', day0 + 10 * 3_600_000 + 120_000, session_id='s1', tool='workos')
    await _insert('u1', day0 + 11 * 3_600_000, name='chat.message.sent', tool='chat',
                  properties={'model': 'm1'}, source='server')
    res = await UsageEvents.user_summary('u1', since_ms=day0)
    assert res['first_seen'] == old
    assert res['last_seen'] == day0 + 11 * 3_600_000
    assert res['sessions'] == 1          # 'old' session outside window
    assert res['avg_session_ms'] == 120_000
    assert res['hours'][10] == 2 and res['hours'][11] == 1
    assert res['daily'] == [{'date': '1970-01-11', 'events': 3}]
    assert res['tools'] == {'workos': 2, 'chat': 1}
    assert res['models'] == [{'model': 'm1', 'messages': 1}]


@pytest.mark.asyncio
async def test_user_summary_no_events():
    res = await UsageEvents.user_summary('ghost', since_ms=0)
    assert res['first_seen'] == 0 and res['last_seen'] == 0
    assert res['sessions'] == 0 and res['hours'] == [0] * 24
    assert res['daily'] == [] and res['tools'] == {} and res['models'] == []


from open_webui.models.groups import GroupMember


async def _add_member(group_id, user_id):
    async with get_async_db_context(None) as db:
        db.add(GroupMember(id=f'{group_id}-{user_id}', group_id=group_id, user_id=user_id))
        await db.commit()


@pytest.mark.asyncio
async def test_group_rollup():
    now = _now()
    await _add_member('g1', 'u1')
    await _add_member('g1', 'u2')
    await _add_member('g2', 'u3')
    await _add_member('g3', 'u9')  # member with no events
    await _insert('u1', now - 1000, tool='workos')
    await _insert('u1', now - 900, tool='workos')
    await _insert('u1', now - 800, tool='workos')
    await _insert('u2', now - 700, tool='chat')
    await _insert('u3', now - 600, tool='policy')
    res = await UsageEvents.group_rollup(0)
    assert res['g1'] == {'active_users': 2, 'events': 4, 'top_tool': 'workos'}
    assert res['g2'] == {'active_users': 1, 'events': 1, 'top_tool': 'policy'}
    assert 'g3' not in res


@pytest.mark.asyncio
async def test_group_rollup_window():
    now = _now()
    await _add_member('g1', 'u1')
    await _insert('u1', now - 10_000)
    await _insert('u1', now - 50 * 86_400_000)
    res = await UsageEvents.group_rollup(now - 86_400_000)
    assert res['g1']['events'] == 1
