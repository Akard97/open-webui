import os
import tempfile

# Must run before importing open_webui.* — these configure the engine at import
# time (same dance as the policy_review suite).
_DB_FILE = tempfile.mktemp(suffix='.db')
os.environ['DATABASE_URL'] = f'sqlite:///{_DB_FILE}'
os.environ['ENABLE_DB_MIGRATIONS'] = 'false'

from sqlalchemy import text  # noqa: E402

from open_webui.internal.db import engine  # noqa: E402

# open_webui.config runs `CONFIG_DATA = get_config()` at import time; migrations
# are off, so create the table it reads before any test module imports it.
with engine.begin() as _conn:
    _conn.execute(
        text(
            'CREATE TABLE IF NOT EXISTS config ('
            'id INTEGER PRIMARY KEY, data JSON, version INTEGER, '
            'created_at TIMESTAMP, updated_at TIMESTAMP)'
        )
    )
