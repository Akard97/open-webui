"""Create/patch assignee rules: every task needs at least one assignee."""
import pytest

from open_webui.test.workos.test_router_teams import _client, U1
from open_webui.test.workos.test_router_task import _stream


@pytest.mark.asyncio
async def test_create_without_assignees_rejected(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'X'})
        assert r.status_code == 400
        assert r.json()['detail'] == 'Task needs at least one assignee.'
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                         json={'title': 'X', 'assignee_ids': []})
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_create_with_assignee_succeeds(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                         json={'title': 'X', 'assignee_ids': ['u1']})
        assert r.status_code == 200, r.text
        assert r.json()['assignee_ids'] == ['u1']


@pytest.mark.asyncio
async def test_patch_cannot_clear_assignees(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                          json={'title': 'X', 'assignee_ids': ['u1']})).json()
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_ids': []})
        assert r.status_code == 400
        assert r.json()['detail'] == 'Task needs at least one assignee.'
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_ids': ['u1']})
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_create_carries_attachment_required(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                         json={'title': 'X', 'assignee_ids': ['u1'], 'attachment_required': True})
        assert r.status_code == 200, r.text
        assert r.json()['attachment_required'] is True
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                         json={'title': 'Y', 'assignee_ids': ['u1']})
        assert r.json()['attachment_required'] is False
