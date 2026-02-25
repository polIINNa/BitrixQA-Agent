"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0001_initial_schema'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'chats',
        sa.Column('id', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'support_session',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('chat_id', sa.String(), sa.ForeignKey('chats.id'), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('assistant_type', sa.String(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now()),
        sa.Column('edited_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('closed_at', sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'messages',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('support_session_id', sa.String(), sa.ForeignKey('support_session.id'), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('created_at_str', sa.String(), nullable=True),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('assistant_type', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('messages')
    op.drop_table('support_session')
    op.drop_table('chats')
