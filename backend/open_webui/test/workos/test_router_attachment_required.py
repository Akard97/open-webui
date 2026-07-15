"""Attachment-required-to-complete: toggle permission matrix + done-block guard."""
import pytest
from types import SimpleNamespace

from open_webui.models.workos import Attachments
from open_webui.test.workos.test_router_teams import _client, U1, U2

ADMIN = SimpleNamespace(id='adm', name='Root', role='admin')


async def _setup(c, creator_id='u1', flag=True, key='OSL'):
    team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': key})).json()
    await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                       json={'name': 'Eng', 'visibility': 'team'})).json()
    s = (await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'P'})).json()
    task = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                         json={'title': 'T', 'assignee_ids': [creator_id, 'u2'],
                               'attachment_required': flag})).json()
    return team, ws, s, task


@pytest.mark.asyncio
async def test_done_blocked_without_attachment(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _setup(c)
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'status': 'done'})
        assert r.status_code == 400
        assert r.json()['detail'] == 'ATTACHMENT_REQUIRED'
        # nothing persisted
        assert (await c.get(f"/api/v1/workos/tasks/{t['id']}")).json()['status'] == 'backlog'


@pytest.mark.asyncio
async def test_done_allowed_with_task_attachment(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _setup(c)
        await Attachments.insert(t['id'], None, 'k1', 'proof.txt', 3, 'text/plain', 'u1')
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'status': 'done'})
        assert r.status_code == 200, r.text
        assert r.json()['status'] == 'done'


@pytest.mark.asyncio
async def test_done_allowed_with_comment_attachment(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _setup(c)
        comment = (await c.post(f"/api/v1/workos/tasks/{t['id']}/comments", json={'body': 'proof below'})).json()
        await Attachments.insert(t['id'], comment['id'], 'k2', 'proof.png', 3, 'image/png', 'u1')
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'status': 'done'})
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_flag_off_and_non_done_transitions_unaffected(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, plain = await _setup(c, flag=False)
        assert (await c.patch(f"/api/v1/workos/tasks/{plain['id']}", json={'status': 'done'})).status_code == 200
        _, _, _, flagged = await _setup(c, key='OSL2')
        assert (await c.patch(f"/api/v1/workos/tasks/{flagged['id']}",
                              json={'status': 'in_progress'})).status_code == 200


@pytest.mark.asyncio
async def test_resave_of_done_task_not_blocked(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _setup(c, flag=False)
        assert (await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'status': 'done'})).status_code == 200
        assert (await c.patch(f"/api/v1/workos/tasks/{t['id']}",
                              json={'attachment_required': True})).status_code == 200
        # already done: a resave that still says 'done' is not a transition
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'status': 'done', 'title': 'Renamed'})
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_toggle_creator_and_app_admin_allowed(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _setup(c)
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'attachment_required': False})
        assert r.status_code == 200 and r.json()['attachment_required'] is False
    async with _client(monkeypatch, user=ADMIN) as c:
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'attachment_required': True})
        assert r.status_code == 200 and r.json()['attachment_required'] is True


@pytest.mark.asyncio
async def test_toggle_assignee_forbidden(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _setup(c)
    async with _client(monkeypatch, user=U2) as c:  # assignee, task-writable, NOT creator
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'attachment_required': False})
        assert r.status_code == 403
        assert r.json()['detail'] == 'Only the task creator or an admin may change the attachment requirement.'
        # flag unchanged
        assert (await c.get(f"/api/v1/workos/tasks/{t['id']}")).json()['attachment_required'] is True


@pytest.mark.asyncio
async def test_toggle_team_owner_forbidden_when_not_creator(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:  # U1 = team owner
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                           json={'name': 'Eng', 'visibility': 'team'})).json()
        s = (await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'P'})).json()
    async with _client(monkeypatch, user=U2) as c:  # u2 creates the task
        t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                          json={'title': 'T', 'assignee_ids': ['u2'], 'attachment_required': True})).json()
    async with _client(monkeypatch, user=U1) as c:  # owner but not creator → 403
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'attachment_required': False})
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_resending_same_flag_value_is_not_gated(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _setup(c)
    async with _client(monkeypatch, user=U2) as c:  # assignee resends unchanged value
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}",
                          json={'attachment_required': True, 'priority': 'high'})
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_toggle_records_activity(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _setup(c, flag=False)
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'attachment_required': True})
        assert r.status_code == 200, r.text
        acts = (await c.get(f"/api/v1/workos/tasks/{t['id']}/activity")).json()
        changed = [a for a in acts if a['type'] == 'attachment_required_changed']
        assert changed, 'expected an attachment_required_changed activity'
        assert changed[0]['data'] == {'from': False, 'to': True}


@pytest.mark.asyncio
async def test_mixed_patch_fails_atomically(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _setup(c, flag=False)
        # turning the flag ON and completing in the same patch, with no attachment → blocked, nothing saved
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}",
                          json={'status': 'done', 'attachment_required': True})
        assert r.status_code == 400 and r.json()['detail'] == 'ATTACHMENT_REQUIRED'
        after = (await c.get(f"/api/v1/workos/tasks/{t['id']}")).json()
        assert after['status'] == 'backlog' and after['attachment_required'] is False
        # turning it OFF and completing in one patch is the creator's prerogative → allowed
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}",
                          json={'status': 'done', 'attachment_required': False})
        assert r.status_code == 200, r.text
