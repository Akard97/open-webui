"""workos task attachment_required flag

Adds ``workos_task.attachment_required`` — a per-task boolean set by the
creator; when true the task cannot move to ``done`` until it has at least
one attachment (task-level or comment-level).

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-07-15 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f8a9b0c1d2e3'
down_revision: Union[str, None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'workos_task',
        # sa.false() compiles to the right literal per dialect (0 on SQLite, false on Postgres).
        sa.Column('attachment_required', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    with op.batch_alter_table('workos_task') as batch:
        batch.drop_column('attachment_required')
