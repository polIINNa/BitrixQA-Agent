"""Сервис бизнес-правил."""
import logging
from datetime import datetime, timedelta

from telegram_bot.database import crud
from telegram_bot.database.models import Message

logger = logging.getLogger(__name__)


async def should_send_auto_reply(session_id: str) -> bool:
    """
    Определяет, нужно ли отправить автоответ.
    
    Автоответ отправляется:
    - При первом сообщении в первой сессии
    - Если последнее сообщение было более 14 дней назад
    """
    session_messages = await crud.get_all_messages(session_id)
    
    # Первая сессия и первое сообщение
    session_number = _get_session_number(session_id)
    if session_number == 1 and len(session_messages) == 1:
        return True
    
    # Проверка давности последнего сообщения
    if not session_messages:
        return True
    return _is_message_older_than_days(session_messages[-1], days=14)


async def should_show_ad_on_positive_acknowledgement(session_id: str) -> bool:
    """
    Определяет, показывать ли рекламу при положительном отклике.
    
    Реклама показывается если последнее сообщение было более 10 дней назад.
    """
    session_messages = await crud.get_all_messages(session_id)
    if not session_messages:
        return True
    return _is_message_older_than_days(session_messages[-1], days=10)


def _get_session_number(session_id: str) -> int:
    """Извлечь номер сессии из session_id."""
    try:
        return int(session_id.rsplit("_", 1)[-1])
    except (ValueError, IndexError):
        return 0


def _is_message_older_than_days(message: Message, days: int) -> bool:
    """Проверить, старше ли сообщение указанного количества дней."""
    if not message.created_at_str:
        return True
    
    try:
        message_date = datetime.fromisoformat(message.created_at_str)
        return datetime.now() - message_date >= timedelta(days=days)
    except Exception as e:
        logger.warning(f"Ошибка парсинга даты: {e}")
        return True
