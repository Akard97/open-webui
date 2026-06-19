import json
from types import SimpleNamespace

import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport
from fastapi import FastAPI

import open_webui.routers.policy_review as pr_router
from open_webui.utils.auth import get_verified_user
from open_webui.models.policy_review import PolicyChecklistVersions, PolicyDocuments, PolicyLibrary

ACTIVE_DATA = {
    'changeSummary': 'init',
    'themes': [{'id': 'T1', 'name': 'T1', 'weight': 100, 'gate': True, 'threshold': 85}],
    'sections': [{'id': 'S1', 'theme': 'T1', 'items': [{'id': 'S1-1', 'assessment': 'auto'}]}],
    'verdictBands': {'approved': 85, 'conditional': 70},
    'standards': [],
}
META = {'name': 'Test Policy', 'code': 'C-TEST', 'version': 'v1', 'owner': 'O',
        'reviewer': 'R', 'reviewDate': 'd', 'pages': 1, 'filename': ''}


def _make_app(user):
    app = FastAPI()
    app.state.config = SimpleNamespace(USER_PERMISSIONS={})
    app.include_router(pr_router.router, prefix='/api/v1/policy')
    app.dependency_overrides[get_verified_user] = lambda: user
    return app


def _client_keys(monkeypatch, *, user, keys=()):
    granted = set(keys)

    async def _hp(user_id, key, permissions, db=None):
        return key.split('.')[-1] in granted

    monkeypatch.setattr(pr_router, 'has_permission', _hp)
    return httpx.AsyncClient(transport=ASGITransport(app=_make_app(user)), base_url='http://test')


@pytest_asyncio.fixture(autouse=True)
async def _seed_active():
    await PolicyChecklistVersions.insert_version('v2.0', 'active', ACTIVE_DATA, None, 'OE')


class FakeStorage:
    """In-memory storage stand-in: store/read/delete bytes by a fake path."""
    def __init__(self):
        self.blobs = {}
        self._n = 0

    def store(self, contents, filename):
        self._n += 1
        path = f'fake://{self._n}-{filename}'
        self.blobs[path] = contents
        return path

    def read(self, path):
        return self.blobs[path]

    def delete(self, path):
        self.blobs.pop(path, None)


@pytest.fixture
def fake_docs(monkeypatch):
    """Wire the router's document seams to an in-memory FakeStorage + canned parse."""
    fs = FakeStorage()
    monkeypatch.setattr(pr_router, 'validate_upload', lambda filename, size: None)
    monkeypatch.setattr(pr_router, 'store_upload', lambda contents, filename: fs.store(contents, filename))
    monkeypatch.setattr(pr_router, 'read_stored', lambda path: fs.read(path))
    monkeypatch.setattr(pr_router, 'copy_stored', lambda path, filename: fs.store(fs.read(path), filename))
    monkeypatch.setattr(pr_router, 'delete_stored', lambda path: fs.delete(path))

    async def _extract(filename, content_type, path):
        return f'extracted::{filename}'

    monkeypatch.setattr(pr_router, 'extract_text', _extract)
    return fs


def _upload(meta=META):
    return {
        'files': {'file': ('policy.pdf', b'%PDF-1.4 dummy', 'application/pdf')},
        'data': {'meta': json.dumps(meta)},
    }


@pytest.mark.asyncio
async def test_create_with_file_stores_document(monkeypatch, fake_docs):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        res = await c.post('/api/v1/policy/reviews', **_upload())
        assert res.status_code == 200
        body = res.json()
        rid = body['id']
        assert body['policy_meta']['document']['filename'] == 'policy.pdf'
        assert body['policy_meta']['filename'] == 'policy.pdf'

    doc = await PolicyDocuments.get('review', rid)
    assert doc is not None
    assert doc.text == 'extracted::policy.pdf'
    assert doc.storage_path in fake_docs.blobs


@pytest.mark.asyncio
async def test_create_parse_failure_cleans_up(monkeypatch, fake_docs):
    # If text extraction fails, the request must 400, create NO review, and delete the
    # just-stored binary (no orphan).
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')

    async def _boom(filename, content_type, path):
        raise ValueError('bad parse')

    monkeypatch.setattr(pr_router, 'extract_text', _boom)

    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        res = await c.post('/api/v1/policy/reviews', **_upload())
        assert res.status_code == 400

    assert await pr_router.PolicyReviews.list_by_creator('rev1') == []
    assert fake_docs.blobs == {}


@pytest.mark.asyncio
async def test_replace_document_swaps_binary(monkeypatch, fake_docs):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        rid = (await c.post('/api/v1/policy/reviews', **_upload())).json()['id']
        old = await PolicyDocuments.get('review', rid)

        res = await c.put(
            f'/api/v1/policy/reviews/{rid}/document',
            files={'file': ('v2.pdf', b'%PDF-1.4 second', 'application/pdf')},
            data={},
        )
        assert res.status_code == 200

    new = await PolicyDocuments.get('review', rid)
    assert new.filename == 'v2.pdf'
    assert new.storage_path != old.storage_path
    assert old.storage_path not in fake_docs.blobs  # old binary deleted


@pytest.mark.asyncio
async def test_replace_document_reopens_rejected(monkeypatch, fake_docs):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    approver = SimpleNamespace(id='app1', role='user', name='Approver', email='a@x.io')
    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        rid = (await c.post('/api/v1/policy/reviews', **_upload())).json()['id']
        await c.patch(f'/api/v1/policy/reviews/{rid}/results', json={'results': {'S1-1': {'result': 'compliant'}}})
        await c.post(f'/api/v1/policy/reviews/{rid}/submit')
    async with _client_keys(monkeypatch, user=approver, keys={'policy_approver'}) as c:
        await c.post(f'/api/v1/policy/reviews/{rid}/reject', json={'note': 'fix it'})
    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        res = await c.put(
            f'/api/v1/policy/reviews/{rid}/document',
            files={'file': ('fixed.pdf', b'%PDF-1.4 fixed', 'application/pdf')},
            data={},
        )
        assert res.status_code == 200
        assert res.json()['status'] == 'draft'  # editing a returned review reopens it


@pytest.mark.asyncio
async def test_replace_document_forbidden_when_pending(monkeypatch, fake_docs):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        rid = (await c.post('/api/v1/policy/reviews', **_upload())).json()['id']
        await c.patch(f'/api/v1/policy/reviews/{rid}/results', json={'results': {'S1-1': {'result': 'compliant'}}})
        await c.post(f'/api/v1/policy/reviews/{rid}/submit')  # now pending
        res = await c.put(
            f'/api/v1/policy/reviews/{rid}/document',
            files={'file': ('x.pdf', b'%PDF-1.4 x', 'application/pdf')},
            data={},
        )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_download_review_document_access_matrix(monkeypatch, fake_docs):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    approver = SimpleNamespace(id='app1', role='user', name='Approver', email='a@x.io')
    admin = SimpleNamespace(id='ad1', role='admin', name='Admin', email='ad@x.io')
    stranger = SimpleNamespace(id='str1', role='user', name='Stranger', email='s@x.io')

    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        rid = (await c.post('/api/v1/policy/reviews', **_upload())).json()['id']
        owner_dl = await c.get(f'/api/v1/policy/reviews/{rid}/document')
        assert owner_dl.status_code == 200
        assert owner_dl.content == b'%PDF-1.4 dummy'
        assert 'attachment' in owner_dl.headers['content-disposition']

    async with _client_keys(monkeypatch, user=approver, keys={'policy_approver'}) as c:
        assert (await c.get(f'/api/v1/policy/reviews/{rid}/document')).status_code == 200
    async with _client_keys(monkeypatch, user=admin, keys=set()) as c:
        assert (await c.get(f'/api/v1/policy/reviews/{rid}/document')).status_code == 200
    async with _client_keys(monkeypatch, user=stranger, keys=set()) as c:
        assert (await c.get(f'/api/v1/policy/reviews/{rid}/document')).status_code == 403


@pytest.mark.asyncio
async def test_download_review_document_404_when_absent(monkeypatch, fake_docs):
    admin = SimpleNamespace(id='ad1', role='admin', name='Admin', email='ad@x.io')
    # Seed a review row with no document (insert directly via the reviews DAO).
    from open_webui.models.policy_review import PolicyReviews
    active = await PolicyChecklistVersions.get_active()
    review = await PolicyReviews.insert_review(
        created_by_id='ad1', created_by_name='Admin', policy_meta=META, active_version=active
    )
    async with _client_keys(monkeypatch, user=admin, keys=set()) as c:
        res = await c.get(f'/api/v1/policy/reviews/{review.id}/document')
    assert res.status_code == 404


async def _approve_flow(monkeypatch, fake_docs):
    """Create -> resolve -> submit -> approve; returns the review id."""
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    approver = SimpleNamespace(id='app1', role='user', name='Approver', email='a@x.io')
    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        rid = (await c.post('/api/v1/policy/reviews', **_upload())).json()['id']
        await c.patch(f'/api/v1/policy/reviews/{rid}/results', json={'results': {'S1-1': {'result': 'compliant'}}})
        await c.post(f'/api/v1/policy/reviews/{rid}/submit')
    async with _client_keys(monkeypatch, user=approver, keys={'policy_approver'}) as c:
        await c.post(f'/api/v1/policy/reviews/{rid}/approve', json={'note': 'ok'})
    return rid


@pytest.mark.asyncio
async def test_approve_copies_document_to_library(monkeypatch, fake_docs):
    await _approve_flow(monkeypatch, fake_docs)
    lib_doc = await PolicyDocuments.get('library', 'C-TEST')
    assert lib_doc is not None
    assert lib_doc.filename == 'policy.pdf'

    entry = await PolicyLibrary.get_by_code('C-TEST')
    assert entry.data['hasDocument'] is True
    assert entry.data['filename'] == 'policy.pdf'

    # Library download works for any verified user (open access).
    anyone = SimpleNamespace(id='u9', role='user', name='Anyone', email='u9@x.io')
    async with _client_keys(monkeypatch, user=anyone, keys=set()) as c:
        dl = await c.get('/api/v1/policy/library/C-TEST/document')
        assert dl.status_code == 200
        assert dl.content == b'%PDF-1.4 dummy'


@pytest.mark.asyncio
async def test_library_download_survives_review_deletion(monkeypatch, fake_docs):
    rid = await _approve_flow(monkeypatch, fake_docs)
    review_doc = await PolicyDocuments.get('review', rid)

    admin = SimpleNamespace(id='ad1', role='admin', name='Admin', email='ad@x.io')
    async with _client_keys(monkeypatch, user=admin, keys=set()) as c:
        assert (await c.delete(f'/api/v1/policy/reviews/{rid}')).status_code == 200

    # The review document + its binary are gone, but the library copy remains.
    assert await PolicyDocuments.get('review', rid) is None
    assert review_doc.storage_path not in fake_docs.blobs
    assert await PolicyDocuments.get('library', 'C-TEST') is not None
    async with _client_keys(monkeypatch, user=admin, keys=set()) as c:
        assert (await c.get('/api/v1/policy/library/C-TEST/document')).status_code == 200


@pytest.mark.asyncio
async def test_unpublish_removes_library_document(monkeypatch, fake_docs):
    await _approve_flow(monkeypatch, fake_docs)
    lib_doc = await PolicyDocuments.get('library', 'C-TEST')
    approver = SimpleNamespace(id='app1', role='user', name='Approver', email='a@x.io')
    async with _client_keys(monkeypatch, user=approver, keys={'policy_approver'}) as c:
        assert (await c.delete('/api/v1/policy/library/C-TEST')).status_code == 200
    assert await PolicyDocuments.get('library', 'C-TEST') is None
    assert lib_doc.storage_path not in fake_docs.blobs
