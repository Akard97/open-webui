"""add workos tables

Revision ID: f0a1b2c3d4e5
Revises: c3d4e5f6a7b8
Create Date: 2026-06-22 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f0a1b2c3d4e5'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'workos_team',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('key', sa.Text(), nullable=True),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('icon', sa.Text(), nullable=True),
        sa.Column('task_seq', sa.BigInteger(), nullable=True),
        sa.Column('archived', sa.Boolean(), nullable=True),
        sa.Column('created_by_id', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    op.create_table(
        'workos_team_member',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('team_id', sa.Text(), nullable=True),
        sa.Column('user_id', sa.Text(), nullable=True),
        sa.Column('role', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'user_id', name='uq_workos_team_member'),
    )
    op.create_index('ix_workos_team_member_user_id', 'workos_team_member', ['user_id'])
    op.create_table(
        'workos_workspace',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('team_id', sa.Text(), nullable=True),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('icon', sa.Text(), nullable=True),
        sa.Column('visibility', sa.Text(), nullable=True),
        sa.Column('archived', sa.Boolean(), nullable=True),
        sa.Column('created_by_id', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_workos_workspace_team_id', 'workos_workspace', ['team_id'])
    op.create_table(
        'workos_workspace_member',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('workspace_id', sa.Text(), nullable=True),
        sa.Column('user_id', sa.Text(), nullable=True),
        sa.Column('role', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'user_id', name='uq_workos_workspace_member'),
    )
    op.create_table(
        'workos_workstream',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('workspace_id', sa.Text(), nullable=True),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('icon', sa.Text(), nullable=True),
        sa.Column('archived', sa.Boolean(), nullable=True),
        sa.Column('created_by_id', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_workos_workstream_workspace_id', 'workos_workstream', ['workspace_id'])
    op.create_table(
        'workos_label',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('team_id', sa.Text(), nullable=True),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('color', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'workos_task',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('workstream_id', sa.Text(), nullable=True),
        sa.Column('team_id', sa.Text(), nullable=True),
        sa.Column('number', sa.BigInteger(), nullable=True),
        sa.Column('key', sa.Text(), nullable=True),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('priority', sa.Text(), nullable=True),
        sa.Column('assignee_id', sa.Text(), nullable=True),
        sa.Column('due_date', sa.BigInteger(), nullable=True),
        sa.Column('progress', sa.Integer(), nullable=True),
        sa.Column('labels', sa.JSON(), nullable=True),
        sa.Column('sort_key', sa.Float(), nullable=True),
        sa.Column('created_by_id', sa.Text(), nullable=True),
        sa.Column('completed_at', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_workos_task_workstream_id', 'workos_task', ['workstream_id'])
    op.create_index('ix_workos_task_assignee_id', 'workos_task', ['assignee_id'])


def downgrade() -> None:
    op.drop_index('ix_workos_task_assignee_id', table_name='workos_task')
    op.drop_index('ix_workos_task_workstream_id', table_name='workos_task')
    op.drop_table('workos_task')
    op.drop_table('workos_label')
    op.drop_index('ix_workos_workstream_workspace_id', table_name='workos_workstream')
    op.drop_table('workos_workstream')
    op.drop_table('workos_workspace_member')
    op.drop_index('ix_workos_workspace_team_id', table_name='workos_workspace')
    op.drop_table('workos_workspace')
    op.drop_index('ix_workos_team_member_user_id', table_name='workos_team_member')
    op.drop_table('workos_team_member')
    op.drop_table('workos_team')
