import pytest

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_teams import _client, U1, U2
from open_webui.test.workos.test_router_task import _stream


async def _task(c):
    team, ws, s = await _stream(c)
    t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                      json={'title': 'T', 'assignee_ids': ['u1']})).json()
    return team, ws, s, t


async def _comment(c, task_id, body='root', parent_id=None):
    payload = {'body': body}
    if parent_id is not None:
        payload['parent_id'] = parent_id
    r = await c.post(f"/api/v1/workos/tasks/{task_id}/comments", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_reply_chain_and_list_fields(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        root = await _comment(c, t['id'], 'root')
        child = await _comment(c, t['id'], 'child', parent_id=root['id'])
        grand = await _comment(c, t['id'], 'grand', parent_id=child['id'])
        assert root['parent_id'] is None and child['parent_id'] == root['id']
        assert grand['parent_id'] == child['id']
        listed = (await c.get(f"/api/v1/workos/tasks/{t['id']}/comments")).json()
        by_id = {x['id']: x for x in listed}
        assert by_id[root['id']]['deleted_at'] is None
        assert by_id[root['id']]['reactions'] == []


@pytest.mark.asyncio
async def test_reply_parent_validation(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, s, t1 = await _task(c)
        # Second task in the same workstream (not a second `_task(c)` call: that would
        # re-run `_stream(c)` and try to create another team with the same hardcoded
        # key 'OSL', which 400s on the unique-key check unrelated to this test).
        t2 = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                           json={'title': 'T2', 'assignee_ids': ['u1']})).json()
        r = await c.post(f"/api/v1/workos/tasks/{t1['id']}/comments",
                         json={'body': 'x', 'parent_id': 'missing'})
        assert r.status_code == 404
        foreign = await _comment(c, t2['id'], 'other-task root')
        r = await c.post(f"/api/v1/workos/tasks/{t1['id']}/comments",
                         json={'body': 'x', 'parent_id': foreign['id']})
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_delete_with_children_tombstones(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        root = await _comment(c, t['id'], 'root @[X](mention:u2)')
        await _comment(c, t['id'], 'child', parent_id=root['id'])
        r = (await c.delete(f"/api/v1/workos/comments/{root['id']}")).json()
        assert r == {'deleted': True, 'tombstoned': True}
        listed = (await c.get(f"/api/v1/workos/tasks/{t['id']}/comments")).json()
        tomb = next(x for x in listed if x['id'] == root['id'])
        assert tomb['deleted_at'] is not None and tomb['body'] == '' and tomb['mentions'] == []
        # child survives
        assert any(x['parent_id'] == root['id'] for x in listed)
        # tombstone cannot be edited or replied to
        assert (await c.patch(f"/api/v1/workos/comments/{root['id']}",
                              json={'body': 'zombie'})).status_code == 400
        assert (await c.post(f"/api/v1/workos/tasks/{t['id']}/comments",
                             json={'body': 'x', 'parent_id': root['id']})).status_code == 400


@pytest.mark.asyncio
async def test_delete_childless_hard_deletes(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        com = await _comment(c, t['id'], 'lonely')
        r = (await c.delete(f"/api/v1/workos/comments/{com['id']}")).json()
        assert r.get('deleted') is True and 'tombstoned' not in r
        listed = (await c.get(f"/api/v1/workos/tasks/{t['id']}/comments")).json()
        assert all(x['id'] != com['id'] for x in listed)


@pytest.mark.asyncio
async def test_reaction_toggle_allowlist_and_list(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        com = await _comment(c, t['id'], 'react to me')
        r = await c.post(f"/api/v1/workos/comments/{com['id']}/reactions", json={'emoji': '👍'})
        assert r.status_code == 200, r.text
        assert r.json()['added'] is True
        assert r.json()['reactions'] == [{'emoji': '👍', 'count': 1, 'user_ids': ['u1']}]
        # toggle off
        r = await c.post(f"/api/v1/workos/comments/{com['id']}/reactions", json={'emoji': '👍'})
        assert r.json() == {'added': False, 'reactions': []}
        # allowlist
        r = await c.post(f"/api/v1/workos/comments/{com['id']}/reactions", json={'emoji': '🦖'})
        assert r.status_code == 400
        # unknown comment
        r = await c.post("/api/v1/workos/comments/nope/reactions", json={'emoji': '👍'})
        assert r.status_code == 404
        # reactions come back on GET
        await c.post(f"/api/v1/workos/comments/{com['id']}/reactions", json={'emoji': '🎉'})
        listed = (await c.get(f"/api/v1/workos/tasks/{t['id']}/comments")).json()
        got = next(x for x in listed if x['id'] == com['id'])
        assert got['reactions'] == [{'emoji': '🎉', 'count': 1, 'user_ids': ['u1']}]


@pytest.mark.asyncio
async def test_reaction_rejected_on_tombstone(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        root = await _comment(c, t['id'], 'root')
        await _comment(c, t['id'], 'child', parent_id=root['id'])
        await c.delete(f"/api/v1/workos/comments/{root['id']}")
        r = await c.post(f"/api/v1/workos/comments/{root['id']}/reactions", json={'emoji': '👍'})
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_replied_notification_precedence(monkeypatch):
    sent = []

    async def _eu(event, payload, user_ids):
        sent.append((event, tuple(user_ids), payload.get('type')))

    monkeypatch.setattr(wr, 'emit_users', _eu)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        await c.post(f"/api/v1/workos/teams/{t['team_id']}/members", json={'user_id': 'u2', 'role': 'member'})
        root = await _comment(c, t['id'], 'root by u1')
    async with _client(monkeypatch, user=U2) as c:
        sent.clear()
        await _comment(c, t['id'], 'reply to u1', parent_id=root['id'])
    types_for_u1 = [ty for _e, ids, ty in sent if 'u1' in ids]
    assert 'replied' in types_for_u1          # parent author got replied…
    assert 'commented' not in types_for_u1    # …and not a duplicate commented
    assert all('u2' not in ids for _e, ids, _t in sent)  # actor never notified


@pytest.mark.asyncio
async def test_mention_beats_replied(monkeypatch):
    sent = []

    async def _eu(event, payload, user_ids):
        sent.append((event, tuple(user_ids), payload.get('type')))

    monkeypatch.setattr(wr, 'emit_users', _eu)
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        await c.post(f"/api/v1/workos/teams/{t['team_id']}/members", json={'user_id': 'u2', 'role': 'member'})
        root = await _comment(c, t['id'], 'root by u1')
    async with _client(monkeypatch, user=U2) as c:
        sent.clear()
        await _comment(c, t['id'], 'ping @[A](mention:u1)', parent_id=root['id'])
    types_for_u1 = [ty for _e, ids, ty in sent if 'u1' in ids]
    assert types_for_u1 == ['mentioned']  # exactly one notification, the mention


@pytest.mark.asyncio
async def test_comment_attachment_must_be_image(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, _, t = await _task(c)
        com = await _comment(c, t['id'], 'has files')
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/attachments?comment_id={com['id']}",
                         files={'file': ('note.txt', b'hello', 'text/plain')})
        assert r.status_code == 400
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/attachments?comment_id={com['id']}",
                         files={'file': ('shot.png', b'\x89PNG fake', 'image/png')})
        assert r.status_code == 200, r.text
        # task-level upload (no comment_id) still takes non-images
        r = await c.post(f"/api/v1/workos/tasks/{t['id']}/attachments",
                         files={'file': ('note.txt', b'hello', 'text/plain')})
        assert r.status_code == 200, r.text
