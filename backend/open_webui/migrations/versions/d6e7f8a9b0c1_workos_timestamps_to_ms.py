"""workos timestamps to epoch milliseconds

``_now()`` in ``open_webui.models.workos`` previously stamped nanosecond
epochs (``time.time_ns()``); it now stamps milliseconds to match
client-supplied dates and the frontend, which treats all WorkOS timestamps
as Unix ms. This converts existing nanosecond-scale rows in place.

Guard: today's epoch ms is ~1.8e12, epoch ns is ~1.8e18 — comparing against
1e15 unambiguously separates the two scales, and re-running the migration
against already-converted (ms-scale) rows is a no-op since ms values never
exceed 1e15.

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-07-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'd6e7f8a9b0c1'
down_revision: Union[str, None] = 'c5d6e7f8a9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, column) pairs for BigInteger epoch-timestamp columns.
_TIMESTAMP_COLUMNS = [
    ('workos_team', 'created_at'),
    ('workos_team', 'updated_at'),
    ('workos_team_member', 'created_at'),
    ('workos_workspace', 'created_at'),
    ('workos_workspace', 'updated_at'),
    ('workos_workspace_member', 'created_at'),
    ('workos_workstream', 'created_at'),
    ('workos_workstream', 'updated_at'),
    ('workos_task', 'created_at'),
    ('workos_task', 'updated_at'),
    ('workos_task', 'completed_at'),
    ('workos_subtask', 'created_at'),
    ('workos_subtask', 'updated_at'),
    ('workos_subtask', 'completed_at'),
    ('workos_label', 'created_at'),
    ('workos_comment', 'created_at'),
    ('workos_comment', 'updated_at'),
    ('workos_comment', 'edited_at'),
    ('workos_activity', 'created_at'),
    ('workos_attachment', 'created_at'),
    ('workos_notification', 'created_at'),
]

# (table, column) pairs for Float sort-key columns sharing the same scale.
_SORT_KEY_COLUMNS = [
    ('workos_task', 'sort_key'),
    ('workos_subtask', 'sort_key'),
]


def upgrade() -> None:
    for table, col in _TIMESTAMP_COLUMNS + _SORT_KEY_COLUMNS:
        op.execute(f'UPDATE {table} SET {col} = {col} / 1000000 WHERE {col} > 1000000000000000')


def downgrade() -> None:
    for table, col in _TIMESTAMP_COLUMNS + _SORT_KEY_COLUMNS:
        op.execute(f'UPDATE {table} SET {col} = {col} * 1000000 WHERE {col} < 1000000000000000')
