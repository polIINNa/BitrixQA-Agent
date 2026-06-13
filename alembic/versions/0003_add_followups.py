"""add followups table

Revision ID: 0003_add_followups
Revises: e2bb89ec9ab2
Create Date: 2026-06-13

Аддитивная миграция: создаёт таблицу followups для персистентных напоминаний.
Существующие таблицы не затрагиваются, бэкфилл не нужен.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003_add_followups'
down_revision: Union[str, Sequence[str], None] = 'e2bb89ec9ab2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'followups',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('support_session_id', sa.String(), nullable=False),
        sa.Column('chat_id', sa.String(), nullable=False),
        sa.Column('send_chat_id', sa.String(), nullable=False),
        sa.Column('business_connection_id', sa.String(), nullable=True),
        sa.Column('reply_to_message_id', sa.Integer(), nullable=True),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('scheduled_at', sa.TIMESTAMP(), nullable=False),
        sa.Column(
            'status',
            sa.Enum('pending', 'sent', 'cancelled', name='followupstatus', native_enum=False),
            nullable=False,
        ),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['support_session_id'], ['support_session.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_followups_chat_id'), 'followups', ['chat_id'], unique=False)
    op.create_index(op.f('ix_followups_scheduled_at'), 'followups', ['scheduled_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_followups_scheduled_at'), table_name='followups')
    op.drop_index(op.f('ix_followups_chat_id'), table_name='followups')
    op.drop_table('followups')
