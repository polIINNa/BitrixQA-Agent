import asyncio

from aiogram import Bot, types
from aiogram.methods import ReadBusinessMessage

from telegram_bot.constants import AUTO_REPLY
from telegram_bot.database import crud
from telegram_bot.database.models import MessageRole, MessageType, AssistantType
from telegram_bot.privet_messages.utils import should_send_auto_reply, switch_to_human_specialist, \
    process_agent_response
from telegram_bot.utils import get_or_create_support_session, has_media_content, get_media_info, get_agent_answer


async def handle_client_message(
        message: types.Message,
        bot: Bot,
        followup_tasks: dict[str, asyncio.Task],
        operator_id: str,
        tech_support_account_id: str
) -> None:
    """Обработчик сообщений от пользователя"""
    support_session = await get_or_create_support_session(chat_id=str(message.chat.id))
    # отключение отправки сообщения через 30 минут от бота
    task = followup_tasks.pop(str(message.chat.id), None)
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
        message_text = message.text or ""
        await crud.add_message(
            support_session_id=support_session.id,
            content=message_text,
            role=MessageRole.user,
            type=MessageType.text
        )
    # выход, если сессию ведет оператор
    if support_session.assistant_type == AssistantType.human:
        print("Отвечает специалист, выход из функции")
        return
    # чтение сообщения клиента
    await bot(
        ReadBusinessMessage(
            business_connection_id=message.business_connection_id,
            chat_id=message.chat.id,
            message_id=message.message_id
        )
    )
    # проверка на необходимость отправки сообщения-автоответчика
    should_send_auto_reply_res = await should_send_auto_reply(session_id=support_session.id)
    if should_send_auto_reply_res:
        await bot.send_message(
            chat_id=str(message.chat.id),
            text=AUTO_REPLY,
            business_connection_id=message.business_connection_id
        )
        await crud.add_message(
            support_session_id=support_session.id,
            content=AUTO_REPLY,
            role=MessageRole.system
        )
    session_messages = await crud.get_all_messages(support_session.id)
    # получение и отправка сообщения клиенту
    if has_media_content_flag:
        print("Переключение на специалиста из-за наличия медиа-контента")
        await switch_to_human_specialist(
            support_session=support_session,
            bot=bot,
            chat_id=str(message.chat.id),
            business_connection_id=message.business_connection_id,
            username=message.from_user.username,
            operator_id=operator_id,
            tech_support_account_id=tech_support_account_id
        )
        return
    print("Попытка ответить от бота")
    answer, chat_history = await get_agent_answer(support_session_messages=session_messages, user_message=message_text)
    if answer == "need_human":
        print("Переключение диалога на специалиста")
        await switch_to_human_specialist(
            support_session=support_session,
            bot=bot,
            chat_id=str(message.chat.id),
            business_connection_id=message.business_connection_id,
            username=message.from_user.username,
            operator_id=operator_id,
            tech_support_account_id=tech_support_account_id
        )
        return
    else:
        print("Отвечает бот")
        await process_agent_response(
            bot=bot,
            support_session=support_session,
            answer=answer,
            chat_id=str(message.chat.id),
            business_connection_id=message.business_connection_id,
            followup_tasks=followup_tasks
        )
