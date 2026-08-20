"""usage_event table for usage analytics

Spec: docs/superpowers/specs/2026-08-19-usage-analytics-design.md

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'usage_event',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('event_name', sa.Text(), nullable=False),
        sa.Column('tool', sa.Text(), nullable=False),
        sa.Column('properties', sa.JSON(), nullable=True),
        sa.Column('session_id', sa.Text(), nullable=True),
        sa.Column('source', sa.Text(), nullable=False),
        sa.Column('duration_ms', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_usage_event_created_at', 'usage_event', ['created_at'])
    op.create_index('ix_usage_event_user_created', 'usage_event', ['user_id', 'created_at'])
    op.create_index('ix_usage_event_name_created', 'usage_event', ['event_name', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_usage_event_name_created', table_name='usage_event')
    op.drop_index('ix_usage_event_user_created', table_name='usage_event')
    op.drop_index('ix_usage_event_created_at', table_name='usage_event')
    op.drop_table('usage_event')
