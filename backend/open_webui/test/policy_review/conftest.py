import os
import tempfile

# Must run before importing open_webui.* — these configure the engine at import time.
_DB_FILE = tempfile.mktemp(suffix='.db')
os.environ['DATABASE_URL'] = f'sqlite:///{_DB_FILE}'
os.environ['ENABLE_DB_MIGRATIONS'] = 'false'

import pytest_asyncio
from sqlalchemy import select  # noqa: E402

from open_webui.internal.db import Base, async_engine, get_async_db  # noqa: E402
import open_webui.models.policy_review  # noqa: E402,F401  (register tables on Base)


@pytest_asyncio.fixture(autouse=True)
async def _create_schema():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
