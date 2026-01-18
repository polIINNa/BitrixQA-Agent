"""Роутеры Telegram бота."""
from telegram_bot.routers.specialist import specialist_router
from telegram_bot.routers.private import private_router
from telegram_bot.routers.group import group_router

__all__ = ["specialist_router", "private_router", "group_router"]
