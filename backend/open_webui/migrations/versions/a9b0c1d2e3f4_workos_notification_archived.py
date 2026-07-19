"""workos notification archived flag

Adds ``workos_notification.archived`` — inbox lifecycle state
(unread -> read -> archived). Archiving implies read.

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-07-19 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a9b0c1d2e3f4'
down_revision: Union[str, None] = 'f8a9b0c1d2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'workos_notification',
        # sa.false() compiles to the right literal per dialect (0 on SQLite, false on Postgres).
        sa.Column('archived', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    with op.batch_alter_table('workos_notification') as batch:
        batch.drop_column('archived')
