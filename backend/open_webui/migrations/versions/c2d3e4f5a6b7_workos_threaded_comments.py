"""workos threaded comments

Adds ``workos_comment.parent_id`` (threading; NULL = top-level) and
``workos_comment.deleted_at`` (tombstone), plus the
``workos_comment_reaction`` table (6-emoji allowlist enforced at the
router). Existing comments stay top-level (parent_id NULL) — additive only.
Spec: docs/superpowers/specs/2026-07-28-workos-threaded-comments-design.md

Revision ID: c2d3e4f5a6b7
Revises: b0c1d2e3f4a5
Create Date: 2026-07-28 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, None] = 'b0c1d2e3f4a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workos_comment', sa.Column('parent_id', sa.Text(), nullable=True))
    op.add_column('workos_comment', sa.Column('deleted_at', sa.BigInteger(), nullable=True))
    op.create_table(
        'workos_comment_reaction',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('comment_id', sa.Text(), nullable=True),
        sa.Column('user_id', sa.Text(), nullable=True),
        sa.Column('emoji', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('comment_id', 'user_id', 'emoji', name='uq_workos_reaction'),
    )
    op.create_index('ix_workos_comment_parent_id', 'workos_comment', ['parent_id'])
    op.create_index('ix_workos_reaction_comment_id', 'workos_comment_reaction', ['comment_id'])


def downgrade() -> None:
    op.drop_index('ix_workos_reaction_comment_id', table_name='workos_comment_reaction')
    op.drop_index('ix_workos_comment_parent_id', table_name='workos_comment')
    op.drop_table('workos_comment_reaction')
    with op.batch_alter_table('workos_comment') as batch:
        batch.drop_column('deleted_at')
        batch.drop_column('parent_id')
