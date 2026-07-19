import pytest

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_teams import _client, U1
from open_webui.test.workos.test_router_task import _stream


async def _task(c):
    team, ws, s = await _stream(c)
    await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                      json={'title': 'T', 'assignee_ids': ['u1']})).json()
    return team, ws, s, t


@pytest.mark.asyncio
async def test_update_task_records_activity(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'status': 'in_progress', 'priority': 'high'})
        acts = (await c.get(f"/api/v1/workos/tasks/{t['id']}/activity")).json()
        types = {a['type'] for a in acts}
        assert 'status_changed' in types and 'priority_changed' in types


@pytest.mark.asyncio
async def test_assigning_user_notifies_assignee(monkeypatch):
    sent = []

    async def _eu(event, payload, user_ids):
        sent.append((event, tuple(user_ids), payload.get('type')))

    monkeypatch.setattr(wr, 'emit_users', _eu)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_ids': ['u2']})
    assert ('workos:notification.created', ('u2',), 'assigned') in sent


@pytest.mark.asyncio
async def test_actor_not_notified_for_own_status_change(monkeypatch):
    sent = []

    async def _eu(event, payload, user_ids):
        sent.extend(user_ids)

    monkeypatch.setattr(wr, 'emit_users', _eu)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)  # creator + assignee = U1 only (self-assigned, no notification)
        await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'status': 'done'})
    assert 'u1' not in sent  # the actor (creator) is filtered out


@pytest.mark.asyncio
async def test_notifications_list_and_mark_read(monkeypatch):
    from open_webui.models.workos import Notifications
    async with _client(monkeypatch, user=U1) as c:
        n = await Notifications.insert('u1', 'u2', 'assigned', {'task_key': 'OSL-1'}, task_id='t1')
        await Notifications.insert('u1', 'u2', 'mentioned', {'task_key': 'OSL-1'}, task_id='t1')
        listed = (await c.get('/api/v1/workos/notifications')).json()
        assert len(listed) == 2
        r = (await c.post('/api/v1/workos/notifications/read', json={'ids': [n.id]})).json()
        assert r['unread'] == 1
        r = (await c.post('/api/v1/workos/notifications/read', json={'all': True})).json()
        assert r['unread'] == 0


@pytest.mark.asyncio
async def test_bootstrap_includes_unread_count(monkeypatch):
    from open_webui.models.workos import Notifications
    async with _client(monkeypatch, user=U1) as c:
        await Notifications.insert('u1', 'u2', 'assigned', {}, task_id='t1')
        body = (await c.get('/api/v1/workos/bootstrap')).json()
        assert body['notifications_unread'] == 1


@pytest.mark.asyncio
async def test_notifications_are_per_user(monkeypatch):
    from open_webui.models.workos import Notifications
    await Notifications.insert('u2', 'u1', 'assigned', {}, task_id='t1')
    async with _client(monkeypatch, user=U1) as c:
        assert (await c.get('/api/v1/workos/notifications')).json() == []


@pytest.mark.asyncio
async def test_archive_endpoint_archives_and_returns_unread(monkeypatch):
    from open_webui.models.workos import Notifications
    async with _client(monkeypatch, user=U1) as c:
        n = await Notifications.insert('u1', 'u2', 'assigned', {}, task_id='t1')
        await Notifications.insert('u1', 'u2', 'mentioned', {}, task_id='t1')
        r = (await c.post('/api/v1/workos/notifications/archive', json={'ids': [n.id]})).json()
        assert r['unread'] == 1  # archive implied read on n
        default = (await c.get('/api/v1/workos/notifications')).json()
        assert len(default) == 1 and default[0]['type'] == 'mentioned'
        archived = (await c.get('/api/v1/workos/notifications?archived=true')).json()
        assert [x['id'] for x in archived] == [n.id]
        assert archived[0]['archived'] is True and archived[0]['read'] is True


@pytest.mark.asyncio
async def test_archive_all_read_sweep_and_unarchive(monkeypatch):
    from open_webui.models.workos import Notifications
    async with _client(monkeypatch, user=U1) as c:
        a = await Notifications.insert('u1', 'u2', 'assigned', {}, task_id='t1')
        await Notifications.insert('u1', 'u2', 'commented', {}, task_id='t1')
        await c.post('/api/v1/workos/notifications/read', json={'ids': [a.id]})
        await c.post('/api/v1/workos/notifications/archive', json={'all_read': True})
        assert len((await c.get('/api/v1/workos/notifications')).json()) == 1
        await c.post('/api/v1/workos/notifications/archive', json={'ids': [a.id], 'archived': False})
        assert len((await c.get('/api/v1/workos/notifications')).json()) == 2


@pytest.mark.asyncio
async def test_archive_cannot_touch_other_users_rows(monkeypatch):
    from open_webui.models.workos import Notifications
    async with _client(monkeypatch, user=U1) as c:
        other = await Notifications.insert('u2', 'u1', 'assigned', {}, task_id='t1')
        await c.post('/api/v1/workos/notifications/archive', json={'ids': [other.id]})
    rows = await Notifications.list_for_user('u2')
    assert [x.id for x in rows] == [other.id]  # untouched


@pytest.mark.asyncio
async def test_counts_endpoint(monkeypatch):
    from open_webui.models.workos import Notifications
    async with _client(monkeypatch, user=U1) as c:
        await Notifications.insert('u1', 'u2', 'mentioned', {}, task_id='t1')
        n = await Notifications.insert('u1', 'u2', 'commented', {}, task_id='t1')
        await c.post('/api/v1/workos/notifications/archive', json={'ids': [n.id]})
        counts = (await c.get('/api/v1/workos/notifications/counts')).json()
        assert counts['unread'] == 1
        assert counts['by_type'] == {'assigned': 0, 'mentioned': 1, 'commented': 0, 'status_changed': 0}
