"""Роутер для бизнес-сообщений (личные чаты через бизнес-аккаунт)."""
import asyncio

from aiogram import Bot, types, Router

from telegram_bot.config import get_config
from telegram_bot.database import crud
from telegram_bot.enums import ChatType
from telegram_bot.utils import get_chat_id
from telegram_bot.message_handlers.client import handle_client_message
from telegram_bot.message_handlers.specialist import handle_specialist_message


config = get_config()

# Роутер для личных сообщений (бизнес-аккаунт)
private_router = Router(name="private")


@private_router.business_message()
async def handle_business_message(
    message: types.Message,
    bot: Bot,
    followup_tasks: dict[str, asyncio.Task],
):
    """Обработка сообщений в бизнес-аккаунте."""
    print(f"Обработка бизнес-сообщения: {message.text}")
    
    chat_id = get_chat_id(message, ChatType.PRIVATE)
    
    if str(message.from_user.id) == config.tech_support_account_id:
        print("Обработка сообщения специалиста")
        await handle_specialist_message(
            chat_id=chat_id,
            message=message,
        )
    else:
        print("Обработка сообщения пользователя")
        # Создаём/обновляем чат с username пользователя
        user_username = message.from_user.username if message.from_user else None
        await crud.get_or_create_chat(chat_id=chat_id, username=user_username, chat_type=ChatType.PRIVATE)
        
        await handle_client_message(
            chat_type=ChatType.PRIVATE,
            chat_id=chat_id,
            bot=bot,
            message=message,
            followup_tasks=followup_tasks,
            operator_id=config.operator_id,
            tech_support_account_id=config.tech_support_account_id,
        )
