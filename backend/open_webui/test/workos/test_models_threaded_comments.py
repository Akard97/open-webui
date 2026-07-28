import pytest

from open_webui.models.workos import Comments, Reactions


@pytest.mark.asyncio
async def test_insert_with_parent_and_defaults():
    root = await Comments.insert('t1', 'u1', 'root', [])
    child = await Comments.insert('t1', 'u2', 'child', [], parent_id=root.id)
    assert root.parent_id is None and root.deleted_at is None and root.reactions == []
    assert child.parent_id == root.id


@pytest.mark.asyncio
async def test_has_children():
    root = await Comments.insert('t1', 'u1', 'root', [])
    assert await Comments.has_children(root.id) is False
    await Comments.insert('t1', 'u2', 'child', [], parent_id=root.id)
    assert await Comments.has_children(root.id) is True


@pytest.mark.asyncio
async def test_tombstone_blanks_body_and_mentions():
    c = await Comments.insert('t1', 'u1', 'secret @[X](mention:u9)', ['u9'])
    tomb = await Comments.tombstone(c.id)
    assert tomb.deleted_at is not None
    assert tomb.body == '' and tomb.mentions == []
    assert await Comments.tombstone('nope') is None


@pytest.mark.asyncio
async def test_reaction_toggle_and_aggregate():
    c = await Comments.insert('t1', 'u1', 'hi', [])
    assert await Reactions.toggle(c.id, 'u1', '👍') is True
    assert await Reactions.toggle(c.id, 'u2', '👍') is True
    assert await Reactions.toggle(c.id, 'u2', '🎉') is True
    agg = await Reactions.aggregate_for_comments([c.id])
    entries = {e['emoji']: e for e in agg[c.id]}
    assert entries['👍']['count'] == 2 and set(entries['👍']['user_ids']) == {'u1', 'u2'}
    assert entries['🎉']['count'] == 1
    # toggle off
    assert await Reactions.toggle(c.id, 'u1', '👍') is False
    agg = await Reactions.aggregate_for_comments([c.id])
    entries = {e['emoji']: e for e in agg[c.id]}
    assert entries['👍']['count'] == 1


@pytest.mark.asyncio
async def test_reaction_purge_and_empty_aggregate():
    c = await Comments.insert('t1', 'u1', 'hi', [])
    await Reactions.toggle(c.id, 'u1', '👍')
    await Reactions.purge_for_comment(c.id)
    assert await Reactions.aggregate_for_comments([c.id]) == {}
    assert await Reactions.aggregate_for_comments([]) == {}
