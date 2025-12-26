import asyncio

from aiogram import Bot, types
from aiogram.methods import ReadBusinessMessage

from telegram_bot.constants import AUTO_REPLY
from telegram_bot.database import crud
from telegram_bot.database.models import MessageRole, MessageType, AssistantType
from telegram_bot.privet_messages.utils import should_send_auto_reply, switch_to_human_specialist, \
    process_agent_response
from telegram_bot.utils import get_or_create_support_session, has_media_content, get_media_content, get_agent_answer
from service import get_user_message_from_media


async def handle_client_message(
        message: types.Message,
        bot: Bot,
        followup_tasks: dict[str, asyncio.Task],
        operator_id: str,
        tech_support_account_id: str
) -> None:
    """Обработчик сообщений от пользователя"""
    chat_id = str(message.chat.id)
    support_session = await get_or_create_support_session(chat_id=chat_id)
    # отключение отправки сообщения через 30 минут от бота
    task = followup_tasks.pop(chat_id, None)
    if task:
        task.cancel()
    # определения сообщения клиента, сохранение сообщения клиента в базе данных
    if has_media_content(message):
        print("Обработка медиа-контента")
        media_data = await get_media_content(message, bot)
        await crud.add_message(
            support_session_id=support_session.id,
            role=MessageRole.user,
            type=media_data["media_type"],
        )
        user_message = await get_user_message_from_media(
            type=media_data["media_type"],
            content=media_data["content"],
            caption=media_data["caption"] if "caption" in media_data else None,
        )
    else:
        user_message = message.text
        await crud.add_message(
            support_session_id=support_session.id,
            content=user_message,
            role=MessageRole.user,
            type=MessageType.text
        )
    # выход, если сессию ведет оператор
    if support_session.assistant_type == AssistantType.human:
        print("Сессию ведет специалист, выход из функции")
        return
    print("Сессию ведет бот")
    # чтение сообщения клиента
    await bot(
        ReadBusinessMessage(
            business_connection_id=message.business_connection_id,
            chat_id=int(chat_id),
            message_id=message.message_id
        )
    )
    # проверка на необходимость отправки сообщения-автоответчика
    should_send_auto_reply_res = await should_send_auto_reply(session_id=support_session.id)
    if should_send_auto_reply_res:
        await bot.send_message(
            chat_id=chat_id,
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
    if user_message is None:
        print("Переключение на специалиста из-за невозможности определения сообщения клиента")
        await switch_to_human_specialist(
            support_session=support_session,
            bot=bot,
            chat_id=chat_id,
            business_connection_id=message.business_connection_id,
            username=message.from_user.username,
            operator_id=operator_id,
            tech_support_account_id=tech_support_account_id
        )
        return
    print("Попытка ответить от бота")
    answer, chat_history = await get_agent_answer(support_session_messages=session_messages, user_message=user_message)
    if answer == "need_human":
        print("Бот определил необходимость переключить диалог на специалиста")
        await switch_to_human_specialist(
            support_session=support_session,
            bot=bot,
            chat_id=chat_id,
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
            chat_id=chat_id,
            business_connection_id=message.business_connection_id,
            followup_tasks=followup_tasks
        )
