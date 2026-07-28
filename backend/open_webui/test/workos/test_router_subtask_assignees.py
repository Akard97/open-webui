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


@pytest.mark.asyncio
async def test_patch_auto_adds_and_notifies_only_new_ids(monkeypatch):
    sent = _capture(monkeypatch, {'subtask_assigned', 'assigned'})
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c, assignee_ids=['u1', 'u2'])
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                           json={'title': 'A', 'assignee_ids': ['u2']})).json()
        sent.clear()
        r = await c.patch(f"/api/v1/workos/subtasks/{st['id']}",
                          json={'assignee_ids': ['u2', 'u3']})
        assert r.status_code == 200, r.text
        assert r.json()['assignee_ids'] == ['u2', 'u3']
    parent = None
    async with _client(monkeypatch, user=U1) as c:
        parent = (await c.get(f"/api/v1/workos/tasks/{t['id']}")).json()
    assert parent['assignee_ids'] == ['u1', 'u2', 'u3']
    # only the NEW subtask assignee is notified, and only subtask_assigned
    assert [x[0] for x in sent] == ['subtask_assigned']
    assert sent[0][1] == ('u3',)


@pytest.mark.asyncio
async def test_patch_clear_to_empty_allowed(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks", json={'title': 'A'})).json()
        assert st['assignee_ids'] == ['u1']
        r = await c.patch(f"/api/v1/workos/subtasks/{st['id']}", json={'assignee_ids': []})
        assert r.status_code == 200, r.text
        assert r.json()['assignee_ids'] == []


@pytest.mark.asyncio
async def test_patch_unrelated_edit_does_not_renotify(monkeypatch):
    sent = _capture(monkeypatch, {'subtask_assigned'})
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c, assignee_ids=['u1', 'u2'])
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                           json={'title': 'A', 'assignee_ids': ['u2']})).json()
        sent.clear()
        await c.patch(f"/api/v1/workos/subtasks/{st['id']}", json={'completed': True})
        # resending the same assignee list is also not a new assignment
        await c.patch(f"/api/v1/workos/subtasks/{st['id']}", json={'assignee_ids': ['u2']})
    assert sent == []


@pytest.mark.asyncio
async def test_subtask_creator_without_task_write_cannot_expand_parent(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s, t = await _task(c)  # u2 is a plain member, task-visible
    async with _client(monkeypatch, user=U2) as c:
        # u2 creates a subtask (open posture) without touching assignees
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks", json={'title': 'mine'})).json()
        # u2 IS the subtask creator -> passes subtask.write, but self-assign
        # would expand the parent -> 403
        r = await c.patch(f"/api/v1/workos/subtasks/{st['id']}", json={'assignee_ids': ['u2']})
        assert r.status_code == 403, r.text
        assert 'Only task editors' in r.text


@pytest.mark.asyncio
async def test_parent_removal_cascades_to_subtasks(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c, assignee_ids=['u1', 'u2', 'u3'])
        a = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                          json={'title': 'A', 'assignee_ids': ['u2', 'u3']})).json()
        b = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                          json={'title': 'B', 'assignee_ids': ['u1']})).json()
        # drop u2 from the parent
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_ids': ['u1', 'u3']})
        assert r.status_code == 200, r.text
        listed = {s['title']: s['assignee_ids'] for s in
                  (await c.get(f"/api/v1/workos/tasks/{t['id']}/subtasks")).json()}
        assert listed['A'] == ['u3']   # u2 stripped
        assert listed['B'] == ['u1']   # untouched


@pytest.mark.asyncio
async def test_cascade_can_empty_a_subtask(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c, assignee_ids=['u1', 'u2'])
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                           json={'title': 'A', 'assignee_ids': ['u2']})).json()
        await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_ids': ['u1']})
        listed = (await c.get(f"/api/v1/workos/tasks/{t['id']}/subtasks")).json()
        assert listed[0]['assignee_ids'] == []


@pytest.mark.asyncio
async def test_create_rejects_non_string_assignee_ids(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                         json={'title': 'A', 'assignee_ids': [{}]})
        assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_patch_rejects_non_string_assignee_ids(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks", json={'title': 'A'})).json()
        r = await c.patch(f"/api/v1/workos/subtasks/{st['id']}", json={'assignee_ids': [{}]})
        assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_patch_invisible_assignee_rejected(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks", json={'title': 'A'})).json()
        r = await c.patch(f"/api/v1/workos/subtasks/{st['id']}", json={'assignee_ids': ['u9']})
        assert r.status_code == 400
        assert 'cannot access this workstream' in r.text


@pytest.mark.asyncio
async def test_expand_gate_non_403_not_remapped(monkeypatch):
    """A non-403 from require_task_writable (e.g. a future 401) must propagate,
    not be masked as 'Only task editors...'."""
    from fastapi import HTTPException

    async def _boom(user, task, stream, db):
        raise HTTPException(status_code=401, detail='session expired')

    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        monkeypatch.setattr(wr, 'require_task_writable', _boom)
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                         json={'title': 'A', 'assignee_ids': ['u3']})
        assert r.status_code == 401, r.text
        assert 'session expired' in r.text


@pytest.mark.asyncio
async def test_expand_emits_single_task_updated(monkeypatch):
    """Auto-add used to emit task.updated inside the helper AND again via
    _emit_parent_after_subtask — exactly one emit should survive."""
    events = []
    real_emit = wr.emit_event

    async def _ee(event, room, payload):
        if event == 'workos:task.updated':
            events.append(payload['id'])
        return await real_emit(event, room, payload)

    monkeypatch.setattr(wr, 'emit_event', _ee)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)  # parent assignees ['u1']
        events.clear()
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                         json={'title': 'A', 'assignee_ids': ['u3']})
        assert r.status_code == 200, r.text
    assert events == [t['id']]


@pytest.mark.asyncio
async def test_cascade_emits_subtask_updated_events(monkeypatch):
    events = []
    real_emit = wr.emit_event

    async def _ee(event, room, payload):
        if event == 'workos:subtask.updated':
            events.append(payload['id'])
        return await real_emit(event, room, payload)

    monkeypatch.setattr(wr, 'emit_event', _ee)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c, assignee_ids=['u1', 'u2'])
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                           json={'title': 'A', 'assignee_ids': ['u2']})).json()
        events.clear()
        await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_ids': ['u1']})
    assert events == [st['id']]


# ───────────────────── race / atomicity hardening (adversarial review) ─────────────────────


@pytest.mark.asyncio
async def test_auto_add_does_not_restore_concurrently_removed_assignee(monkeypatch):
    """A parent-assignee removal that commits inside the auto-add window must
    stay removed: the union is computed from the fresh row, never from the
    snapshot loaded at the top of the request."""
    real_gate = wr.require_task_writable

    async def _gate_then_remove(user, task, stream, db):
        await real_gate(user, task, stream, db)
        # Concurrent admin edit lands inside the window: drop u2 from the parent.
        await wr.Tasks.update_fields(task.id, {'assignee_ids': ['u1']}, db=db)

    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c, assignee_ids=['u1', 'u2'])
        monkeypatch.setattr(wr, 'require_task_writable', _gate_then_remove)
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                         json={'title': 'A', 'assignee_ids': ['u3']})
        assert r.status_code == 200, r.text
        monkeypatch.setattr(wr, 'require_task_writable', real_gate)
        parent = (await c.get(f"/api/v1/workos/tasks/{t['id']}")).json()
        assert parent['assignee_ids'] == ['u1', 'u3']  # u2 must NOT be restored


@pytest.mark.asyncio
async def test_cascade_failure_rolls_back_parent_removal(monkeypatch):
    """Parent-assignee removal and the subtask strip commit atomically: if the
    cascade blows up mid-flight the parent update rolls back with it, so the
    subset invariant can never half-commit."""

    async def _boom(self, db, task_id, removed):
        raise RuntimeError('injected cascade failure')

    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c, assignee_ids=['u1', 'u2'])
        await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                     json={'title': 'A', 'assignee_ids': ['u2']})
        orig = type(wr.Tasks)._cascade_subtask_assignees
        monkeypatch.setattr(type(wr.Tasks), '_cascade_subtask_assignees', _boom)
        with pytest.raises(RuntimeError, match='injected cascade failure'):
            await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_ids': ['u1']})
        monkeypatch.setattr(type(wr.Tasks), '_cascade_subtask_assignees', orig)
        parent = (await c.get(f"/api/v1/workos/tasks/{t['id']}")).json()
        assert parent['assignee_ids'] == ['u1', 'u2']  # parent removal rolled back
        listed = (await c.get(f"/api/v1/workos/tasks/{t['id']}/subtasks")).json()
        assert listed[0]['assignee_ids'] == ['u2']  # subtask untouched


@pytest.mark.asyncio
async def test_stale_subtask_write_cannot_exceed_parent_assignees(monkeypatch):
    """Subtask assignee writes intersect against the parent read in the same
    transaction — a stale full-list write racing the removal cascade can never
    resurrect a removed assignee on a subtask."""
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c, assignee_ids=['u1', 'u2'])
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                           json={'title': 'A', 'assignee_ids': ['u2']})).json()
        await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_ids': ['u1']})
        # Stale writer that raced past the endpoint checks replays the old list.
        updated = await wr.Subtasks.update_fields(st['id'], {'assignee_ids': ['u2']})
        assert updated.assignee_ids == []  # intersected against fresh parent ['u1']


@pytest.mark.asyncio
async def test_stale_subtask_insert_cannot_exceed_parent_assignees(monkeypatch):
    """Same subset enforcement at insert time: a create landing after a
    concurrent parent removal must not carry the removed assignee."""
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c, assignee_ids=['u1', 'u2'])
        await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_ids': ['u1']})
        inserted = await wr.Subtasks.insert(t['id'], 'stale', 'u1', assignee_ids=['u2'])
        assert inserted.assignee_ids == []


@pytest.mark.asyncio
async def test_assignee_writers_serialize_on_the_task_lock(monkeypatch):
    """SQLite (the default backend) has no row locks — with_for_update() is a
    no-op there — so every assignee-invariant writer must queue on the
    process-local task lock: while it is held, merge, cascade and subtask
    writes all block; on release they land strictly in order."""
    import asyncio
    from open_webui.models import workos as wm

    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c, assignee_ids=['u1', 'u2'])
        st = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                           json={'title': 'A', 'assignee_ids': ['u2']})).json()

    lock = wm._task_write_lock(t['id'])
    async with lock:
        writers = [
            asyncio.create_task(wm.Tasks.merge_assignees(t['id'], ['u3'])),
            asyncio.create_task(wm.Tasks.update_with_cascade(t['id'], {'assignee_ids': ['u1', 'u3']})),
            asyncio.create_task(wm.Subtasks.update_fields(st['id'], {'assignee_ids': ['u1']})),
        ]
        await asyncio.sleep(0.1)
        assert not any(w.done() for w in writers)  # all queued behind the held lock
    for w in writers:
        await w
    task = await wm.Tasks.get_by_id(t['id'])
    subs = await wm.Subtasks.list_for_task(t['id'])
    # FIFO wakeup: merge -> [u1,u2,u3]; cascade -> [u1,u3], stripping u2 from
    # the subtask; the subtask write then intersects [u1] against the fresh parent.
    assert task.assignee_ids == ['u1', 'u3']
    assert subs[0].assignee_ids == ['u1']


@pytest.mark.asyncio
async def test_cascade_emits_only_for_touched_subtasks(monkeypatch):
    """Two subtasks, one loses an assignee — exactly one subtask.updated fires."""
    events = []
    real_emit = wr.emit_event

    async def _ee(event, room, payload):
        if event == 'workos:subtask.updated':
            events.append(payload['id'])
        return await real_emit(event, room, payload)

    monkeypatch.setattr(wr, 'emit_event', _ee)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c, assignee_ids=['u1', 'u2', 'u3'])
        a = (await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                          json={'title': 'A', 'assignee_ids': ['u2', 'u3']})).json()
        await c.post(f"/api/v1/workos/tasks/{t['id']}/subtasks",
                     json={'title': 'B', 'assignee_ids': ['u1']})
        events.clear()
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'assignee_ids': ['u1', 'u3']})
        assert r.status_code == 200, r.text
    assert events == [a['id']]  # B untouched -> no event for it
