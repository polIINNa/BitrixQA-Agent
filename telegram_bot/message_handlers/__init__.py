"""Обработчики сообщений."""
from telegram_bot.message_handlers.client import handle_client_message
from telegram_bot.message_handlers.specialist import handle_specialist_message

__all__ = ["handle_client_message", "handle_specialist_message"]
