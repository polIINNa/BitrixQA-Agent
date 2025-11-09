from telegram_bot.database.models import Message, MessageRole


def create_chat_history(messages: list[Message]) -> str:
    """Сформировать историю сообщений по сообщениям сессии"""
    chat_history = ""
    for message in messages:
        if message.role == MessageRole.user:
            chat_history += f"Пользователь: {message.content}\n"
        else:
            chat_history += f"Ассистент: {message.content}\n"
    return chat_history
