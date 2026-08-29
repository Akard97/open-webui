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
