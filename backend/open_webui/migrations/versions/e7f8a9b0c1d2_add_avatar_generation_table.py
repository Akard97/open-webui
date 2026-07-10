"""add avatar_generation table

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-07-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, None] = 'd6e7f8a9b0c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'avatar_generation',
        sa.Column('user_id', sa.Text(), primary_key=True),
        sa.Column('date', sa.Text(), primary_key=True),
        sa.Column('count', sa.BigInteger(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_table('avatar_generation')
