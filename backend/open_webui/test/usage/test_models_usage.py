import pytest

from open_webui.models.usage import EVENT_ALLOWLIST, TOOLS, UsageEvents


@pytest.mark.asyncio
async def test_insert_client_batch_accepts_valid_and_rejects_invalid():
    events = [
        {'name': 'page.view', 'properties': {'tool': 'workos', 'view': 'board', 'path': '/workos'}, 'session_id': 's1'},
        {'name': 'page.leave', 'properties': {'tool': 'workos', 'view': 'board', 'duration_ms': 5000}, 'session_id': 's1'},
        {'name': 'workos.task.create', 'properties': {}, 'session_id': 's1'},  # server-kind -> rejected
        {'name': 'not.a.event', 'properties': {}, 'session_id': 's1'},  # unknown -> rejected
        {'name': 'page.view', 'properties': {'tool': 'nope'}, 'session_id': 's1'},  # bad tool -> rejected
    ]
    accepted, rejected = await UsageEvents.insert_client_batch('u1', events)
    assert accepted == 2
    assert rejected == 3
    rows = await UsageEvents.user_activity('u1', since_ms=0, page=1, limit=10)
    assert rows['total'] == 2
    leave = next(r for r in rows['events'] if r['event_name'] == 'page.leave')
    assert leave['tool'] == 'workos'


@pytest.mark.asyncio
async def test_insert_client_batch_rejects_oversize_properties():
    big = {'x': 'a' * 3000}
    accepted, rejected = await UsageEvents.insert_client_batch(
        'u1', [{'name': 'page.view', 'properties': {'tool': 'chat', **big}, 'session_id': 's1'}]
    )
    assert (accepted, rejected) == (0, 1)


@pytest.mark.asyncio
async def test_emit_writes_server_event():
    await UsageEvents.emit('u2', 'workos.task.create', {'task_id': 't1', 'team_id': 'tm1'})
    rows = await UsageEvents.user_activity('u2', since_ms=0, page=1, limit=10)
    assert rows['total'] == 1
    assert rows['events'][0]['source'] == 'server'
    assert rows['events'][0]['tool'] == 'workos'


@pytest.mark.asyncio
async def test_emit_never_raises_on_unknown_or_client_event():
    await UsageEvents.emit('u3', 'totally.unknown')  # must not raise
    await UsageEvents.emit('u3', 'page.view')  # client-kind: refused, must not raise
    rows = await UsageEvents.user_activity('u3', since_ms=0, page=1, limit=10)
    assert rows['total'] == 0


def test_allowlist_shape():
    assert all(
        kind in ('client', 'server') and (tool in TOOLS or tool == 'app')
        for tool, kind in EVENT_ALLOWLIST.values()
    )
