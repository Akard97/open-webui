import pytest

from open_webui.models.workos import Notifications


@pytest.mark.asyncio
async def test_archive_sets_read_and_leaves_default_list():
    n = await Notifications.insert('u1', 'u2', 'assigned', {}, task_id='t1')
    assert n.archived is False
    count = await Notifications.set_archived('u1', ids=[n.id])
    assert count == 1
    default_list = await Notifications.list_for_user('u1')
    assert default_list == []
    archived = await Notifications.list_for_user('u1', archived=True)
    assert [x.id for x in archived] == [n.id]
    assert archived[0].read is True and archived[0].archived is True


@pytest.mark.asyncio
async def test_unarchive_restores_row_without_unreading():
    n = await Notifications.insert('u1', 'u2', 'commented', {}, task_id='t1')
    await Notifications.set_archived('u1', ids=[n.id])
    await Notifications.set_archived('u1', ids=[n.id], archived=False)
    restored = await Notifications.list_for_user('u1')
    assert [x.id for x in restored] == [n.id]
    assert restored[0].read is True  # unarchive does not un-read


@pytest.mark.asyncio
async def test_archive_scoped_to_owner():
    n = await Notifications.insert('u2', 'u1', 'assigned', {}, task_id='t1')
    count = await Notifications.set_archived('u1', ids=[n.id])
    assert count == 0
    assert [x.id for x in await Notifications.list_for_user('u2')] == [n.id]


@pytest.mark.asyncio
async def test_archive_all_read_sweeps_only_read_rows():
    a = await Notifications.insert('u1', 'u2', 'assigned', {}, task_id='t1')
    b = await Notifications.insert('u1', 'u2', 'commented', {}, task_id='t1')
    await Notifications.mark_read('u1', ids=[a.id])
    count = await Notifications.set_archived('u1', all_read=True)
    assert count == 1
    remaining = await Notifications.list_for_user('u1')
    assert [x.id for x in remaining] == [b.id]


@pytest.mark.asyncio
async def test_counts_for_user_by_type_unread_nonarchived_only():
    await Notifications.insert('u1', 'u2', 'mentioned', {}, task_id='t1')
    await Notifications.insert('u1', 'u2', 'mentioned', {}, task_id='t1')
    n3 = await Notifications.insert('u1', 'u2', 'assigned', {}, task_id='t1')
    n4 = await Notifications.insert('u1', 'u2', 'commented', {}, task_id='t1')
    await Notifications.mark_read('u1', ids=[n3.id])       # read → not counted
    await Notifications.set_archived('u1', ids=[n4.id])    # archived → not counted
    counts = await Notifications.counts_for_user('u1')
    assert counts == {
        'unread': 2,
        'by_type': {'assigned': 0, 'subtask_assigned': 0, 'mentioned': 2, 'commented': 0, 'status_changed': 0},
    }


@pytest.mark.asyncio
async def test_pagination_compound_cursor_covers_shared_millisecond(monkeypatch):
    import open_webui.models.workos as mw
    monkeypatch.setattr(mw, '_now', lambda: 12345)  # 3 rows share one millisecond
    ids = {(await Notifications.insert('u1', 'u2', 'commented', {}, task_id='t1')).id for _ in range(3)}
    page1 = await Notifications.list_for_user('u1', limit=2)
    assert len(page1) == 2
    page2 = await Notifications.list_for_user(
        'u1', limit=2, before=page1[-1].created_at, before_id=page1[-1].id
    )
    assert len(page2) == 1
    assert {x.id for x in page1} | {x.id for x in page2} == ids
