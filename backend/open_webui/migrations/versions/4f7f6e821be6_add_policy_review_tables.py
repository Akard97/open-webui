"""add policy review tables

Revision ID: 4f7f6e821be6
Revises: a0b1c2d3e4f5
Create Date: 2026-06-15 22:33:10.512406

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = '4f7f6e821be6'
down_revision: Union[str, None] = 'a0b1c2d3e4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'policy_checklist_version',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('label', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('published_at', sa.BigInteger(), nullable=True),
        sa.Column('published_by_id', sa.Text(), nullable=True),
        sa.Column('published_by_name', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_policy_checklist_version_status', 'policy_checklist_version', ['status'])

    op.create_table(
        'policy_review',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('policy_meta', sa.JSON(), nullable=True),
        sa.Column('checklist_version_id', sa.Text(), nullable=True),
        sa.Column('checklist_snapshot', sa.JSON(), nullable=True),
        sa.Column('results', sa.JSON(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('approval', sa.JSON(), nullable=True),
        sa.Column('strengths', sa.JSON(), nullable=True),
        sa.Column('created_by_id', sa.Text(), nullable=True),
        sa.Column('created_by_name', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_policy_review_created_by_id', 'policy_review', ['created_by_id'])
    op.create_index('ix_policy_review_status', 'policy_review', ['status'])

    op.create_table(
        'policy_library',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('code', sa.Text(), nullable=True),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('source_review_id', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )

    op.create_table(
        'policy_audit',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('entity_type', sa.Text(), nullable=True),
        sa.Column('entity_id', sa.Text(), nullable=True),
        sa.Column('action', sa.Text(), nullable=True),
        sa.Column('actor_id', sa.Text(), nullable=True),
        sa.Column('actor_name', sa.Text(), nullable=True),
        sa.Column('detail', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_policy_audit_entity', 'policy_audit', ['entity_type', 'entity_id'])


def downgrade() -> None:
    op.drop_index('ix_policy_audit_entity', table_name='policy_audit')
    op.drop_table('policy_audit')
    op.drop_table('policy_library')
    op.drop_index('ix_policy_review_status', table_name='policy_review')
    op.drop_index('ix_policy_review_created_by_id', table_name='policy_review')
    op.drop_table('policy_review')
    op.drop_index('ix_policy_checklist_version_status', table_name='policy_checklist_version')
    op.drop_table('policy_checklist_version')
