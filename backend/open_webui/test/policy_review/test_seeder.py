import pytest

from open_webui.internal.policy_review.seeder import seed_policy_review_data
from open_webui.models.policy_review import PolicyChecklistVersions, PolicyReviews, PolicyLibrary


@pytest.mark.asyncio
async def test_seeder_populates_then_is_idempotent():
    await seed_policy_review_data()

    active = await PolicyChecklistVersions.get_active()
    assert active is not None
    assert active.label == 'v2.0'
    item_count = sum(len(s.get('items', [])) for s in active.data['sections'])
    assert item_count > 0

    library_count = len(await PolicyLibrary.list_all())
    pending = await PolicyReviews.list_by_status('pending')
    assert library_count > 0
    assert len(pending) > 0  # demo reviews include pending ones

    # Second run must not duplicate.
    await seed_policy_review_data()
    assert len(await PolicyChecklistVersions.list_versions()) == 1
    assert len(await PolicyLibrary.list_all()) == library_count
