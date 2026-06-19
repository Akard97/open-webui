import pytest

from open_webui.models.policy_review import (
    PolicyChecklistVersions,
    PolicyReviews,
    PolicyLibrary,
    PolicyAudits,
    PolicyDocuments,
)

ACTIVE_DATA = {'changeSummary': 'init', 'themes': [], 'sections': [], 'verdictBands': {'approved': 85, 'conditional': 70}, 'standards': []}


@pytest.mark.asyncio
async def test_checklist_active_and_draft_singletons():
    active = await PolicyChecklistVersions.insert_version(label='v2.0', status='active', data=ACTIVE_DATA, published_by_id=None, published_by_name='OE')
    assert (await PolicyChecklistVersions.get_active()).id == active.id

    draft = await PolicyChecklistVersions.start_draft()
    assert draft.status == 'draft'
    assert (await PolicyChecklistVersions.get_draft()).id == draft.id

    published = await PolicyChecklistVersions.publish_draft(by_id='u1', by_name='Admin')
    assert published.status == 'active'
    assert published.label == 'v2.1'
    assert (await PolicyChecklistVersions.get_draft()) is None
    versions = await PolicyChecklistVersions.list_versions()
    statuses = sorted(v.status for v in versions)
    assert statuses == ['active', 'archived']  # old active archived, new active present


@pytest.mark.asyncio
async def test_review_crud_and_snapshot_pinning():
    await PolicyChecklistVersions.insert_version(label='v2.0', status='active', data=ACTIVE_DATA, published_by_id=None, published_by_name='OE')
    active = await PolicyChecklistVersions.get_active()

    review = await PolicyReviews.insert_review(
        created_by_id='u1',
        created_by_name='Reviewer One',
        policy_meta={'name': 'P', 'code': 'C-1', 'version': 'v1', 'owner': 'O', 'reviewer': 'R', 'reviewDate': 'd', 'pages': 1, 'filename': 'f.pdf'},
        active_version=active,
    )
    assert review.status == 'draft'
    assert review.checklist_version_id == active.id
    assert review.checklist_snapshot['changeSummary'] == 'init'

    # Publishing a NEW version must not change the in-flight review's snapshot.
    await PolicyChecklistVersions.start_draft()
    await PolicyChecklistVersions.publish_draft(by_id='u2', by_name='Admin')
    fetched = await PolicyReviews.get_by_id(review.id)
    assert fetched.checklist_version_id == active.id
    assert fetched.checklist_snapshot['changeSummary'] == 'init'

    assert [r.id for r in await PolicyReviews.list_by_creator('u1')] == [review.id]
    assert await PolicyReviews.list_by_status('pending') == []


@pytest.mark.asyncio
async def test_library_upsert_by_code():
    e1 = await PolicyLibrary.upsert(code='C-1', data={'code': 'C-1', 'title': 'First'}, source_review_id=None)
    e2 = await PolicyLibrary.upsert(code='C-1', data={'code': 'C-1', 'title': 'Updated'}, source_review_id='rev1')
    assert e1.id == e2.id  # same row reused
    assert (await PolicyLibrary.get_by_code('C-1')).data['title'] == 'Updated'
    assert len(await PolicyLibrary.list_all()) == 1


@pytest.mark.asyncio
async def test_audit_append():
    await PolicyAudits.insert('review', 'rev1', 'created', 'u1', 'Reviewer One', None)
    rows = await PolicyAudits.list_for('review', 'rev1')
    assert len(rows) == 1
    assert rows[0].action == 'created'


@pytest.mark.asyncio
async def test_policy_document_upsert_get_delete_roundtrip():
    created = await PolicyDocuments.upsert(
        'review', 'rev-1', 'a.pdf', 'application/pdf', 1234, 'uploads/a.pdf', 'hello text'
    )
    assert created.owner_type == 'review'
    assert created.owner_id == 'rev-1'
    assert created.text == 'hello text'

    got = await PolicyDocuments.get('review', 'rev-1')
    assert got is not None
    assert got.filename == 'a.pdf'
    assert got.storage_path == 'uploads/a.pdf'

    deleted = await PolicyDocuments.delete('review', 'rev-1')
    assert deleted is not None
    assert deleted.storage_path == 'uploads/a.pdf'
    assert await PolicyDocuments.get('review', 'rev-1') is None


@pytest.mark.asyncio
async def test_policy_document_upsert_overwrites_same_owner():
    await PolicyDocuments.upsert('review', 'rev-2', 'old.pdf', 'application/pdf', 1, 'uploads/old.pdf', 'old')
    await PolicyDocuments.upsert('review', 'rev-2', 'new.pdf', 'application/pdf', 2, 'uploads/new.pdf', 'new')

    rows = await PolicyDocuments.list_all_for_test()
    same_owner = [r for r in rows if r.owner_type == 'review' and r.owner_id == 'rev-2']
    assert len(same_owner) == 1  # UNIQUE(owner_type, owner_id) — replace, not duplicate
    assert same_owner[0].filename == 'new.pdf'
    assert same_owner[0].text == 'new'
