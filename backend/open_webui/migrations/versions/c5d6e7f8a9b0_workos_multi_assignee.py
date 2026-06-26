"""workos multiple assignees per task

Replaces the single ``workos_task.assignee_id`` text column with an
``assignee_ids`` JSON list (mirroring the existing ``labels`` column).

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-06-26 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c5d6e7f8a9b0'
down_revision: Union[str, None] = 'b4c5d6e7f8a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _task_table(*cols: sa.Column) -> sa.Table:
    # Minimal table reflection so the active dialect serializes JSON correctly.
    return sa.Table('workos_task', sa.MetaData(), *cols)


def upgrade() -> None:
    op.add_column('workos_task', sa.Column('assignee_ids', sa.JSON(), nullable=True))

    tbl = _task_table(
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('assignee_id', sa.Text()),
        sa.Column('assignee_ids', sa.JSON()),
    )
    conn = op.get_bind()
    for row in conn.execute(sa.select(tbl.c.id, tbl.c.assignee_id)):
        value = [row.assignee_id] if row.assignee_id else []
        conn.execute(tbl.update().where(tbl.c.id == row.id).values(assignee_ids=value))

    # Drop the old single-assignee index before the batch rebuild (SQLite reflects
    # remaining indexes; reflecting one on a column we're dropping would fail).
    op.drop_index('ix_workos_task_assignee_id', table_name='workos_task')
    with op.batch_alter_table('workos_task') as batch:
        batch.drop_column('assignee_id')


def downgrade() -> None:
    op.add_column('workos_task', sa.Column('assignee_id', sa.Text(), nullable=True))

    tbl = _task_table(
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('assignee_id', sa.Text()),
        sa.Column('assignee_ids', sa.JSON()),
    )
    conn = op.get_bind()
    for row in conn.execute(sa.select(tbl.c.id, tbl.c.assignee_ids)):
        ids = row.assignee_ids or []
        conn.execute(
            tbl.update().where(tbl.c.id == row.id).values(assignee_id=ids[0] if ids else None)
        )

    op.create_index('ix_workos_task_assignee_id', 'workos_task', ['assignee_id'])
    with op.batch_alter_table('workos_task') as batch:
        batch.drop_column('assignee_ids')
