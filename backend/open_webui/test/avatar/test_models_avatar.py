import pytest

from open_webui.models.avatar import AvatarGenerations


@pytest.mark.asyncio
async def test_get_count_defaults_to_zero():
    assert await AvatarGenerations.get_count('u1', '2026-07-11') == 0


@pytest.mark.asyncio
async def test_increment_creates_then_counts_up():
    assert await AvatarGenerations.increment('u1', '2026-07-11') == 1
    assert await AvatarGenerations.increment('u1', '2026-07-11') == 2
    assert await AvatarGenerations.get_count('u1', '2026-07-11') == 2


@pytest.mark.asyncio
async def test_counts_are_per_user_and_per_day():
    await AvatarGenerations.increment('u1', '2026-07-11')
    assert await AvatarGenerations.get_count('u2', '2026-07-11') == 0
    assert await AvatarGenerations.get_count('u1', '2026-07-12') == 0
