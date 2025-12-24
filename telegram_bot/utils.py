from aiogram import types

from service import get_answer
from telegram_bot.database import crud, models
from telegram_bot.database.models import Message, MessageRole, SupportStatus, AssistantType

# Медиа-типы и их описания
MEDIA_TYPE_MAP = {
    'photo': (models.MessageType.image, "[Фото]"),
    'video': (models.MessageType.video, "[Видео]"),
    'video_note': (models.MessageType.video, "[Видеосообщение]"),
    'audio': (models.MessageType.audio, "[Аудио]"),
    'voice': (models.MessageType.audio, "[Голосовое сообщение]"),
    'document': (models.MessageType.text, None),  # Будет обработан отдельно
    'sticker': (models.MessageType.text, "[Стикер]"),
    'animation': (models.MessageType.text, "[GIF]"),
    'location': (models.MessageType.text, None),  # Будет обработан отдельно
    'contact': (models.MessageType.text, None),  # Будет обработан отдельно
    'poll': (models.MessageType.text, None),  # Будет обработан отдельно
}


def create_chat(support_session_messages: list[Message]) -> str:
    """Сформировать историю сообщений по сообщениям сессии"""
    chat = ""
    for message in support_session_messages:
        if message.role == MessageRole.user:
            chat += f"<Пользователь>\n{message.content}\n</Пользователь>\n\n"
        if message.role == MessageRole.assistant:
            chat += f"<Ассистент>\n{message.content}\n</Ассистент>\n\n"
    return chat


def has_media_content(message: types.Message) -> bool:
    """Проверяет, содержит ли сообщение медиа-контент (не только текст)"""
    return any((
        message.photo, message.video, message.audio, message.voice,
        message.video_note, message.document, message.sticker,
        message.animation, message.location, message.contact, message.poll
    ))


def get_media_info(message: types.Message) -> tuple[models.MessageType, str]:
    """Определяет тип и форматирует содержимое медиа-сообщения"""
    # Проверяем типы медиа по приоритету
    if message.photo:
        media_type, description = MEDIA_TYPE_MAP['photo']
    elif message.video:
        media_type, description = MEDIA_TYPE_MAP['video']
    elif message.video_note:
        media_type, description = MEDIA_TYPE_MAP['video_note']
    elif message.audio:
        media_type, description = MEDIA_TYPE_MAP['audio']
    elif message.voice:
        media_type, description = MEDIA_TYPE_MAP['voice']
    elif message.document:
        media_type = MEDIA_TYPE_MAP['document'][0]
        description = f"[Документ: {message.document.file_name or 'без названия'}]"
    elif message.sticker:
        media_type, description = MEDIA_TYPE_MAP['sticker']
    elif message.animation:
        media_type, description = MEDIA_TYPE_MAP['animation']
    elif message.location:
        media_type = MEDIA_TYPE_MAP['location'][0]
        description = f"[Локация: {message.location.latitude}, {message.location.longitude}]"
    elif message.contact:
        media_type = MEDIA_TYPE_MAP['contact'][0]
        description = f"[Контакт: {message.contact.first_name} {message.contact.phone_number}]"
    elif message.poll:
        media_type = MEDIA_TYPE_MAP['poll'][0]
        description = f"[Опрос: {message.poll.question}]"
    else:
        media_type = models.MessageType.text
        description = "[Медиа-контент]"

    # Добавляем подпись, если есть
    content_parts = [description]
    if message.caption:
        content_parts.append(message.caption)

    return media_type, " ".join(content_parts)


async def get_or_create_support_session(chat_id: str) -> models.SupportSession:
    """Получает или создает активную сессию поддержки"""
    chat = await crud.get_or_create_chat(chat_id)
    support_session = await crud.get_active_session(chat.id)
    if not support_session:
        support_session = await crud.create_support_session(chat_id=chat.id)
    return support_session


async def get_chat_history(support_session_messages: list[Message]) -> str | None:
    """Получает историю чата для сессии"""
    if len(support_session_messages) == 1:
        return None
    return create_chat(support_session_messages[:-1])

async def get_agent_answer(
    support_session_messages: list[Message],
    user_message: str
) -> tuple[str, str | None]:
    """Получить ответ от агента"""
    chat_history = await get_chat_history(support_session_messages=support_session_messages)
    answer = await get_answer(chat_history=chat_history, last_user_message=user_message)
    return answer, chat_history
