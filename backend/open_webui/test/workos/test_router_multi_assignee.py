import pytest

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_teams import _client, U1
from open_webui.test.workos.test_router_task import _stream


async def _task(c, **body):
    team, ws, s = await _stream(c)
    for uid in ('u2', 'u3'):
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': uid, 'role': 'member'})
    t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                      json={'title': 'T', 'assignee_ids': ['u1'], **body})).json()
    return team, ws, s, t


@pytest.mark.asyncio
async def test_create_task_with_multiple_assignees(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c, assignee_ids=['u2', 'u3'])
        assert t['assignee_ids'] == ['u2', 'u3']
        assert 'assignee_id' not in t


@pytest.mark.asyncio
async def test_create_task_without_assignees_rejected(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'T'})
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_creating_task_with_assignees_notifies_them(monkeypatch):
    sent = []

    async def _eu(event, payload, user_ids):
        if payload.get('type') == 'assigned':
            sent.extend(user_ids)

    monkeypatch.setattr(wr, 'emit_users', _eu)
    async with _client(monkeypatch, user=U1) as c:
        # U1 creates a task assigned to u1 (self) + u2; only u2 is notified.
        await _task(c, assignee_ids=['u1', 'u2'])
    assert 'u1' not in sent and 'u2' in sent


@pytest.mark.asyncio
async def test_assigning_users_notifies_all_assignees(monkeypatch):
    sent = []

    async def _eu(event, payload, user_ids):
        if payload.get('type') == 'assigned':
            sent.extend(user_ids)

    monkeypatch.setattr(wr, 'emit_users', _eu)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_ids': ['u2', 'u3']})
    assert set(sent) == {'u2', 'u3'}


@pytest.mark.asyncio
async def test_adding_an_assignee_renotifies_existing_assignees(monkeypatch):
    """Per design: any assignee-set change notifies ALL current assignees."""
    sent = []

    async def _eu(event, payload, user_ids):
        if payload.get('type') == 'assigned':
            sent.append(tuple(sorted(user_ids)))

    monkeypatch.setattr(wr, 'emit_users', _eu)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_ids': ['u2']})
        await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_ids': ['u2', 'u3']})
    # second edit fires notifications to both the existing (u2) and the new (u3) assignee
    flat = [uid for batch in sent for uid in batch]
    assert flat.count('u2') == 2 and flat.count('u3') == 1


@pytest.mark.asyncio
async def test_actor_excluded_from_assignment_notifications(monkeypatch):
    sent = []

    async def _eu(event, payload, user_ids):
        sent.extend(user_ids)

    monkeypatch.setattr(wr, 'emit_users', _eu)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        # U1 assigns themselves + u2; U1 (the actor) must not be notified
        await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_ids': ['u1', 'u2']})
    assert 'u1' not in sent and 'u2' in sent


@pytest.mark.asyncio
async def test_assignee_change_records_added_and_removed_activity(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c, assignee_ids=['u2'])
        await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_ids': ['u3']})
        acts = (await c.get(f"/api/v1/workos/tasks/{t['id']}/activity")).json()
        changed = [a for a in acts if a['type'] == 'assignee_changed']
        assert changed, 'expected an assignee_changed activity'
        data = changed[0]['data']
        assert data.get('added') == ['u3']
        assert data.get('removed') == ['u2']


@pytest.mark.asyncio
async def test_status_change_notifies_creator_and_all_assignees(monkeypatch):
    sent = []

    async def _eu(event, payload, user_ids):
        if payload.get('type') == 'status_changed':
            sent.extend(user_ids)

    monkeypatch.setattr(wr, 'emit_users', _eu)
    async with _client(monkeypatch, user=U1) as c:
        # creator is U1; assignees u2 + u3. U1 changes status -> u2, u3 notified (U1 is actor).
        _, _, _, t = await _task(c, assignee_ids=['u2', 'u3'])
        await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'status': 'in_progress'})
    assert set(sent) == {'u2', 'u3'}
