"""Перечисления для Telegram бота."""
import enum


class ChatType(enum.Enum):
    """Тип чата, куда было отправлено сообщение."""
    PRIVATE = 'private'
    GROUP = 'group'


class SupportStatus(str, enum.Enum):
    """Статус сессии поддержки."""
    end = "end"
    process = "process"


class MessageType(str, enum.Enum):
    """Тип сообщения."""
    text = "text"
    image = "image"
    audio = "audio"
    video = "video"


class MessageRole(str, enum.Enum):
    """Роль отправителя сообщения."""
    user = "user"
    assistant = "assistant"
    system = "system"


class AssistantType(str, enum.Enum):
    """Тип ассистента, отвечающего в чате."""
    ai = "ai"
    human = "human"


class FollowupStatus(str, enum.Enum):
    """Статус отложенного напоминания (follow-up)."""
    pending = "pending"      # запланировано, ждёт времени отправки
    sent = "sent"            # отправлено (или заявлено sweep'ом к отправке)
    cancelled = "cancelled"  # отменено (клиент ответил раньше)

