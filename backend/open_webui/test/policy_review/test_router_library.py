import pytest
from types import SimpleNamespace

import httpx
from httpx import ASGITransport
from fastapi import FastAPI

import open_webui.routers.policy_review as pr_router
from open_webui.utils.auth import get_verified_user
from open_webui.models.policy_review import PolicyLibrary


def _client(user):
    app = FastAPI()
    app.state.config = SimpleNamespace(USER_PERMISSIONS={})
    app.include_router(pr_router.router, prefix='/api/v1/policy')
    app.dependency_overrides[get_verified_user] = lambda: user
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url='http://test')


@pytest.mark.asyncio
async def test_library_open_to_any_verified_user():
    await PolicyLibrary.upsert(code='C-1', data={'code': 'C-1', 'title': 'First'}, source_review_id=None)
    user = SimpleNamespace(id='u', role='user', name='Any', email='a@x.io')
    async with _client(user) as c:
        lst = await c.get('/api/v1/policy/library')
        assert lst.status_code == 200
        assert len(lst.json()) == 1
        one = await c.get('/api/v1/policy/library/C-1')
        assert one.status_code == 200
        assert one.json()['data']['title'] == 'First'
        missing = await c.get('/api/v1/policy/library/NOPE')
        assert missing.status_code == 404
