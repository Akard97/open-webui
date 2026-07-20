import pytest
from types import SimpleNamespace

import httpx
from httpx import ASGITransport
from fastapi import FastAPI

import open_webui.routers.workos as wr
import open_webui.utils.workos_access as wa
from open_webui.utils.auth import get_verified_user
from open_webui.test.workos.test_router_teams import U1, U2, ADMIN

import open_webui.routers.workos_internal as wi

SECRET = 'test-service-secret'
HDRS = {'X-Service-Token': SECRET}

_USERS = {u.id: u for u in (U1, U2, ADMIN)}


def _make_app(user):
    app = FastAPI()
    app.state.config = SimpleNamespace(
        USER_PERMISSIONS={},
        WORKOS_RULES={'team_creation': 'all_users', 'default_workspace_visibility': 'team'},
    )
    app.include_router(wr.router, prefix='/api/v1/workos')
    app.include_router(wi.router, prefix='/api/v1/workos/internal')
    app.dependency_overrides[get_verified_user] = lambda: user
    return app


def _client(monkeypatch, *, user=U1, allow=True, secret=SECRET):
    """Client with both routers mounted. `user` drives the PUBLIC routes
    (setup); internal routes name their acting user in the path. `allow`
    stubs has_permission for everyone; `secret` is the service secret in env
    (empty string = unset)."""
    async def _hp(user_id, key, permissions, db=None):
        return allow
    monkeypatch.setattr(wa, 'has_permission', _hp)
    if secret:
        monkeypatch.setenv('WORKOS_SERVICE_SECRET', secret)
    else:
        monkeypatch.delenv('WORKOS_SERVICE_SECRET', raising=False)

    async def _stub_load(uid):
        return _USERS.get(uid)
    monkeypatch.setattr(wi, '_load_user', _stub_load)

    async def _stub_names(ids):
        return [{'id': i, 'name': _USERS[i].name} for i in ids if i in _USERS]
    monkeypatch.setattr(wi, 'resolve_user_names', _stub_names)
    return httpx.AsyncClient(transport=ASGITransport(app=_make_app(user)), base_url='http://test')


async def _seed(c, *, visibility='team'):
    """U1 creates team -> workspace -> workstream via the public API."""
    team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
    ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                       json={'name': 'Eng', 'visibility': visibility})).json()
    s = (await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'Platform'})).json()
    return team, ws, s


# ──────────────────────────── service-token gate ────────────────────────────


@pytest.mark.asyncio
async def test_missing_token_rejected(monkeypatch):
    async with _client(monkeypatch) as c:
        r = await c.get('/api/v1/workos/internal/users/u1/bootstrap')
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_wrong_token_rejected(monkeypatch):
    async with _client(monkeypatch) as c:
        r = await c.get('/api/v1/workos/internal/users/u1/bootstrap',
                        headers={'X-Service-Token': 'nope'})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_unset_secret_fails_closed(monkeypatch):
    # Even if the router were mounted with no secret configured, every
    # request must be rejected — including one presenting an empty token.
    async with _client(monkeypatch, secret='') as c:
        r = await c.get('/api/v1/workos/internal/users/u1/bootstrap',
                        headers={'X-Service-Token': ''})
        assert r.status_code == 401


# ──────────────────────────── acting user ────────────────────────────


@pytest.mark.asyncio
async def test_unknown_user_404(monkeypatch):
    async with _client(monkeypatch) as c:
        r = await c.get('/api/v1/workos/internal/users/ghost/bootstrap', headers=HDRS)
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_feature_gate_parity(monkeypatch):
    # A user without features.workos gets 401 via the internal API too.
    async with _client(monkeypatch, allow=False) as c:
        r = await c.get('/api/v1/workos/internal/users/u1/bootstrap', headers=HDRS)
        assert r.status_code == 401


# ──────────────────────────── bootstrap ────────────────────────────


@pytest.mark.asyncio
async def test_bootstrap_returns_visible_tree(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _seed(c)
        body = (await c.get('/api/v1/workos/internal/users/u1/bootstrap', headers=HDRS)).json()
        assert [t['id'] for t in body['teams']] == [team['id']]
        assert [w['id'] for w in body['workspaces']] == [ws['id']]
        assert [x['id'] for x in body['workstreams']] == [s['id']]
        # Non-member sees an empty tree through the same endpoint.
        body2 = (await c.get('/api/v1/workos/internal/users/u2/bootstrap', headers=HDRS)).json()
        assert body2 == {'teams': [], 'workspaces': [], 'workstreams': []}


# ──────────────────────────── my tasks ────────────────────────────


@pytest.mark.asyncio
async def test_my_tasks_scoped_per_user(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _seed(c)
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        mine = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                             json={'title': 'Mine', 'assignee_ids': ['u1']})).json()
        theirs = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                               json={'title': 'For u2', 'assignee_ids': ['u2']})).json()
        u1_body = (await c.get('/api/v1/workos/internal/users/u1/tasks', headers=HDRS)).json()
        u2_body = (await c.get('/api/v1/workos/internal/users/u2/tasks', headers=HDRS)).json()
        u1_ids = {t['id'] for t in u1_body['tasks']}
        u2_ids = {t['id'] for t in u2_body['tasks']}
        assert mine['id'] in u1_ids and theirs['id'] in u1_ids  # U1 created both
        assert u2_ids == {theirs['id']}
        assert u2_body['users'].get('u2') == 'Yusuf'  # names resolved


@pytest.mark.asyncio
async def test_my_tasks_parity_with_public_endpoint(monkeypatch):
    # The internal endpoint must return exactly what GET /me/tasks returns.
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _seed(c)
        await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                     json={'title': 'T1', 'assignee_ids': ['u1']})
        public_ids = {t['id'] for t in (await c.get('/api/v1/workos/me/tasks')).json()}
        internal = (await c.get('/api/v1/workos/internal/users/u1/tasks', headers=HDRS)).json()
        assert {t['id'] for t in internal['tasks']} == public_ids


@pytest.mark.asyncio
async def test_my_tasks_excludes_restricted_after_revoke(monkeypatch):
    # Mirror of the /me/tasks leak test, through the internal API.
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
        body = (await c.get('/api/v1/workos/internal/users/u2/tasks', headers=HDRS)).json()
        assert task['id'] in {t['id'] for t in body['tasks']}
    async with _client(monkeypatch, user=U1) as c:
        assert (await c.delete(f"/api/v1/workos/workspaces/{rws['id']}/members/u2")).status_code == 200
        body = (await c.get('/api/v1/workos/internal/users/u2/tasks', headers=HDRS)).json()
        assert task['id'] not in {t['id'] for t in body['tasks']}


# ──────────────────────────── workstream tasks ────────────────────────────


@pytest.mark.asyncio
async def test_workstream_tasks_visible(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _seed(c)
        t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                          json={'title': 'T', 'assignee_ids': ['u1']})).json()
        body = (await c.get(f"/api/v1/workos/internal/users/u1/workstreams/{s['id']}/tasks",
                            headers=HDRS)).json()
        assert [x['id'] for x in body['tasks']] == [t['id']]


@pytest.mark.asyncio
async def test_workstream_tasks_invisible_404(monkeypatch):
    # u2 is not a team member -> the workstream must look nonexistent.
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _seed(c)
        r = await c.get(f"/api/v1/workos/internal/users/u2/workstreams/{s['id']}/tasks",
                        headers=HDRS)
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_workstream_tasks_parity_with_public_endpoint(monkeypatch):
    # bootstrap and my-tasks share helpers with their public counterparts, so
    # parity there is structural. This endpoint re-states the two-line public
    # sequence (require_workstream_visible + list_for_workstream) instead of
    # sharing it - pin the parity explicitly.
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _seed(c)
        await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                     json={'title': 'T1', 'assignee_ids': ['u1']})
        await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                     json={'title': 'T2', 'assignee_ids': ['u1']})
        public_ids = {t['id'] for t in
                      (await c.get(f"/api/v1/workos/workstreams/{s['id']}/tasks")).json()}
        internal = (await c.get(f"/api/v1/workos/internal/users/u1/workstreams/{s['id']}/tasks",
                                headers=HDRS)).json()
        assert public_ids and {t['id'] for t in internal['tasks']} == public_ids


@pytest.mark.asyncio
async def test_admin_bypass_parity(monkeypatch):
    # App-admin bypass: ADMIN is a member of nothing, yet sees the whole
    # tree and any workstream's tasks - same as in the UI.
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _seed(c)
        t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                          json={'title': 'T', 'assignee_ids': ['u1']})).json()
        body = (await c.get('/api/v1/workos/internal/users/admin1/bootstrap',
                            headers=HDRS)).json()
        assert [x['id'] for x in body['teams']] == [team['id']]
        assert [x['id'] for x in body['workstreams']] == [s['id']]
        r = await c.get(f"/api/v1/workos/internal/users/admin1/workstreams/{s['id']}/tasks",
                        headers=HDRS)
        assert [x['id'] for x in r.json()['tasks']] == [t['id']]
