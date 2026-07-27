import pytest

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_teams import _client, U1, U2
from open_webui.test.workos.test_router_task import _stream


async def _task(c, **body):
    """Team with members u1(owner)/u2/u3, one workstream, one task created by u1."""
    team, ws, s = await _stream(c)
    for uid in ('u2', 'u3'):
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': uid, 'role': 'member'})
    t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                      json={'title': 'T', 'assignee_ids': ['u1'], **body})).json()
    return team, ws, s, t


def _capture(monkeypatch, types):
    """Collect (type, user_ids) pairs emitted via notify()'s emit_users call."""
    sent = []

    async def _eu(event, payload, user_ids):
        if payload.get('type') in types:
            sent.append((payload['type'], tuple(sorted(user_ids)), payload.get('data', {})))

    monkeypatch.setattr(wr, 'emit_users', _eu)
    return sent


@pytest.mark.asyncio
async def test_create_defaults_to_parents_first_assignee(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c, assignee_ids=['u2', 'u3'])
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks", json={'title': 'A'})).json()
        assert st['assignee_ids'] == ['u2']


@pytest.mark.asyncio
async def test_create_empty_list_also_defaults(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                           json={'title': 'A', 'assignee_ids': []})).json()
        assert st['assignee_ids'] == ['u1']


@pytest.mark.asyncio
async def test_create_explicit_within_parent_kept_and_deduped(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c, assignee_ids=['u1', 'u2'])
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                           json={'title': 'A', 'assignee_ids': ['u2', 'u2']})).json()
        assert st['assignee_ids'] == ['u2']
        parent = (await c.get(f"/api/v1/workos/tasks/{t['id']}")).json()
        assert parent['assignee_ids'] == ['u1', 'u2']  # unchanged


@pytest.mark.asyncio
async def test_create_auto_adds_missing_assignee_to_parent_end(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)  # parent assignees ['u1']
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                           json={'title': 'A', 'assignee_ids': ['u3']})).json()
        assert st['assignee_ids'] == ['u3']
        parent = (await c.get(f"/api/v1/workos/tasks/{t['id']}")).json()
        assert parent['assignee_ids'] == ['u1', 'u3']  # appended at end, first stays first
        acts = (await c.get(f"/api/v1/workos/tasks/{t['id']}/activity")).json()
        changed = [a for a in acts if a['type'] == 'assignee_changed']
        assert changed and changed[0]['data'].get('added') == ['u3']


@pytest.mark.asyncio
async def test_create_notifies_subtask_assigned_not_parent_assigned(monkeypatch):
    sent = _capture(monkeypatch, {'subtask_assigned', 'assigned'})
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                     json={'title': 'Wire it', 'assignee_ids': ['u2']})
    types = [x[0] for x in sent]
    assert types == ['subtask_assigned']
    assert sent[0][1] == ('u2',)
    assert sent[0][2].get('subtask_title') == 'Wire it'


@pytest.mark.asyncio
async def test_default_assignee_is_actor_no_notification(monkeypatch):
    sent = _capture(monkeypatch, {'subtask_assigned'})
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)  # parent first assignee == u1 == actor
        await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks", json={'title': 'A'})
    assert sent == []


@pytest.mark.asyncio
async def test_non_task_writer_cannot_auto_add_on_create(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s, t = await _task(c)  # creator u1, assignees ['u1']; u2 plain member
    async with _client(monkeypatch, user=U2) as c:
        # u2 is task-visible so may create a subtask, but expanding the parent
        # list requires task.write -> 403 (blocks self-assign escalation).
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                         json={'title': 'sneak', 'assignee_ids': ['u2']})
        assert r.status_code == 403, r.text
        assert 'Only task editors' in r.text
        # within the parent's existing list: allowed
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                         json={'title': 'ok', 'assignee_ids': ['u1']})
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_create_invisible_assignee_rejected(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                         json={'title': 'A', 'assignee_ids': ['u9']})
        assert r.status_code == 400
        assert 'cannot access this workstream' in r.text


@pytest.mark.asyncio
async def test_subtask_assigned_respects_assigned_rules_toggle(monkeypatch):
    sent = _capture(monkeypatch, {'subtask_assigned'})
    rules = {'team_creation': 'all_users', 'default_workspace_visibility': 'team',
             'notifications': {'assigned': False}}
    async with _client(monkeypatch, user=U1, rules=rules) as c:
        _, _, _, t = await _task(c)
        await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                     json={'title': 'A', 'assignee_ids': ['u2']})
    assert sent == []
