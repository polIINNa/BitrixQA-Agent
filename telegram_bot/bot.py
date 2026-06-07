"""Точка входа Telegram бота."""
import sys
import asyncio
import logging

from aiogram.enums import ParseMode
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import BotCommand, BotCommandScopeDefault

from telegram_bot.routers import specialist_router, private_router, group_router
from telegram_bot.config import get_config


config = get_config()

dp = Dispatcher()

# Хранилище задач для отложенных сообщений (напоминаний)
followup_tasks: dict[str, asyncio.Task] = {}

# Регистрируем роутеры
dp.include_router(specialist_router)
dp.include_router(private_router)
dp.include_router(group_router)

session = AiohttpSession(proxy=config.proxy_url) if config.proxy_url else None

bot = Bot(
    config.token,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    **({"session": session} if session else {}),
)

# Список команд для меню "/"
COMMANDS = [
    BotCommand(command="takeover", description="🔄 Переключить режим сессии"),
    BotCommand(command="status", description="📊 Проверить статус сессии для конкретного пользователя"),
    BotCommand(command="sessions_mode", description="📋 Список чатов со статусом ассистента: бот или специалист"),
    BotCommand(command="cancel", description="❌ Отменить текущую операцию"),
]

async def set_bot_commands(bot: Bot) -> None:
    """Установить список быстрых команд для меню /"""
    await bot.set_my_commands(
        commands=COMMANDS,
        scope=BotCommandScopeDefault()  # Для всех чатов
    )
    logging.info("Команды бота зарегистрированы")


async def main():
    # Регистрируем команды при запуске
    await set_bot_commands(bot)

    # Передаём followup_tasks через workflow_data диспетчера
    dp.workflow_data["followup_tasks"] = followup_tasks
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
