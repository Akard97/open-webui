import pytest

from open_webui.models.workos import (
    Comments, Activity, parse_mentions, task_change_activities,
)


def test_parse_mentions_extracts_unique_ids_in_order():
    body = "hi @[Lara](mention:u1) and @[Yusuf](mention:u2) and again @[Lara](mention:u1)"
    assert parse_mentions(body) == ['u1', 'u2']


def test_parse_mentions_empty_when_none():
    assert parse_mentions("plain text, email a@b.com, code `mention:x`") == []


def test_task_change_activities_diffs_relevant_fields():
    before = {'status': 'todo', 'assignee_id': None, 'priority': None,
              'due_date': None, 'title': 'A', 'description': None}
    after = {'status': 'in_progress', 'assignee_id': 'u2', 'priority': 'high',
             'due_date': 123, 'title': 'A', 'description': None}
    acts = task_change_activities('u1', before, after)
    types = {a['type'] for a in acts}
    assert types == {'status_changed', 'assignee_changed', 'priority_changed', 'due_changed'}
    status = next(a for a in acts if a['type'] == 'status_changed')
    assert status['data'] == {'from': 'todo', 'to': 'in_progress'}


def test_task_change_activities_marks_completed_and_reopened():
    done = task_change_activities('u1', {'status': 'todo'}, {'status': 'done'})
    assert any(a['type'] == 'completed' for a in done)
    reopened = task_change_activities('u1', {'status': 'done'}, {'status': 'todo'})
    assert any(a['type'] == 'reopened' for a in reopened)


@pytest.mark.asyncio
async def test_comments_crud():
    c = await Comments.insert('t1', 'u1', 'hello @[Y](mention:u2)', ['u2'])
    assert c.body == 'hello @[Y](mention:u2)' and c.mentions == ['u2'] and c.edited_at is None
    listed = await Comments.list_for_task('t1')
    assert [x.id for x in listed] == [c.id]
    edited = await Comments.update_body(c.id, 'edited', [])
    assert edited.body == 'edited' and edited.edited_at is not None
    assert await Comments.delete(c.id) is True
    assert await Comments.list_for_task('t1') == []


@pytest.mark.asyncio
async def test_activity_insert_and_list():
    a = await Activity.insert('t1', 'team1', 'u1', 'status_changed', {'from': 'todo', 'to': 'done'})
    assert a.type == 'status_changed' and a.data == {'from': 'todo', 'to': 'done'}
    assert [x.id for x in await Activity.list_for_task('t1')] == [a.id]


@pytest.mark.asyncio
async def test_attachments_crud():
    from open_webui.models.workos import Attachments
    a = await Attachments.insert('t1', None, 'wos/abc_file.pdf', 'file.pdf', 1234, 'application/pdf', 'u1')
    assert a.comment_id is None and a.storage_key == 'wos/abc_file.pdf' and a.size == 1234
    assert [x.id for x in await Attachments.list_for_task('t1')] == [a.id]
    assert (await Attachments.get_by_id(a.id)).name == 'file.pdf'
    assert await Attachments.delete(a.id) is True
    assert await Attachments.list_for_task('t1') == []


@pytest.mark.asyncio
async def test_notifications_list_count_and_mark_read():
    from open_webui.models.workos import Notifications
    n1 = await Notifications.insert('u1', 'u2', 'assigned', {'task_key': 'OSL-1'}, task_id='t1')
    await Notifications.insert('u1', 'u2', 'mentioned', {'task_key': 'OSL-1'}, task_id='t1')
    assert await Notifications.unread_count('u1') == 2
    assert len(await Notifications.list_for_user('u1')) == 2
    assert len(await Notifications.list_for_user('u1', unread_only=True)) == 2
    assert await Notifications.mark_read('u1', ids=[n1.id]) == 1
    assert await Notifications.unread_count('u1') == 1
    assert await Notifications.mark_read('u1', all=True) == 1
    assert await Notifications.unread_count('u1') == 0
