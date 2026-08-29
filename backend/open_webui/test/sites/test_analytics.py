import asyncio
import time
import uuid
from datetime import datetime, timezone

import pytest

from open_webui.internal.db import get_async_db_context
from open_webui.models.sites import SiteView, SiteViews


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


DAY_MS = 86_400_000
# 2026-08-29T12:00:00Z, pinned so day bucketing is deterministic.
NOW_MS = int(datetime(2026, 8, 29, 12, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)


async def _record_at(site_id, path, key, is_owner, ts_ms, *, user_id=None):
    """Insert a SiteView row directly with a pinned created_at.

    Deliberately bypasses record_view (which stamps its own wall-clock time)
    instead of inserting via it and then rewriting/re-querying the row
    afterward: re-querying by ORDER BY created_at DESC on the very column
    about to be rewritten is unsound once an earlier call in the same test
    has already pinned a row's created_at ahead of the real clock.
    """
    async with get_async_db_context(None) as db:
        db.add(
            SiteView(
                id=str(uuid.uuid4()),
                site_id=site_id,
                path=path,
                visitor_key=key,
                is_owner=is_owner,
                user_id=user_id,
                created_at=ts_ms,
            )
        )
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
    assert a['series'][0] == {'day': '2026-08-23', 'views': 0}
    assert a['series'][-1] == {'day': '2026-08-29', 'views': 1}
    assert a['series'][-3] == {'day': '2026-08-27', 'views': 1}
    assert a['series'][-2] == {'day': '2026-08-28', 'views': 0}
    days = [p['day'] for p in a['series']]
    assert days == sorted(days)


@pytest.mark.asyncio
async def test_get_analytics_sums_multiple_views_on_the_same_day():
    """Two non-owner views on the same UTC day, at different times, must land
    in the same day bucket and sum together.

    Regression test for a bucketing bug where SQLAlchemy compiled the
    `created_at / day_ms` day-index expression to true (fractional) division
    in SQL. GROUP BY then grouped on the fractional value, so two views on
    the same calendar day at different times of day fell into separate SQL
    groups; truncating those distinct fractional keys to the same integer
    day afterward in Python silently kept only the last group's count.
    """
    day_start = int(datetime(2026, 8, 29, 0, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    morning = day_start + 9 * 60 * 60 * 1000  # 2026-08-29T09:00:00Z
    evening = day_start + 21 * 60 * 60 * 1000  # 2026-08-29T21:00:00Z

    await _record_at('s1', 'index.html', 'k1', False, morning)
    await _record_at('s1', 'about.html', 'k2', False, evening)

    a = await SiteViews.get_analytics('s1', 7, now_ms=NOW_MS)

    assert a['series'][-1] == {'day': '2026-08-29', 'views': 2}
    assert a['totals']['views'] == 2


@pytest.mark.asyncio
async def test_get_analytics_ignores_views_outside_the_window():
    await _record_at('s1', 'index.html', 'k1', False, NOW_MS - 40 * DAY_MS)

    a = await SiteViews.get_analytics('s1', 7, now_ms=NOW_MS)

    assert a['totals']['views'] == 0
    assert all(p['views'] == 0 for p in a['series'])


@pytest.mark.asyncio
async def test_get_analytics_excludes_future_dated_rows_so_the_series_sums_to_the_total():
    """A row stamped after the end of today (clock rollback, bad import) has a
    day index past the last series bucket, so counting it in `totals` while no
    `series` entry can hold it would make a single response contradict itself."""
    await _record_at('s1', 'index.html', 'k1', False, NOW_MS)
    await _record_at('s1', 'index.html', 'kfuture', False, NOW_MS + 3 * DAY_MS)
    await _record_at('s1', 'index.html', 'kowner-future', True, NOW_MS + 3 * DAY_MS)

    a = await SiteViews.get_analytics('s1', 7, now_ms=NOW_MS)

    assert a['totals']['views'] == 1
    assert a['totals']['unique_visitors'] == 1
    assert a['totals']['owner_views'] == 0
    assert sum(p['views'] for p in a['series']) == a['totals']['views']
    assert a['top_pages'] == [{'path': 'index.html', 'views': 1}]


@pytest.mark.asyncio
async def test_get_analytics_keeps_the_last_millisecond_of_today():
    """The upper bound is exclusive at the END of today, not at `now`: a view
    recorded later today must still count."""
    end_of_today = ((NOW_MS // DAY_MS) + 1) * DAY_MS - 1

    await _record_at('s1', 'index.html', 'k1', False, end_of_today)

    a = await SiteViews.get_analytics('s1', 7, now_ms=NOW_MS)

    assert a['totals']['views'] == 1
    assert a['series'][-1] == {'day': '2026-08-29', 'views': 1}


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


@pytest.mark.asyncio
async def test_prune_older_than_deletes_only_rows_past_the_retention_window():
    await _record_at('s1', 'index.html', 'old', False, NOW_MS - 100 * DAY_MS)
    await _record_at('s1', 'index.html', 'edge', False, NOW_MS - 31 * DAY_MS)
    await _record_at('s1', 'index.html', 'recent', False, NOW_MS - 29 * DAY_MS)
    await _record_at('s2', 'index.html', 'other-site-old', False, NOW_MS - 100 * DAY_MS)

    deleted = await SiteViews.prune_older_than(30, now_ms=NOW_MS)

    assert deleted == 3  # both s1 rows past the window, plus s2's
    assert [r.visitor_key for r in await SiteViews.list_views('s1')] == ['recent']
    assert await SiteViews.list_views('s2') == []


@pytest.mark.asyncio
@pytest.mark.parametrize('days', [0, -1])
async def test_prune_older_than_is_a_no_op_when_retention_is_off(days):
    """Unset (which env.py normalises to 0) must keep every row forever —
    the behaviour before this setting existed."""
    await _record_at('s1', 'index.html', 'ancient', False, NOW_MS - 10_000 * DAY_MS)

    deleted = await SiteViews.prune_older_than(days, now_ms=NOW_MS)

    assert deleted == 0
    assert len(await SiteViews.list_views('s1')) == 1


def test_retention_setting_defaults_to_off_and_survives_garbage():
    """The env default and the parsing fallbacks: anything that is not a
    positive integer must mean 'keep forever', never 'delete everything'."""
    import importlib
    import os

    import open_webui.env as env_module

    # One value per branch: unset, unparseable, negative, valid.
    for raw, expected in [(None, 0), ('not-a-number', 0), ('-5', 0), ('90', 90)]:
        before = os.environ.pop('SITES_ANALYTICS_RETENTION_DAYS', None)
        try:
            if raw is not None:
                os.environ['SITES_ANALYTICS_RETENTION_DAYS'] = raw
            reloaded = importlib.reload(env_module)
            assert reloaded.SITES_ANALYTICS_RETENTION_DAYS == expected, raw
        finally:
            os.environ.pop('SITES_ANALYTICS_RETENTION_DAYS', None)
            if before is not None:
                os.environ['SITES_ANALYTICS_RETENTION_DAYS'] = before
    importlib.reload(env_module)


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


from types import SimpleNamespace

import httpx
from fastapi import FastAPI, Request
from httpx import ASGITransport

from open_webui.models.sites import Sites

R_OWNER = SimpleNamespace(id='ro1', role='user', name='Owner', email='ro@x.io')
R_VIEWER = SimpleNamespace(id='rv1', role='user', name='Viewer', email='rv@x.io')

BROWSER_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36'


def _serve_client(monkeypatch, tmp_path, *, viewer):
    """An httpx client wired to the public serve routes.

    When `viewer` is not None the client also sends a `token` cookie, because
    that is the only request shape that can produce an authenticated viewer in
    production: `_get_optional_user` returns None unless a bearer header or a
    token cookie is present. A client that claims a viewer while sending no
    credentials tests a request that cannot exist.

    The returned client carries `.auth_calls`, a counter of how many times
    `_get_optional_user` ran during the request. Tests use it to pin that
    anonymous traffic to a public site performs no token decode and no user
    lookup, and that a credentialed request resolves the viewer exactly once.
    """
    auth_calls = {'count': 0}

    async def _fake_optional_user(request):
        auth_calls['count'] += 1
        return viewer

    app = FastAPI()
    app.include_router(sites_router.serve_router)
    monkeypatch.setattr(sites_router, '_get_optional_user', _fake_optional_user)
    monkeypatch.setattr(sites_router, 'SITES_DIR', tmp_path)
    client = httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url='http://test',
        headers={'user-agent': BROWSER_UA},
        cookies={'token': 'test-session-token'} if viewer is not None else {},
    )
    client.auth_calls = auth_calls
    return client


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
async def test_missing_document_is_not_recorded(monkeypatch, tmp_path):
    """The pageview is queued only after _serve_file has returned, so an HTML
    file the site does not have is never counted as a view."""
    site = await _seed_site(tmp_path, slug='rec-ghost', public=True)
    async with _serve_client(monkeypatch, tmp_path, viewer=None) as c:
        assert (await c.get('/sites/rec-ghost/ghost.html')).status_code == 404

    assert await SiteViews.list_views(site.id) == []


@pytest.mark.asyncio
async def test_head_requests_are_not_recorded(monkeypatch, tmp_path):
    """A HEAD renders no page, so it must never count as a pageview — and the
    bot filter will not catch one, because link-preview fetchers and uptime
    monitors routinely send browser-shaped User-Agents.

    Today these are FastAPI APIRoutes, which (unlike Starlette's plain Route)
    do not auto-add HEAD to a GET route, so the request is rejected with 405
    and never reaches recording. This test pins the outcome, not the mechanism:
    it stays green if HEAD is ever allowed through, because `_record_view`'s
    method guard then does the rejecting instead.
    """
    site = await _seed_site(tmp_path, slug='rec-head', public=True)
    async with _serve_client(monkeypatch, tmp_path, viewer=None) as c:
        assert (await c.head('/sites/rec-head/')).status_code in (200, 405)
        assert (await c.head('/sites/rec-head/about.html')).status_code in (200, 405)

    assert await SiteViews.list_views(site.id) == []


@pytest.mark.asyncio
async def test_record_view_ignores_non_get_methods():
    """The method guard itself, exercised directly: it is the backstop that
    keeps HEAD uncounted if these routes are ever declared with
    methods=['GET', 'HEAD'] or mounted as plain Starlette routes."""
    for method in ('HEAD', 'OPTIONS'):
        await sites_router._record_view(
            site_id='s-head',
            owner_id='o1',
            filename='index.html',
            method=method,
            user_agent=BROWSER_UA,
            ip='10.0.0.1',
            has_credentials=False,
            request=None,
            viewer=None,
        )
    assert await SiteViews.list_views('s-head') == []

    await sites_router._record_view(
        site_id='s-head',
        owner_id='o1',
        filename='index.html',
        method='GET',
        user_agent=BROWSER_UA,
        ip='10.0.0.1',
        has_credentials=False,
        request=None,
        viewer=None,
    )
    assert len(await SiteViews.list_views('s-head')) == 1


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
async def test_anonymous_view_of_a_public_site_resolves_no_user(monkeypatch, tmp_path):
    """Rule 5: anonymous traffic to a public site pays no token decode and no
    user lookup. Access resolution short-circuits on `public`, and recording
    only resolves a viewer when the request actually carries credentials."""
    site = await _seed_site(tmp_path, slug='rec-anon-cost', public=True)
    async with _serve_client(monkeypatch, tmp_path, viewer=None) as c:
        assert (await c.get('/sites/rec-anon-cost/')).status_code == 200
        assert c.auth_calls['count'] == 0

    rows = await SiteViews.list_views(site.id)
    assert len(rows) == 1
    assert rows[0].is_owner is False


@pytest.mark.asyncio
async def test_owner_visit_is_flagged(monkeypatch, tmp_path):
    """Private site: the viewer access resolution already resolved is reused,
    so the owner is flagged without a second token decode."""
    site = await _seed_site(tmp_path, slug='rec-owner', public=False)
    async with _serve_client(monkeypatch, tmp_path, viewer=R_OWNER) as c:
        assert (await c.get('/sites/rec-owner/')).status_code == 200
        assert c.auth_calls['count'] == 1  # resolved once, by access control

    rows = await SiteViews.list_views(site.id)
    assert len(rows) == 1
    assert rows[0].is_owner is True


@pytest.mark.asyncio
async def test_owner_visit_to_a_public_site_is_flagged(monkeypatch, tmp_path):
    """The common real case: the owner is logged in and opens their own public
    site. Access resolution skips the viewer for public sites, so the owner is
    only recognised because the request carries credentials."""
    site = await _seed_site(tmp_path, slug='rec-pub-owner', public=True)
    async with _serve_client(monkeypatch, tmp_path, viewer=R_OWNER) as c:
        assert (await c.get('/sites/rec-pub-owner/')).status_code == 200
        assert c.auth_calls['count'] == 1  # credentials present -> resolved

    rows = await SiteViews.list_views(site.id)
    assert len(rows) == 1
    assert rows[0].is_owner is True


@pytest.mark.asyncio
async def test_non_owner_visit_is_not_flagged(monkeypatch, tmp_path):
    """A logged-in non-owner on a public site: the viewer IS resolved (the
    auth_calls assertion proves it) and is still not flagged as the owner."""
    site = await _seed_site(tmp_path, slug='rec-viewer', public=True)
    async with _serve_client(monkeypatch, tmp_path, viewer=R_VIEWER) as c:
        assert (await c.get('/sites/rec-viewer/')).status_code == 200
        assert c.auth_calls['count'] == 1

    rows = await SiteViews.list_views(site.id)
    assert len(rows) == 1
    assert rows[0].is_owner is False


@pytest.mark.asyncio
async def test_queueing_a_view_does_no_analytics_work_on_the_response_path(monkeypatch, tmp_path):
    """`_queue_view` must only capture request scalars and append a task.

    The token decode, the visitor-key HMAC and the INSERT all belong after the
    response. This checks the boundary directly: queueing resolves no user and
    writes no row, and both happen only once the queued task is awaited.
    """
    from fastapi import BackgroundTasks

    site = await _seed_site(tmp_path, slug='rec-deferred', public=True)
    calls = {'count': 0}

    async def _fake_optional_user(request):
        calls['count'] += 1
        return R_OWNER

    monkeypatch.setattr(sites_router, '_get_optional_user', _fake_optional_user)

    request = httpx.Request(
        'GET',
        'http://test/sites/rec-deferred/',
        headers={'user-agent': BROWSER_UA, 'cookie': 'token=t'},
    )
    scope = {
        'type': 'http',
        'method': 'GET',
        'path': '/sites/rec-deferred/',
        'headers': [(k.lower().encode(), v.encode()) for k, v in request.headers.items()],
        'client': ('10.0.0.7', 51234),
        'query_string': b'',
    }

    background = BackgroundTasks()
    assert not asyncio.iscoroutinefunction(sites_router._queue_view)
    sites_router._queue_view(site, 'index.html', Request(scope), background, viewer=None)

    # Queued, but nothing has happened yet.
    assert len(background.tasks) == 1
    assert calls['count'] == 0
    assert await SiteViews.list_views(site.id) == []

    await background()

    assert calls['count'] == 1
    rows = await SiteViews.list_views(site.id)
    assert len(rows) == 1
    assert rows[0].is_owner is True  # the credentialed owner, resolved in the task


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


def _api_client(monkeypatch, *, user, allow=True):
    """An httpx client wired to the authenticated site-management routes.

    Mocks only `has_permission` — `_require_publisher`'s single external
    dependency — so `_require_publisher`'s real body runs, including its
    `user.role != 'admin'` short-circuit and its 401 raise. `allow` controls
    what a non-admin's `features.site_publisher` check returns; admins never
    consult it.
    """
    from open_webui.utils.auth import get_verified_user

    app = FastAPI()
    app.state.config = SimpleNamespace(USER_PERMISSIONS={})
    app.include_router(sites_router.router, prefix='/api/v1/sites')
    app.dependency_overrides[get_verified_user] = lambda: user

    async def _has_permission(*args, **kwargs):
        return allow

    monkeypatch.setattr(sites_router, 'has_permission', _has_permission)
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

    async with _api_client(monkeypatch, user=admin, allow=False) as c:
        r = await c.get(f'/api/v1/sites/{site.id}/analytics?days=7')

    assert r.status_code == 200
    assert r.json()['days'] == 7


@pytest.mark.asyncio
async def test_analytics_endpoint_denies_without_the_site_publisher_permission(monkeypatch, tmp_path):
    site = await _seed_site(tmp_path, slug='api-no-perm', public=True)

    async with _api_client(monkeypatch, user=R_OWNER, allow=False) as c:
        r = await c.get(f'/api/v1/sites/{site.id}/analytics?days=30')

    assert r.status_code == 401


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


@pytest.mark.asyncio
async def test_analytics_endpoint_returns_named_viewers(monkeypatch, tmp_path):
    from open_webui.models.users import Users

    site = await _seed_site(tmp_path, slug='api-viewers', public=True)
    await Users.insert_new_user(id='u1', name='Sara', email='sara@x.io', profile_image_url='/img/a.png')

    # record_view stamps the real wall clock (not the pinned NOW_MS used
    # elsewhere in this file), so last_viewed_at is pinned against a window
    # bracketing the call rather than against itself.
    before_ms = int(time.time() * 1000)
    await SiteViews.record_view(site.id, 'index.html', 'k1', False, user_id='u1')
    after_ms = int(time.time() * 1000)
    await SiteViews.record_view(site.id, 'index.html', 'k2', False)

    async with _api_client(monkeypatch, user=R_OWNER) as c:
        r = await c.get(f'/api/v1/sites/{site.id}/analytics?days=30')

    assert r.status_code == 200
    viewers = r.json()['viewers']
    last_viewed_at = viewers['people'][0]['last_viewed_at']
    assert before_ms <= last_viewed_at <= after_ms
    assert viewers['people'] == [
        {
            'user_id': 'u1',
            'name': 'Sara',
            'profile_image_url': '/img/a.png',
            'views': 1,
            'last_viewed_at': last_viewed_at,
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
