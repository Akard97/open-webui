import os
import tempfile

_DB_FILE = tempfile.mktemp(suffix='.db')
os.environ['DATABASE_URL'] = f'sqlite:///{_DB_FILE}'
os.environ['ENABLE_DB_MIGRATIONS'] = 'false'

import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402

from open_webui.internal.db import Base, async_engine, engine  # noqa: E402
import open_webui.models.usage  # noqa: E402,F401  (register tables on Base)

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
    tables = [t for name, t in Base.metadata.tables.items() if name in ('usage_event',)]
    async with async_engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.create_all(c, tables=tables))
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(lambda c: Base.metadata.drop_all(c, tables=tables))
