import os
import sys
import asyncio
import logging

from dotenv import load_dotenv
from aiogram.enums import ParseMode
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties

from telegram_bot.database import crud, models
from telegram_bot.utils import (
    create_chat_history,
    has_media_content,
    get_media_info,
    get_or_create_support_session,
    get_chat_history
)
from telegram_bot.constants import NEED_HUMAN_MESSAGE
from service import get_answer, check_support_session_end, get_answer_test


load_dotenv()
TOKEN = os.environ["TELEGRAM_API_TOKEN"]

dp = Dispatcher()
bot = Bot(
    TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)


@dp.business_message()
async def handle_business_message(message: types.Message):
    """Обработка сообщений"""
    if message.from_user.id == int(os.environ["ADMIN_USER_ID"]):
        print("Обработка сообщения специалиста")
        await handle_specialist_message(message=message)
    else:
        print("Обработка сообщения пользователя")
        await handle_client_message(message=message)


async def switch_to_human_specialist(
    support_session: models.SupportSession,
    chat_id: int,
    business_connection_id: str | None = None
) -> None:
    """Переключает сессию на специалиста и отправляет сообщение пользователю"""
    await crud.update_session_assistant_type(
        session_id=support_session.id,
        assistant_type=models.AssistantType.human
    )
    await bot.send_message(
        chat_id=chat_id,
        text=NEED_HUMAN_MESSAGE,
        business_connection_id=business_connection_id
    )


async def handle_media_message(
    message: types.Message,
    support_session: models.SupportSession
) -> None:
    """Обрабатывает медиа-сообщение: сохраняет и переключает на специалиста"""
    print("Обнаружен медиа-контент, переключение на специалиста")
    media_type, content = get_media_info(message)
    
    await crud.add_message(
        support_session_id=support_session.id,
        content=content,
        role=models.MessageRole.user,
        type=media_type
    )
    
    await switch_to_human_specialist(
        support_session=support_session,
        chat_id=message.chat.id,
        business_connection_id=message.business_connection_id
    )


async def get_ai_answer(
    support_session: models.SupportSession,
    user_message: str
) -> tuple[str, str | None]:
    """Получает ответ от AI на основе истории диалога"""
    chat_history = await get_chat_history(support_session)
    answer = await get_answer_test(chat_history=chat_history, last_user_message=user_message)
    return answer, chat_history


async def process_ai_response(
    support_session: models.SupportSession,
    answer: str,
    chat_history: str | None,
    chat_id: int,
    business_connection_id: str | None = None
) -> None:
    """Обрабатывает ответ от AI: сохраняет, проверяет окончание сессии и отправляет"""
    await crud.add_message(
        support_session_id=support_session.id,
        content=answer,
        role=models.MessageRole.assistant,
        assistant_type=models.AssistantType.ai
    )
    
    # Проверка на окончание диалога
    full_chat = f"{chat_history}\nАссистент: {answer}" if chat_history else f"Ассистент: {answer}"
    is_support_session_end = await check_support_session_end(chat=full_chat)
    if is_support_session_end:
        await crud.update_session_status(
            session_id=support_session.id,
            status=models.SupportStatus.end
        )
    
    # Отправка ответа пользователю
    await bot.send_message(
        chat_id=chat_id,
        text=answer,
        business_connection_id=business_connection_id
    )


async def handle_client_message(message: types.Message):
    """Обработка сообщений от пользователя"""
    message_preview = message.text or message.caption or '[Медиа-контент]'
    print(f"ID чата: {message.chat.id}.\nСообщение пользователя: {message_preview}")
    
    # Получение или создание сессии поддержки
    support_session = await get_or_create_support_session(message.chat.id)
    
    # Обработка медиа-контента
    if has_media_content(message):
        await handle_media_message(message, support_session)
        return
    
    # Обработка текстового сообщения
    message_text = message.text or ""
    await crud.add_message(
        support_session_id=support_session.id,
        content=message_text,
        role=models.MessageRole.user
    )
    
    # Проверка, не переключен ли уже диалог на специалиста
    if support_session.assistant_type == models.AssistantType.human:
        print("Отвечает специалист, выход из функции")
        return
    
    # Получение ответа от AI
    print("Попытка ответить от бота")
    answer, chat_history = await get_ai_answer(support_session, message_text)
    
    if answer == "need_human":
        print("Переключение диалога на специалиста")
        await switch_to_human_specialist(
            support_session=support_session,
            chat_id=message.chat.id,
            business_connection_id=message.business_connection_id
        )
    else:
        print("Отвечает бот")
        await process_ai_response(
            support_session=support_session,
            answer=answer,
            chat_history=chat_history,
            chat_id=message.chat.id,
            business_connection_id=message.business_connection_id
        )


async def handle_specialist_message(message: types.Message):
    """Обработка сообщений от специалиста"""
    support_session = await crud.get_active_session(message.chat.id)
    await crud.add_message(
        support_session_id=support_session.id,
        content=message.text,
        role=models.MessageRole.assistant,
        assistant_type=models.AssistantType.human
    )
    messages = await crud.get_all_messages(support_session_id=support_session.id)
    chat = create_chat_history(messages)
    is_support_session_end = await check_support_session_end(chat=chat)
    if is_support_session_end:
        await crud.update_session_status(
            session_id=support_session.id,
            status=models.SupportStatus.end
        )


async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())