import pytest

from open_webui.test.workos.test_router_teams import _client, U1, U2


async def _stream(c):
    team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
    ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                       json={'name': 'Eng', 'visibility': 'team'})).json()
    s = (await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'Platform'})).json()
    return team, ws, s


@pytest.mark.asyncio
async def test_task_create_patch_delete(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                         json={'title': 'Migrate billing', 'assignee_ids': ['u1']})
        assert r.status_code == 200, r.text
        t = r.json()
        assert t['key'] == 'OSL-1' and t['status'] == 'backlog'
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}",
                          json={'status': 'in_progress', 'priority': 'high', 'sort_key': 5.0})
        assert r.json()['status'] == 'in_progress' and r.json()['priority'] == 'high'
        r = await c.get(f"/api/v1/workos/workstreams/{s['id']}/tasks")
        assert len(r.json()) == 1
        assert (await c.delete(f"/api/v1/workos/tasks/{t['id']}")).json()['deleted'] is True


@pytest.mark.asyncio
async def test_task_patch_rejects_bad_status(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                          json={'title': 'X', 'assignee_ids': ['u1']})).json()
        r = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'status': 'bogus'})
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_labels_crud(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        r = await c.post(f"/api/v1/workos/teams/{team['id']}/labels", json={'name': 'backend', 'color': 'cyan'})
        assert r.status_code == 200
        lab = r.json()
        assert [x['id'] for x in (await c.get(f"/api/v1/workos/teams/{team['id']}/labels")).json()] == [lab['id']]
        assert (await c.delete(f"/api/v1/workos/labels/{lab['id']}")).json()['deleted'] is True


@pytest.mark.asyncio
async def test_any_member_can_create_tag(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        assert (await c.post(f"/api/v1/workos/teams/{team['id']}/members",
                             json={'user_id': 'u2', 'role': 'member'})).status_code == 200
    # u2 is a plain member (not owner/admin) and may still create a tag.
    async with _client(monkeypatch, user=U2) as c:
        r = await c.post(f"/api/v1/workos/teams/{team['id']}/labels", json={'name': 'frontend', 'color': 'green'})
        assert r.status_code == 200, r.text
        assert r.json()['name'] == 'frontend'


@pytest.mark.asyncio
async def test_unused_tag_auto_deleted_on_unassign(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        lab = (await c.post(f"/api/v1/workos/teams/{team['id']}/labels",
                            json={'name': 'backend', 'color': 'cyan'})).json()
        a = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                          json={'title': 'A', 'labels': [lab['id']], 'assignee_ids': ['u1']})).json()
        b = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                          json={'title': 'B', 'labels': [lab['id']], 'assignee_ids': ['u1']})).json()

        # Removing the tag from A leaves it on B, so it survives.
        r = await c.patch(f"/api/v1/workos/tasks/{a['id']}", json={'labels': []})
        assert r.json()['deleted_label_ids'] == []
        assert [x['id'] for x in (await c.get(f"/api/v1/workos/teams/{team['id']}/labels")).json()] == [lab['id']]

        # Removing it from B orphans it -> auto-deleted and reported back.
        r = await c.patch(f"/api/v1/workos/tasks/{b['id']}", json={'labels': []})
        assert r.json()['deleted_label_ids'] == [lab['id']]
        assert (await c.get(f"/api/v1/workos/teams/{team['id']}/labels")).json() == []


@pytest.mark.asyncio
async def test_unused_tag_auto_deleted_on_task_delete(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        shared = (await c.post(f"/api/v1/workos/teams/{team['id']}/labels",
                               json={'name': 'shared', 'color': 'cyan'})).json()
        solo = (await c.post(f"/api/v1/workos/teams/{team['id']}/labels",
                             json={'name': 'solo', 'color': 'green'})).json()
        keep = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                             json={'title': 'Keep', 'labels': [shared['id']], 'assignee_ids': ['u1']})).json()
        gone = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                             json={'title': 'Gone', 'labels': [shared['id'], solo['id']], 'assignee_ids': ['u1']})).json()

        # Deleting 'Gone' orphans only 'solo'; 'shared' is still on 'Keep'.
        r = await c.delete(f"/api/v1/workos/tasks/{gone['id']}")
        assert r.json()['deleted'] is True
        assert r.json()['deleted_label_ids'] == [solo['id']]
        assert [x['id'] for x in (await c.get(f"/api/v1/workos/teams/{team['id']}/labels")).json()] == [shared['id']]


@pytest.mark.asyncio
async def test_non_member_cannot_create_task(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
    async with _client(monkeypatch, user=U2) as c:
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                         json={'title': 'X', 'assignee_ids': ['u2']})
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_task_schedule_fields_and_validation(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        r = await c.post(
            f"/api/v1/workos/workstreams/{s['id']}/tasks",
            json={'title': 'Scheduled', 'start_date': 1000, 'due_date': 2000, 'assignee_ids': ['u1']},
        )
        assert r.status_code == 200, r.text
        t = r.json()
        assert t['start_date'] == 1000
        assert t['due_date'] == 2000

        bad = await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'start_date': 3000, 'due_date': 2000})
        assert bad.status_code == 400
        assert 'Start date must be before due date' in bad.text


@pytest.mark.asyncio
async def test_subtask_crud_updates_parent_counts(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        task = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                             json={'title': 'Parent', 'assignee_ids': ['u1']})).json()

        created = (await c.post(f"/api/v1/workos/tasks/{task['id']}/subtasks", json={'title': 'Draft'})).json()
        assert created['title'] == 'Draft'
        assert created['completed'] is False

        listed = (await c.get(f"/api/v1/workos/tasks/{task['id']}/subtasks")).json()
        assert [s['id'] for s in listed] == [created['id']]

        updated = (await c.patch(f"/api/v1/workos/subtasks/{created['id']}", json={'completed': True})).json()
        assert updated['completed'] is True
        assert updated['completed_at'] is not None

        parent = (await c.get(f"/api/v1/workos/tasks/{task['id']}")).json()
        assert parent['subtask_total'] == 1
        assert parent['subtask_completed'] == 1

        deleted = (await c.delete(f"/api/v1/workos/subtasks/{created['id']}")).json()
        assert deleted['deleted'] is True
