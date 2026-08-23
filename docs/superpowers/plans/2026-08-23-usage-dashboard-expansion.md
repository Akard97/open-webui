# Usage Dashboard Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the admin Usage dashboard with group scoping, presence counts (online now, DAU/WAU/MAU with previous-period deltas), an hour×weekday heatmap, sessions/day, top models, a groups comparison table, and a richer per-user modal.

**Architecture:** All new aggregates are SQL in the existing DAO (`backend/open_webui/models/usage.py`); new admin-only endpoints extend `backend/open_webui/routers/analytics.py`. Group scoping = router resolves `group_id` → member ids, DAO methods take an optional `user_ids` filter (DAO stays group-agnostic and testable without group tables; the one exception, `group_rollup`, JOINs `group_member` directly). Presence reads the websocket `SESSION_POOL` via a lazy, monkeypatchable accessor. Frontend: one Usage tab gains a scope selector; new small components + a pure-utils module (`usageStats.ts`) carrying all testable math.

**Tech Stack:** FastAPI + SQLAlchemy async (SQLite/Postgres both supported), Svelte 4 + Tailwind (admin styling), pytest (`backend/.venv/Scripts/python.exe`), vitest.

**Spec:** `docs/superpowers/specs/2026-08-23-usage-dashboard-expansion-design.md`

## Global Constraints

- Admin-only viewing behind existing `ENABLE_ADMIN_ANALYTICS`; every new endpoint uses `Depends(get_admin_user)`.
- All aggregation in SQL in the DAO — no in-Python crunching (exception: picking top-tool per group from a grouped query result, matching the existing `user_rollup` tool_counts pattern).
- Epoch **milliseconds** everywhere; day bucket = `created_at / 86_400_000`; heatmap buckets computed in **UTC** in SQL, rotated to local time client-side.
- "Previous period" = equal-length window immediately before the current one (`created_at >= prev_since AND created_at < since`).
- New user = `MIN(created_at)` over the user's entire event history falls inside the window (subquery, not the user table).
- Session length = `MAX(created_at) − MIN(created_at)` per `session_id`; zero-length (single-event) sessions excluded from averages; `session_id IS NULL` rows (server events) excluded from session counts.
- Presence = snapshot on load, no polling; entries older than `SESSION_POOL_TIMEOUT` (120 s) skipped; deduped by user id.
- `group_id` referencing a missing group → HTTP 404 `'Group not found'`; frontend resets scope to Everyone. Empty group → zeros, adoption `—`.
- Deliberate spec deviation (YAGNI): `GET /usage/users/{id}/activity` does NOT gain `group_id` — it is already single-user scoped, a group filter is a no-op.
- Cross-DB JSON extraction for model ids: `UsageEvent.properties['model'].as_string()` (compiles to `json_extract` on SQLite, `->>` on Postgres). Missing model → `'unknown'`.
- Admin styling only (match existing Analytics tab) — NOT the bold WorkOS look.
- i18n: every new UI string added to `src/lib/i18n/locales/en-US/translation.json` (value `""`) AND `src/lib/i18n/locales/ar/translation.json` (Arabic translation), keys inserted alphabetically. Grep before adding — some keys already exist.
- Backend tests: run from `backend/` with `.venv/Scripts/python.exe -m pytest open_webui/test/usage -q`. Frontend: `npm run test:frontend` from repo root.
- NEVER use haiku-model subagents for Svelte edits (cp1252 corruption risk). Do not start a Vite dev server without asking the user first.

---

### Task 1: DAO — `user_ids` scoping on existing aggregates

**Files:**
- Modify: `backend/open_webui/models/usage.py` (methods `overview`, `daily`, `event_counts`, `user_rollup`)
- Test: `backend/open_webui/test/usage/test_aggregates_expansion.py` (new file)

**Interfaces:**
- Produces: module-level helper `_apply_user_filter(q, user_ids)`; every listed method gains keyword arg `user_ids: Optional[list[str]] = None`. `None` = no filter; empty list = match nothing (all zeros/empty). Also produces the `_insert(...)` test helper reused by Tasks 2–5.

- [ ] **Step 1: Write the failing tests**

Create `backend/open_webui/test/usage/test_aggregates_expansion.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `.venv/Scripts/python.exe -m pytest open_webui/test/usage/test_aggregates_expansion.py -q`
Expected: 4 FAIL with `TypeError: ... got an unexpected keyword argument 'user_ids'`

- [ ] **Step 3: Implement the filter**

In `backend/open_webui/models/usage.py`, add after `MAX_PROPERTIES_BYTES = 2048`:

```python
def _apply_user_filter(q, user_ids: Optional[list[str]]):
    # None = unscoped; [] = empty group, must match nothing.
    if user_ids is not None:
        q = q.filter(UsageEvent.user_id.in_(user_ids))
    return q
```

Change signatures and thread the filter through every query in each method (including `user_rollup`'s `total` count query and its per-page `tool_counts` query, and `overview`'s durations query):

- `async def overview(self, since_ms: int, user_ids: Optional[list[str]] = None, db: Optional[AsyncSession] = None) -> list[dict]:` — this task adds only `user_ids`; Task 2 later adds a `prev_since_ms` keyword to this same method.
- `async def daily(self, since_ms: int, tool: Optional[str] = None, user_ids: Optional[list[str]] = None, db: Optional[AsyncSession] = None) -> list[dict]:`
- `async def event_counts(self, since_ms: int, tool: Optional[str] = None, user_ids: Optional[list[str]] = None, db: Optional[AsyncSession] = None) -> list[dict]:`
- `async def user_rollup(self, since_ms: int, sort: str = 'events', page: int = 1, limit: int = 25, user_ids: Optional[list[str]] = None, db: Optional[AsyncSession] = None) -> dict:`

Example for `overview` (apply the same `q = _apply_user_filter(q, user_ids)` pattern to each select in all four methods):

```python
    async def overview(
        self,
        since_ms: int,
        user_ids: Optional[list[str]] = None,
        db: Optional[AsyncSession] = None,
    ) -> list[dict]:
        async with get_async_db_context(db) as db:
            q = (
                select(
                    UsageEvent.tool,
                    func.count(func.distinct(UsageEvent.user_id)),
                    func.count(func.distinct(UsageEvent.session_id)),
                    func.count(UsageEvent.id),
                )
                .filter(UsageEvent.created_at >= since_ms)
                .group_by(UsageEvent.tool)
            )
            res = await db.execute(_apply_user_filter(q, user_ids))
            rows = res.all()
            dq = (
                select(UsageEvent.tool, func.avg(UsageEvent.duration_ms))
                .filter(
                    UsageEvent.created_at >= since_ms,
                    UsageEvent.event_name == 'page.leave',
                )
                .group_by(UsageEvent.tool)
            )
            dres = await db.execute(_apply_user_filter(dq, user_ids))
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
```

- [ ] **Step 4: Run tests to verify they pass, plus the existing suite**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/usage -q`
Expected: all PASS (new 4 + existing 28)

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/models/usage.py backend/open_webui/test/usage/test_aggregates_expansion.py
git commit -m "feat(usage): user_ids scoping on existing DAO aggregates"
```

---

### Task 2: DAO — `active_counts` + overview previous-period actives

**Files:**
- Modify: `backend/open_webui/models/usage.py`
- Test: `backend/open_webui/test/usage/test_aggregates_expansion.py`

**Interfaces:**
- Consumes: `_insert` helper and `_apply_user_filter` from Task 1.
- Produces: `async def active_counts(self, days: int, user_ids=None, db=None) -> dict` returning `{'dau'|'wau'|'mau'|'new_users': {'current': int, 'previous': int}}`. `overview` gains `prev_since_ms: Optional[int] = None`; each returned dict gains `'prev_active_users': int` (0 when `prev_since_ms` is None).

- [ ] **Step 1: Write the failing tests**

Append to `test_aggregates_expansion.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/usage/test_aggregates_expansion.py -q`
Expected: new tests FAIL (`AttributeError: ... active_counts` / `unexpected keyword argument 'prev_since_ms'` / `KeyError: 'prev_active_users'`)

- [ ] **Step 3: Implement**

In `overview`, add the `prev_since_ms: Optional[int] = None` keyword (after `user_ids`), and inside the context before the return:

```python
            prev_active: dict = {}
            if prev_since_ms is not None:
                pq = (
                    select(
                        UsageEvent.tool,
                        func.count(func.distinct(UsageEvent.user_id)),
                    )
                    .filter(
                        UsageEvent.created_at >= prev_since_ms,
                        UsageEvent.created_at < since_ms,
                    )
                    .group_by(UsageEvent.tool)
                )
                prev_active = dict((await db.execute(_apply_user_filter(pq, user_ids))).all())
```

and add `'prev_active_users': int(prev_active.get(t) or 0),` to the returned dict.

Add the new method to `UsageEventsDao`:

```python
    async def active_counts(
        self,
        days: int,
        user_ids: Optional[list[str]] = None,
        db: Optional[AsyncSession] = None,
    ) -> dict:
        now = _now()
        out: dict[str, dict] = {}
        async with get_async_db_context(db) as db:
            for key, span in (('dau', 1), ('wau', 7), ('mau', 30)):
                span_ms = span * 86_400_000
                counts = []
                for start, end in (
                    (now - span_ms, None),
                    (now - 2 * span_ms, now - span_ms),
                ):
                    q = select(func.count(func.distinct(UsageEvent.user_id))).filter(
                        UsageEvent.created_at >= start
                    )
                    if end is not None:
                        q = q.filter(UsageEvent.created_at < end)
                    counts.append(
                        (await db.execute(_apply_user_filter(q, user_ids))).scalar() or 0
                    )
                out[key] = {'current': counts[0], 'previous': counts[1]}
            # New users: first-EVER event falls inside the window.
            first_q = select(
                UsageEvent.user_id, func.min(UsageEvent.created_at).label('first_seen')
            )
            first = (
                _apply_user_filter(first_q, user_ids)
                .group_by(UsageEvent.user_id)
                .subquery()
            )
            window_ms = days * 86_400_000
            since, prev_since = now - window_ms, now - 2 * window_ms
            cur = (
                await db.execute(
                    select(func.count())
                    .select_from(first)
                    .filter(first.c.first_seen >= since)
                )
            ).scalar() or 0
            prev = (
                await db.execute(
                    select(func.count())
                    .select_from(first)
                    .filter(first.c.first_seen >= prev_since, first.c.first_seen < since)
                )
            ).scalar() or 0
            out['new_users'] = {'current': cur, 'previous': prev}
        return out
```

- [ ] **Step 4: Run the whole usage suite**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/usage -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/models/usage.py backend/open_webui/test/usage/test_aggregates_expansion.py
git commit -m "feat(usage): active_counts (DAU/WAU/MAU/new users) + overview prev-period actives"
```

---

### Task 3: DAO — `heatmap` + `sessions_daily`

**Files:**
- Modify: `backend/open_webui/models/usage.py`
- Test: `backend/open_webui/test/usage/test_aggregates_expansion.py`

**Interfaces:**
- Produces: `async def heatmap(self, since_ms, user_ids=None, db=None) -> list[list[int]]` — 7 rows (0=Sunday, UTC) × 24 hour columns of event counts. `async def sessions_daily(self, since_ms, user_ids=None, db=None) -> dict` — `{'days': [{'date': 'YYYY-MM-DD', 'sessions': int}], 'avg_session_ms': int}`.

- [ ] **Step 1: Write the failing tests**

Append to `test_aggregates_expansion.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/usage/test_aggregates_expansion.py -q`
Expected: new tests FAIL with `AttributeError`

- [ ] **Step 3: Implement**

Add to `UsageEventsDao`:

```python
    async def heatmap(
        self,
        since_ms: int,
        user_ids: Optional[list[str]] = None,
        db: Optional[AsyncSession] = None,
    ) -> list[list[int]]:
        # UTC buckets; epoch day 0 (1970-01-01) was a Thursday, so +4 makes
        # row index 0 = Sunday. The frontend rotates to local time.
        # precedence=8 forces SQLAlchemy to parenthesize the (day + 4) operand:
        # the default (precedence 0) renders `day + 4 % 7`, which SQL evaluates
        # as `day + (4 % 7)` — verified empirically on this repo's SQLAlchemy.
        dow = (
            (UsageEvent.created_at.op('/')(86_400_000) + 4).op('%', precedence=8)(7)
        ).label('dow')
        hour = ((UsageEvent.created_at.op('/')(3_600_000)).op('%')(24)).label('hour')
        async with get_async_db_context(db) as db:
            q = (
                select(dow, hour, func.count(UsageEvent.id))
                .filter(UsageEvent.created_at >= since_ms)
                .group_by(dow, hour)
            )
            matrix = [[0] * 24 for _ in range(7)]
            for d, h, c in (await db.execute(_apply_user_filter(q, user_ids))).all():
                matrix[int(d)][int(h)] = c
            return matrix

    async def sessions_daily(
        self,
        since_ms: int,
        user_ids: Optional[list[str]] = None,
        db: Optional[AsyncSession] = None,
    ) -> dict:
        day = (UsageEvent.created_at.op('/')(86_400_000)).label('day')
        async with get_async_db_context(db) as db:
            q = (
                select(day, func.count(func.distinct(UsageEvent.session_id)))
                .filter(
                    UsageEvent.created_at >= since_ms,
                    UsageEvent.session_id.isnot(None),
                )
                .group_by(day)
                .order_by(day)
            )
            days_out = [
                {
                    'date': datetime.fromtimestamp(int(d) * 86400, tz=timezone.utc).strftime('%Y-%m-%d'),
                    'sessions': c,
                }
                for d, c in (await db.execute(_apply_user_filter(q, user_ids))).all()
            ]
            sess_q = (
                select(
                    UsageEvent.session_id,
                    (func.max(UsageEvent.created_at) - func.min(UsageEvent.created_at)).label('length'),
                )
                .filter(
                    UsageEvent.created_at >= since_ms,
                    UsageEvent.session_id.isnot(None),
                )
                .group_by(UsageEvent.session_id)
            )
            sess = _apply_user_filter(sess_q, user_ids).subquery()
            # Single-event sessions (length 0) would drag the average to 0.
            avg_ms = (
                await db.execute(select(func.avg(sess.c.length)).filter(sess.c.length > 0))
            ).scalar()
            return {'days': days_out, 'avg_session_ms': int(avg_ms or 0)}
```

- [ ] **Step 4: Run the whole usage suite**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/usage -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/models/usage.py backend/open_webui/test/usage/test_aggregates_expansion.py
git commit -m "feat(usage): heatmap and sessions_daily DAO aggregates"
```

---

### Task 4: DAO — `model_counts` + `user_summary`

**Files:**
- Modify: `backend/open_webui/models/usage.py`
- Test: `backend/open_webui/test/usage/test_aggregates_expansion.py`

**Interfaces:**
- Produces: `async def model_counts(self, since_ms, user_ids=None, limit=10, db=None) -> list[dict]` — `[{'model': str, 'messages': int, 'unique_users': int}]` sorted by messages desc. `async def user_summary(self, user_id, since_ms, db=None) -> dict` — `{'first_seen': int, 'last_seen': int, 'sessions': int, 'avg_session_ms': int, 'hours': list[24 int], 'daily': [{'date','events'}], 'tools': dict[str,int], 'models': [{'model','messages'}]}`. `first_seen`/`last_seen` are ALL-TIME; the rest respect `since_ms`.

- [ ] **Step 1: Write the failing tests**

Append to `test_aggregates_expansion.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/usage/test_aggregates_expansion.py -q`
Expected: new tests FAIL with `AttributeError`

- [ ] **Step 3: Implement**

Add to `UsageEventsDao`:

```python
    async def model_counts(
        self,
        since_ms: int,
        user_ids: Optional[list[str]] = None,
        limit: int = 10,
        db: Optional[AsyncSession] = None,
    ) -> list[dict]:
        model = UsageEvent.properties['model'].as_string().label('model')
        async with get_async_db_context(db) as db:
            q = (
                select(
                    model,
                    func.count(UsageEvent.id).label('messages'),
                    func.count(func.distinct(UsageEvent.user_id)),
                )
                .filter(
                    UsageEvent.created_at >= since_ms,
                    UsageEvent.event_name == 'chat.message.sent',
                )
                .group_by(model)
                .order_by(desc('messages'))
                .limit(limit)
            )
            return [
                {'model': m or 'unknown', 'messages': c, 'unique_users': u}
                for m, c, u in (await db.execute(_apply_user_filter(q, user_ids))).all()
            ]

    async def user_summary(
        self, user_id: str, since_ms: int, db: Optional[AsyncSession] = None
    ) -> dict:
        async with get_async_db_context(db) as db:
            bounds = (
                await db.execute(
                    select(
                        func.min(UsageEvent.created_at),
                        func.max(UsageEvent.created_at),
                    ).filter(UsageEvent.user_id == user_id)
                )
            ).one()
            base = [UsageEvent.user_id == user_id, UsageEvent.created_at >= since_ms]
            sessions = (
                await db.execute(
                    select(func.count(func.distinct(UsageEvent.session_id))).filter(
                        *base, UsageEvent.session_id.isnot(None)
                    )
                )
            ).scalar() or 0
            sess = (
                select(
                    UsageEvent.session_id,
                    (func.max(UsageEvent.created_at) - func.min(UsageEvent.created_at)).label('length'),
                )
                .filter(*base, UsageEvent.session_id.isnot(None))
                .group_by(UsageEvent.session_id)
                .subquery()
            )
            avg_ms = (
                await db.execute(select(func.avg(sess.c.length)).filter(sess.c.length > 0))
            ).scalar()
            hour = ((UsageEvent.created_at.op('/')(3_600_000)).op('%')(24)).label('hour')
            hours = [0] * 24
            for h, c in (
                await db.execute(select(hour, func.count(UsageEvent.id)).filter(*base).group_by(hour))
            ).all():
                hours[int(h)] = c
            day = (UsageEvent.created_at.op('/')(86_400_000)).label('day')
            daily = [
                {
                    'date': datetime.fromtimestamp(int(d) * 86400, tz=timezone.utc).strftime('%Y-%m-%d'),
                    'events': c,
                }
                for d, c in (
                    await db.execute(
                        select(day, func.count(UsageEvent.id)).filter(*base).group_by(day).order_by(day)
                    )
                ).all()
            ]
            tools = dict(
                (
                    await db.execute(
                        select(UsageEvent.tool, func.count(UsageEvent.id)).filter(*base).group_by(UsageEvent.tool)
                    )
                ).all()
            )
            model = UsageEvent.properties['model'].as_string().label('model')
            models = [
                {'model': m or 'unknown', 'messages': c}
                for m, c in (
                    await db.execute(
                        select(model, func.count(UsageEvent.id).label('messages'))
                        .filter(*base, UsageEvent.event_name == 'chat.message.sent')
                        .group_by(model)
                        .order_by(desc('messages'))
                        .limit(5)
                    )
                ).all()
            ]
            return {
                'first_seen': bounds[0] or 0,
                'last_seen': bounds[1] or 0,
                'sessions': sessions,
                'avg_session_ms': int(avg_ms or 0),
                'hours': hours,
                'daily': daily,
                'tools': tools,
                'models': models,
            }
```

- [ ] **Step 4: Run the whole usage suite**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/usage -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/models/usage.py backend/open_webui/test/usage/test_aggregates_expansion.py
git commit -m "feat(usage): model_counts and user_summary DAO aggregates"
```

---

### Task 5: DAO — `group_rollup` (+ group tables in test schema)

**Files:**
- Modify: `backend/open_webui/models/usage.py`, `backend/open_webui/test/usage/conftest.py`
- Test: `backend/open_webui/test/usage/test_aggregates_expansion.py`

**Interfaces:**
- Produces: `async def group_rollup(self, since_ms, db=None) -> dict[str, dict]` mapping `group_id -> {'active_users': int, 'events': int, 'top_tool': Optional[str]}`. Groups with no events in the window are absent from the dict (router fills zeros).

- [ ] **Step 1: Extend the test schema**

In `backend/open_webui/test/usage/conftest.py`:
- After `import open_webui.models.usage`, add: `import open_webui.models.groups  # noqa: E402,F401  (register tables on Base)`
- Change the fixture's table filter from `('usage_event',)` to `('usage_event', 'group', 'group_member')`.

- [ ] **Step 2: Write the failing tests**

Append to `test_aggregates_expansion.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/usage/test_aggregates_expansion.py -q`
Expected: new tests FAIL with `AttributeError: ... group_rollup`

- [ ] **Step 4: Implement**

Add to `UsageEventsDao`:

```python
    async def group_rollup(
        self, since_ms: int, db: Optional[AsyncSession] = None
    ) -> dict[str, dict]:
        # Function-level import: groups model must not become an import-time
        # dependency of the usage DAO.
        from open_webui.models.groups import GroupMember

        async with get_async_db_context(db) as db:
            q = (
                select(
                    GroupMember.group_id,
                    func.count(func.distinct(UsageEvent.user_id)),
                    func.count(UsageEvent.id),
                )
                .join(UsageEvent, UsageEvent.user_id == GroupMember.user_id)
                .filter(UsageEvent.created_at >= since_ms)
                .group_by(GroupMember.group_id)
            )
            out = {
                gid: {'active_users': a, 'events': e, 'top_tool': None}
                for gid, a, e in (await db.execute(q)).all()
            }
            tq = (
                select(
                    GroupMember.group_id,
                    UsageEvent.tool,
                    func.count(UsageEvent.id).label('cnt'),
                )
                .join(UsageEvent, UsageEvent.user_id == GroupMember.user_id)
                .filter(UsageEvent.created_at >= since_ms)
                .group_by(GroupMember.group_id, UsageEvent.tool)
            )
            best: dict[str, tuple[int, str]] = {}
            for gid, tool, cnt in (await db.execute(tq)).all():
                if gid in out and (gid not in best or cnt > best[gid][0]):
                    best[gid] = (cnt, tool)
            for gid, (_, tool) in best.items():
                out[gid]['top_tool'] = tool
            return out
```

- [ ] **Step 5: Run the whole usage suite**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/usage -q`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/models/usage.py backend/open_webui/test/usage/conftest.py backend/open_webui/test/usage/test_aggregates_expansion.py
git commit -m "feat(usage): group_rollup DAO aggregate"
```

---

### Task 6: Router — group scoping on existing endpoints

**Files:**
- Modify: `backend/open_webui/routers/analytics.py`
- Test: `backend/open_webui/test/usage/test_router_expansion.py` (new file)

**Interfaces:**
- Consumes: DAO `user_ids`/`prev_since_ms` kwargs (Tasks 1–2); `Groups.get_group_by_id(id, db=)`, `Groups.get_group_user_ids_by_id(id, db=)` (already imported in analytics.py).
- Produces: `async def _group_user_ids(group_id: Optional[str], db) -> Optional[list[str]]` (raises HTTPException 404 `'Group not found'`); `group_id: Optional[str]` query param on `/usage/overview`, `/usage/daily`, `/usage/events`, `/usage/users`; `UsageToolOverview` gains `prev_active_users: int = 0`. NOT on `/usage/users/{id}/activity` (deliberate — single-user scoped already).

- [ ] **Step 1: Write the failing tests**

Create `backend/open_webui/test/usage/test_router_expansion.py`:

```python
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport

import open_webui.routers.analytics as ar
from open_webui.models.groups import Groups
from open_webui.models.usage import UsageEvents, _now
from open_webui.utils.auth import get_admin_user

ADMIN = SimpleNamespace(id='admin1', name='Admin', role='admin')


def _make_app(admin=True):
    app = FastAPI()
    app.include_router(ar.router, prefix='/api/v1/analytics')
    if admin:
        app.dependency_overrides[get_admin_user] = lambda: ADMIN
    return app


def _client(admin=True):
    return httpx.AsyncClient(
        transport=ASGITransport(app=_make_app(admin)), base_url='http://test'
    )


def _stub_group(monkeypatch, members):
    async def _get_group_by_id(id, db=None):
        return SimpleNamespace(id=id, name='G') if id == 'g1' else None

    async def _get_group_user_ids_by_id(id, db=None):
        return members

    monkeypatch.setattr(Groups, 'get_group_by_id', staticmethod(_get_group_by_id))
    monkeypatch.setattr(
        Groups, 'get_group_user_ids_by_id', staticmethod(_get_group_user_ids_by_id)
    )


async def _seed():
    await UsageEvents.insert_client_batch('u1', [
        {'name': 'page.view', 'properties': {'tool': 'workos', 'view': 'board'}, 'session_id': 's1'},
    ])
    await UsageEvents.emit('u2', 'chat.message.sent', {'model': 'm1'})


@pytest.mark.asyncio
async def test_overview_group_filter(monkeypatch):
    await _seed()
    _stub_group(monkeypatch, ['u1'])
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/overview?days=30&group_id=g1')
    assert r.status_code == 200
    tools = {t['tool'] for t in r.json()['tools']}
    assert tools == {'workos'}


@pytest.mark.asyncio
async def test_overview_includes_prev_active_users():
    await _seed()
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/overview?days=30')
    assert r.status_code == 200
    assert all('prev_active_users' in t for t in r.json()['tools'])


@pytest.mark.asyncio
async def test_unknown_group_404(monkeypatch):
    _stub_group(monkeypatch, [])
    async with _client() as c:
        for path in (
            'usage/overview?group_id=nope',
            'usage/daily?group_id=nope',
            'usage/events?group_id=nope',
            'usage/users?group_id=nope',
        ):
            r = await c.get(f'/api/v1/analytics/{path}')
            assert r.status_code == 404, path


@pytest.mark.asyncio
async def test_users_group_filter(monkeypatch):
    await _seed()
    _stub_group(monkeypatch, ['u2'])

    async def _fake_get_users_by_user_ids(ids, db=None):
        return []

    from open_webui.models.users import Users
    monkeypatch.setattr(
        Users, 'get_users_by_user_ids', staticmethod(_fake_get_users_by_user_ids)
    )
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/users?days=30&group_id=g1')
    assert r.status_code == 200
    data = r.json()
    assert data['total'] == 1
    assert data['users'][0]['user_id'] == 'u2'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/usage/test_router_expansion.py -q`
Expected: FAIL (422/validation or missing field)

- [ ] **Step 3: Implement**

In `backend/open_webui/routers/analytics.py`:

1. Change the fastapi import line to: `from fastapi import APIRouter, Depends, HTTPException, Query`
2. Add after `_since_ms`:

```python
async def _group_user_ids(
    group_id: Optional[str], db: AsyncSession
) -> Optional[list[str]]:
    if not group_id:
        return None
    group = await Groups.get_group_by_id(group_id, db=db)
    if group is None:
        raise HTTPException(status_code=404, detail='Group not found')
    return await Groups.get_group_user_ids_by_id(group_id, db=db)
```

3. `UsageToolOverview` gains field `prev_active_users: int = 0`.
4. Each of the four endpoints gains `group_id: Optional[str] = Query(None)` and resolves `user_ids = await _group_user_ids(group_id, db)` before calling the DAO with `user_ids=user_ids`. `get_usage_overview` additionally passes `prev_since_ms=_since_ms(2 * days)`:

```python
@router.get('/usage/overview', response_model=UsageOverviewResponse)
async def get_usage_overview(
    days: int = Query(30, ge=1, le=365),
    group_id: Optional[str] = Query(None),
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    user_ids = await _group_user_ids(group_id, db)
    tools = await UsageEvents.overview(
        _since_ms(days),
        user_ids=user_ids,
        prev_since_ms=_since_ms(2 * days),
        db=db,
    )
    return UsageOverviewResponse(tools=[UsageToolOverview(**t) for t in tools])
```

(`daily`, `events`, `users` follow the same pattern without `prev_since_ms`.)

- [ ] **Step 4: Run the whole usage suite**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/usage -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/analytics.py backend/open_webui/test/usage/test_router_expansion.py
git commit -m "feat(usage): group_id scoping on existing usage endpoints"
```

---

### Task 7: Router — new aggregate endpoints

**Files:**
- Modify: `backend/open_webui/routers/analytics.py`
- Test: `backend/open_webui/test/usage/test_router_expansion.py`

**Interfaces:**
- Consumes: DAO methods from Tasks 2–5; `_group_user_ids` from Task 6; `Groups.get_all_groups(db=)`, `Groups.get_group_user_ids_by_ids(ids, db=)`.
- Produces endpoints (all admin-only): `GET /usage/active?days=&group_id=`, `GET /usage/heatmap?days=&group_id=`, `GET /usage/models?days=&group_id=`, `GET /usage/sessions/daily?days=&group_id=`, `GET /usage/groups?days=`, `GET /usage/users/{user_id}/summary?days=`. Response shapes below (frontend Task 10 consumes these verbatim).

- [ ] **Step 1: Write the failing tests**

Append to `test_router_expansion.py`:

```python
@pytest.mark.asyncio
async def test_active_endpoint():
    await _seed()
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/active?days=30')
    assert r.status_code == 200
    data = r.json()
    assert set(data) == {'dau', 'wau', 'mau', 'new_users'}
    assert data['dau'] == {'current': 2, 'previous': 0}


@pytest.mark.asyncio
async def test_heatmap_endpoint():
    await _seed()
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/heatmap?days=30')
    assert r.status_code == 200
    m = r.json()['matrix']
    assert len(m) == 7 and all(len(row) == 24 for row in m)
    assert sum(sum(row) for row in m) == 2


@pytest.mark.asyncio
async def test_models_endpoint():
    await _seed()
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/models?days=30')
    assert r.status_code == 200
    assert r.json()['models'] == [{'model': 'm1', 'messages': 1, 'unique_users': 1}]


@pytest.mark.asyncio
async def test_sessions_daily_endpoint():
    await _seed()
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/sessions/daily?days=30')
    assert r.status_code == 200
    data = r.json()
    assert data['days'][0]['sessions'] == 1
    assert data['avg_session_ms'] == 0


@pytest.mark.asyncio
async def test_groups_endpoint(monkeypatch):
    await _seed()

    async def _get_all_groups(db=None):
        return [
            SimpleNamespace(id='g1', name='Engineering'),
            SimpleNamespace(id='g2', name='Empty'),
        ]

    async def _get_group_user_ids_by_ids(ids, db=None):
        return {'g1': ['u1', 'u2', 'u3'], 'g2': []}

    async def _group_rollup(since_ms, db=None):
        return {'g1': {'active_users': 2, 'events': 2, 'top_tool': 'workos'}}

    monkeypatch.setattr(Groups, 'get_all_groups', staticmethod(_get_all_groups))
    monkeypatch.setattr(
        Groups, 'get_group_user_ids_by_ids', staticmethod(_get_group_user_ids_by_ids)
    )
    monkeypatch.setattr(UsageEvents, 'group_rollup', _group_rollup)
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/groups?days=30')
    assert r.status_code == 200
    groups = r.json()['groups']
    assert groups[0] == {
        'group_id': 'g1', 'name': 'Engineering', 'members': 3,
        'active_users': 2, 'events': 2, 'top_tool': 'workos',
    }
    assert groups[1] == {
        'group_id': 'g2', 'name': 'Empty', 'members': 0,
        'active_users': 0, 'events': 0, 'top_tool': None,
    }


@pytest.mark.asyncio
async def test_user_summary_endpoint():
    await _seed()
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/users/u2/summary?days=30')
    assert r.status_code == 200
    data = r.json()
    assert data['tools'] == {'chat': 1}
    assert data['models'] == [{'model': 'm1', 'messages': 1}]
    assert len(data['hours']) == 24


@pytest.mark.asyncio
async def test_new_endpoints_require_admin():
    async with _client(admin=False) as c:
        for path in (
            'usage/active', 'usage/heatmap', 'usage/models',
            'usage/sessions/daily', 'usage/groups', 'usage/users/u1/summary',
        ):
            r = await c.get(f'/api/v1/analytics/{path}')
            assert r.status_code in (401, 403), path


@pytest.mark.asyncio
async def test_new_endpoints_group_filter(monkeypatch):
    # The router→DAO user_ids handoff on each scoped new endpoint — exactly
    # where a copy-paste omission would hide.
    await _seed()
    _stub_group(monkeypatch, ['u1'])
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/active?days=30&group_id=g1')
        assert r.json()['dau']['current'] == 1
        r = await c.get('/api/v1/analytics/usage/heatmap?days=30&group_id=g1')
        assert sum(sum(row) for row in r.json()['matrix']) == 1
        r = await c.get('/api/v1/analytics/usage/models?days=30&group_id=g1')
        assert r.json()['models'] == []  # u2's chat message excluded
        r = await c.get('/api/v1/analytics/usage/sessions/daily?days=30&group_id=g1')
        assert r.json()['days'][0]['sessions'] == 1


@pytest.mark.asyncio
async def test_new_endpoints_unknown_group_404(monkeypatch):
    _stub_group(monkeypatch, [])
    async with _client() as c:
        for path in (
            'usage/active?group_id=nope',
            'usage/heatmap?group_id=nope',
            'usage/models?group_id=nope',
            'usage/sessions/daily?group_id=nope',
        ):
            r = await c.get(f'/api/v1/analytics/{path}')
            assert r.status_code == 404, path


@pytest.mark.asyncio
async def test_empty_group_zeros(monkeypatch):
    # 0-member group must yield zeros, not silently degrade to unscoped data
    # (the None-vs-[] seam in _group_user_ids).
    await _seed()
    _stub_group(monkeypatch, [])
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/overview?days=30&group_id=g1')
        assert r.json()['tools'] == []
        r = await c.get('/api/v1/analytics/usage/active?days=30&group_id=g1')
        assert r.json()['dau'] == {'current': 0, 'previous': 0}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/usage/test_router_expansion.py -q`
Expected: new tests FAIL with 404 (routes missing)

- [ ] **Step 3: Implement**

Append to the Usage Analytics section of `analytics.py`:

```python
class UsagePeriodCount(BaseModel):
    current: int
    previous: int


class UsageActiveResponse(BaseModel):
    dau: UsagePeriodCount
    wau: UsagePeriodCount
    mau: UsagePeriodCount
    new_users: UsagePeriodCount


@router.get('/usage/active', response_model=UsageActiveResponse)
async def get_usage_active(
    days: int = Query(30, ge=1, le=365),
    group_id: Optional[str] = Query(None),
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    user_ids = await _group_user_ids(group_id, db)
    res = await UsageEvents.active_counts(days, user_ids=user_ids, db=db)
    return UsageActiveResponse(**{k: UsagePeriodCount(**v) for k, v in res.items()})


class UsageHeatmapResponse(BaseModel):
    matrix: list[list[int]]


@router.get('/usage/heatmap', response_model=UsageHeatmapResponse)
async def get_usage_heatmap(
    days: int = Query(30, ge=1, le=365),
    group_id: Optional[str] = Query(None),
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    user_ids = await _group_user_ids(group_id, db)
    matrix = await UsageEvents.heatmap(_since_ms(days), user_ids=user_ids, db=db)
    return UsageHeatmapResponse(matrix=matrix)


class UsageModelEntry(BaseModel):
    model: str
    messages: int
    unique_users: int


class UsageModelsResponse(BaseModel):
    models: list[UsageModelEntry]


@router.get('/usage/models', response_model=UsageModelsResponse)
async def get_usage_models(
    days: int = Query(30, ge=1, le=365),
    group_id: Optional[str] = Query(None),
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    user_ids = await _group_user_ids(group_id, db)
    rows = await UsageEvents.model_counts(_since_ms(days), user_ids=user_ids, db=db)
    return UsageModelsResponse(models=[UsageModelEntry(**r) for r in rows])


class UsageSessionsDayEntry(BaseModel):
    date: str
    sessions: int


class UsageSessionsDailyResponse(BaseModel):
    days: list[UsageSessionsDayEntry]
    avg_session_ms: int


@router.get('/usage/sessions/daily', response_model=UsageSessionsDailyResponse)
async def get_usage_sessions_daily(
    days: int = Query(30, ge=1, le=365),
    group_id: Optional[str] = Query(None),
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    user_ids = await _group_user_ids(group_id, db)
    res = await UsageEvents.sessions_daily(_since_ms(days), user_ids=user_ids, db=db)
    return UsageSessionsDailyResponse(
        days=[UsageSessionsDayEntry(**d) for d in res['days']],
        avg_session_ms=res['avg_session_ms'],
    )


class UsageGroupEntry(BaseModel):
    group_id: str
    name: str
    members: int
    active_users: int
    events: int
    top_tool: Optional[str] = None


class UsageGroupsResponse(BaseModel):
    groups: list[UsageGroupEntry]


@router.get('/usage/groups', response_model=UsageGroupsResponse)
async def get_usage_groups(
    days: int = Query(30, ge=1, le=365),
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    groups = await Groups.get_all_groups(db=db)
    member_map = (
        await Groups.get_group_user_ids_by_ids([g.id for g in groups], db=db)
        if groups
        else {}
    )
    stats = await UsageEvents.group_rollup(_since_ms(days), db=db)
    entries = [
        UsageGroupEntry(
            group_id=g.id,
            name=g.name,
            members=len(member_map.get(g.id, [])),
            active_users=stats.get(g.id, {}).get('active_users', 0),
            events=stats.get(g.id, {}).get('events', 0),
            top_tool=stats.get(g.id, {}).get('top_tool'),
        )
        for g in groups
    ]
    entries.sort(key=lambda e: -e.events)
    return UsageGroupsResponse(groups=entries)


class UsageUserDailyEntry(BaseModel):
    date: str
    events: int


class UsageUserModelEntry(BaseModel):
    model: str
    messages: int


class UsageUserSummaryResponse(BaseModel):
    first_seen: int
    last_seen: int
    sessions: int
    avg_session_ms: int
    hours: list[int]
    daily: list[UsageUserDailyEntry]
    tools: dict[str, int]
    models: list[UsageUserModelEntry]


@router.get('/usage/users/{user_id}/summary', response_model=UsageUserSummaryResponse)
async def get_usage_user_summary(
    user_id: str,
    days: int = Query(30, ge=1, le=365),
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    res = await UsageEvents.user_summary(user_id, _since_ms(days), db=db)
    return UsageUserSummaryResponse(**res)
```

Note: `test_active_endpoint` asserts `dau == {'current': 2, 'previous': 0}` because `_seed()` writes both users' events at now. `test_sessions_daily_endpoint` expects `avg_session_ms == 0` because the single seeded session has one event (length 0, excluded).

- [ ] **Step 4: Run the whole usage suite**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/usage -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/analytics.py backend/open_webui/test/usage/test_router_expansion.py
git commit -m "feat(usage): active/heatmap/models/sessions/groups/user-summary endpoints"
```

---

### Task 8: Router — presence endpoint

**Files:**
- Modify: `backend/open_webui/routers/analytics.py`
- Test: `backend/open_webui/test/usage/test_router_expansion.py`

**Interfaces:**
- Consumes: `SESSION_POOL` / `SESSION_POOL_TIMEOUT` from `open_webui.socket.main` (lazy import); `_group_user_ids` from Task 6; `Users.get_users_by_user_ids` (already imported in analytics.py) to detect deleted users.
- Produces: `GET /usage/presence?group_id=` → `{online: int, users: [{id, name}]}`; module-level `def _get_session_pool()` (the monkeypatch seam for tests). Deleted-but-still-connected users render as `'removed user'` (pool entries cache the real name from connect time, so an existence cross-check is required — the `or 'removed user'` fallback alone never fires for them).

- [ ] **Step 1: Write the failing tests**

Append to `test_router_expansion.py`:

```python
import time as _time


def _pool(monkeypatch, entries, timeout=120):
    monkeypatch.setattr(ar, '_get_session_pool', lambda: (entries, timeout))


def _stub_users(monkeypatch, existing_ids):
    async def _get_users_by_user_ids(user_ids, db=None):
        return [SimpleNamespace(id=i) for i in user_ids if i in existing_ids]

    from open_webui.models.users import Users
    monkeypatch.setattr(
        Users, 'get_users_by_user_ids', staticmethod(_get_users_by_user_ids)
    )


@pytest.mark.asyncio
async def test_presence_dedupes_and_skips_stale(monkeypatch):
    now = int(_time.time())
    _stub_users(monkeypatch, {'u1', 'u3'})
    _pool(monkeypatch, {
        'sid1': {'id': 'u1', 'name': 'Lara', 'last_seen_at': now},
        'sid2': {'id': 'u1', 'name': 'Lara', 'last_seen_at': now},   # 2nd tab
        'sid3': {'id': 'u2', 'name': 'Omar', 'last_seen_at': now - 999},  # stale
        'sid4': {'id': 'u3', 'name': 'Zed', 'last_seen_at': now},
    })
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/presence')
    assert r.status_code == 200
    data = r.json()
    assert data['online'] == 2
    assert [u['id'] for u in data['users']] == ['u1', 'u3']  # sorted by name


@pytest.mark.asyncio
async def test_presence_group_intersection(monkeypatch):
    now = int(_time.time())
    _stub_group(monkeypatch, ['u1'])
    _stub_users(monkeypatch, {'u1', 'u2'})
    _pool(monkeypatch, {
        'sid1': {'id': 'u1', 'name': 'Lara', 'last_seen_at': now},
        'sid2': {'id': 'u2', 'name': 'Omar', 'last_seen_at': now},
    })
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/presence?group_id=g1')
    assert r.json() == {'online': 1, 'users': [{'id': 'u1', 'name': 'Lara'}]}


@pytest.mark.asyncio
async def test_presence_deleted_user_shows_removed(monkeypatch):
    now = int(_time.time())
    _stub_users(monkeypatch, {'u1'})  # 'ghost' no longer exists in the user table
    _pool(monkeypatch, {
        'sid1': {'id': 'u1', 'name': 'Lara', 'last_seen_at': now},
        'sid2': {'id': 'ghost', 'name': 'Ghost', 'last_seen_at': now},
    })
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/presence')
    names = {u['id']: u['name'] for u in r.json()['users']}
    assert names == {'u1': 'Lara', 'ghost': 'removed user'}


@pytest.mark.asyncio
async def test_presence_unknown_group_404(monkeypatch):
    _stub_group(monkeypatch, [])
    _pool(monkeypatch, {})
    async with _client() as c:
        r = await c.get('/api/v1/analytics/usage/presence?group_id=nope')
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_presence_requires_admin():
    async with _client(admin=False) as c:
        r = await c.get('/api/v1/analytics/usage/presence')
    assert r.status_code in (401, 403)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/usage/test_router_expansion.py -q`
Expected: presence tests FAIL (404 route / AttributeError on `_get_session_pool`)

- [ ] **Step 3: Implement**

Append to `analytics.py`:

```python
def _get_session_pool():
    # Lazy import keeps socket machinery out of router import time and gives
    # tests a clean monkeypatch seam.
    from open_webui.socket.main import SESSION_POOL, SESSION_POOL_TIMEOUT

    return SESSION_POOL, SESSION_POOL_TIMEOUT


class UsagePresenceUser(BaseModel):
    id: str
    name: str


class UsagePresenceResponse(BaseModel):
    online: int
    users: list[UsagePresenceUser]


@router.get('/usage/presence', response_model=UsagePresenceResponse)
async def get_usage_presence(
    group_id: Optional[str] = Query(None),
    user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_async_session),
):
    member_ids = await _group_user_ids(group_id, db)
    members = set(member_ids) if member_ids is not None else None
    pool, timeout = _get_session_pool()
    now = int(time.time())
    online: dict[str, str] = {}
    for entry in list(pool.values()):
        if not entry:
            continue
        uid = entry.get('id')
        if not uid or now - entry.get('last_seen_at', 0) > timeout:
            continue
        if members is not None and uid not in members:
            continue
        online[uid] = entry.get('name') or 'removed user'
    # Pool entries cache the user's name from connect time, so a deleted user
    # keeps their real name there; cross-check existence like the users table.
    if online:
        existing = {
            u.id for u in await Users.get_users_by_user_ids(list(online), db=db)
        }
        for uid in online:
            if uid not in existing:
                online[uid] = 'removed user'
    users = [
        UsagePresenceUser(id=uid, name=name)
        for uid, name in sorted(online.items(), key=lambda kv: kv[1].lower())
    ]
    return UsagePresenceResponse(online=len(users), users=users)
```

- [ ] **Step 4: Run the whole usage suite**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/usage -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/analytics.py backend/open_webui/test/usage/test_router_expansion.py
git commit -m "feat(usage): presence endpoint from websocket session pool"
```

---

### Task 9: Frontend — `usageStats` utils (pure math)

**Files:**
- Create: `src/lib/utils/usageStats.ts`
- Test: `src/lib/utils/usageStats.test.ts`

**Interfaces:**
- Produces (consumed by Tasks 11–13):
  - `rotateHeatmap(utcMatrix: number[][], offsetHours: number): number[][]` — rotates the 7×24 UTC matrix (row 0 = Sunday) into local time by treating it as a 168-hour week vector. Fractional offsets (UTC+5:30) rounded to the nearest hour.
  - `busiestHour(utcHours: number[], offsetHours: number): number | null` — local hour (0–23) with most events; null when all zero. Fractional offsets rounded.
  - `delta(current: number, previous: number): { dir: 'up' | 'down' | 'flat'; pct: number | null }` — pct null when previous is 0.
  - `adoptionPct(active: number, members: number): string` — `'63%'` (Math.round) or `'—'` for 0 members.

- [ ] **Step 1: Write the failing tests**

Create `src/lib/utils/usageStats.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { adoptionPct, busiestHour, delta, rotateHeatmap } from './usageStats';

const empty = () => Array.from({ length: 7 }, () => new Array(24).fill(0));

describe('rotateHeatmap', () => {
	it('is identity at offset 0', () => {
		const m = empty();
		m[1][10] = 5;
		expect(rotateHeatmap(m, 0)[1][10]).toBe(5);
	});

	it('shifts forward for positive offsets (UTC+3)', () => {
		const m = empty();
		m[1][10] = 5; // Monday 10:00 UTC
		const local = rotateHeatmap(m, 3);
		expect(local[1][13]).toBe(5); // Monday 13:00 local
		expect(local[1][10]).toBe(0);
	});

	it('wraps across day boundaries', () => {
		const m = empty();
		m[6][23] = 7; // Saturday 23:00 UTC
		const local = rotateHeatmap(m, 3);
		expect(local[0][2]).toBe(7); // Sunday 02:00 local (wraps week)
	});

	it('handles negative offsets', () => {
		const m = empty();
		m[0][0] = 4; // Sunday 00:00 UTC
		const local = rotateHeatmap(m, -5);
		expect(local[6][19]).toBe(4); // Saturday 19:00 local
	});

	it('rounds fractional offsets to the nearest hour (UTC+5:30)', () => {
		const m = empty();
		m[1][10] = 5;
		expect(rotateHeatmap(m, 5.5)[1][16]).toBe(5); // rounds to +6
	});
});

describe('busiestHour', () => {
	it('returns the rotated max hour', () => {
		const hours = new Array(24).fill(0);
		hours[10] = 9;
		expect(busiestHour(hours, 3)).toBe(13);
	});

	it('returns null when empty', () => {
		expect(busiestHour(new Array(24).fill(0), 3)).toBeNull();
	});

	it('rounds fractional offsets', () => {
		const hours = new Array(24).fill(0);
		hours[10] = 9;
		expect(busiestHour(hours, 5.5)).toBe(16);
	});
});

describe('delta', () => {
	it('computes direction and pct', () => {
		expect(delta(150, 100)).toEqual({ dir: 'up', pct: 50 });
		expect(delta(50, 100)).toEqual({ dir: 'down', pct: -50 });
		expect(delta(100, 100)).toEqual({ dir: 'flat', pct: 0 });
	});

	it('handles zero previous', () => {
		expect(delta(5, 0)).toEqual({ dir: 'up', pct: null });
		expect(delta(0, 0)).toEqual({ dir: 'flat', pct: null });
	});
});

describe('adoptionPct', () => {
	it('formats percentage', () => {
		expect(adoptionPct(5, 8)).toBe('63%');
	});
	it('em-dash for empty groups', () => {
		expect(adoptionPct(0, 0)).toBe('—');
	});
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test:frontend -- usageStats`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement**

Create `src/lib/utils/usageStats.ts`:

```ts
// Pure math for the admin Usage dashboard. The backend buckets heatmap data
// in UTC (row 0 = Sunday); rotation to the viewer's timezone happens here.

export const rotateHeatmap = (utcMatrix: number[][], offsetHours: number): number[][] => {
	// Fractional zones (UTC+5:30 etc.): round to the nearest hour — a fractional
	// index would silently write off-array keys and render the grid empty.
	const offset = Math.round(offsetHours);
	const flat = utcMatrix.flat(); // index = dow * 24 + hour
	const local = new Array(168).fill(0);
	for (let i = 0; i < 168; i++) {
		local[(((i + offset) % 168) + 168) % 168] = flat[i];
	}
	return Array.from({ length: 7 }, (_, d) => local.slice(d * 24, d * 24 + 24));
};

export const busiestHour = (utcHours: number[], offsetHours: number): number | null => {
	if (!utcHours.some((v) => v > 0)) return null;
	const offset = Math.round(offsetHours);
	const local = new Array(24).fill(0);
	for (let h = 0; h < 24; h++) {
		local[(((h + offset) % 24) + 24) % 24] += utcHours[h];
	}
	let best = 0;
	for (let h = 1; h < 24; h++) {
		if (local[h] > local[best]) best = h;
	}
	return best;
};

export const delta = (
	current: number,
	previous: number
): { dir: 'up' | 'down' | 'flat'; pct: number | null } => {
	if (previous === 0) {
		return { dir: current > 0 ? 'up' : 'flat', pct: null };
	}
	if (current === previous) return { dir: 'flat', pct: 0 };
	return {
		dir: current > previous ? 'up' : 'down',
		pct: Math.round(((current - previous) / previous) * 100)
	};
};

export const adoptionPct = (active: number, members: number): string =>
	members > 0 ? `${Math.round((active / members) * 100)}%` : '—';
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test:frontend -- usageStats`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/utils/usageStats.ts src/lib/utils/usageStats.test.ts
git commit -m "feat(usage): heatmap rotation, delta, adoption utils"
```

---

### Task 10: Frontend — API client fetchers

**Files:**
- Modify: `src/lib/apis/analytics/index.ts`

**Interfaces:**
- Consumes: endpoints from Tasks 6–8.
- Produces (consumed by Tasks 12–13): existing `getUsageOverview`, `getUsageDaily`, `getUsageEventCounts`, `getUsageUsers` each gain a trailing `groupId: string | null = null` param; new fetchers `getUsagePresence(token, groupId)`, `getUsageActive(token, days, groupId)`, `getUsageHeatmap(token, days, groupId)`, `getUsageModels(token, days, groupId)`, `getUsageSessionsDaily(token, days, groupId)`, `getUsageGroups(token, days)`, `getUsageUserSummary(token, userId, days)`. All follow the existing fetch pattern (throw `error.detail` string on failure).

- [ ] **Step 1: Extend existing fetchers**

In each of `getUsageOverview`, `getUsageDaily`, `getUsageEventCounts`, `getUsageUsers`: add trailing parameter `groupId: string | null = null` and, next to the other `searchParams.append` calls, add:

```ts
	if (groupId) searchParams.append('group_id', groupId);
```

(`getUsageOverview` gets the same `const searchParams` treatment it already has; just append the line.)

- [ ] **Step 2: Add new fetchers**

Append after `getUsageUserActivity` (every fetcher uses the exact same fetch/throw pattern as `getUsageOverview` — full code follows):

```ts
export const getUsagePresence = async (token: string = '', groupId: string | null = null) => {
	let error = null;

	const searchParams = new URLSearchParams();
	if (groupId) searchParams.append('group_id', groupId);

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/analytics/usage/presence?${searchParams.toString()}`,
		{
			method: 'GET',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getUsageActive = async (
	token: string = '',
	days: number = 30,
	groupId: string | null = null
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	searchParams.append('days', days.toString());
	if (groupId) searchParams.append('group_id', groupId);

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/analytics/usage/active?${searchParams.toString()}`,
		{
			method: 'GET',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getUsageHeatmap = async (
	token: string = '',
	days: number = 30,
	groupId: string | null = null
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	searchParams.append('days', days.toString());
	if (groupId) searchParams.append('group_id', groupId);

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/analytics/usage/heatmap?${searchParams.toString()}`,
		{
			method: 'GET',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getUsageModels = async (
	token: string = '',
	days: number = 30,
	groupId: string | null = null
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	searchParams.append('days', days.toString());
	if (groupId) searchParams.append('group_id', groupId);

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/analytics/usage/models?${searchParams.toString()}`,
		{
			method: 'GET',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getUsageSessionsDaily = async (
	token: string = '',
	days: number = 30,
	groupId: string | null = null
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	searchParams.append('days', days.toString());
	if (groupId) searchParams.append('group_id', groupId);

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/analytics/usage/sessions/daily?${searchParams.toString()}`,
		{
			method: 'GET',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getUsageGroups = async (token: string = '', days: number = 30) => {
	let error = null;

	const searchParams = new URLSearchParams();
	searchParams.append('days', days.toString());

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/analytics/usage/groups?${searchParams.toString()}`,
		{
			method: 'GET',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getUsageUserSummary = async (
	token: string = '',
	userId: string,
	days: number = 30
) => {
	let error = null;

	const searchParams = new URLSearchParams();
	searchParams.append('days', days.toString());

	const res = await fetch(
		`${WEBUI_API_BASE_URL}/analytics/usage/users/${userId}/summary?${searchParams.toString()}`,
		{
			method: 'GET',
			headers: {
				Accept: 'application/json',
				'Content-Type': 'application/json',
				authorization: `Bearer ${token}`
			}
		}
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err.detail;
			console.error(err);
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};
```

- [ ] **Step 3: Verify with the frontend test suite (compile-level sanity)**

Run: `npm run test:frontend`
Expected: existing tests still PASS

- [ ] **Step 4: Commit**

```bash
git add src/lib/apis/analytics/index.ts
git commit -m "feat(usage): API client fetchers for new usage endpoints"
```

---

### Task 11: Frontend — components + i18n keys

**Files:**
- Create: `src/lib/components/admin/Analytics/UsageStatCard.svelte`
- Create: `src/lib/components/admin/Analytics/UsageHeatmap.svelte`
- Create: `src/lib/components/admin/Analytics/UsageBars.svelte`
- Create: `src/lib/components/admin/Analytics/UsageGroupsTable.svelte`
- Modify: `src/lib/i18n/locales/en-US/translation.json`, `src/lib/i18n/locales/ar/translation.json`

**Interfaces:**
- Consumes: `rotateHeatmap`, `adoptionPct` from `$lib/utils/usageStats` (Task 9).
- Produces (consumed by Tasks 12–13):
  - `UsageStatCard` props: `label: string`, `value: string`, `delta: {dir, pct} | null = null`, `sub: string = ''`, `clickable: boolean = false`; forwards `on:click`.
  - `UsageHeatmap` props: `matrix: number[][]` (7×24 UTC).
  - `UsageBars` props: `items: { label: string; value: number; sub?: string }[]`.
  - `UsageGroupsTable` props: `groups: {group_id, name, members, active_users, events, top_tool}[]`, `onSelect: (groupId: string) => void`.

- [ ] **Step 1: Create UsageStatCard.svelte**

```svelte
<script lang="ts">
	export let label: string;
	export let value: string;
	export let delta: { dir: 'up' | 'down' | 'flat'; pct: number | null } | null = null;
	export let sub: string = '';
	export let clickable: boolean = false;
</script>

<svelte:element
	this={clickable ? 'button' : 'div'}
	type={clickable ? 'button' : undefined}
	class="border border-gray-50 dark:border-gray-850 rounded-lg px-3 py-2 text-left w-full {clickable
		? 'cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-850 transition-colors'
		: ''}"
	on:click
>
	<div class="text-xs text-gray-500 dark:text-gray-400 mb-1 truncate">{label}</div>
	<div class="flex items-baseline gap-2">
		<div class="text-xl font-medium text-gray-900 dark:text-white">{value}</div>
		{#if delta}
			<span
				class="text-xs {delta.dir === 'up'
					? 'text-green-600 dark:text-green-400'
					: delta.dir === 'down'
						? 'text-red-600 dark:text-red-400'
						: 'text-gray-400'}"
			>
				{delta.dir === 'up' ? '▲' : delta.dir === 'down' ? '▼' : '—'}{delta.pct !== null
					? ` ${Math.abs(delta.pct)}%`
					: ''}
			</span>
		{/if}
	</div>
	{#if sub}
		<div class="text-xs text-gray-400 mt-0.5 truncate">{sub}</div>
	{/if}
</svelte:element>
```

- [ ] **Step 2: Create UsageHeatmap.svelte**

```svelte
<script lang="ts">
	import dayjs from 'dayjs';
	import { rotateHeatmap } from '$lib/utils/usageStats';

	export let matrix: number[][] = []; // 7×24, UTC, row 0 = Sunday

	const offset = -new Date().getTimezoneOffset() / 60;
	// dayjs().day(i) = day-of-week i (0 = Sunday), locale-aware short label.
	const dayLabels = Array.from({ length: 7 }, (_, i) => dayjs().day(i).format('dd'));

	$: local = matrix.length === 7 ? rotateHeatmap(matrix, offset) : [];
	$: max = Math.max(1, ...local.flat());
</script>

{#if local.length === 7}
	<div class="flex flex-col gap-[3px]">
		{#each local as row, d}
			<div class="flex items-center gap-[3px]">
				<div class="w-8 shrink-0 text-[10px] text-gray-400 text-right pr-1">
					{dayLabels[d]}
				</div>
				{#each row as count, h}
					<div
						class="h-4 flex-1 rounded-[2px] min-w-0"
						style="background-color: rgba(59,130,246,{count === 0
							? 0.05
							: 0.2 + 0.8 * (count / max)})"
						title={`${dayLabels[d]} ${h}:00 — ${count}`}
					></div>
				{/each}
			</div>
		{/each}
		<div class="flex items-center gap-[3px]">
			<div class="w-8 shrink-0"></div>
			{#each Array.from({ length: 24 }, (_, h) => h) as h}
				<div class="flex-1 min-w-0 text-center text-[9px] text-gray-400">
					{h % 6 === 0 ? h : ''}
				</div>
			{/each}
		</div>
	</div>
{/if}
```

- [ ] **Step 3: Create UsageBars.svelte**

```svelte
<script lang="ts">
	export let items: { label: string; value: number; sub?: string }[] = [];

	$: max = Math.max(1, ...items.map((i) => i.value));
</script>

<div class="flex flex-col gap-1">
	{#each items as item (item.label)}
		<div class="flex items-center gap-2 text-xs">
			<div class="w-36 shrink-0 truncate font-medium text-gray-900 dark:text-white">
				{item.label}
			</div>
			<div class="flex-1 h-3 bg-gray-50 dark:bg-gray-850 rounded overflow-hidden">
				<div
					class="h-full bg-blue-500/70 rounded"
					style="width: {(item.value / max) * 100}%"
				></div>
			</div>
			<div class="w-14 shrink-0 text-right text-gray-500 dark:text-gray-400">
				{item.value.toLocaleString()}
			</div>
			{#if item.sub !== undefined}
				<div class="w-20 shrink-0 text-right text-gray-400 truncate">{item.sub}</div>
			{/if}
		</div>
	{/each}
</div>
```

- [ ] **Step 4: Create UsageGroupsTable.svelte**

```svelte
<script lang="ts">
	import { getContext } from 'svelte';
	import { adoptionPct } from '$lib/utils/usageStats';

	export let groups: {
		group_id: string;
		name: string;
		members: number;
		active_users: number;
		events: number;
		top_tool: string | null;
	}[] = [];
	export let onSelect: (groupId: string) => void = () => {};

	const i18n = getContext('i18n');
</script>

<div class="scrollbar-hidden relative whitespace-nowrap overflow-x-auto max-w-full">
	<table class="w-full text-sm text-left text-gray-500 dark:text-gray-400 table-auto">
		<thead class="text-xs text-gray-800 uppercase bg-transparent dark:text-gray-200">
			<tr class="border-b-[1.5px] border-gray-50 dark:border-gray-850/30">
				<th scope="col" class="px-2.5 py-2">{$i18n.t('Group')}</th>
				<th scope="col" class="px-2.5 py-2 text-right">{$i18n.t('Members')}</th>
				<th scope="col" class="px-2.5 py-2 text-right">{$i18n.t('Active Users')}</th>
				<th scope="col" class="px-2.5 py-2 text-right">{$i18n.t('Adoption')}</th>
				<th scope="col" class="px-2.5 py-2 text-right">{$i18n.t('Events')}</th>
				<th scope="col" class="px-2.5 py-2">{$i18n.t('Top Tool')}</th>
			</tr>
		</thead>
		<tbody>
			{#each groups as g (g.group_id)}
				<tr
					class="bg-white dark:bg-gray-900 dark:border-gray-850 text-xs cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
					on:click={() => onSelect(g.group_id)}
				>
					<td class="px-3 py-1 font-medium text-gray-900 dark:text-white truncate max-w-[150px]">
						{g.name}
					</td>
					<td class="px-3 py-1 text-right">{g.members.toLocaleString()}</td>
					<td class="px-3 py-1 text-right">{g.active_users.toLocaleString()}</td>
					<td class="px-3 py-1 text-right">{adoptionPct(g.active_users, g.members)}</td>
					<td class="px-3 py-1 text-right">{g.events.toLocaleString()}</td>
					<td class="px-3 py-1 capitalize">{g.top_tool ?? '—'}</td>
				</tr>
			{/each}
			{#if groups.length === 0}
				<tr>
					<td colspan="6" class="px-3 py-2 text-center text-gray-400">{$i18n.t('No data')}</td>
				</tr>
			{/if}
		</tbody>
	</table>
</div>
```

- [ ] **Step 5: Add i18n keys**

For each key below: grep `src/lib/i18n/locales/en-US/translation.json` first; if missing, add to en-US with value `""` and to `ar/translation.json` with the given Arabic value, both in alphabetical position. Verified against the catalog 2026-08-23: already present — `Members`, `Messages`, `Refresh`, `Tools`, `Groups`, `No data`, `Users`, `Active Users`. Casing traps: `Session` (singular) exists but `Sessions` does NOT; `Groups` exists but `Group` (singular) does NOT. `Sessions`, `Last Seen`, and `Daily Usage` are used by the base dashboard markup but missing from the catalog — they are included below to close that pre-existing gap.

| key | ar |
|---|---|
| `Active (7d)` | `نشط (7 أيام)` |
| `Active (30d)` | `نشط (30 يومًا)` |
| `Active today` | `نشط اليوم` |
| `Activity by hour` | `النشاط حسب الساعة` |
| `Adoption` | `نسبة التبني` |
| `Avg session` | `متوسط الجلسة` |
| `Busiest hour` | `الساعة الأكثر نشاطًا` |
| `Daily Usage` | `الاستخدام اليومي` |
| `Everyone` | `الجميع` |
| `First seen` | `أول ظهور` |
| `Group` | `المجموعة` |
| `Last Seen` | `آخر ظهور` |
| `Members` | `الأعضاء` |
| `Messages` | `الرسائل` |
| `New users` | `مستخدمون جدد` |
| `No one is online` | `لا أحد متصل الآن` |
| `Online now` | `متصل الآن` |
| `Refresh` | `تحديث` |
| `Sessions` | `الجلسات` |
| `Sessions per day` | `الجلسات في اليوم` |
| `Top Models` | `أكثر النماذج استخدامًا` |
| `Top Tool` | `الأداة الأكثر استخدامًا` |
| `Tools` | `الأدوات` |

- [ ] **Step 6: Verify**

Run: `npm run test:frontend`
Expected: PASS. Then run `npx svelte-check --output human 2>&1 | grep -i "Analytics"` — expected: no errors from the four new components (repo has ~9392 pre-existing baseline errors elsewhere; only check our files).

- [ ] **Step 7: Commit**

```bash
git add src/lib/components/admin/Analytics/UsageStatCard.svelte src/lib/components/admin/Analytics/UsageHeatmap.svelte src/lib/components/admin/Analytics/UsageBars.svelte src/lib/components/admin/Analytics/UsageGroupsTable.svelte src/lib/i18n/locales/en-US/translation.json src/lib/i18n/locales/ar/translation.json
git commit -m "feat(usage): stat card, heatmap, bars, groups table components + i18n"
```

---

### Task 12: Frontend — Usage.svelte wiring (scope, presence, new sections)

**Files:**
- Modify: `src/lib/components/admin/Analytics/Usage.svelte`

**Interfaces:**
- Consumes: everything from Tasks 9–11; `getGroups` from `$lib/apis/groups`.
- Produces: the full dashboard. `UsageUserModal` keeps its existing props (`show`, `user`, `days`, `onClose`).

- [ ] **Step 1: Rework Usage.svelte**

Apply these changes to `src/lib/components/admin/Analytics/Usage.svelte` (keep everything not mentioned — the modal mount, `formatMs`, `topTool`, `toolColors`, `buildDateRange`, users-table handlers, `dailyData`/`chartPeriod` reactives, tables markup):

**Script — new imports:**

```ts
	import {
		getUsageOverview,
		getUsageDaily,
		getUsageEventCounts,
		getUsageUsers,
		getUsagePresence,
		getUsageActive,
		getUsageHeatmap,
		getUsageModels,
		getUsageSessionsDaily,
		getUsageGroups
	} from '$lib/apis/analytics';
	import { getGroups } from '$lib/apis/groups';
	import { delta } from '$lib/utils/usageStats';
	import UsageStatCard from './UsageStatCard.svelte';
	import UsageHeatmap from './UsageHeatmap.svelte';
	import UsageBars from './UsageBars.svelte';
	import UsageGroupsTable from './UsageGroupsTable.svelte';
```

**Script — extend the existing `ToolOverview` type** with `prev_active_users: number;` (the API now always returns it).

**Script — new types and state (after the existing type declarations):**

```ts
	type PeriodCount = { current: number; previous: number };
	type ActiveCounts = {
		dau: PeriodCount;
		wau: PeriodCount;
		mau: PeriodCount;
		new_users: PeriodCount;
	};
	type GroupRollupEntry = {
		group_id: string;
		name: string;
		members: number;
		active_users: number;
		events: number;
		top_tool: string | null;
	};

	let groupId: string | null = null;
	let groupOptions: { id: string; name: string }[] = [];

	let presence: { online: number; users: { id: string; name: string }[] } | null = null;
	let active: ActiveCounts | null = null;
	let heatmapMatrix: number[][] = [];
	let models: { model: string; messages: number; unique_users: number }[] = [];
	let sessionsDaily: { days: { date: string; sessions: number }[]; avg_session_ms: number } = {
		days: [],
		avg_session_ms: 0
	};
	let groupsRollup: GroupRollupEntry[] = [];
	let showOnlineList = false;
```

**Script — replace the `load` function** (keeps the seq-counter guard; switches to `allSettled` so one failure doesn't blank the page; presence failure renders `—` without the banner; deleted group resets scope):

```ts
	const load = async () => {
		const seq = ++loadSeq;
		const uSeq = ++usersSeq;
		loading = true;
		showOnlineList = false;
		const results = await Promise.allSettled([
			getUsageOverview(localStorage.token, days, groupId),
			getUsageDaily(localStorage.token, days, null, groupId),
			getUsageEventCounts(localStorage.token, days, null, groupId),
			getUsageUsers(localStorage.token, days, userSort, userPage, groupId),
			getUsageActive(localStorage.token, days, groupId),
			getUsageHeatmap(localStorage.token, days, groupId),
			getUsageModels(localStorage.token, days, groupId),
			getUsageSessionsDaily(localStorage.token, days, groupId),
			groupId ? Promise.resolve(null) : getUsageGroups(localStorage.token, days),
			getUsagePresence(localStorage.token, groupId)
		]);
		if (seq !== loadSeq) return;

		// A scoped load against a deleted group: drop back to Everyone.
		if (
			groupId &&
			results.some((r) => r.status === 'rejected' && `${r.reason}` === 'Group not found')
		) {
			groupId = null;
			load();
			return;
		}

		const value = <T,>(r: PromiseSettledResult<T>): T | null =>
			r.status === 'fulfilled' ? r.value : null;

		const [
			overviewRes,
			dailyRes,
			eventsRes,
			usersRes,
			activeRes,
			heatmapRes,
			modelsRes,
			sessionsRes,
			groupsRes,
			presenceRes
		] = results;

		overview = (value(overviewRes) as any)?.tools ?? overview;
		dailyRaw = (value(dailyRes) as any)?.days ?? dailyRaw;
		eventCounts = (value(eventsRes) as any)?.events ?? eventCounts;
		if (uSeq === usersSeq) {
			const u = value(usersRes) as any;
			if (u) {
				users = u.users ?? [];
				usersTotal = u.total ?? 0;
			}
		}
		active = (value(activeRes) as any) ?? active;
		heatmapMatrix = (value(heatmapRes) as any)?.matrix ?? heatmapMatrix;
		models = (value(modelsRes) as any)?.models ?? models;
		sessionsDaily = (value(sessionsRes) as any) ?? sessionsDaily;
		if (!groupId) {
			groupsRollup = (value(groupsRes) as any)?.groups ?? groupsRollup;
		}
		// Presence is the least-critical number: on failure show — without
		// escalating to the banner.
		presence = (value(presenceRes) as any) ?? null;

		// Banner covers every fetch except presence (the last entry).
		loadError = results.slice(0, -1).some((r) => r.status === 'rejected');
		loading = false;
	};
```

**Script — scope selection + groups fetch (add; and extend `onMount`):**

```ts
	const selectScope = (id: string | null) => {
		groupId = id;
		userPage = 1;
		load();
	};

	onMount(async () => {
		load();
		try {
			const res = await getGroups(localStorage.token);
			groupOptions = (res ?? []).map((g: { id: string; name: string }) => ({
				id: g.id,
				name: g.name
			}));
		} catch (err) {
			console.error('Failed to load groups:', err);
		}
	});
```

(Remove the old `onMount(load);` line.)

**Script — sessions chart + reactives (near `dailyData`):**

```ts
	$: sessionsByDate = new Map(sessionsDaily.days.map((d) => [d.date, d.sessions]));
	$: sessionsData = buildDateRange(days).map((date) => ({
		date,
		models: { sessions: sessionsByDate.get(date) ?? 0 }
	}));
```

**Markup — header:** inside the existing header flex (next to the period `<select>`), add before it:

```svelte
			<select
				value={groupId ?? ''}
				on:change={(e) => selectScope((e.target as HTMLSelectElement).value || null)}
				class="w-fit pr-8 rounded-sm px-2 text-xs bg-transparent outline-none text-right max-w-[180px] truncate"
			>
				<option value="">{$i18n.t('Everyone')}</option>
				{#each groupOptions as g (g.id)}
					<option value={g.id}>{g.name}</option>
				{/each}
			</select>
```

and after the period select, a refresh button:

```svelte
			<button
				class="px-2 py-0.5 rounded-full text-xs text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-850"
				on:click={() => load()}
				aria-label={$i18n.t('Refresh')}
			>
				{$i18n.t('Refresh')}
			</button>
```

**Markup — presence & reach strip:** insert directly after the `loadError` banner block, before the overview cards (inside the `{:else}` branch alongside them — the strip renders in the non-loading state):

```svelte
		<div
			class="grid gap-3 mb-4"
			style="grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));"
		>
			<div class="relative">
				<UsageStatCard
					label={$i18n.t('Online now')}
					value={presence ? presence.online.toLocaleString() : '—'}
					clickable={!!presence && presence.online > 0}
					on:click={() => (showOnlineList = !showOnlineList)}
				/>
				{#if showOnlineList && presence}
					<div
						class="absolute z-20 mt-1 w-full max-h-48 overflow-y-auto rounded-lg border border-gray-100 dark:border-gray-850 bg-white dark:bg-gray-900 shadow-lg p-2 text-xs"
					>
						{#each presence.users as u (u.id)}
							<div class="py-0.5 truncate text-gray-700 dark:text-gray-300">{u.name}</div>
						{:else}
							<div class="text-gray-400">{$i18n.t('No one is online')}</div>
						{/each}
					</div>
				{/if}
			</div>
			<UsageStatCard
				label={$i18n.t('Active today')}
				value={active ? active.dau.current.toLocaleString() : '—'}
				delta={active ? delta(active.dau.current, active.dau.previous) : null}
			/>
			<UsageStatCard
				label={$i18n.t('Active (7d)')}
				value={active ? active.wau.current.toLocaleString() : '—'}
				delta={active ? delta(active.wau.current, active.wau.previous) : null}
			/>
			<UsageStatCard
				label={$i18n.t('Active (30d)')}
				value={active ? active.mau.current.toLocaleString() : '—'}
				delta={active ? delta(active.mau.current, active.mau.previous) : null}
			/>
			<UsageStatCard
				label={$i18n.t('New users')}
				value={active ? active.new_users.current.toLocaleString() : '—'}
				delta={active ? delta(active.new_users.current, active.new_users.previous) : null}
			/>
		</div>
```

**Markup — per-tool delta arrows:** inside each overview card, next to the `active_users` number, add:

```svelte
					{#if t.prev_active_users !== undefined}
						{@const d = delta(t.active_users, t.prev_active_users)}
						<span
							class="text-xs {d.dir === 'up'
								? 'text-green-600 dark:text-green-400'
								: d.dir === 'down'
									? 'text-red-600 dark:text-red-400'
									: 'text-gray-400'}"
						>
							{d.dir === 'up' ? '▲' : d.dir === 'down' ? '▼' : '—'}{d.pct !== null
								? ` ${Math.abs(d.pct)}%`
								: ''}
						</span>
					{/if}
```

(wrap the existing value in a `flex items-baseline gap-2` container like the stat card does).

**Markup — charts row:** replace the single Daily Usage chart block with a two-column grid:

```svelte
		<div class="grid md:grid-cols-2 gap-4 mb-4">
			{#if dailyData.length > 0}
				<div>
					<div class="text-xs font-medium text-gray-600 dark:text-gray-400 mb-2 px-0.5">
						{$i18n.t('Daily Usage')}
					</div>
					<ChartLine
						data={dailyData}
						models={toolNames}
						colors={toolColors}
						height={200}
						period={chartPeriod}
					/>
				</div>
			{/if}
			<div>
				<div
					class="flex items-center justify-between text-xs font-medium text-gray-600 dark:text-gray-400 mb-2 px-0.5"
				>
					<span>{$i18n.t('Sessions per day')}</span>
					<span class="text-gray-400 font-normal">
						{$i18n.t('Avg session')}: {formatMs(sessionsDaily.avg_session_ms)}
					</span>
				</div>
				<ChartLine
					data={sessionsData}
					models={['sessions']}
					colors={['#10b981']}
					height={200}
					period={chartPeriod}
				/>
			</div>
		</div>
```

**Markup — heatmap + models row (after the charts row):**

```svelte
		<div class="grid md:grid-cols-2 gap-4 mb-4">
			<div>
				<div class="text-xs font-medium text-gray-600 dark:text-gray-400 mb-2 px-0.5">
					{$i18n.t('Activity by hour')}
				</div>
				<UsageHeatmap matrix={heatmapMatrix} />
			</div>
			<div>
				<div class="text-xs font-medium text-gray-600 dark:text-gray-400 mb-2 px-0.5">
					{$i18n.t('Top Models')}
				</div>
				{#if models.length > 0}
					<UsageBars
						items={models.map((m) => ({
							label: m.model,
							value: m.messages,
							sub: `${m.unique_users.toLocaleString()} ${$i18n.t('Users').toLowerCase()}`
						}))}
					/>
				{:else}
					<div class="text-gray-400 text-xs px-0.5">{$i18n.t('No data')}</div>
				{/if}
			</div>
		</div>
```

**Markup — groups table (Everyone scope only, before the events/users tables):**

```svelte
		{#if !groupId}
			<div class="mb-4">
				<div class="text-xs font-medium text-gray-700 dark:text-gray-300 mb-1 px-0.5">
					{$i18n.t('Groups')}
				</div>
				<UsageGroupsTable groups={groupsRollup} onSelect={(id) => selectScope(id)} />
			</div>
		{/if}
```

- [ ] **Step 2: Verify**

Run: `npm run test:frontend`
Expected: PASS. Then `npx svelte-check --output human 2>&1 | grep -i "Usage.svelte"` — no new errors from this file beyond the repo-wide i18n-store baseline noise pattern.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/admin/Analytics/Usage.svelte
git commit -m "feat(usage): scope selector, presence strip, heatmap, models, sessions, groups table"
```

---

### Task 13: Frontend — UsageUserModal summary upgrade

**Files:**
- Modify: `src/lib/components/admin/Analytics/UsageUserModal.svelte`

**Interfaces:**
- Consumes: `getUsageUserSummary` (Task 10), `busiestHour` (Task 9), `UsageBars` (Task 11), `ChartLine` (existing).
- Produces: modal now shows a stats header + sparkline + tool/model bars above the existing activity timeline. Props unchanged.

- [ ] **Step 1: Extend the modal**

Add imports:

```ts
	import { getUsageUserSummary } from '$lib/apis/analytics';
	import { busiestHour } from '$lib/utils/usageStats';
	import UsageBars from './UsageBars.svelte';
	import ChartLine from './ChartLine.svelte';
```

Add state + loader (near the existing state):

```ts
	type Summary = {
		first_seen: number;
		last_seen: number;
		sessions: number;
		avg_session_ms: number;
		hours: number[];
		daily: { date: string; events: number }[];
		tools: Record<string, number>;
		models: { model: string; messages: number }[];
	};

	let summary: Summary | null = null;

	const tzOffset = -new Date().getTimezoneOffset() / 60;

	const formatMs = (ms: number): string => {
		if (!ms) return '—';
		const totalSeconds = Math.round(ms / 1000);
		const m = Math.floor(totalSeconds / 60);
		const s = totalSeconds % 60;
		return `${m}m ${s}s`;
	};

	const loadSummary = async () => {
		if (!user?.user_id) return;
		const seq = reqSeq; // ride the same invalidation counter
		try {
			const res = await getUsageUserSummary(localStorage.token, user.user_id, days);
			if (seq !== reqSeq) return;
			summary = res;
		} catch (err) {
			if (seq !== reqSeq) return;
			console.error('Failed to load user summary:', err);
			summary = null;
		}
	};

	$: sparklineData = (summary?.daily ?? []).map((d) => ({
		date: d.date,
		models: { events: d.events }
	}));
	$: hour = summary ? busiestHour(summary.hours, tzOffset) : null;
```

In the `$: if (show && user?.user_id)` open-reset block, add `summary = null;` and call `loadSummary();` AFTER `load();` (load() bumps `reqSeq` first; loadSummary must capture the post-bump value or it gets invalidated immediately). In `close()`, add `summary = null;`.

Insert the summary markup between the modal title row and the Activity section:

```svelte
			<div class="px-5 pb-2">
				{#if summary}
					<div class="grid grid-cols-2 sm:grid-cols-5 gap-2 mb-3 text-xs">
						<div>
							<div class="text-gray-400">{$i18n.t('First seen')}</div>
							<div class="font-medium text-gray-900 dark:text-white">
								{summary.first_seen ? dayjs(summary.first_seen).format('MMM D, YYYY') : '—'}
							</div>
						</div>
						<div>
							<div class="text-gray-400">{$i18n.t('Last Seen')}</div>
							<div class="font-medium text-gray-900 dark:text-white">
								{summary.last_seen ? dayjs(summary.last_seen).fromNow() : '—'}
							</div>
						</div>
						<div>
							<div class="text-gray-400">{$i18n.t('Sessions')}</div>
							<div class="font-medium text-gray-900 dark:text-white">
								{summary.sessions.toLocaleString()}
							</div>
						</div>
						<div>
							<div class="text-gray-400">{$i18n.t('Avg session')}</div>
							<div class="font-medium text-gray-900 dark:text-white">
								{formatMs(summary.avg_session_ms)}
							</div>
						</div>
						<div>
							<div class="text-gray-400">{$i18n.t('Busiest hour')}</div>
							<div class="font-medium text-gray-900 dark:text-white">
								{hour !== null ? `${hour}:00` : '—'}
							</div>
						</div>
					</div>

					{#if sparklineData.length > 1}
						<div class="mb-3">
							<ChartLine
								data={sparklineData}
								models={['events']}
								colors={['#3b82f6']}
								height={80}
								period={days === 7 ? 'week' : days === 90 ? 'year' : 'month'}
							/>
						</div>
					{/if}

					<div class="grid sm:grid-cols-2 gap-4 mb-1">
						{#if Object.keys(summary.tools).length > 0}
							<div>
								<div class="text-xs text-gray-400 mb-1">{$i18n.t('Tools')}</div>
								<UsageBars
									items={Object.entries(summary.tools)
										.sort((a, b) => b[1] - a[1])
										.map(([label, value]) => ({ label, value }))}
								/>
							</div>
						{/if}
						{#if summary.models.length > 0}
							<div>
								<div class="text-xs text-gray-400 mb-1">{$i18n.t('Top Models')}</div>
								<UsageBars
									items={summary.models.map((m) => ({ label: m.model, value: m.messages }))}
								/>
							</div>
						{/if}
					</div>
				{/if}
			</div>
```

Also add `import relativeTime from 'dayjs/plugin/relativeTime';` + `dayjs.extend(relativeTime);` to this file unconditionally — `fromNow` currently only works here via a side effect of Usage.svelte's own extend call; do not rely on it.

Note: UsageBars' fixed `w-36` label column is wide for the narrow modal — acceptable; do not fork the component.

- [ ] **Step 2: Verify**

Run: `npm run test:frontend`
Expected: PASS. Then `npx svelte-check --output human 2>&1 | grep -i "UsageUserModal"` — no new errors from this file.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/admin/Analytics/UsageUserModal.svelte
git commit -m "feat(usage): user modal summary header, sparkline, tool and model bars"
```

---

### Task 14: Full verification + smoke checklist

**Files:**
- Modify: `docs/superpowers/specs/2026-08-23-usage-dashboard-expansion-design.md` (known deviations — see Step 5)
- Modify: `docs/superpowers/specs/2026-08-19-usage-analytics-design.md` (§11 caveats — see Step 5)

- [ ] **Step 1: Backend suites**

Run (from `backend/`): `.venv/Scripts/python.exe -m pytest open_webui/test/usage open_webui/test/workos -q`
Expected: all PASS (usage = 28 existing + ~40 new; workos 261+; the 4 pre-existing `test_redis` sentinel failures and `test/apps` collection breakage are known baseline issues, not regressions)

- [ ] **Step 2: Frontend suite**

Run: `npm run test:frontend`
Expected: all PASS (471 existing + ~12 new usageStats tests)

- [ ] **Step 3: svelte-check targeted**

Run: `npx svelte-check --output human 2>&1 | grep -iE "Usage(StatCard|Heatmap|Bars|GroupsTable|UserModal)?\.svelte|usageStats"`
Expected: no errors introduced by this branch's files (repo baseline noise excluded)

- [ ] **Step 4: Record the browser smoke checklist (manual, user-driven — do NOT start a dev server unprompted)**

The combined smoke (base dashboard smoke is still pending) must cover:

1. Admin → Analytics → Usage renders: presence strip, tool cards with delta arrows, both charts, heatmap, top models, groups table, events + users tables.
2. "Online now" shows ≥1 with the admin logged in; clicking it lists names; a second logged-in browser increments it after refresh.
3. Scope selector: pick a group → all numbers shrink to members; groups table hides; "Everyone" restores it.
4. Click a groups-table row → scope switches to that group.
5. Period switch 7/30/90 re-scopes charts, heatmap, new-users.
6. Heatmap hottest cells match local working hours (rotation sanity: an event just generated should land in the current local hour/day cell).
7. Top models populated after sending a chat message.
8. User modal: stats header, sparkline, tool/model bars, activity list; busiest hour plausible in local time.
9. Refresh button reloads presence.
10. Base-dashboard pending item: log in WITHOUT a reload (soft navigation), browse, confirm new `page.view` rows in `usage_event`.

- [ ] **Step 5: Spec sync + final commit**

Known deviations to record in the expansion spec (verified during plan review 2026-08-23), plus anything else that drifted during implementation:

- §3.1 / §6: `users/{id}/activity` deliberately does NOT gain `group_id` (single-user scoped already).
- §3.2: `/usage/users/{id}/summary` returns `hours[24]` (UTC); `busiest_hour` is computed client-side (server-side would be wrong for any non-UTC admin). `/usage/heatmap`, `/usage/models`, `/usage/groups` responses are wrapped in envelope keys (`matrix`, `models`, `groups`).
- §3.4: presence applies the 120 s `SESSION_POOL_TIMEOUT` staleness filter — the reaper only sweeps every 120 s, so entries can be ~240 s stale, i.e. the count is NOT "trustworthy as-is". Session counts exclude `session_id IS NULL` rows (server events).
- §5 deleted-user bullet: implemented via a `Users.get_users_by_user_ids` existence cross-check in the presence endpoint (Task 8) — the pool caches real names, so the fallback alone never fires.

Also: spec §7 calls its four metric caveats "additions to the base spec's §11" — actually append them to §11 of `docs/superpowers/specs/2026-08-19-usage-analytics-design.md`; no other task does this.

```bash
git add -A docs/
git commit -m "docs: sync usage dashboard specs with implementation"
```
