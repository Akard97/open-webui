import pytest

from open_webui.test.workos.test_router_teams import _client, U1, U2


async def _stream(c, *, visibility='team', name='Eng'):
    team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
    ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                       json={'name': name, 'visibility': visibility})).json()
    s = (await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'Platform'})).json()
    return team, ws, s


@pytest.mark.asyncio
async def test_me_tasks_returns_created_and_assigned(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        # U1 adds U2 to the team so U2 is a valid (visible) assignee.
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        created = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                                json={'title': 'Mine', 'assignee_ids': ['u1']})).json()
        assigned = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                                 json={'title': 'For u2', 'assignee_ids': ['u2']})).json()
        # U1 created both -> both appear for U1.
        ids = {t['id'] for t in (await c.get('/api/v1/workos/me/tasks')).json()}
        assert created['id'] in ids and assigned['id'] in ids
    async with _client(monkeypatch, user=U2) as c:
        u2_ids = {t['id'] for t in (await c.get('/api/v1/workos/me/tasks')).json()}
        # U2 sees only the task assigned to U2, not U1's solo task.
        assert assigned['id'] in u2_ids
        assert created['id'] not in u2_ids


@pytest.mark.asyncio
async def test_me_tasks_excludes_restricted_after_membership_revoked(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        rws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                            json={'name': 'Secret', 'visibility': 'restricted'})).json()
        await c.post(f"/api/v1/workos/workspaces/{rws['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        s = (await c.post(f"/api/v1/workos/workspaces/{rws['id']}/workstreams", json={'name': 'S'})).json()
    async with _client(monkeypatch, user=U2) as c:
        task = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                             json={'title': 'U2 secret', 'assignee_ids': ['u2']})).json()
        assert task['id'] in {t['id'] for t in (await c.get('/api/v1/workos/me/tasks')).json()}
    # U1 revokes U2's access to the restricted workspace.
    async with _client(monkeypatch, user=U1) as c:
        assert (await c.delete(f"/api/v1/workos/workspaces/{rws['id']}/members/u2")).status_code == 200
    async with _client(monkeypatch, user=U2) as c:
        # U2 created the task but can no longer see the workstream -> excluded.
        assert task['id'] not in {t['id'] for t in (await c.get('/api/v1/workos/me/tasks')).json()}
