import os
import tempfile

# Must run before importing open_webui.* — these configure the engine at import time.
_DB_FILE = tempfile.mktemp(suffix='.db')
os.environ['DATABASE_URL'] = f'sqlite:///{_DB_FILE}'
os.environ['ENABLE_DB_MIGRATIONS'] = 'false'

import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402

from open_webui.internal.db import Base, async_engine, engine  # noqa: E402
import open_webui.models.sites  # noqa: E402,F401  (register tables on Base)
import open_webui.models.access_grants  # noqa: E402,F401
import open_webui.models.groups  # noqa: E402,F401

# Pre-create the config table read at import time by open_webui.config
# (migrations are disabled for tests). Same workaround as test/policy_review.
with engine.begin() as _conn:
    _conn.execute(
        text(
            'CREATE TABLE IF NOT EXISTS config ('
            'id INTEGER PRIMARY KEY, data JSON, version INTEGER, '
            'created_at TIMESTAMP, updated_at TIMESTAMP)'
        )
    )


@pytest_asyncio.fixture(autouse=True)
async def _create_schema():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
