"""add workos task schedule and subtasks

Revision ID: b4c5d6e7f8a9
Revises: a2b3c4d5e6f7
Create Date: 2026-06-24 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b4c5d6e7f8a9'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workos_task', sa.Column('start_date', sa.BigInteger(), nullable=True))
    op.create_table(
        'workos_subtask',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('task_id', sa.Text(), nullable=True),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('completed', sa.Boolean(), nullable=True),
        sa.Column('sort_key', sa.Float(), nullable=True),
        sa.Column('created_by_id', sa.Text(), nullable=True),
        sa.Column('completed_at', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_workos_subtask_task_id', 'workos_subtask', ['task_id'])


def downgrade() -> None:
    op.drop_index('ix_workos_subtask_task_id', table_name='workos_subtask')
    op.drop_table('workos_subtask')
    op.drop_column('workos_task', 'start_date')
