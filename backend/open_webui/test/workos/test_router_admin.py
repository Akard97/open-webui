import pytest
from types import SimpleNamespace

from open_webui.test.workos.test_router_teams import _client, U1

ADMIN = SimpleNamespace(id='admin1', name='Admin', role='admin')


@pytest.mark.asyncio
async def test_admin_lists_all_teams_with_counts(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
    async with _client(monkeypatch, user=ADMIN) as c:
        r = await c.get('/api/v1/workos/admin/teams')
        assert r.status_code == 200
        rows = r.json()
        row = next(x for x in rows if x['team']['id'] == team['id'])
        assert row['member_count'] == 1
        assert 'u1' in row['owner_ids']


@pytest.mark.asyncio
async def test_settings_get_and_patch(monkeypatch):
    async with _client(monkeypatch, user=ADMIN) as c:
        r = await c.get('/api/v1/workos/admin/settings')
        assert r.json()['team_creation'] in ('all_users', 'admins_only')
        r = await c.patch('/api/v1/workos/admin/settings', json={'team_creation': 'admins_only'})
        assert r.json()['team_creation'] == 'admins_only'


@pytest.mark.asyncio
async def test_settings_patch_forbidden_for_non_admin(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        r = await c.patch('/api/v1/workos/admin/settings', json={'team_creation': 'admins_only'})
        assert r.status_code == 403
