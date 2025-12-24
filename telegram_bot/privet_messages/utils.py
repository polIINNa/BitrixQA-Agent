import asyncio
from datetime import datetime, timedelta

from aiogram import Bot

from service import check_support_session_end
from telegram_bot.constants import CHECK_USER_MESSAGE, NEED_HUMAN_MESSAGE_WITH_GREETINGS, NEED_HUMAN_MESSAGE
from telegram_bot.database import crud
from telegram_bot.database.models import MessageRole, SupportSession, AssistantType, SupportStatus
from telegram_bot.utils import create_chat


async def schedule_followup(
        chat_id: str, business_connection_id: str, support_session_id: str, bot: Bot
) -> None:
    """Отправить сообщение с вопросом 'все ли клиенту понятно'"""
    await asyncio.sleep(1800)
    await crud.add_message(
        support_session_id=support_session_id,
        content=CHECK_USER_MESSAGE,
        role=MessageRole.system
    )
    await bot.send_message(
        chat_id=chat_id,
        text=CHECK_USER_MESSAGE,
        business_connection_id=business_connection_id
    )


async def switch_to_human_specialist(
    support_session: SupportSession,
    bot: Bot,
    chat_id: str,
    username: str,
    business_connection_id: str,
    operator_id: str,
    tech_support_account_id: str
) -> None:
    """Переключить сессию на специалиста и отправляет сообщение пользователю"""
    # проверяем, первое ли это сообщение клиента
    support_session_messages = await crud.get_all_messages(support_session_id=support_session.id)
    user_messages = 0
    for message in support_session_messages:
        if message.role == MessageRole.user:
            user_messages += 1
    if user_messages == 1:
        text = NEED_HUMAN_MESSAGE_WITH_GREETINGS
    else:
        text = NEED_HUMAN_MESSAGE
    # обновление типа ассистента на human и отправка сообщения
    await crud.update_session_assistant_type(
        session_id=support_session.id,
        assistant_type=AssistantType.human
    )
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        business_connection_id=business_connection_id
    )
    # отправка уведомления специалисту
    chat_link = f"https://t.me/{username}"
    await bot.send_message(
        chat_id=operator_id,
        text=f"Бот перевел поддержку на специалиста ЛИЧНЫЕ СООБЩЕНИЯ"
    )
    await bot.send_message(
        chat_id=tech_support_account_id,
        text=f"Ссылка на чат для специалиста: {chat_link}"
    )

async def should_send_auto_reply(session_id: str) -> bool:
    """Решает, нужен ли сообщение-автоответчика"""
    session_messages = await crud.get_all_messages(session_id)
    if session_id.split("_")[1] == "1" and len(session_messages) == 1:
        return True
    last_message = session_messages[-1]
    if last_message.created_at_str:
        try:
            last_date = datetime.fromisoformat(last_message.created_at_str)
            if datetime.now() - last_date >= timedelta(days=14):
                return True
        except Exception as e:
            print(f"Ошибка парсинга даты: {e}")
            return True
    else:
        return True
    return False


async def process_agent_response(
    bot: Bot,
    support_session: SupportSession,
    answer: str,
    chat_id: str,
    business_connection_id: str,
    followup_tasks: dict[str, asyncio.Task]
) -> None:
    """Обработка ответа агента: сохранение в БД, установка таймера, отправка сообщения клиенту"""
    await crud.add_message(
        support_session_id=support_session.id,
        content=answer,
        role=MessageRole.assistant,
        assistant_type=AssistantType.ai
    )
    # удаление старой задачи с сообщением с напоминанием
    old_task = followup_tasks.pop(chat_id, None)
    if old_task:
        old_task.cancel()
    # Проверка на окончание диалога
    support_session_messages = await crud.get_all_messages(support_session_id=support_session.id)
    chat = create_chat(support_session_messages=support_session_messages)
    is_support_session_end = await check_support_session_end(chat=chat)
    if is_support_session_end:
        await crud.update_session_status(
            session_id=support_session.id,
            status=SupportStatus.end
        )
    else:
        # установка таймера 30 мин для отправки уведомления клиенту
        task = asyncio.create_task(schedule_followup(
            bot=bot,
            chat_id=chat_id,
            business_connection_id=business_connection_id,
            support_session_id=support_session.id
        ))
        followup_tasks[chat_id] = task
    # Отправка ответа пользователю
    await bot.send_message(
        chat_id=chat_id,
        text=answer,
        business_connection_id=business_connection_id
    )