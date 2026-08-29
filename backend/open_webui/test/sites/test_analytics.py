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
