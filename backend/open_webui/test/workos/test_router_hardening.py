import pytest

from open_webui.test.workos.test_router_teams import _client, U1


@pytest.mark.asyncio
async def test_workspace_defaults_to_configured_visibility(monkeypatch):
    rules = {'team_creation': 'all_users', 'default_workspace_visibility': 'restricted'}
    async with _client(monkeypatch, user=U1, rules=rules) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces", json={'name': 'Eng'})).json()
        assert ws['visibility'] == 'restricted'


@pytest.mark.asyncio
async def test_explicit_visibility_overrides_default(monkeypatch):
    rules = {'team_creation': 'all_users', 'default_workspace_visibility': 'restricted'}
    async with _client(monkeypatch, user=U1, rules=rules) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                           json={'name': 'Eng', 'visibility': 'team'})).json()
        assert ws['visibility'] == 'team'


@pytest.mark.asyncio
async def test_cannot_remove_last_owner(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        r = await c.delete(f"/api/v1/workos/teams/{team['id']}/members/u1")
        assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_can_remove_owner_when_another_owner_exists(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'owner'})
        r = await c.delete(f"/api/v1/workos/teams/{team['id']}/members/u1")
        assert r.json()['removed'] is True


@pytest.mark.asyncio
async def test_cannot_demote_last_owner(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        r = await c.patch(f"/api/v1/workos/teams/{team['id']}/members/u1", json={'role': 'admin'})
        assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_notifications_limit_is_clamped(monkeypatch):
    from open_webui.models.workos import Notifications
    captured = {}

    async def _fake_list(user_id, *, unread_only=False, limit=50, before=None, db=None):
        captured['limit'] = limit
        return []

    monkeypatch.setattr(Notifications, 'list_for_user', _fake_list)
    async with _client(monkeypatch, user=U1) as c:
        await c.get('/api/v1/workos/notifications?limit=99999')
    assert captured['limit'] == 200
