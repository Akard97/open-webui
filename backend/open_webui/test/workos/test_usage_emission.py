from unittest.mock import AsyncMock

import pytest

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_comments import _task
from open_webui.test.workos.test_router_task import _stream
from open_webui.test.workos.test_router_teams import U1, _client


@pytest.fixture()
def emit_spy(monkeypatch):
    spy = AsyncMock()
    monkeypatch.setattr(wr.UsageEvents, 'emit', spy)
    return spy


def _emitted(spy):
    return [c.args[1] for c in spy.await_args_list]


@pytest.mark.asyncio
async def test_task_create_emits(monkeypatch, emit_spy):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        r = await c.post(
            f"/api/v1/workos/workstreams/{s['id']}/tasks",
            json={'title': 'task', 'assignee_ids': [U1.id]},
        )
        assert r.status_code == 200
    assert 'workos.task.create' in _emitted(emit_spy)


@pytest.mark.asyncio
async def test_task_complete_emits_only_on_transition_to_done(monkeypatch, emit_spy):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s, task = await _task(c)
        await c.patch(f"/api/v1/workos/tasks/{task['id']}", json={'status': 'in_progress'})
        assert 'workos.task.complete' not in _emitted(emit_spy)
        await c.patch(f"/api/v1/workos/tasks/{task['id']}", json={'status': 'done'})
        assert 'workos.task.complete' in _emitted(emit_spy)
        emit_spy.reset_mock()
        await c.patch(f"/api/v1/workos/tasks/{task['id']}", json={'title': 'renamed'})
        assert 'workos.task.complete' not in _emitted(emit_spy)


@pytest.mark.asyncio
async def test_task_delete_and_comment_emit(monkeypatch, emit_spy):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s, task = await _task(c)
        await c.post(f"/api/v1/workos/tasks/{task['id']}/comments", json={'body': 'hi'})
        assert 'workos.comment.create' in _emitted(emit_spy)
        await c.delete(f"/api/v1/workos/tasks/{task['id']}")
        assert 'workos.task.delete' in _emitted(emit_spy)


@pytest.mark.asyncio
async def test_workspace_membership_changes_emit(monkeypatch, emit_spy):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        r = await c.post(
            f"/api/v1/workos/workspaces/{ws['id']}/members",
            json={'user_id': 'u2', 'role': 'member'},
        )
        assert r.status_code == 200, r.text
        assert 'workos.workspace.member_add' in _emitted(emit_spy)
        call = emit_spy.await_args_list[-1]
        assert call.args[0] == U1.id
        assert call.args[2] == {'workspace_id': ws['id'], 'member_id': 'u2'}

        r = await c.delete(f"/api/v1/workos/workspaces/{ws['id']}/members/u2")
        assert r.status_code == 200
        assert r.json()['removed'] is True
        assert 'workos.workspace.member_remove' in _emitted(emit_spy)
        call = emit_spy.await_args_list[-1]
        assert call.args[0] == U1.id
        assert call.args[2] == {'workspace_id': ws['id'], 'member_id': 'u2'}

        # Removing a non-member is a no-op and must not emit again.
        emit_spy.reset_mock()
        r = await c.delete(f"/api/v1/workos/workspaces/{ws['id']}/members/u2")
        assert r.status_code == 200
        assert r.json()['removed'] is False
        assert 'workos.workspace.member_remove' not in _emitted(emit_spy)


@pytest.mark.asyncio
async def test_workspace_visibility_change_emits_only_on_transition(monkeypatch, emit_spy):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)  # created with visibility 'team'
        await c.patch(f"/api/v1/workos/workspaces/{ws['id']}", json={'name': 'Renamed'})
        assert 'workos.workspace.visibility_change' not in _emitted(emit_spy)

        r = await c.patch(f"/api/v1/workos/workspaces/{ws['id']}", json={'visibility': 'restricted'})
        assert r.status_code == 200, r.text
        assert 'workos.workspace.visibility_change' in _emitted(emit_spy)
        call = emit_spy.await_args_list[-1]
        assert call.args[0] == U1.id
        assert call.args[2] == {'workspace_id': ws['id'], 'from': 'team', 'to': 'restricted'}

        # Same-value update is not a transition.
        emit_spy.reset_mock()
        r = await c.patch(f"/api/v1/workos/workspaces/{ws['id']}", json={'visibility': 'restricted'})
        assert r.status_code == 200, r.text
        assert 'workos.workspace.visibility_change' not in _emitted(emit_spy)


@pytest.mark.asyncio
async def test_membership_changes_emit(monkeypatch, emit_spy):
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'T', 'key': 'T'})).json()
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        assert 'workos.team.member_add' in _emitted(emit_spy)
        call = emit_spy.await_args_list[-1]
        assert call.args[0] == U1.id
        assert call.args[2]['member_id'] == 'u2'
        await c.delete(f"/api/v1/workos/teams/{team['id']}/members/u2")
        assert 'workos.team.member_remove' in _emitted(emit_spy)
        call = emit_spy.await_args_list[-1]
        assert call.args[0] == U1.id
        assert call.args[2]['member_id'] == 'u2'
