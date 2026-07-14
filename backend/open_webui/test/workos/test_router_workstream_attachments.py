import io

import pytest

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_teams import _client, U1, U2
from open_webui.test.workos.test_router_task import _stream
from open_webui.test.workos.test_router_attachments import _FakeStorage
from open_webui.test.workos.test_router_access_leaks import _restricted_task


async def _upload(c, task_id, name='f.txt', body=b'x', ctype='text/plain', comment_id=None):
    files = {'file': (name, io.BytesIO(body), ctype)}
    qs = f'?comment_id={comment_id}' if comment_id else ''
    r = await c.post(f'/api/v1/workos/tasks/{task_id}/attachments{qs}', files=files)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_member_lists_files_across_tasks_with_task_join(monkeypatch):
    monkeypatch.setattr(wr, 'Storage', _FakeStorage)
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        t1 = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'A'})).json()
        t2 = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'B'})).json()
        a1 = await _upload(c, t1['id'], name='one.txt')
        a2 = await _upload(c, t2['id'], name='two.pdf', ctype='application/pdf')
        # comment attachment on t1 must be included, with comment_id set
        com = (await c.post(f"/api/v1/workos/tasks/{t1['id']}/comments", json={'body': 'ctx'})).json()
        a3 = await _upload(c, t1['id'], name='three.png', ctype='image/png', comment_id=com['id'])

        r = await c.get(f"/api/v1/workos/workstreams/{s['id']}/attachments")
        assert r.status_code == 200, r.text
        rows = r.json()
        assert {x['id'] for x in rows} == {a1['id'], a2['id'], a3['id']}
        by_id = {x['id']: x for x in rows}
        assert by_id[a1['id']]['task_key'] == t1['key']
        assert by_id[a1['id']]['task_title'] == 'A'
        assert by_id[a1['id']]['task_status'] == t1['status']
        assert by_id[a2['id']]['task_key'] == t2['key']
        assert by_id[a3['id']]['comment_id'] == com['id']
        # newest first (ties allowed)
        times = [x['created_at'] for x in rows]
        assert times == sorted(times, reverse=True)


@pytest.mark.asyncio
async def test_empty_workstream_returns_empty_list(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, s = await _stream(c)
        r = await c.get(f"/api/v1/workos/workstreams/{s['id']}/attachments")
        assert r.status_code == 200 and r.json() == []


@pytest.mark.asyncio
async def test_non_member_gets_404(monkeypatch):
    monkeypatch.setattr(wr, 'Storage', _FakeStorage)
    async with _client(monkeypatch, user=U1) as c:
        _, _, s = await _stream(c)
        stream_id = s['id']
    async with _client(monkeypatch, user=U2) as c2:
        r = await c2.get(f'/api/v1/workos/workstreams/{stream_id}/attachments')
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_restricted_workspace_gates_team_member_without_ws_row(monkeypatch):
    monkeypatch.setattr(wr, 'Storage', _FakeStorage)
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s, t = await _restricted_task(c)
        await _upload(c, t['id'])
        # u2 joins the TEAM but not the restricted workspace
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    async with _client(monkeypatch, user=U2) as c2:
        r = await c2.get(f"/api/v1/workos/workstreams/{s['id']}/attachments")
        assert r.status_code == 404
    async with _client(monkeypatch, user=U1) as c:
        await c.post(f"/api/v1/workos/workspaces/{ws['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    async with _client(monkeypatch, user=U2) as c2:
        r = await c2.get(f"/api/v1/workos/workstreams/{s['id']}/attachments")
        assert r.status_code == 200
        assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_unknown_workstream_404(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        r = await c.get('/api/v1/workos/workstreams/nope/attachments')
        assert r.status_code == 404
