import os
import pytest

from open_webui.models.workos import Teams


@pytest.mark.asyncio
async def test_seeder_is_idempotent_and_gated(monkeypatch):
    from open_webui.internal.workos import seeder

    monkeypatch.setattr(seeder, '_first_admin_id', lambda db=None: _async_str('admin1'))

    # Gate off -> no-op
    monkeypatch.delenv('WORKOS_SEED_DEMO', raising=False)
    await seeder.seed_workos_demo()
    assert await Teams.list_all() == []

    # Gate on -> seeds once
    monkeypatch.setenv('WORKOS_SEED_DEMO', 'true')
    await seeder.seed_workos_demo()
    teams = await Teams.list_all()
    assert len(teams) == 1 and teams[0].key == 'OSL'

    # Second run is idempotent
    await seeder.seed_workos_demo()
    assert len(await Teams.list_all()) == 1


def _async_str(v):
    async def _f(db=None):
        return v
    return _f()
