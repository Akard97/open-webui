import pytest
import pytest_asyncio
from types import SimpleNamespace

import httpx
from httpx import ASGITransport
from fastapi import FastAPI

import open_webui.routers.policy_review as pr_router
from open_webui.routers.policy_review import get_verified_user
from open_webui.models.policy_review import PolicyChecklistVersions

ACTIVE_DATA = {'changeSummary': 'init', 'themes': [{'id': 'T1', 'name': 'T1', 'weight': 100, 'gate': True, 'threshold': 85}], 'sections': [{'id': 'S1', 'theme': 'T1', 'items': [{'id': 'S1-1'}]}], 'verdictBands': {'approved': 85, 'conditional': 70}, 'standards': []}


def _make_app(current_user):
    app = FastAPI()
    app.state.config = SimpleNamespace(USER_PERMISSIONS={})
    app.include_router(pr_router.router, prefix='/api/v1/policy')
    app.dependency_overrides[get_verified_user] = lambda: current_user
    return app


@pytest_asyncio.fixture
async def client_factory(monkeypatch):
    def factory(role='user', allow=True):
        monkeypatch.setattr(pr_router, 'has_permission', _AsyncReturn(allow))
        user = SimpleNamespace(id='u1', role=role, name='Tester', email='t@x.io')
        app = _make_app(user)
        return httpx.AsyncClient(transport=ASGITransport(app=app), base_url='http://test')

    return factory


class _AsyncReturn:
    def __init__(self, value):
        self.value = value

    async def __call__(self, *args, **kwargs):
        return self.value


@pytest.mark.asyncio
async def test_get_active_requires_seeded_version(client_factory):
    await PolicyChecklistVersions.insert_version('v2.0', 'active', ACTIVE_DATA, None, 'OE')
    async with client_factory(role='user', allow=True) as client:
        res = await client.get('/api/v1/policy/checklist/active')
    assert res.status_code == 200
    assert res.json()['label'] == 'v2.0'


@pytest.mark.asyncio
async def test_start_draft_requires_admin_permission(client_factory):
    await PolicyChecklistVersions.insert_version('v2.0', 'active', ACTIVE_DATA, None, 'OE')
    # Lacks policy_admin -> 401
    async with client_factory(role='user', allow=False) as client:
        res = await client.post('/api/v1/policy/checklist/draft')
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_admin_can_start_and_publish_draft(client_factory):
    await PolicyChecklistVersions.insert_version('v2.0', 'active', ACTIVE_DATA, None, 'OE')
    async with client_factory(role='admin', allow=False) as client:  # admin bypass
        start = await client.post('/api/v1/policy/checklist/draft')
        assert start.status_code == 200
        publish = await client.post('/api/v1/policy/checklist/draft/publish')
        assert publish.status_code == 200
        assert publish.json()['label'] == 'v2.1'
