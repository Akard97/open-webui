"""add policy document table

Revision ID: c3d4e5f6a7b8
Revises: 4f7f6e821be6
Create Date: 2026-06-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = '4f7f6e821be6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'policy_document',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('owner_type', sa.Text(), nullable=True),
        sa.Column('owner_id', sa.Text(), nullable=True),
        sa.Column('filename', sa.Text(), nullable=True),
        sa.Column('content_type', sa.Text(), nullable=True),
        sa.Column('size', sa.BigInteger(), nullable=True),
        sa.Column('storage_path', sa.Text(), nullable=True),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('owner_type', 'owner_id', name='uq_policy_document_owner'),
    )
    op.create_index('ix_policy_document_owner', 'policy_document', ['owner_type', 'owner_id'])


def downgrade() -> None:
    op.drop_index('ix_policy_document_owner', table_name='policy_document')
    op.drop_table('policy_document')
