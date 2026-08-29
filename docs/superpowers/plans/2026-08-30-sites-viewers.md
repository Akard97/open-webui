# Sites Viewers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show the site owner a roster of who viewed their published site — named for signed-in viewers, aggregated as "Anonymous" otherwise — and fix the unique-visitor overcount in the shipped analytics.

**Architecture:** `site_view` gains a nullable `user_id`. The recording path already resolves the viewer for exactly the cases that need it, so it only passes the id along; nothing about *when* resolution happens changes. A new `get_viewers` aggregation groups the window by `user_id`, batch-resolves names, and rides along in the existing `/analytics` response. A presentational `ViewersCard` renders beside Top pages, fed by `OverviewTab`, which already owns the fetch.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, Alembic, pytest + pytest-asyncio + httpx ASGITransport, Svelte 5 (runes), Vitest, Tailwind.

**Spec:** `docs/superpowers/specs/2026-08-30-sites-viewers-design.md`

## Global Constraints

- Migration revision id is `c1d2e3f4a5b7`, `down_revision = 'b1c2d3e4f5a6'` (verified free and current head). Do not invent a different id.
- `user_id` on `site_view` is **nullable**. NULL means anonymous *or* a row predating this migration; the two are indistinguishable and need not be distinguished.
- **Do not change when a viewer is resolved.** The gate `if viewer is None and has_credentials:` in `_record_view` stays exactly as it is. Anonymous traffic to a public site must continue to perform zero token decodes and zero user lookups — this is pinned by existing `auth_calls` tests and is both the privacy property and the performance property.
- Owner visits stay excluded from every visitor-facing number, including the new roster. The KPI row's `Yours` already reports them.
- `unique_visitors` becomes `COUNT(DISTINCT COALESCE(user_id, visitor_key))`. Signed-in viewers dedupe across the window; anonymous visitors remain sum-of-daily-uniques because `visitor_key` rotates daily by design — that rotation is not to be weakened.
- Timestamps are epoch **milliseconds** (`_now()` returns `int(time.time() * 1000)`).
- Queries must run on SQLite and Postgres. No SQL date functions; day bucketing already uses `.op('/')`.
- Analytics read access is unchanged: `_require_publisher` then `_get_owned_site`, 404 (not 403) for anyone else.
- Roster cap is **8** named viewers, with a `more` remainder count.
- Python style: single quotes, 4-space indent. Backend CI gate is `ruff format --check`, `line-length = 120`; ruff is not in `backend/.venv` — a pinned copy is at `C:/Users/AALSAW~1/AppData/Local/Temp/claude/C--Projects-open-webui/105823d4-65cb-4d27-a0b2-d4c3097754e0/scratchpad/rufftools/bin/ruff.exe`.
- Frontend style: tabs, single quotes, semicolons (Prettier-enforced). Svelte 5 runes. Every user-visible string through `$i18n.t(...)`. Colors from the `--st-*` custom properties in `sites.css`; no hardcoded hex; light and dark.
- Backend tests: from `backend/`, `.venv/Scripts/python.exe -m pytest open_webui/test/sites/ -v` (**115 passing** at plan time).
- Frontend tests: `CI=true npm run test:frontend -- --run src/lib/components/sites/` — the `CI=true` prefix matters or vitest hangs in watch mode.
- `npm run check` baseline is **9550 errors / 282 warnings**, all pre-existing. Gate is no NEW error class; the known "i18n as store" noise on new `$i18n.t(...)` call sites is expected.
- Do NOT start a Vite dev server. Do not restart Docker containers.

## File Structure

**Created:**
- `backend/open_webui/migrations/versions/c1d2e3f4a5b7_site_view_user_id.py`
- `src/lib/components/sites/ViewersCard.svelte` — presentational roster

**Modified:**
- `backend/open_webui/models/sites.py` — `user_id` column, `record_view` argument, `get_viewers`, corrected `unique_visitors`
- `backend/open_webui/routers/sites.py` — pass the viewer id; include `viewers` in the response
- `backend/open_webui/test/sites/test_analytics.py`
- `src/lib/components/sites/tabs/OverviewTab.svelte` — two-column row becomes Viewers | Top pages; Details full width
- `src/lib/components/sites/lib/analytics.ts` (+ `analytics.test.ts`) — roster formatting helper
- `docs/superpowers/specs/2026-08-29-sites-analytics-design.md` — rewrite the `user_id` omission section as a recorded reversal

---

### Task 1: `user_id` column, migration, and recording

**Files:**
- Modify: `backend/open_webui/models/sites.py` (the `SiteView` model, `SiteViewModel`, `SiteViewsTable.record_view`)
- Modify: `backend/open_webui/routers/sites.py` (`_record_view`'s call to `record_view`)
- Create: `backend/open_webui/migrations/versions/c1d2e3f4a5b7_site_view_user_id.py`
- Test: `backend/open_webui/test/sites/test_analytics.py`

**Interfaces:**
- Consumes: existing `SiteView`, `record_view`, `_record_view`
- Produces: `SiteView.user_id` (nullable Text); `SiteViewModel.user_id: Optional[str]`; `record_view(site_id, path, visitor_key, is_owner, user_id=None, db=None)`

- [ ] **Step 1: Write the failing tests**

Append to `backend/open_webui/test/sites/test_analytics.py`:

```python
@pytest.mark.asyncio
async def test_record_view_stores_the_signed_in_viewer():
    await SiteViews.record_view('s1', 'index.html', 'k1', False, user_id='u42')
    rows = await SiteViews.list_views('s1')
    assert rows[0].user_id == 'u42'


@pytest.mark.asyncio
async def test_record_view_leaves_anonymous_views_unattributed():
    await SiteViews.record_view('s1', 'index.html', 'k1', False)
    rows = await SiteViews.list_views('s1')
    assert rows[0].user_id is None


@pytest.mark.asyncio
async def test_signed_in_viewer_is_attributed_on_a_served_page(monkeypatch, tmp_path):
    site = await _seed_site(tmp_path, slug='attr-named', public=True)
    async with _serve_client(monkeypatch, tmp_path, viewer=R_VIEWER) as c:
        assert (await c.get('/sites/attr-named/')).status_code == 200

    rows = await SiteViews.list_views(site.id)
    assert len(rows) == 1
    assert rows[0].user_id == R_VIEWER.id
    assert rows[0].is_owner is False


@pytest.mark.asyncio
async def test_anonymous_view_is_recorded_without_a_user_id(monkeypatch, tmp_path):
    site = await _seed_site(tmp_path, slug='attr-anon', public=True)
    async with _serve_client(monkeypatch, tmp_path, viewer=None) as c:
        assert (await c.get('/sites/attr-anon/')).status_code == 200

    rows = await SiteViews.list_views(site.id)
    assert len(rows) == 1
    assert rows[0].user_id is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run from `backend/`: `.venv/Scripts/python.exe -m pytest open_webui/test/sites/test_analytics.py -k "attributed or unattributed or stores_the_signed_in" -v`

Expected: FAIL with `TypeError: record_view() got an unexpected keyword argument 'user_id'` on the first two, and `AttributeError: 'SiteViewModel' object has no attribute 'user_id'` on the others.

- [ ] **Step 3: Add the column**

In `backend/open_webui/models/sites.py`, in the `SiteView` model, after `is_owner`:

```python
    # The signed-in viewer, when there was one. NULL means anonymous — or a
    # row recorded before this column existed; the two are indistinguishable
    # and do not need distinguishing. Anonymous views are unattributed
    # because such requests are never resolved in the first place, not
    # because the result is discarded.
    user_id = Column(Text, nullable=True)
```

And in `SiteViewModel`, after `is_owner: bool`:

```python
    user_id: Optional[str] = None
```

- [ ] **Step 4: Thread it through `record_view`**

Change the signature and the row construction in `SiteViewsTable.record_view`:

```python
    async def record_view(
        self,
        site_id: str,
        path: str,
        visitor_key: str,
        is_owner: bool,
        user_id: Optional[str] = None,
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
                    user_id=user_id,
                    created_at=_now(),
                )
            )
            await db.commit()
```

- [ ] **Step 5: Pass the viewer id from the recording path**

In `backend/open_webui/routers/sites.py`, in `_record_view`, change the `record_view` call to pass the id. **Do not touch the resolution gate above it** — when and whether a viewer is resolved must not change:

```python
        await SiteViews.record_view(
            site_id,
            filename,
            _visitor_key(site_id, ip, user_agent),
            bool(viewer is not None and viewer.id == owner_id),
            user_id=viewer.id if viewer is not None else None,
        )
```

- [ ] **Step 6: Run the tests to verify they pass**

Run from `backend/`: `.venv/Scripts/python.exe -m pytest open_webui/test/sites/test_analytics.py -v`

Expected: PASS, 119 tests (115 existing + 4 new).

- [ ] **Step 7: Write the migration**

Create `backend/open_webui/migrations/versions/c1d2e3f4a5b7_site_view_user_id.py`:

```python
"""attribute site views to the signed-in viewer

Spec: docs/superpowers/specs/2026-08-30-sites-viewers-design.md

Revision ID: c1d2e3f4a5b7
Revises: b1c2d3e4f5a6
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c1d2e3f4a5b7'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: existing rows have no attribution, and anonymous views never
    # will. No backfill — an unattributed past view is the honest record.
    op.add_column('site_view', sa.Column('user_id', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('site_view', 'user_id')
```

- [ ] **Step 8: Verify the migration graph still has exactly one head**

Run from `backend/open_webui/migrations/versions/`:

```bash
python -c "import os,re; d={}; s=set(); [d.update({m.group(1):f}) for f in os.listdir('.') if f.endswith('.py') for m in [re.search(r\"^revision(?::\s*str)?\s*=\s*['\\\"]([^'\\\"]+)\",open(f,encoding='utf-8',errors='replace').read(),re.M)] if m]; [s.add(m.group(1)) for f in os.listdir('.') if f.endswith('.py') for m in [re.search(r\"^down_revision(?::\s*[^=]+)?\s*=\s*['\\\"]([^'\\\"]+)\",open(f,encoding='utf-8',errors='replace').read(),re.M)] if m]; print('HEADS:',[k for k in d if k not in s])"
```

Expected: `HEADS: ['c1d2e3f4a5b7']`. More than one head means `down_revision` is wrong — fix before continuing.

- [ ] **Step 9: Run the full sites suite and check formatting**

Run from `backend/`: `.venv/Scripts/python.exe -m pytest open_webui/test/sites/ -v` → 119 passing.

Then `ruff format --check` on `backend/open_webui/models/sites.py` and `backend/open_webui/routers/sites.py` (ruff path in Global Constraints). Both must pass.

- [ ] **Step 10: Commit**

```bash
git add backend/open_webui/models/sites.py backend/open_webui/routers/sites.py backend/open_webui/migrations/versions/c1d2e3f4a5b7_site_view_user_id.py backend/open_webui/test/sites/test_analytics.py
git commit -m "feat(sites): attribute pageviews to the signed-in viewer"
```

---

### Task 2: Correct `unique_visitors`

**Files:**
- Modify: `backend/open_webui/models/sites.py` (`get_analytics`)
- Test: `backend/open_webui/test/sites/test_analytics.py`

**Interfaces:**
- Consumes: `SiteView.user_id` (Task 1)
- Produces: no signature change — `totals['unique_visitors']` changes meaning

- [ ] **Step 1: Write the failing tests**

Append to `backend/open_webui/test/sites/test_analytics.py`:

```python
@pytest.mark.asyncio
async def test_a_signed_in_viewer_counts_once_across_many_days():
    # visitor_key deliberately rotates daily, so the same person on three days
    # produces three keys. Attributed views must still be one visitor.
    for offset, key in enumerate(['k-day1', 'k-day2', 'k-day3']):
        await _record_at('s1', 'index.html', key, False, NOW_MS - offset * DAY_MS, user_id='u1')

    a = await SiteViews.get_analytics('s1', 30, now_ms=NOW_MS)

    assert a['totals']['views'] == 3
    assert a['totals']['unique_visitors'] == 1


@pytest.mark.asyncio
async def test_anonymous_visitors_still_count_per_day():
    # Unattributable by design: the daily salt rotation is the privacy
    # property, so two days of anonymous traffic read as two.
    await _record_at('s1', 'index.html', 'anon-day1', False, NOW_MS)
    await _record_at('s1', 'index.html', 'anon-day2', False, NOW_MS - DAY_MS)

    a = await SiteViews.get_analytics('s1', 30, now_ms=NOW_MS)

    assert a['totals']['unique_visitors'] == 2


@pytest.mark.asyncio
async def test_named_and_anonymous_visitors_are_both_counted():
    await _record_at('s1', 'index.html', 'k1', False, NOW_MS, user_id='u1')
    await _record_at('s1', 'index.html', 'k2', False, NOW_MS, user_id='u2')
    await _record_at('s1', 'index.html', 'k3', False, NOW_MS)

    a = await SiteViews.get_analytics('s1', 30, now_ms=NOW_MS)

    assert a['totals']['unique_visitors'] == 3
```

`_record_at` currently takes positional `(site_id, path, key, is_owner, ts_ms)`. Extend it with a keyword-only `user_id=None` that it passes into the `SiteView(...)` it constructs, leaving every existing call site working unchanged.

- [ ] **Step 2: Run the tests to verify they fail**

Run from `backend/`: `.venv/Scripts/python.exe -m pytest open_webui/test/sites/test_analytics.py -k "counts_once_across or per_day or both_counted" -v`

Expected: FAIL — `test_a_signed_in_viewer_counts_once_across_many_days` asserts `1` but gets `3`, which is the defect this task fixes.

- [ ] **Step 3: Fix the count**

In `get_analytics`, replace the distinct-visitor expression in the totals query:

```python
            totals_row = (
                await db.execute(
                    select(
                        func.count(SiteView.id),
                        func.count(func.distinct(func.coalesce(SiteView.user_id, SiteView.visitor_key))),
                    ).where(*visitors)
                )
            ).one()
```

Add to the `get_analytics` docstring, after the existing paragraphs:

```
        `unique_visitors` counts distinct COALESCE(user_id, visitor_key).
        Signed-in viewers dedupe correctly across the whole window. Anonymous
        ones cannot: `visitor_key` embeds the UTC date so it rotates daily —
        that rotation is the privacy property, deliberately not weakened here
        — so the anonymous portion remains a sum of daily uniques and
        overstates a returning anonymous visitor. The UI says so rather than
        presenting a number that is exact for one half of its inputs.
```

- [ ] **Step 4: Run the tests to verify they pass**

Run from `backend/`: `.venv/Scripts/python.exe -m pytest open_webui/test/sites/ -v`

Expected: PASS, 122 tests. The pre-existing `test_get_analytics_counts_repeat_visitors_once_in_uniques` must still pass — same key twice with no `user_id` still coalesces to one.

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/models/sites.py backend/open_webui/test/sites/test_analytics.py
git commit -m "fix(sites): stop counting a daily visitor as a new unique each day"
```

---

### Task 3: `get_viewers` aggregation

**Files:**
- Modify: `backend/open_webui/models/sites.py` (add to `SiteViewsTable`)
- Test: `backend/open_webui/test/sites/test_analytics.py`

**Interfaces:**
- Consumes: `SiteView.user_id` (Task 1); `Users.get_users_by_user_ids(user_ids, db=None) -> list[UserModel]` from `open_webui.models.users` (each has `.id`, `.name`, `.profile_image_url`)
- Produces: `SiteViews.get_viewers(site_id, days, limit=8, now_ms=None, db=None) -> dict` returning
  `{'people': [{'user_id', 'name', 'profile_image_url', 'views', 'last_viewed_at'}], 'anonymous_views': int, 'more': int}`

- [ ] **Step 1: Write the failing tests**

Append to `backend/open_webui/test/sites/test_analytics.py`:

```python
@pytest.mark.asyncio
async def test_get_viewers_ranks_named_people_by_view_count():
    for _ in range(3):
        await _record_at('s1', 'index.html', 'k', False, NOW_MS, user_id='u1')
    await _record_at('s1', 'index.html', 'k', False, NOW_MS, user_id='u2')

    v = await SiteViews.get_viewers('s1', 30, now_ms=NOW_MS)

    assert [p['user_id'] for p in v['people']] == ['u1', 'u2']
    assert v['people'][0]['views'] == 3
    assert v['people'][0]['last_viewed_at'] == NOW_MS
    # No User row exists for these ids at this layer; the roster must still
    # name the row rather than dropping it, or the counts stop reconciling.
    assert v['people'][0]['name']


@pytest.mark.asyncio
async def test_get_viewers_aggregates_anonymous_views():
    await _record_at('s1', 'index.html', 'a1', False, NOW_MS)
    await _record_at('s1', 'index.html', 'a2', False, NOW_MS)
    await _record_at('s1', 'index.html', 'k', False, NOW_MS, user_id='u1')

    v = await SiteViews.get_viewers('s1', 30, now_ms=NOW_MS)

    assert v['anonymous_views'] == 2
    assert [p['user_id'] for p in v['people']] == ['u1']


@pytest.mark.asyncio
async def test_get_viewers_caps_the_roster_and_reports_the_remainder():
    for i in range(11):
        await _record_at('s1', 'index.html', 'k', False, NOW_MS, user_id=f'u{i:02d}')

    v = await SiteViews.get_viewers('s1', 30, limit=8, now_ms=NOW_MS)

    assert len(v['people']) == 8
    assert v['more'] == 3


@pytest.mark.asyncio
async def test_get_viewers_excludes_the_owner():
    # is_owner is the 4th positional arg — pass True there, not as a keyword.
    await _record_at('s1', 'index.html', 'k', True, NOW_MS, user_id='owner1')
    await _record_at('s1', 'index.html', 'k', False, NOW_MS, user_id='u1')

    v = await SiteViews.get_viewers('s1', 30, now_ms=NOW_MS)

    assert [p['user_id'] for p in v['people']] == ['u1']
    assert v['anonymous_views'] == 0


@pytest.mark.asyncio
async def test_get_viewers_respects_the_window_and_the_site():
    await _record_at('s1', 'index.html', 'k', False, NOW_MS - 40 * DAY_MS, user_id='old')
    await _record_at('s2', 'index.html', 'k', False, NOW_MS, user_id='other')
    await _record_at('s1', 'index.html', 'k', False, NOW_MS, user_id='u1')

    v = await SiteViews.get_viewers('s1', 7, now_ms=NOW_MS)

    assert [p['user_id'] for p in v['people']] == ['u1']


@pytest.mark.asyncio
async def test_get_viewers_returns_empty_for_a_site_with_no_views():
    v = await SiteViews.get_viewers('nobody', 30, now_ms=NOW_MS)

    assert v == {'people': [], 'anonymous_views': 0, 'more': 0}
```

The `name` / `profile_image_url` fields are exercised properly in Task 4's endpoint tests, where real `User` rows exist. At this layer no `User` rows are created, so every viewer falls into the deleted-account branch — which is exactly what pins that branch's behavior.

- [ ] **Step 2: Run the tests to verify they fail**

Run from `backend/`: `.venv/Scripts/python.exe -m pytest open_webui/test/sites/test_analytics.py -k "get_viewers" -v`

Expected: FAIL with `AttributeError: 'SiteViewsTable' object has no attribute 'get_viewers'`.

- [ ] **Step 3: Implement `get_viewers`**

Add to `SiteViewsTable` in `backend/open_webui/models/sites.py`:

```python
    async def get_viewers(
        self,
        site_id: str,
        days: int,
        limit: int = 8,
        now_ms: Optional[int] = None,
        db: Optional[AsyncSession] = None,
    ) -> dict:
        """Who viewed a site in the window: named people, plus an anonymous total.

        Owner visits are excluded, like every other visitor-facing number —
        the `Yours` stat already reports them.

        Ranking is by view count, tie-broken by most recent view then by
        user id, so the order is deterministic rather than whatever the
        database happens to return.

        `more` lets the card say "+N more" without shipping the whole roster
        for a site with a large audience.
        """
        now_ms = _now() if now_ms is None else now_ms
        day_ms = 86_400_000
        today_idx = now_ms // day_ms
        window_start = (today_idx - (days - 1)) * day_ms
        window_end = (today_idx + 1) * day_ms

        async with get_async_db_context(db) as db:
            visitors = (
                SiteView.site_id == site_id,
                SiteView.created_at >= window_start,
                SiteView.created_at < window_end,
                SiteView.is_owner.is_(False),
            )

            rows = (
                await db.execute(
                    select(
                        SiteView.user_id,
                        func.count(SiteView.id).label('n'),
                        func.max(SiteView.created_at).label('last'),
                    )
                    .where(*visitors, SiteView.user_id.is_not(None))
                    .group_by(SiteView.user_id)
                    .order_by(
                        func.count(SiteView.id).desc(),
                        func.max(SiteView.created_at).desc(),
                        SiteView.user_id.asc(),
                    )
                )
            ).all()

            anonymous_views = (
                await db.execute(
                    select(func.count(SiteView.id)).where(*visitors, SiteView.user_id.is_(None))
                )
            ).scalar_one()

            top = rows[:limit]
            users = {}
            if top:
                from open_webui.models.users import Users

                found = await Users.get_users_by_user_ids([r[0] for r in top], db=db)
                users = {u.id: u for u in found}

        people = []
        for user_id, n, last in top:
            user = users.get(user_id)
            people.append(
                {
                    'user_id': user_id,
                    # A viewer whose account was deleted still has views that
                    # are counted in `views`; dropping the row would make the
                    # roster fail to reconcile with the totals beside it.
                    'name': user.name if user else 'Deleted user',
                    'profile_image_url': user.profile_image_url if user else None,
                    'views': int(n),
                    'last_viewed_at': int(last),
                }
            )

        return {
            'people': people,
            'anonymous_views': int(anonymous_views),
            'more': max(0, len(rows) - limit),
        }
```

The `Users` import is local to the function to avoid a module-level import cycle — `models/sites.py` is imported early, and `update_site_access` already uses this same local-import pattern for `access_grants`.

- [ ] **Step 4: Run the tests to verify they pass**

Run from `backend/`: `.venv/Scripts/python.exe -m pytest open_webui/test/sites/ -v`

Expected: PASS, 128 tests.

- [ ] **Step 5: Check formatting and commit**

`ruff format --check backend/open_webui/models/sites.py` must pass.

```bash
git add backend/open_webui/models/sites.py backend/open_webui/test/sites/test_analytics.py
git commit -m "feat(sites): viewer roster aggregation"
```

---

### Task 4: Expose `viewers` on the analytics endpoint

**Files:**
- Modify: `backend/open_webui/routers/sites.py` (`get_site_analytics`)
- Test: `backend/open_webui/test/sites/test_analytics.py`

**Interfaces:**
- Consumes: `SiteViews.get_analytics`, `SiteViews.get_viewers` (Task 3)
- Produces: the `/analytics` response gains a `viewers` key

- [ ] **Step 1: Write the failing tests**

Append to `backend/open_webui/test/sites/test_analytics.py`. These need real `User` rows so names resolve — create them via the `Users` table the same way the existing suite creates sites:

```python
@pytest.mark.asyncio
async def test_analytics_endpoint_returns_named_viewers(monkeypatch, tmp_path):
    from open_webui.models.users import Users

    site = await _seed_site(tmp_path, slug='api-viewers', public=True)
    await Users.insert_new_user(id='u1', name='Sara', email='sara@x.io', profile_image_url='/img/a.png')
    await SiteViews.record_view(site.id, 'index.html', 'k1', False, user_id='u1')
    await SiteViews.record_view(site.id, 'index.html', 'k2', False)

    async with _api_client(monkeypatch, user=R_OWNER) as c:
        r = await c.get(f'/api/v1/sites/{site.id}/analytics?days=30')

    assert r.status_code == 200
    viewers = r.json()['viewers']
    assert viewers['people'] == [
        {
            'user_id': 'u1',
            'name': 'Sara',
            'profile_image_url': '/img/a.png',
            'views': 1,
            'last_viewed_at': viewers['people'][0]['last_viewed_at'],
        }
    ]
    assert viewers['anonymous_views'] == 1
    assert viewers['more'] == 0


@pytest.mark.asyncio
async def test_analytics_endpoint_returns_an_empty_roster_for_a_quiet_site(monkeypatch, tmp_path):
    site = await _seed_site(tmp_path, slug='api-quiet', public=True)

    async with _api_client(monkeypatch, user=R_OWNER) as c:
        r = await c.get(f'/api/v1/sites/{site.id}/analytics?days=30')

    assert r.json()['viewers'] == {'people': [], 'anonymous_views': 0, 'more': 0}
```

Check `Users.insert_new_user`'s real signature before writing this — adapt the call to whatever it actually takes rather than assuming these exact kwargs.

- [ ] **Step 2: Run the tests to verify they fail**

Run from `backend/`: `.venv/Scripts/python.exe -m pytest open_webui/test/sites/test_analytics.py -k "named_viewers or quiet_site" -v`

Expected: FAIL with `KeyError: 'viewers'`.

- [ ] **Step 3: Add `viewers` to the response**

In `backend/open_webui/routers/sites.py`, in `get_site_analytics`, after the existing `get_analytics` call:

```python
    data = await SiteViews.get_analytics(site.id, days, db=db)
    data['viewers'] = await SiteViews.get_viewers(site.id, days, db=db)
    return data
```

Keep the validation and auth lines above exactly as they are.

- [ ] **Step 4: Run the tests to verify they pass**

Run from `backend/`: `.venv/Scripts/python.exe -m pytest open_webui/test/sites/ -v`

Expected: PASS, 130 tests. The existing endpoint tests must still pass — a new key in the response must not break them.

- [ ] **Step 5: Check formatting and commit**

`ruff format --check backend/open_webui/routers/sites.py` must pass.

```bash
git add backend/open_webui/routers/sites.py backend/open_webui/test/sites/test_analytics.py
git commit -m "feat(sites): return the viewer roster from the analytics endpoint"
```

---

### Task 5: Roster formatting helper

**Files:**
- Modify: `src/lib/components/sites/lib/analytics.ts`
- Test: `src/lib/components/sites/lib/analytics.test.ts`

**Interfaces:**
- Consumes: nothing
- Produces: `viewerInitials(name: string): string` — up to two uppercase initials for the avatar fallback

- [ ] **Step 1: Write the failing test**

Append to `src/lib/components/sites/lib/analytics.test.ts`:

```ts
describe('viewerInitials', () => {
	it('takes the first letter of the first two words', () => {
		expect(viewerInitials('Sara Al-Mutairi')).toBe('SA');
		expect(viewerInitials('Omar')).toBe('O');
	});

	it('ignores extra whitespace', () => {
		expect(viewerInitials('  Sara   Al-Mutairi  ')).toBe('SA');
	});

	it('returns a placeholder rather than nothing for an empty name', () => {
		expect(viewerInitials('')).toBe('?');
		expect(viewerInitials('   ')).toBe('?');
	});

	it('handles non-Latin names without mangling them', () => {
		expect(viewerInitials('سارة المطيري')).toBe('سا');
	});
});
```

Add `viewerInitials` to the existing import at the top of the file.

- [ ] **Step 2: Run the test to verify it fails**

Run: `CI=true npx vitest run src/lib/components/sites/lib/analytics.test.ts`

Expected: FAIL — `viewerInitials is not a function`.

- [ ] **Step 3: Implement it**

Append to `src/lib/components/sites/lib/analytics.ts`:

```ts
export const viewerInitials = (name: string): string => {
	// Array.from, not slice: a name may start with a character outside the
	// BMP, and cutting a surrogate pair in half renders a replacement box.
	const words = name.trim().split(/\s+/).filter(Boolean);
	if (words.length === 0) return '?';
	return words
		.slice(0, 2)
		.map((w) => Array.from(w)[0] ?? '')
		.join('')
		.toUpperCase();
};
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `CI=true npx vitest run src/lib/components/sites/lib/analytics.test.ts`

Expected: PASS — 14 existing plus the 4 new.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/sites/lib/analytics.ts src/lib/components/sites/lib/analytics.test.ts
git commit -m "feat(sites): viewer initials helper"
```

---

### Task 6: `ViewersCard` and the Overview layout

**Files:**
- Create: `src/lib/components/sites/ViewersCard.svelte`
- Modify: `src/lib/components/sites/tabs/OverviewTab.svelte`

**Interfaces:**
- Consumes: `viewerInitials`, `formatCount` from `./lib/analytics` (Task 5); the `viewers` block from the API (Task 4)
- Produces: `<ViewersCard {loading} {viewers} />` where `viewers` is `{people, anonymous_views, more}`

- [ ] **Step 1: Create the card**

Create `src/lib/components/sites/ViewersCard.svelte`, following `TopPagesCard.svelte`'s conventions exactly — same wrapper classes, same heading style, same loading skeleton, same presentational contract:

```svelte
<script lang="ts">
	import { getContext } from 'svelte';
	import dayjs from 'dayjs';
	import relativeTime from 'dayjs/plugin/relativeTime';
	import { formatCount, viewerInitials } from './lib/analytics';

	dayjs.extend(relativeTime);

	const i18n = getContext('i18n');

	// Presentational: OverviewTab owns the fetch and hands the roster down.
	let {
		loading = false,
		viewers = { people: [], anonymous_views: 0, more: 0 }
	}: {
		loading?: boolean;
		viewers?: {
			people: {
				user_id: string;
				name: string;
				profile_image_url: string | null;
				views: number;
				last_viewed_at: number;
			}[];
			anonymous_views: number;
			more: number;
		};
	} = $props();

	const locale = $derived($i18n.language);
	const isEmpty = $derived(
		!loading && viewers.people.length === 0 && viewers.anonymous_views === 0
	);
</script>

<div class="rounded-xl border border-[var(--st-hairline)] px-4 py-3.5">
	<h4 class="mb-2 text-xs font-medium text-gray-400 dark:text-gray-500">
		{$i18n.t('Viewers')}
	</h4>
	{#if loading}
		<!-- A skeleton, never the roster still in state: those names belong to
		     the previous site (or range) and must not appear under a new header. -->
		<div class="space-y-2 py-1.5" aria-hidden="true">
			<div class="h-3 animate-pulse rounded bg-[var(--st-hover)]"></div>
			<div class="h-3 w-4/5 animate-pulse rounded bg-[var(--st-hover)]"></div>
			<div class="h-3 w-3/5 animate-pulse rounded bg-[var(--st-hover)]"></div>
		</div>
	{:else if isEmpty}
		<div class="py-1.5 text-[13px] text-[var(--st-muted)]">{$i18n.t('No viewers yet')}</div>
	{:else}
		{#each viewers.people as p (p.user_id)}
			<div
				class="flex items-center gap-2.5 border-b border-[var(--st-hairline)] py-1.5 text-[13px] last:border-b-0"
			>
				{#if p.profile_image_url}
					<img
						class="size-6 shrink-0 rounded-full object-cover"
						src={p.profile_image_url}
						alt=""
					/>
				{:else}
					<span
						class="flex size-6 shrink-0 items-center justify-center rounded-full bg-[var(--st-accent-soft)] text-[10px] font-semibold text-[var(--st-accent-soft-ink)]"
						aria-hidden="true">{viewerInitials(p.name)}</span
					>
				{/if}
				<span class="min-w-0 flex-1 truncate" title={p.name}>{p.name}</span>
				<span class="shrink-0 text-[11px] text-[var(--st-faint)]"
					>{dayjs(p.last_viewed_at).fromNow()}</span
				>
				<span class="w-8 shrink-0 text-right tabular-nums text-[var(--st-muted)]"
					>{formatCount(p.views, locale)}</span
				>
			</div>
		{/each}

		{#if viewers.anonymous_views > 0}
			<!-- Sorts last regardless of count: an aggregate over many people is
			     a different kind of row from a named one, and it has no single
			     last-seen time to report. -->
			<div
				class="flex items-center gap-2.5 border-b border-[var(--st-hairline)] py-1.5 text-[13px] last:border-b-0"
			>
				<span
					class="flex size-6 shrink-0 items-center justify-center rounded-full bg-[var(--st-hover)] text-[10px] text-[var(--st-faint)]"
					aria-hidden="true">·</span
				>
				<span class="min-w-0 flex-1 truncate text-[var(--st-muted)]"
					>{$i18n.t('Anonymous')}</span
				>
				<span class="w-8 shrink-0 text-right tabular-nums text-[var(--st-muted)]"
					>{formatCount(viewers.anonymous_views, locale)}</span
				>
			</div>
		{/if}

		{#if viewers.more > 0}
			<div class="pt-1.5 text-[11px] text-[var(--st-faint)]">
				+{formatCount(viewers.more, locale)}
				{$i18n.t('more')}
			</div>
		{/if}
	{/if}
</div>
```

- [ ] **Step 2: Wire it into `OverviewTab`**

In `src/lib/components/sites/tabs/OverviewTab.svelte`:

Add the import beside the other card imports:

```svelte
	import ViewersCard from '../ViewersCard.svelte';
```

Add state beside `topPages`:

```svelte
	let viewers = $state<{
		people: {
			user_id: string;
			name: string;
			profile_image_url: string | null;
			views: number;
			last_viewed_at: number;
		}[];
		anonymous_views: number;
		more: number;
	}>({ people: [], anonymous_views: 0, more: 0 });
```

In `load`, inside the `if (seq !== loadSeq) return;`-guarded success block, beside `topPages = res.top_pages;`:

```svelte
			viewers = res.viewers ?? { people: [], anonymous_views: 0, more: 0 };
```

Replace the two-column grid so Viewers and Top pages pair, and Details drops below at full width:

```svelte
	<div class="grid gap-4 lg:grid-cols-2">
		<ViewersCard {loading} {viewers} />
		{#if showTopPages}
			<TopPagesCard {loading} {topPages} />
		{/if}
	</div>

	<div class="rounded-xl border border-[var(--st-hairline)] px-4 py-3.5">
```

The Details block keeps its existing contents; it loses only the conditional `lg:col-span-2` class, since it is now always full width. `ViewersCard` renders unconditionally — it has its own empty state, so it holds the left column rather than letting Top pages jump across on a quiet site.

- [ ] **Step 3: Typecheck**

Run: `npm run check`

Baseline is 9550 errors / 282 warnings. Report before/after and characterize every delta; only the known "i18n as store" noise on new `$i18n.t(...)` call sites is acceptable.

- [ ] **Step 4: Run the frontend tests**

Run: `CI=true npm run test:frontend -- --run src/lib/components/sites/`

Expected: PASS.

- [ ] **Step 5: Prettier and commit**

Run Prettier on both touched files, then verify the non-ASCII characters (`·`, `↗`, `—`) in `OverviewTab.svelte` survived byte-for-byte.

```bash
git add src/lib/components/sites/ViewersCard.svelte src/lib/components/sites/tabs/OverviewTab.svelte
git commit -m "feat(sites): viewer roster beside Top pages on Overview"
```

---

### Task 7: The unique-visitors caveat in the UI

**Files:**
- Modify: `src/lib/components/sites/InsightsCard.svelte`

**Interfaces:**
- Consumes: nothing new

- [ ] **Step 1: Add the note**

The `Unique visitors` KPI now means "distinct signed-in viewers, plus anonymous visitors counted once per day". Without a hint, a reader takes it as an exact headcount.

In `src/lib/components/sites/InsightsCard.svelte`, add a `title` attribute to the `Unique visitors` label element so hovering explains it:

```svelte
title={$i18n.t('Signed-in viewers are counted once. Anonymous visitors are counted once per day.')}
```

Keep it to the label element — do not restructure the KPI row, and do not add a visible second line that would change the row's height.

- [ ] **Step 2: Typecheck**

Run: `npm run check` — expect one additional "i18n as store" error from the new `$i18n.t(...)` call site, and nothing else.

- [ ] **Step 3: Prettier and commit**

```bash
git add src/lib/components/sites/InsightsCard.svelte
git commit -m "docs(sites): explain what Unique visitors counts"
```

---

### Task 8: Record the reversal in the prior spec

**Files:**
- Modify: `docs/superpowers/specs/2026-08-29-sites-analytics-design.md`

- [ ] **Step 1: Rewrite the omission section**

That spec contains a section titled **"Deliberate omission: `user_id`"** arguing that storing the viewer's user id would make `site_view` "a per-employee browsing log of internal pages". That decision has been reversed.

Rewrite the section in place — retitle it to something like "Reversed: the `user_id` omission" and keep the original argument visible, followed by what changed and why:

- The user asked for named viewers, which cannot be delivered without storing the identity.
- The consequence is exactly what the original argument described, and is accepted knowingly rather than dismissed.
- Mitigations that are part of the decision: the roster is visible only to the site owner and app admins (the analytics endpoint's existing 404-not-403 audience), and `SITES_ANALYTICS_RETENTION_DAYS` now bounds how long the record persists.
- Cross-reference `docs/superpowers/specs/2026-08-30-sites-viewers-design.md`.

Do not delete the original reasoning. A spec that silently drops a decision it once argued for is worse than one that never made the argument.

Also update that spec's `unique_visitors` description, which still says `COUNT(DISTINCT visitor_key)` and calls the result "exact against honest clients" — it is now `COUNT(DISTINCT COALESCE(user_id, visitor_key))`, exact for signed-in viewers and sum-of-daily-uniques for anonymous ones.

- [ ] **Step 2: Verify and commit**

Re-read the edited sections against the shipped code and confirm every claim is true. `git diff --stat` must show exactly one file.

```bash
git add docs/superpowers/specs/2026-08-29-sites-analytics-design.md
git commit -m "docs(sites): record the user_id reversal in the analytics spec"
```

---

### Task 9: Full verification and smoke checklist

**Files:** none modified — verification only

- [ ] **Step 1: Backend suite**

Run from `backend/`: `.venv/Scripts/python.exe -m pytest open_webui/test/sites/ -v`

Expected: PASS, ~130 tests. Record the count and any warnings.

- [ ] **Step 2: Whole backend suite for regressions**

Run from `backend/`: `.venv/Scripts/python.exe -m pytest open_webui/test/ -q --continue-on-collection-errors`

This repo has known pre-existing failures (historically 4 failures and 99 collection errors). Verify any failure also fails at this branch's base before calling it new. Report pre-existing vs new explicitly.

- [ ] **Step 3: Frontend tests and typecheck**

Run: `CI=true npm run test:frontend -- --run` and `npm run check`.

Report counts against the 9550 / 282 baseline and characterize every delta.

- [ ] **Step 4: Formatting and migration chain**

`ruff format --check` on `backend/open_webui/models/sites.py` and `backend/open_webui/routers/sites.py`.

Recompute the migration head set (same command as Task 1 Step 8); expect exactly `c1d2e3f4a5b7`.

- [ ] **Step 5: Apply the migration to the running container**

The new column does not exist in the dev container until the backend restarts. Ask the user before restarting — do not restart it unprompted.

```bash
docker restart osool-ai-open-webui-1
```

Then confirm:

```bash
docker exec osool-ai-open-webui-1 python -c "from open_webui.internal.db import engine; from sqlalchemy import inspect; print([c['name'] for c in inspect(engine).get_columns('site_view')])"
```

Expected: the list includes `user_id`.

- [ ] **Step 6: Manual browser smoke**

The user drives their own Vite hot-reload server; frontend edits are live on save. Do not start a dev server. Ask the user to run this and report:

1. Open a site's Overview. Viewers sits beside Top pages; Details is full width below.
2. A site with no traffic shows "No viewers yet".
3. Open the site's public URL in a private window. Reload Overview — Anonymous appears with a count and no last-seen time.
4. Have a second signed-in user open the link (or use a second browser profile). Their name and avatar appear, with a relative last-seen.
5. A viewer with no profile photo shows initials on a teal circle.
6. Your own visits do **not** appear in the roster — they show as `Yours` in the KPI row.
7. Switch the range to 7d and 90d; the roster changes with the window.
8. Switch to a different site in the rail; the previous site's names never appear under the new header (a skeleton shows instead).
9. Hover `Unique visitors`; the tooltip explains that anonymous visitors are counted per day.
10. Check dark mode and phone width: avatars, names, and counts stay legible and the two columns collapse cleanly.
