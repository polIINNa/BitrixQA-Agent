"""add_username_and_chat_type_to_chats

Revision ID: e2bb89ec9ab2
Revises: 
Create Date: 2026-01-17 17:54:44.333868

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2bb89ec9ab2'
down_revision: Union[str, Sequence[str], None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('chats', sa.Column('username', sa.String(), nullable=True))
    op.add_column('chats', sa.Column('chat_type', sa.Enum('PRIVATE', 'GROUP', name='chattype', native_enum=False), nullable=True))
    op.create_index(op.f('ix_chats_username'), 'chats', ['username'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_chats_username'), table_name='chats')
    op.drop_column('chats', 'chat_type')
    op.drop_column('chats', 'username')
