"""site_view table for Sites analytics

Spec: docs/superpowers/specs/2026-08-29-sites-analytics-design.md

Revision ID: b1c2d3e4f5a6
Revises: e4f5a6b7c8d9
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'site_view',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('site_id', sa.Text(), nullable=False),
        sa.Column('path', sa.Text(), nullable=False),
        sa.Column('visitor_key', sa.Text(), nullable=False),
        sa.Column('is_owner', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_site_view_site_created', 'site_view', ['site_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_site_view_site_created', table_name='site_view')
    op.drop_table('site_view')
