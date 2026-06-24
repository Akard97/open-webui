import pytest

from open_webui.models.workos import Teams, Workspaces, Workstreams, Labels, Tasks


async def _stream():
    team = await Teams.insert('Acme', 'OSL', None, 'u1')
    ws = await Workspaces.insert(team.id, 'Engineering', None, 'team', 'u1')
    s = await Workstreams.insert(ws.id, 'Platform', None, 'u1')
    return team, s


@pytest.mark.asyncio
async def test_task_create_generates_sequential_keys():
    team, s = await _stream()
    t1 = await Tasks.insert(s.id, team.id, team.key, 'First', 'u1')
    t2 = await Tasks.insert(s.id, team.id, team.key, 'Second', 'u1')
    assert t1.key == 'OSL-1' and t1.number == 1
    assert t2.key == 'OSL-2' and t2.number == 2
    assert t1.status == 'backlog' and t1.priority is None and t1.progress == 0
    assert t1.labels == []


@pytest.mark.asyncio
async def test_task_update_and_list_order():
    team, s = await _stream()
    a = await Tasks.insert(s.id, team.id, team.key, 'A', 'u1')
    b = await Tasks.insert(s.id, team.id, team.key, 'B', 'u1')
    await Tasks.update_fields(a.id, {'status': 'todo', 'sort_key': 200.0})
    await Tasks.update_fields(b.id, {'status': 'todo', 'sort_key': 100.0})
    ordered = await Tasks.list_for_workstream(s.id)
    todo = [t.key for t in ordered if t.status == 'todo']
    assert todo == [b.key, a.key]  # ascending sort_key within status


@pytest.mark.asyncio
async def test_labels_crud():
    team, _ = await _stream()
    lab = await Labels.insert(team.id, 'backend', 'cyan')
    assert [x.id for x in await Labels.list_for_team(team.id)] == [lab.id]
    lab2 = await Labels.update_fields(lab.id, {'name': 'infra'})
    assert lab2.name == 'infra'
    assert await Labels.delete(lab.id) is True


@pytest.mark.asyncio
async def test_task_start_date_round_trips():
    team, s = await _stream()
    t = await Tasks.insert(
        s.id, team.id, team.key, 'Scheduled task', 'u1',
        start_date=1_788_120_000_000,
        due_date=1_788_465_600_000,
    )
    assert t.start_date == 1_788_120_000_000
    assert t.due_date == 1_788_465_600_000

    updated = await Tasks.update_fields(t.id, {'start_date': 1_788_206_400_000})
    assert updated.start_date == 1_788_206_400_000


@pytest.mark.asyncio
async def test_subtask_counts_enrich_task_models():
    from open_webui.models.workos import Subtasks

    team, s = await _stream()
    task = await Tasks.insert(s.id, team.id, team.key, 'Parent', 'u1')
    first = await Subtasks.insert(task.id, 'Draft', 'u1')
    await Subtasks.insert(task.id, 'Review', 'u1')
    await Subtasks.update_fields(first.id, {'completed': True})

    reloaded = await Tasks.get_by_id(task.id)
    assert reloaded.subtask_total == 2
    assert reloaded.subtask_completed == 1

    listed = await Tasks.list_for_workstream(s.id)
    parent = next(t for t in listed if t.id == task.id)
    assert parent.subtask_total == 2
    assert parent.subtask_completed == 1
