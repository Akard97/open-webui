import pytest

from open_webui.routers.workos import _daily_counts
from open_webui.test.workos.test_router_teams import _client, U1, U2
from open_webui.test.workos.test_router_task import _stream


def test_daily_counts_buckets_by_viewer_local_day():
    # 2026-06-17T22:30Z; viewer at UTC+3 → local day is already 2026-06-18.
    now_ms = 1781735400000
    late_evening_utc = now_ms
    assert _daily_counts([late_evening_utc], days=2, tz_offset_minutes=180, now_ms=now_ms) == [
        {'day': '2026-06-17', 'n': 0},
        {'day': '2026-06-18', 'n': 1},
    ]
    # Same instant for a UTC viewer lands on the 17th.
    assert _daily_counts([late_evening_utc], days=2, tz_offset_minutes=0, now_ms=now_ms) == [
        {'day': '2026-06-16', 'n': 0},
        {'day': '2026-06-17', 'n': 1},
    ]


def test_daily_counts_window_length_and_order():
    now_ms = 1781735400000
    out = _daily_counts([], days=14, tz_offset_minutes=0, now_ms=now_ms)
    assert len(out) == 14
    assert out[-1]['day'] > out[0]['day']


@pytest.mark.asyncio
async def test_member_gets_items_with_task_join_and_daily(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                          json={'title': 'T', 'assignee_ids': ['u1']})).json()
        await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'status': 'in_progress'})
        r = await c.get(f"/api/v1/workos/workstreams/{s['id']}/activity")
        assert r.status_code == 200
        body = r.json()
        assert len(body['daily']) == 14
        assert body['items'], 'status change must produce activity'
        first = body['items'][0]
        assert first['task_key'] == t['key'] and first['task_title'] == 'T'
        # newest first
        times = [i['created_at'] for i in body['items']]
        assert times == sorted(times, reverse=True)


@pytest.mark.asyncio
async def test_clamps_do_not_error(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, s = await _stream(c)
        r = await c.get(
            f"/api/v1/workos/workstreams/{s['id']}/activity?limit=99999&days=9999&tz_offset_minutes=99999"
        )
        assert r.status_code == 200
        assert len(r.json()['daily']) == 31


@pytest.mark.asyncio
async def test_non_member_gets_404(monkeypatch):
    # U2 (from test_router_teams) has no membership row in the team — a valid outsider,
    # mirroring the pattern used in test_router_access_leaks.py.
    async with _client(monkeypatch, user=U1) as c:
        _, _, s = await _stream(c)
        stream_id = s['id']
    async with _client(monkeypatch, user=U2) as c2:
        r = await c2.get(f'/api/v1/workos/workstreams/{stream_id}/activity')
        assert r.status_code == 404
