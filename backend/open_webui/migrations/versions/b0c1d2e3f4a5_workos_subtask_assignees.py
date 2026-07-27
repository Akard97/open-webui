"""workos subtask assignees

Adds ``workos_subtask.assignee_ids`` as a JSON list (mirroring
``workos_task.assignee_ids``). Pre-feature subtasks stay unassigned
(spec 2026-07-28, decision 4) but rows are backfilled to ``[]`` — NOT
left NULL — because ``SubtaskModel.assignee_ids: list = []`` rejects an
explicit ``None`` (pydantic defaults apply only to MISSING attributes).
Same posture as the task-side migration c5d6e7f8a9b0.

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
Create Date: 2026-07-28 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b0c1d2e3f4a5'
down_revision: Union[str, None] = 'a9b0c1d2e3f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workos_subtask', sa.Column('assignee_ids', sa.JSON(), nullable=True))
    # Backfill every existing row to [] so model validation never sees NULL.
    tbl = sa.Table(
        'workos_subtask', sa.MetaData(),
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('assignee_ids', sa.JSON()),
    )
    op.get_bind().execute(tbl.update().values(assignee_ids=[]))


def downgrade() -> None:
    with op.batch_alter_table('workos_subtask') as batch:
        batch.drop_column('assignee_ids')
