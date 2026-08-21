import pytest

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_teams import _client, U1


@pytest.mark.parametrize(
    'raw,expected',
    [
        ('data:image/png;base64,AAAA', 'data:image/png;base64,AAAA'),
        ('https://example.com/pic.jpg', 'https://example.com/pic.jpg'),
        ('http://example.com/pic.jpg', 'http://example.com/pic.jpg'),
        ('/user.png', None),
        ('/api/v1/users/u1/profile/image', None),
        ('', None),
        (None, None),
    ],
)
def test_sanitize_profile_image_url(raw, expected):
    # Only genuine custom images (data URLs, OAuth http urls) pass through;
    # the '/user.png' and per-user endpoint defaults mean "no upload" → None,
    # so the UI keeps its initials fallback.
    assert wr.sanitize_profile_image_url(raw) == expected


@pytest.mark.parametrize(
    'raw,expected',
    [
        # External http(s) URLs are suppressed so viewer browsers never fetch
        # a third-party origin while forwarding is disabled (IP/UA/Referer
        # leak prevention — same policy as the profile-image endpoint).
        ('https://example.com/pic.jpg', None),
        ('http://example.com/pic.jpg', None),
        # Uploaded avatars are data: URLs served inline — no external fetch,
        # so they still pass through.
        ('data:image/png;base64,AAAA', 'data:image/png;base64,AAAA'),
        ('/user.png', None),
        (None, None),
    ],
)
def test_sanitize_profile_image_url_forwarding_disabled(monkeypatch, raw, expected):
    monkeypatch.setattr(wr, 'ENABLE_PROFILE_IMAGE_URL_FORWARDING', False)
    assert wr.sanitize_profile_image_url(raw) == expected


@pytest.mark.asyncio
async def test_resolve_user_names_includes_profile_image(monkeypatch):
    from types import SimpleNamespace

    from open_webui.models.users import Users

    stub = {
        'u1': SimpleNamespace(id='u1', name='Lara', profile_image_url='data:image/png;base64,AAAA'),
        'u2': SimpleNamespace(id='u2', name='Yusuf', profile_image_url='/user.png'),
    }

    async def _fake_get(uid):
        return stub.get(uid)

    monkeypatch.setattr(Users, 'get_user_by_id', staticmethod(_fake_get))
    rows = await wr.resolve_user_names(['u1', 'u2', 'missing'])
    assert rows == [
        {'id': 'u1', 'name': 'Lara', 'profile_image_url': 'data:image/png;base64,AAAA'},
        {'id': 'u2', 'name': 'Yusuf', 'profile_image_url': None},
    ]


@pytest.mark.asyncio
async def test_list_all_users_includes_profile_image(monkeypatch):
    from types import SimpleNamespace

    from open_webui.models.users import Users

    async def _fake_get_users():
        return {
            'users': [
                SimpleNamespace(id='u1', name='Lara', profile_image_url='https://cdn.example/a.jpg'),
                SimpleNamespace(id='u2', name='Yusuf', profile_image_url='/api/v1/users/u2/profile/image'),
            ]
        }

    monkeypatch.setattr(Users, 'get_users', staticmethod(_fake_get_users))
    rows = await wr.list_all_users()
    assert rows == [
        {'id': 'u1', 'name': 'Lara', 'profile_image_url': 'https://cdn.example/a.jpg'},
        {'id': 'u2', 'name': 'Yusuf', 'profile_image_url': None},
    ]


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


@pytest.mark.asyncio
async def test_users_roster_returned_to_team_owner(monkeypatch):
    async def _fake_all_users():
        return [{'id': 'u1', 'name': 'Lara'}, {'id': 'u2', 'name': 'Yusuf'}, {'id': 'u3', 'name': 'Mona'}]

    monkeypatch.setattr(wr, 'list_all_users', _fake_all_users)
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        r = await c.get(f"/api/v1/workos/users?team_id={team['id']}")
        assert r.status_code == 200, r.text
        assert {row['id'] for row in r.json()} == {'u1', 'u2', 'u3'}


@pytest.mark.asyncio
async def test_users_denied_to_plain_member(monkeypatch):
    from open_webui.test.workos.test_router_teams import U2

    async def _fake_all_users():
        return []

    monkeypatch.setattr(wr, 'list_all_users', _fake_all_users)
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    async with _client(monkeypatch, user=U2) as c:
        r = await c.get(f"/api/v1/workos/users?team_id={team['id']}")
        assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_users_requires_team_id(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        r = await c.get('/api/v1/workos/users')
        assert r.status_code == 422  # missing required query param


@pytest.mark.asyncio
async def test_users_requires_workos_access(monkeypatch):
    async def _fake_all_users():
        return []

    monkeypatch.setattr(wr, 'list_all_users', _fake_all_users)
    # team_id present so the handler body runs; the feature gate then rejects.
    async with _client(monkeypatch, user=U1, allow=False) as c:
        r = await c.get('/api/v1/workos/users?team_id=anything')
        assert r.status_code == 401
