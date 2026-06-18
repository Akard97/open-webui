import pytest
import pytest_asyncio
from types import SimpleNamespace

import httpx
from httpx import ASGITransport
from fastapi import FastAPI

import open_webui.routers.policy_review as pr_router
from open_webui.utils.auth import get_verified_user
from open_webui.models.policy_review import PolicyChecklistVersions, PolicyLibrary

# One theme, one item -> compliant => fully resolved, score 100, gates pass.
ACTIVE_DATA = {
    'changeSummary': 'init',
    'themes': [{'id': 'T1', 'name': 'T1', 'weight': 100, 'gate': True, 'threshold': 85}],
    'sections': [{'id': 'S1', 'theme': 'T1', 'items': [{'id': 'S1-1', 'assessment': 'auto'}]}],
    'verdictBands': {'approved': 85, 'conditional': 70},
    'standards': [],
}

META = {'name': 'Test Policy', 'code': 'C-TEST', 'version': 'v1', 'owner': 'O', 'reviewer': 'R', 'reviewDate': 'd', 'pages': 1, 'filename': 'f.pdf'}


class _AsyncReturn:
    def __init__(self, value):
        self.value = value

    async def __call__(self, *args, **kwargs):
        return self.value


def _make_app(user):
    app = FastAPI()
    app.state.config = SimpleNamespace(USER_PERMISSIONS={})
    app.include_router(pr_router.router, prefix='/api/v1/policy')
    app.dependency_overrides[get_verified_user] = lambda: user
    return app


def _client(monkeypatch, *, user, allow=True):
    monkeypatch.setattr(pr_router, 'has_permission', _AsyncReturn(allow))
    return httpx.AsyncClient(transport=ASGITransport(app=_make_app(user)), base_url='http://test')


def _client_keys(monkeypatch, *, user, keys=()):
    # Key-aware permission stub: grants only the named feature keys (e.g. {'policy_checker'}),
    # so owner-vs-admin paths can be exercised without the single-bool stub masking them.
    granted = set(keys)

    async def _hp(user_id, key, permissions, db=None):
        return key.split('.')[-1] in granted

    monkeypatch.setattr(pr_router, 'has_permission', _hp)
    return httpx.AsyncClient(transport=ASGITransport(app=_make_app(user)), base_url='http://test')


@pytest_asyncio.fixture(autouse=True)
async def _seed_active():
    await PolicyChecklistVersions.insert_version('v2.0', 'active', ACTIVE_DATA, None, 'OE')


@pytest.mark.asyncio
async def test_full_lifecycle_create_submit_approve_publishes(monkeypatch):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    approver = SimpleNamespace(id='app1', role='user', name='Approver', email='a@x.io')

    # This test exercises the real submit gate (a pending item must block submit),
    # so disable the testing autofill that would otherwise pre-resolve every item.
    monkeypatch.setattr(pr_router, 'AUTOFILL_RESULTS_ON_CREATE', False)

    # Create
    async with _client(monkeypatch, user=reviewer) as c:
        created = await c.post('/api/v1/policy/reviews', json={'policy_meta': META})
        assert created.status_code == 200
        rid = created.json()['id']
        assert created.json()['status'] == 'draft'
        assert created.json()['checklist_snapshot']['changeSummary'] == 'init'

        # Submit blocked while item is pending
        blocked = await c.post(f'/api/v1/policy/reviews/{rid}/submit')
        assert blocked.status_code == 400

        # Resolve the only item, then submit
        await c.patch(f'/api/v1/policy/reviews/{rid}/results', json={'results': {'S1-1': {'result': 'compliant'}}})
        ok = await c.post(f'/api/v1/policy/reviews/{rid}/submit')
        assert ok.status_code == 200
        assert ok.json()['status'] == 'pending'

    # Approver sees it in the queue and approves
    async with _client(monkeypatch, user=approver) as c:
        queue = await c.get('/api/v1/policy/reviews/queue')
        assert any(r['id'] == rid for r in queue.json())
        approved = await c.post(f'/api/v1/policy/reviews/{rid}/approve', json={'note': 'ok'})
        assert approved.status_code == 200
        assert approved.json()['status'] == 'approved'

    # Published into the library
    entry = await PolicyLibrary.get_by_code('C-TEST')
    assert entry is not None
    assert entry.data['score'] == 100


@pytest.mark.asyncio
async def test_submit_stores_reviewer_note_for_approver(monkeypatch):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    async with _client(monkeypatch, user=reviewer) as c:
        rid = (await c.post('/api/v1/policy/reviews', json={'policy_meta': META})).json()['id']
        await c.patch(f'/api/v1/policy/reviews/{rid}/results', json={'results': {'S1-1': {'result': 'compliant'}}})
        submitted = await c.post(
            f'/api/v1/policy/reviews/{rid}/submit', json={'note': '  Please prioritise section 3.  '}
        )
        assert submitted.status_code == 200
        assert submitted.json()['status'] == 'pending'
        # The reviewer's note is meaningful context for the approver and is trimmed.
        assert submitted.json()['approval']['note'] == 'Please prioritise section 3.'


@pytest.mark.asyncio
async def test_submit_without_note_is_allowed(monkeypatch):
    # The note is optional: submitting with no body must still succeed.
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    async with _client(monkeypatch, user=reviewer) as c:
        rid = (await c.post('/api/v1/policy/reviews', json={'policy_meta': META})).json()['id']
        await c.patch(f'/api/v1/policy/reviews/{rid}/results', json={'results': {'S1-1': {'result': 'compliant'}}})
        submitted = await c.post(f'/api/v1/policy/reviews/{rid}/submit')
        assert submitted.status_code == 200
        assert submitted.json()['approval']['note'] == ''


@pytest.mark.asyncio
async def test_non_reviewer_cannot_create(monkeypatch):
    user = SimpleNamespace(id='x', role='user', name='X', email='x@x.io')
    async with _client(monkeypatch, user=user, allow=False) as c:
        res = await c.post('/api/v1/policy/reviews', json={'policy_meta': META})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_reject_requires_note_and_returns_to_owner(monkeypatch):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    approver = SimpleNamespace(id='app1', role='user', name='Approver', email='a@x.io')

    async with _client(monkeypatch, user=reviewer) as c:
        rid = (await c.post('/api/v1/policy/reviews', json={'policy_meta': META})).json()['id']
        await c.patch(f'/api/v1/policy/reviews/{rid}/results', json={'results': {'S1-1': {'result': 'compliant'}}})
        await c.post(f'/api/v1/policy/reviews/{rid}/submit')

    async with _client(monkeypatch, user=approver) as c:
        no_note = await c.post(f'/api/v1/policy/reviews/{rid}/reject', json={'note': ''})
        assert no_note.status_code == 400
        rejected = await c.post(f'/api/v1/policy/reviews/{rid}/reject', json={'note': 'fix it'})
        assert rejected.status_code == 200
        assert rejected.json()['status'] == 'rejected'

    # Owner edits a rejected review -> reopens to draft
    async with _client(monkeypatch, user=reviewer) as c:
        reopened = await c.patch(f'/api/v1/policy/reviews/{rid}/results', json={'results': {'S1-1': {'result': 'non-compliant'}}})
        assert reopened.status_code == 200
        assert reopened.json()['status'] == 'draft'


@pytest.mark.asyncio
async def test_cannot_edit_after_submit(monkeypatch):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    async with _client(monkeypatch, user=reviewer) as c:
        rid = (await c.post('/api/v1/policy/reviews', json={'policy_meta': META})).json()['id']
        await c.patch(f'/api/v1/policy/reviews/{rid}/results', json={'results': {'S1-1': {'result': 'compliant'}}})
        await c.post(f'/api/v1/policy/reviews/{rid}/submit')
        # Now pending -> editing must be refused
        res = await c.patch(f'/api/v1/policy/reviews/{rid}/results', json={'results': {'S1-1': {'result': 'non-compliant'}}})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_cannot_approve_non_pending_review(monkeypatch):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    approver = SimpleNamespace(id='app1', role='user', name='Approver', email='a@x.io')
    # Create but do NOT submit -> stays 'draft'.
    async with _client(monkeypatch, user=reviewer) as c:
        rid = (await c.post('/api/v1/policy/reviews', json={'policy_meta': META})).json()['id']
    # Approving a non-pending (draft) review must be refused.
    async with _client(monkeypatch, user=approver) as c:
        res = await c.post(f'/api/v1/policy/reviews/{rid}/approve', json={'note': 'ok'})
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_get_review_forbidden_for_non_owner_non_approver(monkeypatch):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    async with _client(monkeypatch, user=reviewer) as c:
        rid = (await c.post('/api/v1/policy/reviews', json={'policy_meta': META})).json()['id']
    # A different user who is neither owner, admin, nor approver (permission denied) -> 403.
    stranger = SimpleNamespace(id='str1', role='user', name='Stranger', email='s@x.io')
    async with _client(monkeypatch, user=stranger, allow=False) as c:
        res = await c.get(f'/api/v1/policy/reviews/{rid}')
    assert res.status_code == 403


# ──────────────────────────── admin bypass coverage ────────────────────────────


@pytest.mark.asyncio
async def test_admin_role_bypasses_permission_gate(monkeypatch):
    # An admin-role user passes a policy_admin-gated route even when has_permission says no.
    admin = SimpleNamespace(id='ad1', role='admin', name='Admin', email='ad@x.io')
    async with _client(monkeypatch, user=admin, allow=False) as c:
        res = await c.get('/api/v1/policy/checklist/versions')
    assert res.status_code == 200


# ──────────────────────────── delete a review ────────────────────────────


async def _create(c, **meta_over):
    meta = {**META, **meta_over}
    return (await c.post('/api/v1/policy/reviews', json={'policy_meta': meta})).json()['id']


@pytest.mark.asyncio
async def test_owner_can_delete_draft_review(monkeypatch):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        rid = await _create(c)
        deleted = await c.delete(f'/api/v1/policy/reviews/{rid}')
        assert deleted.status_code == 200
        gone = await c.get(f'/api/v1/policy/reviews/{rid}')
        assert gone.status_code == 404


@pytest.mark.asyncio
async def test_owner_cannot_delete_pending_review(monkeypatch):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        rid = await _create(c)
        await c.patch(f'/api/v1/policy/reviews/{rid}/results', json={'results': {'S1-1': {'result': 'compliant'}}})
        await c.post(f'/api/v1/policy/reviews/{rid}/submit')
        res = await c.delete(f'/api/v1/policy/reviews/{rid}')
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_owner_can_delete_rejected_review(monkeypatch):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    approver = SimpleNamespace(id='app1', role='user', name='Approver', email='a@x.io')
    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        rid = await _create(c)
        await c.patch(f'/api/v1/policy/reviews/{rid}/results', json={'results': {'S1-1': {'result': 'compliant'}}})
        await c.post(f'/api/v1/policy/reviews/{rid}/submit')
    async with _client_keys(monkeypatch, user=approver, keys={'policy_approver'}) as c:
        await c.post(f'/api/v1/policy/reviews/{rid}/reject', json={'note': 'fix it'})
    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        res = await c.delete(f'/api/v1/policy/reviews/{rid}')
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_admin_can_delete_any_review(monkeypatch):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    admin = SimpleNamespace(id='ad1', role='admin', name='Admin', email='ad@x.io')
    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        rid = await _create(c)
        await c.patch(f'/api/v1/policy/reviews/{rid}/results', json={'results': {'S1-1': {'result': 'compliant'}}})
        await c.post(f'/api/v1/policy/reviews/{rid}/submit')  # now pending
    # Admin may delete a pending review (governance cleanup).
    async with _client_keys(monkeypatch, user=admin, keys=set()) as c:
        res = await c.delete(f'/api/v1/policy/reviews/{rid}')
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_non_owner_checker_cannot_delete(monkeypatch):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        rid = await _create(c)
    # Another checker who does not own the review -> 403 (not 401).
    other = SimpleNamespace(id='rev2', role='user', name='Other', email='o@x.io')
    async with _client_keys(monkeypatch, user=other, keys={'policy_checker'}) as c:
        res = await c.delete(f'/api/v1/policy/reviews/{rid}')
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_delete_review_requires_checker_or_admin(monkeypatch):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        rid = await _create(c)
    # A user with no policy permissions at all -> 401.
    nobody = SimpleNamespace(id='nb1', role='user', name='Nobody', email='n@x.io')
    async with _client_keys(monkeypatch, user=nobody, keys=set()) as c:
        res = await c.delete(f'/api/v1/policy/reviews/{rid}')
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_delete_unknown_review_404(monkeypatch):
    admin = SimpleNamespace(id='ad1', role='admin', name='Admin', email='ad@x.io')
    async with _client_keys(monkeypatch, user=admin, keys=set()) as c:
        res = await c.delete('/api/v1/policy/reviews/does-not-exist')
    assert res.status_code == 404


# ──────────────────────────── unpublish a library entry ────────────────────────────


@pytest.mark.asyncio
async def test_approver_can_unpublish_library_entry(monkeypatch):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    approver = SimpleNamespace(id='app1', role='user', name='Approver', email='a@x.io')
    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        rid = await _create(c)
        await c.patch(f'/api/v1/policy/reviews/{rid}/results', json={'results': {'S1-1': {'result': 'compliant'}}})
        await c.post(f'/api/v1/policy/reviews/{rid}/submit')
    async with _client_keys(monkeypatch, user=approver, keys={'policy_approver'}) as c:
        await c.post(f'/api/v1/policy/reviews/{rid}/approve', json={'note': 'ok'})  # publishes C-TEST
        deleted = await c.delete('/api/v1/policy/library/C-TEST')
        assert deleted.status_code == 200
        gone = await c.get('/api/v1/policy/library/C-TEST')
        assert gone.status_code == 404


@pytest.mark.asyncio
async def test_unpublish_unknown_code_404(monkeypatch):
    approver = SimpleNamespace(id='app1', role='user', name='Approver', email='a@x.io')
    async with _client_keys(monkeypatch, user=approver, keys={'policy_approver'}) as c:
        res = await c.delete('/api/v1/policy/library/NO-SUCH-CODE')
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_unpublish_requires_approver_or_admin(monkeypatch):
    nobody = SimpleNamespace(id='nb1', role='user', name='Nobody', email='n@x.io')
    async with _client_keys(monkeypatch, user=nobody, keys={'policy_checker'}) as c:
        res = await c.delete('/api/v1/policy/library/C-TEST')
    assert res.status_code == 401


# ──────────────────────────── re-activate an archived version ────────────────────────────


async def _publish_v21(c):
    # Clone the active v2.0 into a draft and publish -> archives v2.0, active becomes v2.1.
    await c.post('/api/v1/policy/checklist/draft')
    pub = await c.post('/api/v1/policy/checklist/draft/publish')
    assert pub.status_code == 200
    return pub.json()


@pytest.mark.asyncio
async def test_reactivate_archived_version(monkeypatch):
    admin = SimpleNamespace(id='ad1', role='user', name='Nouf', email='n@x.io')
    async with _client_keys(monkeypatch, user=admin, keys={'policy_admin'}) as c:
        published = await _publish_v21(c)
        assert published['label'] == 'v2.1'
        versions = (await c.get('/api/v1/policy/checklist/versions')).json()
        v20 = next(v for v in versions if v['label'] == 'v2.0')
        assert v20['status'] == 'archived'

        res = await c.post(f"/api/v1/policy/checklist/versions/{v20['id']}/activate")
        assert res.status_code == 200
        assert res.json()['status'] == 'active'
        assert res.json()['label'] == 'v2.0'  # label is NOT bumped on re-activation

        active = (await c.get('/api/v1/policy/checklist/active')).json()
        assert active['label'] == 'v2.0'
        # The previously-active v2.1 is now archived.
        versions2 = (await c.get('/api/v1/policy/checklist/versions')).json()
        v21 = next(v for v in versions2 if v['label'] == 'v2.1')
        assert v21['status'] == 'archived'


@pytest.mark.asyncio
async def test_reactivate_active_version_rejected(monkeypatch):
    admin = SimpleNamespace(id='ad1', role='user', name='Nouf', email='n@x.io')
    async with _client_keys(monkeypatch, user=admin, keys={'policy_admin'}) as c:
        versions = (await c.get('/api/v1/policy/checklist/versions')).json()
        active_id = next(v['id'] for v in versions if v['status'] == 'active')
        res = await c.post(f'/api/v1/policy/checklist/versions/{active_id}/activate')
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_reactivate_unknown_version_404(monkeypatch):
    admin = SimpleNamespace(id='ad1', role='user', name='Nouf', email='n@x.io')
    async with _client_keys(monkeypatch, user=admin, keys={'policy_admin'}) as c:
        res = await c.post('/api/v1/policy/checklist/versions/nope/activate')
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_reactivate_requires_admin(monkeypatch):
    approver = SimpleNamespace(id='app1', role='user', name='Approver', email='a@x.io')
    async with _client_keys(monkeypatch, user=approver, keys={'policy_approver'}) as c:
        res = await c.post('/api/v1/policy/checklist/versions/whatever/activate')
    assert res.status_code == 401
