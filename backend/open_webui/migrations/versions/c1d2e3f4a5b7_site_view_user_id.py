"""attribute site views to the signed-in viewer

Spec: docs/superpowers/specs/2026-08-30-sites-viewers-design.md

Revision ID: c1d2e3f4a5b7
Revises: b1c2d3e4f5a6
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c1d2e3f4a5b7'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: existing rows have no attribution, and anonymous views never
    # will. No backfill — an unattributed past view is the honest record.
    op.add_column('site_view', sa.Column('user_id', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('site_view', 'user_id')
