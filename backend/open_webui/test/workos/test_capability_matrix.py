"""Endpoint-level cells of the write-capability matrix that the older suites
didn't cover, with the exact 403 detail strings pinned."""
import pytest
from types import SimpleNamespace

import open_webui.routers.workos as wr
from open_webui.models.workos import Attachments
from open_webui.test.workos.test_router_teams import _client, U1, U2

ADMIN = SimpleNamespace(id='adm', name='Root', role='admin')
U3 = SimpleNamespace(id='u3', name='Zara', role='user')


async def _team_ws_task(c):
    team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
    await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                       json={'name': 'Eng', 'visibility': 'team'})).json()
    s = (await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'P'})).json()
    task = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                         json={'title': 'T', 'assignee_ids': ['u1']})).json()
    return team, ws, s, task


@pytest.mark.asyncio
async def test_attachment_delete_uploader_yes_other_member_no(monkeypatch):
    monkeypatch.setattr(wr, 'Storage', SimpleNamespace(delete_file=lambda key: None))
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s, task = await _team_ws_task(c)
    mine = await Attachments.insert(task['id'], None, 'k1', 'a.txt', 3, 'text/plain', 'u2')
    theirs = await Attachments.insert(task['id'], None, 'k2', 'b.txt', 3, 'text/plain', 'u1')
    async with _client(monkeypatch, user=U2) as c:
        r = await c.delete(f'/api/v1/workos/attachments/{mine.id}')
        assert r.status_code == 200 and r.json()['deleted'] is True
        r = await c.delete(f'/api/v1/workos/attachments/{theirs.id}')
        assert r.status_code == 403
        assert r.json()['detail'] == 'Only the uploader or an admin may delete.'


@pytest.mark.asyncio
async def test_label_manage_requires_team_manager(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, *_ = await _team_ws_task(c)
        label = (await c.post(f"/api/v1/workos/teams/{team['id']}/labels",
                              json={'name': 'bug', 'color': '#f00'})).json()
    async with _client(monkeypatch, user=U2) as c:  # plain member: may create, not manage
        r = await c.patch(f"/api/v1/workos/labels/{label['id']}", json={'name': 'defect'})
        assert r.status_code == 403 and r.json()['detail'] == 'Insufficient role.'
        r = await c.delete(f"/api/v1/workos/labels/{label['id']}")
        assert r.status_code == 403 and r.json()['detail'] == 'Insufficient role.'


@pytest.mark.asyncio
async def test_comment_edit_has_no_app_admin_bypass(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s, task = await _team_ws_task(c)
        comment = (await c.post(f"/api/v1/workos/tasks/{task['id']}/comments", json={'body': 'hi'})).json()
    async with _client(monkeypatch, user=ADMIN) as c:
        r = await c.patch(f"/api/v1/workos/comments/{comment['id']}", json={'body': 'edited'})
        assert r.status_code == 403 and r.json()['detail'] == 'Only the author may edit.'
        # but delete DOES allow the admin (team_role returns 'admin' for app-admins)
        r = await c.delete(f"/api/v1/workos/comments/{comment['id']}")
        assert r.status_code == 200 and r.json()['deleted'] is True


@pytest.mark.asyncio
async def test_member_patch_privileged_grant_is_owner_only(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'admin'})
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u3', 'role': 'member'})
    async with _client(monkeypatch, user=U2) as c:  # team admin, not owner
        r = await c.patch(f"/api/v1/workos/teams/{team['id']}/members/u3", json={'role': 'member'})
        assert r.status_code == 200, r.text
        r = await c.patch(f"/api/v1/workos/teams/{team['id']}/members/u3", json={'role': 'admin'})
        assert r.status_code == 403 and r.json()['detail'] == 'Insufficient role.'
