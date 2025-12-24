import asyncio

from aiogram import types, Bot

from telegram_bot.database import crud
from telegram_bot.database.models import MessageRole, MessageType, AssistantType
from telegram_bot.group_messages.utils import switch_to_human_specialist, clean_message_from_mention, \
    process_agent_response
from telegram_bot.utils import get_or_create_support_session, has_media_content, get_media_info, get_agent_answer


async def handle_group_client_message(
        bot: Bot,
        message: types.Message,
        followup_tasks: dict[str, asyncio.Task],
        operator_id: str
):
    """Обработать сообщение клиента в группе"""
    chat_id = f"{message.chat.id}_{message.from_user.id}"
    support_session = await get_or_create_support_session(chat_id=chat_id)
    task = followup_tasks.pop(chat_id, None)
    if task:
        task.cancel()
    # сохранение сообщения клиента в базе
    has_media_content_flag = False
    if has_media_content(message):
        print("Обнаружен медиа-контент, переключение на специалиста")
        has_media_content_flag  = True
        media_type, content = get_media_info(message)
        await crud.add_message(
            support_session_id=support_session.id,
            content=content,
            role=MessageRole.user,
            type=media_type
        )
    else:
        await crud.add_message(
            support_session_id=support_session.id,
            content=message.text,
            role=MessageRole.user,
            type=MessageType.text
        )
    # выход, если сессию ведет оператор
    if support_session.assistant_type == AssistantType.human:
        print("Отвечает специалист, выход из функции")
        return
    # получение и отправка сообщения клиенту
    if has_media_content_flag:
        print("Переключение на специалиста из-за наличия медиа-контента")
        await switch_to_human_specialist(
            bot=bot,
            support_session=support_session,
            message=message,
            operator_id=operator_id
        )
        return
    print("Попытка ответить от бота")
    session_messages = await crud.get_all_messages(support_session.id)
    answer, chat_history = await get_agent_answer(
        support_session_messages=session_messages,
        user_message=clean_message_from_mention(message.text)
    )
    if answer == "need_human":
        print("Переключение диалога на специалиста")
        await switch_to_human_specialist(
            bot=bot,
            support_session=support_session,
            message=message,
            operator_id=operator_id
        )
        return
    else:
        print("Отвечает бот")
        await process_agent_response(
            support_session=support_session,
            message=message,
            answer=answer,
            chat_id=chat_id,
            followup_tasks=followup_tasks
        )