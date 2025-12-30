import asyncio

from aiogram import Bot, types
from aiogram.methods import ReadBusinessMessage
from aiogram.types import ReactionTypeEmoji

from telegram_bot.constants import AUTO_REPLY
from telegram_bot.database import crud
from telegram_bot.database.models import MessageRole, MessageType, AssistantType, SupportStatus, SupportSession
from telegram_bot.privet_messages.utils import should_send_auto_reply, switch_to_human_specialist, \
    process_agent_response
from telegram_bot.utils import get_active_support_session, has_media_content, get_media_content, get_agent_answer, \
    _save_user_message_to_db, format_chat_from_message
from service import get_user_message_from_media, is_new_intent_check


async def handle_client_message(
        message: types.Message,
        bot: Bot,
        followup_tasks: dict[str, asyncio.Task],
        operator_id: str,
        tech_support_account_id: str
) -> None:
    """Обработчик сообщений от пользователя"""
    chat_id = str(message.chat.id)
    task = followup_tasks.pop(chat_id, None)
    if task:
        task.cancel()
    has_media_content_flag = False
    if has_media_content(message):
        print("Сообщение клиента содержит медиа-контент")
        has_media_content_flag = True
        media_data = await get_media_content(message, bot)
        message_text_content = await get_user_message_from_media(
            type=media_data["media_type"],
            content=media_data["content"],
            caption=media_data["caption"] if "caption" in media_data else None,
        )
    else:
        print("Сообщение клиента просто текст")
        media_data = None
        message_text_content = message.text
    support_session = await get_active_support_session(chat_id=chat_id)
    if support_session:
        print("Есть действующая сессия")
        print("Определить наличие нового интента")
        session_messages = await crud.get_all_messages(support_session.id)
        chat_history = format_chat_from_message(support_session_messages=session_messages)
        # TODO: обработка кейса, когда не удается распознать сообщение клиента
        is_new_intent = await is_new_intent_check(chat_history=chat_history, last_user_message=message_text_content)
        if is_new_intent:
            print("Обнаружен новый интент, создание новой сессии")
            await crud.update_session_status(session_id=support_session.id, status=SupportStatus.end)
            support_session = await crud.create_support_session(chat_id=chat_id)
        else:
            print("Интент не поменялся, обработка действующей сессии")
    else:
        print("Нет действующей сессии, создание новой")
        support_session = await crud.create_support_session(chat_id=chat_id)
    await _save_user_message_to_db(
        has_media_content_flag=has_media_content_flag,
        support_session=support_session,
        message_text_content=message_text_content,
        media_data=media_data
    )
    print("Проверка на автоответчик")
    should_send_auto_reply_res = await should_send_auto_reply(session_id=support_session.id)
    if should_send_auto_reply_res:
        await bot.send_message(
            chat_id=chat_id,
            text=AUTO_REPLY,
            business_connection_id=message.business_connection_id
        )
    if support_session.assistant_type == AssistantType.human:
        print("Сессию ведет специалист, выход из функции")
        return
    print("Сессию ведет бот")
    await process_active_session(
        support_session=support_session,
        chat_id=chat_id,
        bot=bot,
        message=message,
        message_text_content=message_text_content,
        operator_id=operator_id,
        tech_support_account_id=tech_support_account_id,
        followup_tasks=followup_tasks,
    )


async def process_active_session(
        support_session: SupportSession,
        chat_id: str,
        bot: Bot,
        message: types.Message,
        operator_id: str,
        tech_support_account_id: str,
        followup_tasks: dict,
        message_text_content: str | None = None,
) -> None:
    """Обработать сообщение клиента в действующей сессии"""
    await bot(
        ReadBusinessMessage(
            business_connection_id=message.business_connection_id,
            chat_id=int(chat_id),
            message_id=message.message_id
        )
    )
    print("Проверка на необходимость ответа")
    session_messages = await crud.get_all_messages(support_session.id)
    chat_history = format_chat_from_message(support_session_messages=session_messages)
    need_reply = await need_reply(chat_history=chat_history, user_message=message_text_content)
    if not need_reply:
        print("Нет необходимости отвечать, проставление реакции")
        await message.bot.set_message_reaction(
            chat_id=chat_id,
            message_id=message.message_id,
            reaction=[ReactionTypeEmoji(emoji="👍")],
            is_big=False)
        return
    print("Есть необходимость в получении ответа")
    if message_text_content is None:
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
    answer, chat_history = await get_agent_answer(support_session_messages=session_messages, user_message=message_text_content)
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