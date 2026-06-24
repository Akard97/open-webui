import pytest

from open_webui.test.workos.test_router_teams import _client, U1, U2
from open_webui.test.workos.test_router_task import _stream


async def _task(c):
    team, ws, s = await _stream(c)
    t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'T'})).json()
    return team, ws, s, t


@pytest.mark.asyncio
async def test_comment_create_list_edit_delete(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/comments", json={'body': 'first comment'})
        assert r.status_code == 200, r.text
        com = r.json()
        assert com['body'] == 'first comment' and com['edited_at'] is None
        listed = (await c.get(f"/api/v1/workos/tasks/{t['id']}/comments")).json()
        assert [x['id'] for x in listed] == [com['id']]
        edited = (await c.patch(f"/api/v1/workos/comments/{com['id']}", json={'body': 'edited'})).json()
        assert edited['body'] == 'edited' and edited['edited_at'] is not None
        assert (await c.delete(f"/api/v1/workos/comments/{com['id']}")).json()['deleted'] is True


@pytest.mark.asyncio
async def test_comment_create_writes_activity(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        await c.post(f"/api/v1/workos/tasks/{t['id']}/comments", json={'body': 'hi'})
        acts = (await c.get(f"/api/v1/workos/tasks/{t['id']}/activity")).json()
        assert any(a['type'] == 'comment_added' for a in acts)


@pytest.mark.asyncio
async def test_only_author_can_edit_comment(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        await c.post(f"/api/v1/workos/teams/{t['team_id']}/members", json={'user_id': 'u2', 'role': 'member'})
        com = (await c.post(f"/api/v1/workos/tasks/{t['id']}/comments", json={'body': 'mine'})).json()
    async with _client(monkeypatch, user=U2) as c:
        r = await c.patch(f"/api/v1/workos/comments/{com['id']}", json={'body': 'hacked'})
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_non_member_cannot_comment(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
    async with _client(monkeypatch, user=U2) as c:
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/comments", json={'body': 'x'})
        assert r.status_code == 404
