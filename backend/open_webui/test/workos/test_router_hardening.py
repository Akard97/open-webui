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
