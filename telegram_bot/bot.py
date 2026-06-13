"""Точка входа Telegram бота."""
import sys
import asyncio
import logging

from aiogram.enums import ParseMode
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import BotCommand, BotCommandScopeDefault, ErrorEvent

from telegram_bot.routers import specialist_router, private_router, group_router
from telegram_bot.config import get_config
from telegram_bot.services import chat_flow


logger = logging.getLogger(__name__)

config = get_config()

dp = Dispatcher()

# Регистрируем роутеры
dp.include_router(specialist_router)
dp.include_router(private_router)
dp.include_router(group_router)


async def on_unhandled_error(event: ErrorEvent) -> bool:
    """Последний рубеж: ни одно исключение в обработке апдейта не должно теряться молча.

    Основной фолбэк (перевод на специалиста) живёт в обработчике клиента; сюда долетает
    то, что не поймано там (команды специалиста, групповая маршрутизация, неожиданное).
    """
    logger.error("Необработанная ошибка при обработке апдейта", exc_info=event.exception)
    return True


dp.errors.register(on_unhandled_error)

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

    # Фоновый цикл досылки персистентных напоминаний (follow-up)
    asyncio.create_task(chat_flow.run_followup_sweep(bot))

    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
