import pytest

from open_webui.models.workos import Teams, TeamMembers


@pytest.mark.asyncio
async def test_insert_and_get_team():
    team = await Teams.insert(name='Acme', key='OSL', icon=None, created_by_id='u1')
    assert team.name == 'Acme'
    assert team.key == 'OSL'
    assert team.task_seq == 0
    got = await Teams.get_by_id(team.id)
    assert got is not None and got.id == team.id
    assert (await Teams.get_by_key('OSL')).id == team.id


@pytest.mark.asyncio
async def test_next_task_number_increments_atomically():
    team = await Teams.insert(name='Acme', key='OSL', icon=None, created_by_id='u1')
    n1 = await Teams.next_task_number(team.id)
    n2 = await Teams.next_task_number(team.id)
    assert (n1, n2) == (1, 2)
    assert (await Teams.get_by_id(team.id)).task_seq == 2


@pytest.mark.asyncio
async def test_membership_add_list_role_remove():
    team = await Teams.insert(name='Acme', key='OSL', icon=None, created_by_id='u1')
    await TeamMembers.add(team.id, 'u1', 'owner')
    await TeamMembers.add(team.id, 'u2', 'member')
    assert {m.user_id for m in await TeamMembers.list_for_team(team.id)} == {'u1', 'u2'}
    assert (await TeamMembers.get(team.id, 'u1')).role == 'owner'
    await TeamMembers.update_role(team.id, 'u2', 'admin')
    assert (await TeamMembers.get(team.id, 'u2')).role == 'admin'
    assert [t.id for t in await Teams.list_for_user('u2')] == [team.id]
    assert await TeamMembers.remove(team.id, 'u2') is True
    assert await TeamMembers.get(team.id, 'u2') is None
