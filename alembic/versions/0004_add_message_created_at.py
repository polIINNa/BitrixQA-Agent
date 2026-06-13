"""add real created_at to messages

Revision ID: 0004_add_message_created_at
Revises: 0003_add_followups
Create Date: 2026-06-13

Аддитивная миграция: добавляет messages.created_at (реальный TIMESTAMP) для
детерминированной сортировки истории — у created_at_str точность до секунды, порядок
внутри секунды не определён. Бэкфилл существующих строк из created_at_str; новые
сообщения пишутся с микросекундной точностью. created_at_str не трогаем (его ещё
парсит дата-логика chat_flow).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004_add_message_created_at'
down_revision: Union[str, Sequence[str], None] = '0003_add_followups'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('messages', sa.Column('created_at', sa.TIMESTAMP(), nullable=True))
    # Бэкфилл из строкового времени. Postgres кастит ISO-строку с 'T' к timestamp.
    op.execute(
        "UPDATE messages SET created_at = created_at_str::timestamp "
        "WHERE created_at_str IS NOT NULL AND created_at_str <> ''"
    )
    # Индекс под основной запрос истории (фильтр по сессии + сортировка по времени).
    op.create_index(
        op.f('ix_messages_session_created'), 'messages',
        ['support_session_id', 'created_at'], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_messages_session_created'), table_name='messages')
    op.drop_column('messages', 'created_at')
