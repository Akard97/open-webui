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
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'Migrate billing'})
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
        t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'X'})).json()
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
async def test_non_member_cannot_create_task(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
    async with _client(monkeypatch, user=U2) as c:
        r = await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'X'})
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_task_schedule_fields_and_validation(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        r = await c.post(
            f"/api/v1/workos/workstreams/{s['id']}/tasks",
            json={'title': 'Scheduled', 'start_date': 1000, 'due_date': 2000},
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
        task = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'Parent'})).json()

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
