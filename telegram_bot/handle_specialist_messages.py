from aiogram import types

from service import check_support_session_end
from telegram_bot.database import crud
from telegram_bot.database.models import MessageRole, AssistantType, SupportStatus
from telegram_bot.utils import create_chat


async def handle_group_specialist_message(message: types.Message, chat_id: str):
    """Обработать сообщение специалиста"""
    support_session = await crud.get_active_session(chat_id=chat_id)
    await crud.add_message(
        support_session_id=support_session.id,
        content=message.text,
        role=MessageRole.assistant,
        assistant_type=AssistantType.human
    )
    # Проверка на окончание диалога
    support_session_messages = await crud.get_all_messages(support_session_id=support_session.id)
    chat = create_chat(support_session_messages)
    is_support_session_end = await check_support_session_end(chat=chat)
    if is_support_session_end:
        await crud.update_session_status(
            session_id=support_session.id,
            status=SupportStatus.end
        )