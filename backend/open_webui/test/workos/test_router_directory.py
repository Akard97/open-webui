import pytest

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_teams import _client, U1


@pytest.mark.asyncio
async def test_directory_returns_team_member_names(monkeypatch):
    async def _fake_names(ids):
        return [{'id': i, 'name': f'User {i}'} for i in ids]

    monkeypatch.setattr(wr, 'resolve_user_names', _fake_names)
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        r = await c.get('/api/v1/workos/directory')
        assert r.status_code == 200
        ids = {row['id'] for row in r.json()}
        assert {'u1', 'u2'} <= ids
