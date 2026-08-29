# Sites Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record real pageviews for published sites and surface them inside the Sites `Overview` tab, deleting the mock `Analytics` tab.

**Architecture:** A new `site_view` table records one row per HTML pageview, written off the response path via `BackgroundTasks` from the existing public serve routes. Visitors are identified by a daily-rotating HMAC of IP + User-Agent, so no cookie is set and no PII is stored. A single owner-or-admin endpoint aggregates the rows into totals, a zero-filled daily series, and top pages; a new `InsightsCard` component renders them at the top of `Overview`.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, Alembic, pytest + pytest-asyncio + httpx ASGITransport, Svelte 5 (runes), Vitest, Tailwind.

**Spec:** `docs/superpowers/specs/2026-08-29-sites-analytics-design.md`

## Global Constraints

- Timestamps are epoch **milliseconds**, matching `sites.py::_now()` (`int(time.time() * 1000)`).
- Migration revision id is `b1c2d3e4f5a6`, `down_revision = 'e4f5a6b7c8d9'` (the current single head). Do not invent a different id — several obvious ids are already taken.
- The `site_view` table stores `is_owner` but **never** a viewer `user_id`.
- Analytics must never break site serving. Every recording call site is wrapped in `try/except Exception` with `log.warning`, and runs through `BackgroundTasks`.
- Queries must run on both SQLite and Postgres. Day bucketing uses integer division (`created_at / 86_400_000`), never a SQL date function.
- Allowed `days` values are exactly `{7, 30, 90}`. Anything else is a `400`.
- `views`, `series`, `unique_visitors`, and `top_pages` all exclude owner visits. `owner_views` is reported separately.
- Backend tests run with the repo venv: `backend/.venv/Scripts/python.exe -m pytest`. Frontend tests: `npm run test:frontend`.
- Python style in this codebase: single quotes, 4-space indent. Svelte style: tabs, Svelte 5 runes (`$props`, `$state`, `$derived`), `$i18n.t(...)` for every user-visible string.

## File Structure

**Created:**
- `backend/open_webui/migrations/versions/b1c2d3e4f5a6_site_view.py` — the `site_view` table
- `backend/open_webui/test/sites/test_analytics.py` — all backend tests for this feature
- `src/lib/components/sites/lib/analytics.ts` — pure chart/format helpers
- `src/lib/components/sites/lib/analytics.test.ts` — unit tests for those helpers
- `src/lib/components/sites/InsightsCard.svelte` — the chart-led hero card

**Modified:**
- `backend/open_webui/models/sites.py` — `SiteView` ORM model, `SiteViewsTable` DAO, view-row cleanup in `delete_site_by_id`
- `backend/open_webui/routers/sites.py` — recording helpers, serve-route hooks, analytics endpoint
- `src/lib/apis/sites/index.ts` — `getSiteAnalytics`
- `src/lib/components/sites/SiteDetail.svelte` — remove the analytics tab
- `src/lib/components/sites/tabs/OverviewTab.svelte` — restructure around `InsightsCard`

**Deleted:**
- `src/lib/components/sites/tabs/AnalyticsTab.svelte`

---

### Task 1: `site_view` table, model, and `record_view`

**Files:**
- Modify: `backend/open_webui/models/sites.py` (append after `Sites = SitesTable()`, and add the ORM model after the `Site` class)
- Create: `backend/open_webui/migrations/versions/b1c2d3e4f5a6_site_view.py`
- Test: `backend/open_webui/test/sites/test_analytics.py`

**Interfaces:**
- Consumes: `get_async_db_context`, `_now()` from `models/sites.py`
- Produces:
  - `class SiteView(Base)` with columns `id, site_id, path, visitor_key, is_owner, created_at`
  - `SiteViews.record_view(site_id: str, path: str, visitor_key: str, is_owner: bool, db=None) -> None`
  - module-level singleton `SiteViews = SiteViewsTable()`

- [ ] **Step 1: Write the failing test**

Create `backend/open_webui/test/sites/test_analytics.py`:

```python
import pytest

from open_webui.models.sites import SiteViews


@pytest.mark.asyncio
async def test_record_view_inserts_a_row():
    await SiteViews.record_view('s1', 'index.html', 'k1', False)
    rows = await SiteViews.list_views('s1')
    assert len(rows) == 1
    assert rows[0].site_id == 's1'
    assert rows[0].path == 'index.html'
    assert rows[0].visitor_key == 'k1'
    assert rows[0].is_owner is False
    assert rows[0].created_at > 1_600_000_000_000  # milliseconds, not seconds


@pytest.mark.asyncio
async def test_record_view_marks_owner_visits():
    await SiteViews.record_view('s1', 'index.html', 'k1', True)
    rows = await SiteViews.list_views('s1')
    assert rows[0].is_owner is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `backend/.venv/Scripts/python.exe -m pytest open_webui/test/sites/test_analytics.py -v` from `backend/`

Expected: FAIL with `ImportError: cannot import name 'SiteViews'`

- [ ] **Step 3: Add the ORM model and Pydantic model**

In `backend/open_webui/models/sites.py`, directly after the `Site` class and before `class SiteModel`:

```python
class SiteView(Base):
    __tablename__ = 'site_view'

    id = Column(Text, primary_key=True)
    site_id = Column(Text, nullable=False)
    path = Column(Text, nullable=False)
    # Daily-rotating HMAC of IP + User-Agent. Not reversible to an IP, and not
    # linkable to the same visitor on another day or another site.
    visitor_key = Column(Text, nullable=False)
    is_owner = Column(Boolean, nullable=False, default=False)
    created_at = Column(BigInteger, nullable=False)

    __table_args__ = (Index('ix_site_view_site_created', 'site_id', 'created_at'),)
```

Add `Index` to the existing sqlalchemy import at the top of the file:

```python
from sqlalchemy import BigInteger, Boolean, Column, Index, JSON, Text, delete, func, select
```

Add the Pydantic model after `class SiteModel`:

```python
class SiteViewModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    site_id: str
    path: str
    visitor_key: str
    is_owner: bool
    created_at: int
```

- [ ] **Step 4: Add the DAO**

At the end of `backend/open_webui/models/sites.py`, after `Sites = SitesTable()`:

```python
class SiteViewsTable:
    async def record_view(
        self,
        site_id: str,
        path: str,
        visitor_key: str,
        is_owner: bool,
        db: Optional[AsyncSession] = None,
    ) -> None:
        async with get_async_db_context(db) as db:
            db.add(
                SiteView(
                    id=str(uuid.uuid4()),
                    site_id=site_id,
                    path=path,
                    visitor_key=visitor_key,
                    is_owner=is_owner,
                    created_at=_now(),
                )
            )
            await db.commit()

    async def list_views(
        self, site_id: str, db: Optional[AsyncSession] = None
    ) -> list[SiteViewModel]:
        """Test/debug helper: every recorded view for a site, oldest first."""
        async with get_async_db_context(db) as db:
            result = await db.execute(
                select(SiteView)
                .where(SiteView.site_id == site_id)
                .order_by(SiteView.created_at.asc())
            )
            return [SiteViewModel.model_validate(v) for v in result.scalars().all()]


SiteViews = SiteViewsTable()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `backend/.venv/Scripts/python.exe -m pytest open_webui/test/sites/test_analytics.py -v` from `backend/`

Expected: PASS (2 passed)

- [ ] **Step 6: Write the migration**

Create `backend/open_webui/migrations/versions/b1c2d3e4f5a6_site_view.py`:

```python
"""site_view table for Sites analytics

Spec: docs/superpowers/specs/2026-08-29-sites-analytics-design.md

Revision ID: b1c2d3e4f5a6
Revises: e4f5a6b7c8d9
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'site_view',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('site_id', sa.Text(), nullable=False),
        sa.Column('path', sa.Text(), nullable=False),
        sa.Column('visitor_key', sa.Text(), nullable=False),
        sa.Column('is_owner', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_site_view_site_created', 'site_view', ['site_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_site_view_site_created', table_name='site_view')
    op.drop_table('site_view')
```

- [ ] **Step 7: Verify the migration graph still has exactly one head**

Run from the repo root:

```bash
cd backend/open_webui/migrations/versions && python -c "import os,re; revs={}; downs=set(); [ (revs.update({re.search(r\"^revision(?::\s*str)?\s*=\s*['\\\"]([^'\\\"]+)\",open(f,encoding='utf-8',errors='replace').read(),re.M).group(1): f}) if re.search(r\"^revision(?::\s*str)?\s*=\s*['\\\"]([^'\\\"]+)\",open(f,encoding='utf-8',errors='replace').read(),re.M) else None) for f in os.listdir('.') if f.endswith('.py') ]; [ downs.add(m.group(1)) for f in os.listdir('.') if f.endswith('.py') for m in [re.search(r\"^down_revision(?::\s*[^=]+)?\s*=\s*['\\\"]([^'\\\"]+)\",open(f,encoding='utf-8',errors='replace').read(),re.M)] if m ]; print('HEADS:', [k for k in revs if k not in downs])"
```

Expected output: `HEADS: ['b1c2d3e4f5a6']`

If more than one head is printed, the `down_revision` is wrong — fix it before continuing.

- [ ] **Step 8: Commit**

```bash
git add backend/open_webui/models/sites.py backend/open_webui/migrations/versions/b1c2d3e4f5a6_site_view.py backend/open_webui/test/sites/test_analytics.py
git commit -m "feat(sites): site_view table and record_view DAO"
```

---

### Task 2: `get_analytics` aggregation

**Files:**
- Modify: `backend/open_webui/models/sites.py` (add to `SiteViewsTable`)
- Test: `backend/open_webui/test/sites/test_analytics.py`

**Interfaces:**
- Consumes: `SiteViews.record_view`, `SiteView` from Task 1
- Produces: `SiteViews.get_analytics(site_id: str, days: int, now_ms: Optional[int] = None, db=None) -> dict` returning
  `{'days': int, 'totals': {'views': int, 'unique_visitors': int, 'owner_views': int}, 'series': [{'day': 'YYYY-MM-DD', 'views': int}], 'top_pages': [{'path': str, 'views': int}]}`

`now_ms` exists only so tests can pin the window; production callers omit it.

- [ ] **Step 1: Write the failing tests**

Append to `backend/open_webui/test/sites/test_analytics.py`:

```python
from datetime import datetime, timezone

DAY_MS = 86_400_000
# 2026-08-29T12:00:00Z, pinned so day bucketing is deterministic.
NOW_MS = int(datetime(2026, 8, 29, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)


async def _record_at(site_id, path, key, is_owner, ts_ms):
    """record_view stamps its own time; rewrite created_at for windowed tests."""
    from open_webui.internal.db import get_async_db_context
    from open_webui.models.sites import SiteView
    from sqlalchemy import select

    await SiteViews.record_view(site_id, path, key, is_owner)
    async with get_async_db_context(None) as db:
        row = (
            await db.execute(
                select(SiteView).where(SiteView.site_id == site_id).order_by(SiteView.created_at.desc())
            )
        ).scalars().first()
        row.created_at = ts_ms
        await db.commit()


@pytest.mark.asyncio
async def test_get_analytics_excludes_owner_from_views_and_reports_them_separately():
    await _record_at('s1', 'index.html', 'k1', False, NOW_MS)
    await _record_at('s1', 'index.html', 'k2', False, NOW_MS)
    await _record_at('s1', 'index.html', 'kowner', True, NOW_MS)

    a = await SiteViews.get_analytics('s1', 30, now_ms=NOW_MS)

    assert a['totals']['views'] == 2
    assert a['totals']['owner_views'] == 1
    assert a['totals']['unique_visitors'] == 2


@pytest.mark.asyncio
async def test_get_analytics_counts_repeat_visitors_once_in_uniques():
    await _record_at('s1', 'index.html', 'k1', False, NOW_MS)
    await _record_at('s1', 'a.html', 'k1', False, NOW_MS)

    a = await SiteViews.get_analytics('s1', 30, now_ms=NOW_MS)

    assert a['totals']['views'] == 2
    assert a['totals']['unique_visitors'] == 1


@pytest.mark.asyncio
async def test_get_analytics_series_is_zero_filled_and_window_sized():
    await _record_at('s1', 'index.html', 'k1', False, NOW_MS)
    await _record_at('s1', 'index.html', 'k2', False, NOW_MS - 2 * DAY_MS)

    a = await SiteViews.get_analytics('s1', 7, now_ms=NOW_MS)

    assert len(a['series']) == 7
    assert a['series'][-1] == {'day': '2026-08-29', 'views': 1}
    assert a['series'][-3] == {'day': '2026-08-27', 'views': 1}
    assert a['series'][-2] == {'day': '2026-08-28', 'views': 0}
    days = [p['day'] for p in a['series']]
    assert days == sorted(days)


@pytest.mark.asyncio
async def test_get_analytics_ignores_views_outside_the_window():
    await _record_at('s1', 'index.html', 'k1', False, NOW_MS - 40 * DAY_MS)

    a = await SiteViews.get_analytics('s1', 7, now_ms=NOW_MS)

    assert a['totals']['views'] == 0
    assert all(p['views'] == 0 for p in a['series'])


@pytest.mark.asyncio
async def test_get_analytics_top_pages_ranked_owner_excluded_capped_at_five():
    for i in range(3):
        await _record_at('s1', 'index.html', f'k{i}', False, NOW_MS)
    await _record_at('s1', 'about.html', 'k9', False, NOW_MS)
    await _record_at('s1', 'secret.html', 'kowner', True, NOW_MS)
    for i in range(6):
        await _record_at('s1', f'p{i}.html', f'z{i}', False, NOW_MS)

    a = await SiteViews.get_analytics('s1', 30, now_ms=NOW_MS)

    assert len(a['top_pages']) == 5
    assert a['top_pages'][0] == {'path': 'index.html', 'views': 3}
    assert 'secret.html' not in [p['path'] for p in a['top_pages']]


@pytest.mark.asyncio
async def test_get_analytics_is_scoped_to_one_site():
    await _record_at('s1', 'index.html', 'k1', False, NOW_MS)
    await _record_at('s2', 'index.html', 'k2', False, NOW_MS)

    a = await SiteViews.get_analytics('s1', 30, now_ms=NOW_MS)

    assert a['totals']['views'] == 1


@pytest.mark.asyncio
async def test_get_analytics_empty_site_returns_zeros_not_an_error():
    a = await SiteViews.get_analytics('nope', 30, now_ms=NOW_MS)

    assert a['totals'] == {'views': 0, 'unique_visitors': 0, 'owner_views': 0}
    assert len(a['series']) == 30
    assert a['top_pages'] == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `backend/.venv/Scripts/python.exe -m pytest open_webui/test/sites/test_analytics.py -v` from `backend/`

Expected: FAIL with `AttributeError: 'SiteViewsTable' object has no attribute 'get_analytics'`

- [ ] **Step 3: Implement `get_analytics`**

Add to `SiteViewsTable` in `backend/open_webui/models/sites.py`:

```python
    async def get_analytics(
        self,
        site_id: str,
        days: int,
        now_ms: Optional[int] = None,
        db: Optional[AsyncSession] = None,
    ) -> dict:
        """Totals, a zero-filled daily series, and top pages for a time window.

        Owner visits are excluded from every visitor-facing number and reported
        on their own as `owner_views`.

        Day bucketing is integer division on the millisecond timestamp rather
        than a SQL date function, so the identical query runs on SQLite and
        Postgres.
        """
        now_ms = _now() if now_ms is None else now_ms
        day_ms = 86_400_000
        today_idx = now_ms // day_ms
        first_idx = today_idx - (days - 1)
        window_start = first_idx * day_ms

        async with get_async_db_context(db) as db:
            in_window = (SiteView.site_id == site_id, SiteView.created_at >= window_start)
            visitors = (*in_window, SiteView.is_owner.is_(False))

            totals_row = (
                await db.execute(
                    select(
                        func.count(SiteView.id),
                        func.count(func.distinct(SiteView.visitor_key)),
                    ).where(*visitors)
                )
            ).one()
            owner_views = (
                await db.execute(
                    select(func.count(SiteView.id)).where(*in_window, SiteView.is_owner.is_(True))
                )
            ).scalar_one()

            day_idx = (SiteView.created_at / day_ms).label('day_idx')
            rows = (
                await db.execute(
                    select(day_idx, func.count(SiteView.id)).where(*visitors).group_by(day_idx)
                )
            ).all()
            counts = {int(idx): int(n) for idx, n in rows}

            pages = (
                await db.execute(
                    select(SiteView.path, func.count(SiteView.id).label('n'))
                    .where(*visitors)
                    .group_by(SiteView.path)
                    .order_by(func.count(SiteView.id).desc(), SiteView.path.asc())
                    .limit(5)
                )
            ).all()

        series = [
            {
                'day': datetime.fromtimestamp(idx * day_ms / 1000, tz=timezone.utc).strftime('%Y-%m-%d'),
                'views': counts.get(idx, 0),
            }
            for idx in range(first_idx, today_idx + 1)
        ]

        return {
            'days': days,
            'totals': {
                'views': int(totals_row[0]),
                'unique_visitors': int(totals_row[1]),
                'owner_views': int(owner_views),
            },
            'series': series,
            'top_pages': [{'path': p, 'views': int(n)} for p, n in pages],
        }
```

Add the datetime import at the top of `backend/open_webui/models/sites.py`, under the existing `import time`:

```python
from datetime import datetime, timezone
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `backend/.venv/Scripts/python.exe -m pytest open_webui/test/sites/test_analytics.py -v` from `backend/`

Expected: PASS (9 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/models/sites.py backend/open_webui/test/sites/test_analytics.py
git commit -m "feat(sites): analytics aggregation over site_view rows"
```

---

### Task 3: Purge view rows when a site is deleted

**Files:**
- Modify: `backend/open_webui/models/sites.py:SitesTable.delete_site_by_id`
- Test: `backend/open_webui/test/sites/test_analytics.py`

**Interfaces:**
- Consumes: `SiteView` (Task 1), `SiteViews.list_views` (Task 1)
- Produces: no new signature — `delete_site_by_id` gains a third delete inside its existing transaction

- [ ] **Step 1: Write the failing test**

Append to `backend/open_webui/test/sites/test_analytics.py`:

```python
@pytest.mark.asyncio
async def test_deleting_a_site_purges_its_view_rows():
    from open_webui.models.sites import Sites

    site = await Sites.insert_new_site(
        'o1',
        name='Demo',
        slug='demo-purge',
        public=True,
        files=[{'name': 'index.html', 'size': 1, 'content_type': 'text/html'}],
        entry_file='index.html',
    )
    await SiteViews.record_view(site.id, 'index.html', 'k1', False)
    assert len(await SiteViews.list_views(site.id)) == 1

    await Sites.delete_site_by_id(site.id)

    assert await SiteViews.list_views(site.id) == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `backend/.venv/Scripts/python.exe -m pytest open_webui/test/sites/test_analytics.py::test_deleting_a_site_purges_its_view_rows -v` from `backend/`

Expected: FAIL — `assert [SiteViewModel(...)] == []` (the row survives the delete)

- [ ] **Step 3: Extend the delete transaction**

In `backend/open_webui/models/sites.py`, in `SitesTable.delete_site_by_id`, add a third delete after the `AccessGrant` delete and before `await db.commit()`:

```python
            await db.execute(delete(SiteView).where(SiteView.site_id == id))
```

Update that method's docstring to name the third table:

```python
        """Delete a site, its access grants, and its view rows in ONE transaction.

        A crash between the deletes must not leave grant rows behind for a dead
        site id (inert, but clutter that never expires). View rows matter more:
        the table has no retention policy, so orphans would persist forever.
        """
```

- [ ] **Step 4: Run the full sites suite to verify nothing regressed**

Run: `backend/.venv/Scripts/python.exe -m pytest open_webui/test/sites/ -v` from `backend/`

Expected: PASS, all tests in `test_models.py`, `test_router_crud.py`, `test_router_manage.py`, `test_serving.py`, `test_analytics.py`

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/models/sites.py backend/open_webui/test/sites/test_analytics.py
git commit -m "fix(sites): purge view rows when a site is deleted"
```

---

### Task 4: Recording helpers — visitor key, bot filter, HTML filter

**Files:**
- Modify: `backend/open_webui/routers/sites.py` (add after the `SERVE_HEADERS` block, before `_get_optional_user`)
- Test: `backend/open_webui/test/sites/test_analytics.py`

**Interfaces:**
- Consumes: `WEBUI_SECRET_KEY` from `open_webui.env`
- Produces:
  - `_visitor_key(site_id: str, ip: str, user_agent: str, *, now_ms: Optional[int] = None) -> str` — 32 hex chars
  - `_is_bot(user_agent: str) -> bool`
  - `_is_html(filename: str) -> bool`

- [ ] **Step 1: Write the failing tests**

Append to `backend/open_webui/test/sites/test_analytics.py`:

```python
import open_webui.routers.sites as sites_router


def test_visitor_key_is_stable_within_a_day_and_rotates_across_days():
    a = sites_router._visitor_key('s1', '10.0.0.1', 'Mozilla/5.0', now_ms=NOW_MS)
    b = sites_router._visitor_key('s1', '10.0.0.1', 'Mozilla/5.0', now_ms=NOW_MS + 3600_000)
    c = sites_router._visitor_key('s1', '10.0.0.1', 'Mozilla/5.0', now_ms=NOW_MS + DAY_MS)

    assert a == b
    assert a != c
    assert len(a) == 32
    assert all(ch in '0123456789abcdef' for ch in a)


def test_visitor_key_does_not_correlate_across_sites():
    a = sites_router._visitor_key('s1', '10.0.0.1', 'Mozilla/5.0', now_ms=NOW_MS)
    b = sites_router._visitor_key('s2', '10.0.0.1', 'Mozilla/5.0', now_ms=NOW_MS)

    assert a != b


def test_visitor_key_separates_different_visitors():
    a = sites_router._visitor_key('s1', '10.0.0.1', 'Mozilla/5.0', now_ms=NOW_MS)
    b = sites_router._visitor_key('s1', '10.0.0.2', 'Mozilla/5.0', now_ms=NOW_MS)
    c = sites_router._visitor_key('s1', '10.0.0.1', 'Safari/1.0', now_ms=NOW_MS)

    assert len({a, b, c}) == 3


def test_visitor_key_never_embeds_the_raw_ip():
    key = sites_router._visitor_key('s1', '10.0.0.1', 'Mozilla/5.0', now_ms=NOW_MS)

    assert '10.0.0.1' not in key


@pytest.mark.parametrize(
    'ua',
    [
        '',
        '   ',
        'Googlebot/2.1',
        'Mozilla/5.0 (compatible; bingbot/2.0)',
        'Twitterbot/1.0',
        'curl/8.4.0',
        'Wget/1.21',
        'python-requests/2.31.0',
        'HeadlessChrome/120.0',
        'Mozilla/5.0 (compatible; Yahoo! Slurp)',
        'Some Spider 1.0',
        'my-crawler/1',
    ],
)
def test_is_bot_rejects_non_humans(ua):
    assert sites_router._is_bot(ua) is True


@pytest.mark.parametrize(
    'ua',
    [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Version/17.0 Safari/605.1.15',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E148',
    ],
)
def test_is_bot_accepts_real_browsers(ua):
    assert sites_router._is_bot(ua) is False


@pytest.mark.parametrize('name', ['index.html', 'a.htm', 'DEEP.HTML', 'x.Htm'])
def test_is_html_accepts_documents(name):
    assert sites_router._is_html(name) is True


@pytest.mark.parametrize('name', ['pic.png', 'style.css', 'app.js', 'index.html.map', 'noext'])
def test_is_html_rejects_assets(name):
    assert sites_router._is_html(name) is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `backend/.venv/Scripts/python.exe -m pytest open_webui/test/sites/test_analytics.py -k "visitor_key or is_bot or is_html" -v` from `backend/`

Expected: FAIL with `AttributeError: module 'open_webui.routers.sites' has no attribute '_visitor_key'`

- [ ] **Step 3: Implement the helpers**

In `backend/open_webui/routers/sites.py`, add to the imports at the top:

```python
import hashlib
import hmac
import time
from datetime import datetime, timezone
```

Add `WEBUI_SECRET_KEY` to the existing `open_webui.env` import block:

```python
from open_webui.env import (
    DATA_DIR,
    UVICORN_WORKERS,
    WEBUI_AUTH_COOKIE_SAME_SITE,
    WEBUI_AUTH_TRUSTED_EMAIL_HEADER,
    WEBUI_SECRET_KEY,
)
```

Add `SiteViews` to the existing models import:

```python
from open_webui.models.sites import SiteModel, Sites, SiteViews
```

Then add the helpers immediately after the `SERVE_HEADERS` dict:

```python
BOT_UA_RE = re.compile(
    r'bot|crawl|spider|slurp|headless|curl|wget|python-requests', re.IGNORECASE
)

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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `backend/.venv/Scripts/python.exe -m pytest open_webui/test/sites/test_analytics.py -k "visitor_key or is_bot or is_html" -v` from `backend/`

Expected: PASS (25 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/sites.py backend/open_webui/test/sites/test_analytics.py
git commit -m "feat(sites): visitor-key, bot, and html filters for view recording"
```

---

### Task 5: Hook recording into the serve routes

**Files:**
- Modify: `backend/open_webui/routers/sites.py` (`serve_site_entry`, `serve_site_file`, plus a new `_record_view` helper)
- Test: `backend/open_webui/test/sites/test_analytics.py`

**Interfaces:**
- Consumes: `_visitor_key`, `_is_bot`, `_is_html` (Task 4); `SiteViews.record_view` (Task 1); `_resolve_site_for_view`, `_get_optional_user`, `_serve_file` (existing)
- Produces: `_record_view(site, filename: str, request: Request, background: BackgroundTasks, *, viewer=None) -> None`

- [ ] **Step 1: Write the failing tests**

Append to `backend/open_webui/test/sites/test_analytics.py`:

```python
from types import SimpleNamespace

import httpx
from fastapi import FastAPI
from httpx import ASGITransport

from open_webui.models.sites import Sites

R_OWNER = SimpleNamespace(id='ro1', role='user', name='Owner', email='ro@x.io')
R_VIEWER = SimpleNamespace(id='rv1', role='user', name='Viewer', email='rv@x.io')

BROWSER_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36'


def _serve_client(monkeypatch, tmp_path, *, viewer):
    async def _fake_optional_user(request):
        return viewer

    app = FastAPI()
    app.include_router(sites_router.serve_router)
    monkeypatch.setattr(sites_router, '_get_optional_user', _fake_optional_user)
    monkeypatch.setattr(sites_router, 'SITES_DIR', tmp_path)
    return httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url='http://test',
        headers={'user-agent': BROWSER_UA},
    )


async def _seed_site(tmp_path, *, slug, public):
    site = await Sites.insert_new_site(
        R_OWNER.id,
        name='Demo',
        slug=slug,
        public=public,
        files=[
            {'name': 'index.html', 'size': 12, 'content_type': 'text/html'},
            {'name': 'about.html', 'size': 12, 'content_type': 'text/html'},
            {'name': 'pic.png', 'size': 4, 'content_type': 'image/png'},
        ],
        entry_file='index.html',
    )
    d = tmp_path / site.id
    d.mkdir(parents=True)
    (d / 'index.html').write_bytes(b'<h1>demo</h1>')
    (d / 'about.html').write_bytes(b'<h1>about</h1>')
    (d / 'pic.png').write_bytes(b'\x89PNG')
    return site


@pytest.mark.asyncio
async def test_entry_pageview_is_recorded(monkeypatch, tmp_path):
    site = await _seed_site(tmp_path, slug='rec-entry', public=True)
    async with _serve_client(monkeypatch, tmp_path, viewer=None) as c:
        assert (await c.get('/sites/rec-entry/')).status_code == 200

    rows = await SiteViews.list_views(site.id)
    assert len(rows) == 1
    assert rows[0].path == 'index.html'
    assert rows[0].is_owner is False


@pytest.mark.asyncio
async def test_html_subpage_is_recorded_but_assets_are_not(monkeypatch, tmp_path):
    site = await _seed_site(tmp_path, slug='rec-assets', public=True)
    async with _serve_client(monkeypatch, tmp_path, viewer=None) as c:
        assert (await c.get('/sites/rec-assets/about.html')).status_code == 200
        assert (await c.get('/sites/rec-assets/pic.png')).status_code == 200

    rows = await SiteViews.list_views(site.id)
    assert [r.path for r in rows] == ['about.html']


@pytest.mark.asyncio
async def test_bot_requests_are_not_recorded(monkeypatch, tmp_path):
    site = await _seed_site(tmp_path, slug='rec-bot', public=True)
    async with _serve_client(monkeypatch, tmp_path, viewer=None) as c:
        r = await c.get('/sites/rec-bot/', headers={'user-agent': 'Googlebot/2.1'})
        assert r.status_code == 200

    assert await SiteViews.list_views(site.id) == []


@pytest.mark.asyncio
async def test_login_redirect_is_not_recorded(monkeypatch, tmp_path):
    site = await _seed_site(tmp_path, slug='rec-redirect', public=False)
    async with _serve_client(monkeypatch, tmp_path, viewer=None) as c:
        r = await c.get('/sites/rec-redirect/')
        assert r.status_code == 302

    assert await SiteViews.list_views(site.id) == []


@pytest.mark.asyncio
async def test_owner_visit_is_flagged(monkeypatch, tmp_path):
    site = await _seed_site(tmp_path, slug='rec-owner', public=False)
    async with _serve_client(monkeypatch, tmp_path, viewer=R_OWNER) as c:
        assert (await c.get('/sites/rec-owner/')).status_code == 200

    rows = await SiteViews.list_views(site.id)
    assert len(rows) == 1
    assert rows[0].is_owner is True


@pytest.mark.asyncio
async def test_non_owner_visit_is_not_flagged(monkeypatch, tmp_path):
    site = await _seed_site(tmp_path, slug='rec-viewer', public=True)
    async with _serve_client(monkeypatch, tmp_path, viewer=R_VIEWER) as c:
        assert (await c.get('/sites/rec-viewer/')).status_code == 200

    rows = await SiteViews.list_views(site.id)
    assert rows[0].is_owner is False


@pytest.mark.asyncio
async def test_recording_failure_does_not_break_serving(monkeypatch, tmp_path):
    await _seed_site(tmp_path, slug='rec-boom', public=True)

    async def _boom(*args, **kwargs):
        raise RuntimeError('db down')

    monkeypatch.setattr(sites_router.SiteViews, 'record_view', _boom)

    async with _serve_client(monkeypatch, tmp_path, viewer=None) as c:
        r = await c.get('/sites/rec-boom/')

    assert r.status_code == 200
    assert r.content == b'<h1>demo</h1>'
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `backend/.venv/Scripts/python.exe -m pytest open_webui/test/sites/test_analytics.py -k "recorded or flagged or redirect or breaking or break" -v` from `backend/`

Expected: FAIL — `assert len(rows) == 1` fails with `0` (nothing is recorded yet)

- [ ] **Step 3: Add the `_record_view` helper**

In `backend/open_webui/routers/sites.py`, add `BackgroundTasks` to the fastapi import:

```python
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
```

Add the helper immediately after `_is_html`:

```python
async def _record_view_task(site_id: str, filename: str, visitor_key: str, is_owner: bool) -> None:
    """Best-effort. Analytics must never take a published page down."""
    try:
        await SiteViews.record_view(site_id, filename, visitor_key, is_owner)
    except Exception:
        log.warning('Failed to record site view for %s', site_id, exc_info=True)


async def _record_view(
    site, filename: str, request: Request, background: BackgroundTasks, *, viewer=None
) -> None:
    """Queue a pageview for a successfully served document.

    Callers must invoke this only AFTER access resolution succeeds, so a visitor
    bounced to the login page is never counted as having viewed the page.
    """
    try:
        if not _is_html(filename):
            return
        user_agent = request.headers.get('user-agent', '')
        if _is_bot(user_agent):
            return
        if viewer is None and (
            request.headers.get('authorization') or request.cookies.get('token')
        ):
            # Public sites skip user resolution entirely for anonymous traffic;
            # only pay the token decode when a token is actually present.
            viewer = await _get_optional_user(request)
        ip = request.client.host if request.client else ''
        background.add_task(
            _record_view_task,
            site.id,
            filename,
            _visitor_key(site.id, ip, user_agent),
            bool(viewer is not None and viewer.id == site.user_id),
        )
    except Exception:
        log.warning('Failed to queue site view for %s', getattr(site, 'id', '?'), exc_info=True)
```

- [ ] **Step 4: Wire the helper into both serve routes**

Replace `serve_site_entry` and `serve_site_file` at the bottom of `backend/open_webui/routers/sites.py`:

```python
@serve_router.get('/sites/{slug}/')
async def serve_site_entry(
    slug: str,
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_async_session),
):
    site = await _resolve_site_for_view(slug, request, db, is_entry=True)
    if isinstance(site, RedirectResponse):
        return site
    await _record_view(site, site.entry_file, request, background)
    return _serve_file(site, site.entry_file)


@serve_router.get('/sites/{slug}/{filename}')
async def serve_site_file(
    slug: str,
    filename: str,
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_async_session),
):
    site = await _resolve_site_for_view(slug, request, db, is_entry=False)
    await _record_view(site, filename, request, background)
    return _serve_file(site, filename)
```

- [ ] **Step 5: Run the full sites suite**

Run: `backend/.venv/Scripts/python.exe -m pytest open_webui/test/sites/ -v` from `backend/`

Expected: PASS — the seven new recording tests plus every pre-existing serving test

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/routers/sites.py backend/open_webui/test/sites/test_analytics.py
git commit -m "feat(sites): record pageviews from the public serve routes"
```

---

### Task 6: Analytics endpoint

**Files:**
- Modify: `backend/open_webui/routers/sites.py` (add after the existing `get_site` route)
- Test: `backend/open_webui/test/sites/test_analytics.py`

**Interfaces:**
- Consumes: `_require_publisher`, `_get_owned_site` (existing); `SiteViews.get_analytics` (Task 2); the `_seed_site`, `R_OWNER`, and `R_VIEWER` test fixtures defined in Task 5's test additions, in the same file
- Produces: `GET /{id}/analytics?days=` on the authenticated `router`

- [ ] **Step 1: Write the failing tests**

Look at `backend/open_webui/test/sites/test_router_crud.py` first to copy its authenticated-client fixture style, then append to `backend/open_webui/test/sites/test_analytics.py`:

```python
def _api_client(monkeypatch, *, user):
    from open_webui.utils.auth import get_verified_user

    app = FastAPI()
    app.include_router(sites_router.router, prefix='/api/v1/sites')
    app.dependency_overrides[get_verified_user] = lambda: user

    async def _allow(request, u, db):
        return None

    monkeypatch.setattr(sites_router, '_require_publisher', _allow)
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url='http://test')


@pytest.mark.asyncio
async def test_analytics_endpoint_returns_the_full_shape(monkeypatch, tmp_path):
    site = await _seed_site(tmp_path, slug='api-shape', public=True)
    await SiteViews.record_view(site.id, 'index.html', 'k1', False)
    await SiteViews.record_view(site.id, 'index.html', 'kowner', True)

    async with _api_client(monkeypatch, user=R_OWNER) as c:
        r = await c.get(f'/api/v1/sites/{site.id}/analytics?days=30')

    assert r.status_code == 200
    body = r.json()
    assert body['days'] == 30
    assert body['totals'] == {'views': 1, 'unique_visitors': 1, 'owner_views': 1}
    assert len(body['series']) == 30
    assert body['top_pages'] == [{'path': 'index.html', 'views': 1}]


@pytest.mark.asyncio
async def test_analytics_endpoint_defaults_to_thirty_days(monkeypatch, tmp_path):
    site = await _seed_site(tmp_path, slug='api-default', public=True)

    async with _api_client(monkeypatch, user=R_OWNER) as c:
        r = await c.get(f'/api/v1/sites/{site.id}/analytics')

    assert r.status_code == 200
    assert r.json()['days'] == 30


@pytest.mark.asyncio
@pytest.mark.parametrize('days', [1, 14, 365, 0, -7])
async def test_analytics_endpoint_rejects_unsupported_windows(monkeypatch, tmp_path, days):
    site = await _seed_site(tmp_path, slug=f'api-bad-{abs(days)}', public=True)

    async with _api_client(monkeypatch, user=R_OWNER) as c:
        r = await c.get(f'/api/v1/sites/{site.id}/analytics?days={days}')

    assert r.status_code == 400


@pytest.mark.asyncio
async def test_analytics_endpoint_hides_other_peoples_sites(monkeypatch, tmp_path):
    site = await _seed_site(tmp_path, slug='api-private', public=True)

    async with _api_client(monkeypatch, user=R_VIEWER) as c:
        r = await c.get(f'/api/v1/sites/{site.id}/analytics?days=30')

    # 404, not 403: the endpoint must not confirm that the site exists.
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_analytics_endpoint_allows_admins(monkeypatch, tmp_path):
    site = await _seed_site(tmp_path, slug='api-admin', public=True)
    admin = SimpleNamespace(id='adm', role='admin', name='Admin', email='a@x.io')

    async with _api_client(monkeypatch, user=admin) as c:
        r = await c.get(f'/api/v1/sites/{site.id}/analytics?days=7')

    assert r.status_code == 200
    assert r.json()['days'] == 7
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `backend/.venv/Scripts/python.exe -m pytest open_webui/test/sites/test_analytics.py -k "analytics_endpoint" -v` from `backend/`

Expected: FAIL with `assert 404 == 200` (the route does not exist yet)

- [ ] **Step 3: Add the endpoint**

In `backend/open_webui/routers/sites.py`, add immediately after the `_get_owned_site` function:

```python
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
```

Note: `_bad` already exists in this file and returns a 400 `HTTPException`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `backend/.venv/Scripts/python.exe -m pytest open_webui/test/sites/test_analytics.py -k "analytics_endpoint" -v` from `backend/`

Expected: PASS (9 passed — the parametrized case counts as 5)

- [ ] **Step 5: Run the whole backend sites suite**

Run: `backend/.venv/Scripts/python.exe -m pytest open_webui/test/sites/ -v` from `backend/`

Expected: PASS, no failures

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/routers/sites.py backend/open_webui/test/sites/test_analytics.py
git commit -m "feat(sites): owner-scoped analytics endpoint"
```

---

### Task 7: Frontend chart helpers

**Files:**
- Create: `src/lib/components/sites/lib/analytics.ts`
- Test: `src/lib/components/sites/lib/analytics.test.ts`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `type SeriesPoint = { day: string; views: number }`
  - `chartGeometry(series: SeriesPoint[], width: number, height: number): { points: [number, number][]; line: string; area: string }`
  - `nearestIndex(series: SeriesPoint[], x: number, width: number): number`
  - `formatCount(n: number): string`

The client never zero-fills — the API guarantees one entry per day in the window.

- [ ] **Step 1: Write the failing test**

Create `src/lib/components/sites/lib/analytics.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { chartGeometry, nearestIndex, formatCount } from './analytics';

const pts = (...views: number[]) =>
	views.map((v, i) => ({ day: `2026-08-${String(i + 1).padStart(2, '0')}`, views: v }));

describe('chartGeometry', () => {
	it('spans the full width and starts the path with a moveto', () => {
		const g = chartGeometry(pts(0, 5, 10), 100, 50);
		expect(g.points[0][0]).toBe(0);
		expect(g.points[2][0]).toBe(100);
		expect(g.line.startsWith('M')).toBe(true);
	});

	it('puts the largest value highest on the canvas', () => {
		const g = chartGeometry(pts(1, 9), 100, 50);
		expect(g.points[1][1]).toBeLessThan(g.points[0][1]);
	});

	it('produces no NaN for an all-zero series', () => {
		const g = chartGeometry(pts(0, 0, 0), 100, 50);
		expect(g.line).not.toContain('NaN');
		expect(g.area).not.toContain('NaN');
	});

	it('produces no NaN for a single point', () => {
		const g = chartGeometry(pts(7), 100, 50);
		expect(g.line).not.toContain('NaN');
		expect(g.points).toHaveLength(1);
	});

	it('returns empty geometry for an empty series', () => {
		const g = chartGeometry([], 100, 50);
		expect(g.points).toEqual([]);
		expect(g.line).toBe('');
		expect(g.area).toBe('');
	});

	it('closes the area path back to the baseline', () => {
		const g = chartGeometry(pts(1, 2), 100, 50);
		expect(g.area.endsWith('Z')).toBe(true);
	});
});

describe('nearestIndex', () => {
	it('maps an x offset to the closest point', () => {
		const s = pts(1, 2, 3, 4, 5);
		expect(nearestIndex(s, 0, 100)).toBe(0);
		expect(nearestIndex(s, 100, 100)).toBe(4);
		expect(nearestIndex(s, 51, 100)).toBe(2);
	});

	it('clamps outside the canvas instead of returning a bad index', () => {
		const s = pts(1, 2, 3);
		expect(nearestIndex(s, -20, 100)).toBe(0);
		expect(nearestIndex(s, 999, 100)).toBe(2);
	});

	it('returns 0 for an empty series', () => {
		expect(nearestIndex([], 10, 100)).toBe(0);
	});
});

describe('formatCount', () => {
	it('adds thousands separators', () => {
		expect(formatCount(2847)).toBe('2,847');
		expect(formatCount(0)).toBe('0');
		expect(formatCount(999)).toBe('999');
	});
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npx vitest run src/lib/components/sites/lib/analytics.test.ts`

Expected: FAIL — `Failed to resolve import "./analytics"`

- [ ] **Step 3: Implement the helpers**

Create `src/lib/components/sites/lib/analytics.ts`:

```ts
export type SeriesPoint = { day: string; views: number };

export type ChartGeometry = {
	points: [number, number][];
	line: string;
	area: string;
};

const PAD_TOP = 8;
const PAD_BOTTOM = 4;

export const chartGeometry = (
	series: SeriesPoint[],
	width: number,
	height: number
): ChartGeometry => {
	if (series.length === 0) return { points: [], line: '', area: '' };

	// An all-zero series would divide by zero; a single point would divide by
	// zero on the x axis. Both are normal states (a brand-new site, a 1-day
	// window), so they render flat along the baseline rather than as NaN.
	const max = Math.max(...series.map((p) => p.views), 1);
	const span = height - PAD_TOP - PAD_BOTTOM;
	const step = series.length > 1 ? width / (series.length - 1) : 0;

	const points = series.map(
		(p, i) => [i * step, height - PAD_BOTTOM - (p.views / max) * span] as [number, number]
	);

	const line = points
		.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`)
		.join(' ');
	const area = `${line} L${points[points.length - 1][0].toFixed(1)},${height} L${points[0][0].toFixed(1)},${height} Z`;

	return { points, line, area };
};

export const nearestIndex = (series: SeriesPoint[], x: number, width: number): number => {
	if (series.length === 0) return 0;
	const ratio = Math.min(1, Math.max(0, x / width));
	return Math.round(ratio * (series.length - 1));
};

export const formatCount = (n: number): string => new Intl.NumberFormat('en-US').format(n);
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npx vitest run src/lib/components/sites/lib/analytics.test.ts`

Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/sites/lib/analytics.ts src/lib/components/sites/lib/analytics.test.ts
git commit -m "feat(sites): pure chart geometry and formatting helpers"
```

---

### Task 8: API client function

**Files:**
- Modify: `src/lib/apis/sites/index.ts` (append at the end)

**Interfaces:**
- Consumes: the endpoint from Task 6
- Produces: `getSiteAnalytics(token: string, id: string, days: number)` resolving to
  `{ days, totals: { views, unique_visitors, owner_views }, series: SeriesPoint[], top_pages: { path, views }[] }`

- [ ] **Step 1: Add the client function**

Append to `src/lib/apis/sites/index.ts`, following the existing `handle` / `jsonHeaders` pattern used by every other function in that file:

```ts
export const getSiteAnalytics = async (token: string = '', id: string, days: number = 30) => {
	let error = null;
	const res = await fetch(
		`${WEBUI_API_BASE_URL}/sites/${encodeURIComponent(id)}/analytics?days=${days}`,
		{
			method: 'GET',
			headers: jsonHeaders(token)
		}
	)
		.then(handle)
		.catch((err) => {
			error = err.detail ?? err;
			console.error(err);
			return null;
		});
	if (error) throw error;
	return res;
};
```

- [ ] **Step 2: Verify it typechecks**

Run: `npx svelte-check --threshold error --output human src/lib/apis/sites/index.ts` — or, if that path filter is unsupported in this version, `npm run check` and confirm no new errors mention `sites/index.ts`.

Expected: no errors in `src/lib/apis/sites/index.ts`

- [ ] **Step 3: Commit**

```bash
git add src/lib/apis/sites/index.ts
git commit -m "feat(sites): getSiteAnalytics API client"
```

---

### Task 9: `InsightsCard` component

**Files:**
- Create: `src/lib/components/sites/InsightsCard.svelte`

**Interfaces:**
- Consumes: `getSiteAnalytics` (Task 8); `chartGeometry`, `nearestIndex`, `formatCount`, `SeriesPoint` (Task 7)
- Produces: `<InsightsCard {site} />` — a self-contained card that fetches its own data

- [ ] **Step 1: Write the component**

Create `src/lib/components/sites/InsightsCard.svelte`:

```svelte
<script lang="ts">
	import { getContext } from 'svelte';
	import dayjs from 'dayjs';
	import { getSiteAnalytics } from '$lib/apis/sites';
	import { chartGeometry, nearestIndex, formatCount, type SeriesPoint } from './lib/analytics';

	const i18n = getContext('i18n');

	let { site }: { site: any } = $props();

	const W = 640;
	const H = 96;
	const RANGES = [7, 30, 90];

	let days = $state(30);
	let loading = $state(true);
	let failed = $state(false);
	let totals = $state({ views: 0, unique_visitors: 0, owner_views: 0 });
	let series = $state<SeriesPoint[]>([]);
	let topPages = $state<{ path: string; views: number }[]>([]);
	let hover = $state<number | null>(null);

	const geo = $derived(chartGeometry(series, W, H));
	const isEmpty = $derived(!loading && !failed && totals.views === 0 && totals.owner_views === 0);

	const load = async (window: number) => {
		loading = true;
		failed = false;
		try {
			const res = await getSiteAnalytics(localStorage.token, site.id, window);
			totals = res.totals;
			series = res.series;
			topPages = res.top_pages;
		} catch (err) {
			// Analytics is one card, not the whole tab — surface it inline and
			// let the rest of Overview render normally.
			console.error(err);
			failed = true;
		}
		loading = false;
	};

	$effect(() => {
		load(days);
	});

	const onMove = (e: PointerEvent) => {
		const rect = (e.currentTarget as SVGElement).getBoundingClientRect();
		hover = nearestIndex(series, ((e.clientX - rect.left) / rect.width) * W, W);
	};
</script>

<div class="rounded-xl border border-[var(--st-hairline)] px-4 py-3.5">
	<div class="flex flex-wrap items-start justify-between gap-3">
		<div class="flex gap-6">
			<div>
				<div class="text-xs font-medium text-gray-400 dark:text-gray-500">
					{$i18n.t('Views')}
				</div>
				<div class="mt-0.5 text-[21px] font-bold tabular-nums tracking-tight">
					{formatCount(totals.views)}
				</div>
			</div>
			<div>
				<div class="text-xs font-medium text-gray-400 dark:text-gray-500">
					{$i18n.t('Unique visitors')}
				</div>
				<div class="mt-0.5 text-[21px] font-bold tabular-nums tracking-tight">
					{formatCount(totals.unique_visitors)}
				</div>
			</div>
			{#if totals.owner_views > 0}
				<div>
					<div class="text-xs font-medium text-gray-400 dark:text-gray-500">
						{$i18n.t('Yours')}
					</div>
					<div class="mt-0.5 text-[21px] font-bold tabular-nums tracking-tight text-[var(--st-muted)]">
						{formatCount(totals.owner_views)}
					</div>
				</div>
			{/if}
		</div>

		<div class="flex gap-0.5" role="group" aria-label={$i18n.t('Time range')}>
			{#each RANGES as r (r)}
				<button
					type="button"
					aria-pressed={days === r}
					class="st-press rounded-[7px] px-2 py-1 text-xs transition-colors duration-150
						{days === r
						? 'bg-[var(--st-accent-soft)] font-semibold text-[var(--st-accent-soft-ink)]'
						: 'font-medium text-[var(--st-muted)] hover:bg-[var(--st-hover)] hover:text-[var(--st-ink)]'}"
					onclick={() => (days = r)}>{r}{$i18n.t('d')}</button
				>
			{/each}
		</div>
	</div>

	{#if loading}
		<div class="mt-3 h-[96px] animate-pulse rounded-lg bg-[var(--st-hover)]"></div>
	{:else if failed}
		<div class="mt-3 flex h-[96px] items-center justify-center text-[13px] text-[var(--st-muted)]">
			{$i18n.t("Couldn't load view data.")}
		</div>
	{:else if isEmpty}
		<div
			class="mt-3 flex h-[96px] flex-col items-center justify-center gap-1 text-center"
		>
			<div class="text-[13px] font-medium">{$i18n.t('No views yet')}</div>
			<div class="text-xs text-[var(--st-muted)]">
				{$i18n.t('Share the link to start seeing traffic.')}
			</div>
		</div>
	{:else}
		<div class="relative mt-3">
			<svg
				viewBox="0 0 {W} {H}"
				class="block h-auto w-full touch-none"
				role="img"
				aria-label={$i18n.t('Views over time')}
				onpointermove={onMove}
				onpointerleave={() => (hover = null)}
			>
				<path d={geo.area} fill="var(--st-chart-fill)" />
				<path d={geo.line} fill="none" stroke="var(--st-chart)" stroke-width="2" />
				{#if hover !== null && geo.points[hover]}
					<line
						x1={geo.points[hover][0]}
						y1="0"
						x2={geo.points[hover][0]}
						y2={H}
						stroke="var(--st-chart)"
						stroke-width="1"
						opacity="0.35"
					/>
					<circle
						cx={geo.points[hover][0]}
						cy={geo.points[hover][1]}
						r="3.5"
						fill="var(--st-chart)"
					/>
				{/if}
			</svg>
			<div class="mt-1 flex justify-between text-[11px] text-[var(--st-faint)]">
				{#if hover !== null && series[hover]}
					<span>{dayjs(series[hover].day).format('MMM D')}</span>
					<span class="tabular-nums"
						>{formatCount(series[hover].views)}
						{series[hover].views === 1 ? $i18n.t('view') : $i18n.t('views')}</span
					>
				{:else}
					<span>{dayjs(series[0]?.day).format('MMM D')}</span>
					<span>{dayjs(series[series.length - 1]?.day).format('MMM D')}</span>
				{/if}
			</div>
		</div>
	{/if}
</div>

{#if !loading && !failed && topPages.length > 0}
	<div class="rounded-xl border border-[var(--st-hairline)] px-4 py-3.5">
		<h4 class="mb-2 text-xs font-medium text-gray-400 dark:text-gray-500">
			{$i18n.t('Top pages')}
		</h4>
		{#each topPages as p, i (p.path)}
			<div
				class="flex items-center gap-3 py-1.5 text-[13px] {i < topPages.length - 1
					? 'border-b border-[var(--st-hairline)]'
					: ''}"
			>
				<span class="min-w-0 flex-1 truncate">/{p.path}</span>
				<div
					class="h-[5px] w-24 rounded-[3px] bg-[var(--st-chart)]"
					style="width: {Math.max(6, (p.views / topPages[0].views) * 96)}px"
				></div>
				<span class="w-12 text-right tabular-nums text-[var(--st-muted)]">{formatCount(p.views)}</span>
			</div>
		{/each}
	</div>
{/if}
```

- [ ] **Step 2: Verify it typechecks**

Run: `npm run check`

Expected: no new errors mentioning `InsightsCard.svelte`

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/sites/InsightsCard.svelte
git commit -m "feat(sites): InsightsCard with real view data"
```

---

### Task 10: Merge into Overview and delete the Analytics tab

**Files:**
- Modify: `src/lib/components/sites/tabs/OverviewTab.svelte`
- Modify: `src/lib/components/sites/SiteDetail.svelte`
- Delete: `src/lib/components/sites/tabs/AnalyticsTab.svelte`

**Interfaces:**
- Consumes: `<InsightsCard {site} />` (Task 9)
- Produces: an `Overview` tab that owns every insight; the `analytics` tab id no longer exists

- [ ] **Step 1: Remove the analytics tab from the shell**

In `src/lib/components/sites/SiteDetail.svelte`, delete the import:

```svelte
	import AnalyticsTab from './tabs/AnalyticsTab.svelte';
```

Remove the analytics entry from the `tabs` array so it reads:

```svelte
	const tabs = $derived([
		{ id: 'overview', label: $i18n.t('Overview'), preview: false },
		{ id: 'files', label: $i18n.t('Files'), preview: false },
		{ id: 'settings', label: $i18n.t('Settings'), preview: false },
		{ id: 'versions', label: $i18n.t('Versions'), preview: true }
	]);
```

And delete this branch from the tab-body block:

```svelte
		{:else if tab === 'analytics'}
			<AnalyticsTab />
```

- [ ] **Step 2: Rewrite `OverviewTab.svelte`**

Replace the entire file `src/lib/components/sites/tabs/OverviewTab.svelte`:

```svelte
<script lang="ts">
	import { getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import dayjs from 'dayjs';
	import relativeTime from 'dayjs/plugin/relativeTime';
	import { copyToClipboard } from '$lib/utils';
	import { siteAccessLevel } from '../lib/access';
	import { totalSize, formatSize } from '../lib/form';
	import InsightsCard from '../InsightsCard.svelte';

	dayjs.extend(relativeTime);

	const i18n = getContext('i18n');

	let { site, onGoTab = (_t: string) => {} }: { site: any; onGoTab?: (t: string) => void } =
		$props();

	const url = $derived(`${window.location.origin}/sites/${site.slug}/`);
	const level = $derived(siteAccessLevel(site));

	const visLabel = $derived(
		{
			public: $i18n.t('Public'),
			internal: $i18n.t('Everyone'),
			specific: $i18n.t('Specific'),
			private: $i18n.t('Private')
		}[level]
	);
	const visSub = $derived(
		{
			public: $i18n.t('No login needed'),
			internal: $i18n.t('Signed-in viewers'),
			specific: $i18n.t('Signed-in viewers'),
			private: $i18n.t('Only you')
		}[level]
	);

	const copy = async () => {
		await copyToClipboard(url);
		toast.success($i18n.t('Link copied'));
	};
</script>

<div class="st-pane flex flex-col gap-4">
	<div class="flex flex-wrap items-center gap-3 rounded-xl bg-gray-50 px-4 py-3.5 dark:bg-gray-850">
		<span class="min-w-0 flex-1 truncate text-sm text-gray-600 dark:text-gray-300">{url}</span>
		<div class="flex gap-2">
			<button type="button" class="st-btn" onclick={copy}>{$i18n.t('Copy link')}</button>
			<a
				class="st-btn st-btn-primary inline-flex items-center"
				href={url}
				target="_blank"
				rel="noopener">{$i18n.t('Open site')} ↗</a
			>
		</div>
	</div>

	<InsightsCard {site} />

	<div class="rounded-xl border border-[var(--st-hairline)] px-4 py-3.5">
		<h4 class="mb-2 text-xs font-medium text-gray-400 dark:text-gray-500">
			{$i18n.t('Details')}
		</h4>
		{#each [[$i18n.t('Visibility'), `${visLabel} · ${visSub}`], [$i18n.t('Entry file'), site.entry_file], [$i18n.t('Files'), `${(site.files ?? []).length} · ${formatSize(totalSize(site.files ?? []))}`], [$i18n.t('Owner'), site.user_name ?? $i18n.t('You')], [$i18n.t('Updated'), `${dayjs(site.updated_at).fromNow()} · ${$i18n.t('created')} ${dayjs(site.created_at).format('MMM D, YYYY')}`]] as [label, value], i (label)}
			<div
				class="flex justify-between gap-3 py-1.5 text-[13px] {i < 4
					? 'border-b border-[var(--st-hairline)]'
					: ''}"
			>
				<span class="text-[var(--st-muted)]">{label}</span>
				<span class="truncate text-right">{value}</span>
			</div>
		{/each}
	</div>

	<div class="flex flex-wrap items-center gap-1.5">
		{#each [[$i18n.t('Replace files'), 'files'], [$i18n.t('Change who can view'), 'settings'], [$i18n.t('Restore an older version'), 'versions']] as [label, target] (target)}
			<button
				type="button"
				class="st-press rounded-[7px] px-2.5 py-1.5 text-xs text-[var(--st-muted)] hover:bg-[var(--st-hover)] hover:text-[var(--st-ink)]"
				onclick={() => onGoTab(target as string)}>{label} →</button
			>
		{/each}
	</div>
</div>
```

Note the timestamp change: the file being replaced multiplies `updated_at` and `created_at`
by 1000, but `models/sites.py::_now()` already returns **milliseconds**
(`int(time.time() * 1000)`). The old code therefore rendered dates roughly 55,000 years in
the future. Pass the values to `dayjs` unmultiplied, as written above.

- [ ] **Step 3: Delete the mock tab**

```bash
git rm src/lib/components/sites/tabs/AnalyticsTab.svelte
```

- [ ] **Step 4: Verify nothing still references it**

```bash
grep -rn "AnalyticsTab\|'analytics'" src/lib/components/sites/
```

Expected: no matches. Any hit is a dangling reference that must be removed.

- [ ] **Step 5: Typecheck and run the frontend tests**

Run: `npm run check` — expected: no new errors in `src/lib/components/sites/`

Run: `npm run test:frontend -- --run src/lib/components/sites/` — expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/sites/SiteDetail.svelte src/lib/components/sites/tabs/OverviewTab.svelte
git commit -m "feat(sites): merge insights into Overview, drop the Analytics tab"
```

---

### Task 11: Full verification and manual smoke checklist

**Files:**
- None modified — this task only runs and records verification

- [ ] **Step 1: Run the whole backend sites suite**

Run: `backend/.venv/Scripts/python.exe -m pytest open_webui/test/sites/ -v` from `backend/`

Expected: PASS, zero failures. Record the pass count.

- [ ] **Step 2: Run the frontend test suite**

Run: `npm run test:frontend -- --run`

Expected: PASS, zero failures.

- [ ] **Step 3: Typecheck**

Run: `npm run check`

Expected: no new errors versus the pre-change baseline.

- [ ] **Step 4: Apply the migration to the running container**

The dev backend runs in the `osool-ai-open-webui-1` container against its own DB volume. The new table will not exist until migrations run there.

```bash
docker restart osool-ai-open-webui-1
```

Then confirm the table exists:

```bash
docker exec osool-ai-open-webui-1 python -c "from open_webui.internal.db import engine; from sqlalchemy import inspect; print('site_view' in inspect(engine).get_table_names())"
```

Expected: `True`

If it prints `False`, the migration did not run — check `docker logs osool-ai-open-webui-1` for an alembic error before continuing.

- [ ] **Step 5: Manual browser smoke checklist**

The user drives their own Vite hot-reload server; frontend edits are live on save. Ask the user to run through this list and report results — do not start a dev server without asking.

1. Open a site in `Sites`. The tab bar shows Overview · Files · Settings · Versions, with no Analytics tab.
2. Overview shows the insight card at the top. On a site with no traffic it reads "No views yet".
3. Open the site's public URL in a new tab as the owner. Return to Overview, reload. `Yours` appears with a count of 1; `Views` stays 0.
4. Open the same URL in a private/incognito window (or ask a colleague). Reload Overview. `Views` and `Unique visitors` both increment.
5. Hover the chart. The date and view count under it track the pointer.
6. Switch the range to 7d and 90d. The chart and the numbers both change; the series length changes with the window.
7. Confirm an image or CSS file inside the site does not increment `Views`.
8. Check dark mode: card borders, chart fill, and the range toggle are all legible.
9. Narrow to phone width. The KPI row and range toggle wrap without horizontal overflow.
10. As a different non-admin user, confirm the site's Overview is not reachable at all (unchanged behavior — the site should not appear in their rail).

- [ ] **Step 6: Commit any fixes found during smoke**

Only if the checklist surfaced problems. Otherwise this task ends with no commit.
