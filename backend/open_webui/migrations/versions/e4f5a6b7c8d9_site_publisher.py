"""site table for the Site Publisher bonus tool

Spec: docs/superpowers/specs/2026-08-26-site-publisher-design.md

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'site',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('slug', sa.Text(), nullable=False),
        sa.Column('public', sa.Boolean(), nullable=False),
        sa.Column('files', sa.JSON(), nullable=False),
        sa.Column('entry_file', sa.Text(), nullable=False),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug', name='uq_site_slug'),
    )
    op.create_index('ix_site_user_id', 'site', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_site_user_id', table_name='site')
    op.drop_table('site')
