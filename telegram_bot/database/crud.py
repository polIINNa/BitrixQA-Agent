import uuid
import logging
import datetime
from typing import Optional

from sqlalchemy import select, asc, func, and_
from sqlalchemy.exc import IntegrityError

from telegram_bot.database.base import AsyncSessionLocal
from telegram_bot.database.models import Chat, SupportSession, Message
from telegram_bot.enums import SupportStatus, MessageType, MessageRole, AssistantType, ChatType

logger = logging.getLogger(__name__)


async def _create_chat(
    chat_id: str,
    username: str | None = None,
    chat_type: ChatType | None = None
) -> Chat:
    async with AsyncSessionLocal() as session:
        chat = Chat(id=chat_id, username=username, chat_type=chat_type)
        session.add(chat)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            result = await session.execute(select(Chat).where(Chat.id == chat_id))
            chat = result.scalar_one()
        else:
            await session.refresh(chat)
        return chat


async def get_chat(
    chat_id: str | None = None,
    *,
    username: str | None = None,
    chat_type: ChatType | None = None
) -> Optional[Chat]:
    """
    Получить чат по chat_id или по username + chat_type.

    Варианты использования:
    - get_chat(chat_id="123") — поиск по ID чата
    - get_chat(username="polina", chat_type=ChatType.PRIVATE) — поиск по username и типу чата
    """
    async with AsyncSessionLocal() as session:
        if chat_id is not None:
            result = await session.execute(select(Chat).where(Chat.id == chat_id))
        elif username is not None and chat_type is not None:
            result = await session.execute(
                select(Chat).where(Chat.username == username, Chat.chat_type == chat_type)
            )
        else:
            raise ValueError("Укажите chat_id или пару username + chat_type")
        return result.scalar_one_or_none()


async def get_or_create_chat(
    chat_id: str,
    username: str | None = None,
    chat_type: ChatType | None = None
) -> Chat:
    chat = await get_chat(chat_id)
    if chat is None:
        chat = await _create_chat(chat_id, username=username, chat_type=chat_type)
    else:
        needs_update = (
            (username and chat.username != username)
            or (chat_type and chat.chat_type != chat_type)
        )
        if needs_update:
            chat = await _update_chat(chat_id, username=username, chat_type=chat_type)
    return chat


async def _update_chat(
    chat_id: str,
    username: str | None = None,
    chat_type: ChatType | None = None
) -> Optional[Chat]:
    """Обновить username и/или chat_type чата."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Chat).where(Chat.id == chat_id))
        chat = result.scalar_one_or_none()
        if chat is None:
            return None
        if username is not None:
            chat.username = username
        if chat_type is not None:
            chat.chat_type = chat_type
        await session.commit()
        await session.refresh(chat)
        return chat


async def create_support_session(
    chat_id: str,
    assistant_type: AssistantType = AssistantType.ai,
    _max_attempts: int = 5,
) -> SupportSession:
    # id формируется как <chat_id>_<N>. При конкурентной обработке двух сообщений
    # одного чата два вызова могут вычислить одинаковый N -> дубль PK -> IntegrityError.
    # Ловим его и пересчитываем номер (а не падаем, как было раньше).
    for attempt in range(_max_attempts):
        async with AsyncSessionLocal() as session:
            # Выбираем максимальный номер сессии для данного чата
            result = await session.execute(select(SupportSession.id).where(SupportSession.chat_id == chat_id))
            existing_ids = [row[0] for row in result.all() if row[0].startswith(f'{chat_id}_')]
            max_number = 0
            for sid in existing_ids:
                try:
                    n = int(sid.rsplit('_', 1)[-1])
                    max_number = max(max_number, n)
                except Exception:
                    continue
            session_id = f"{chat_id}_{max_number + 1}"
            support_session = SupportSession(
                id=session_id,
                chat_id=chat_id,
                status=SupportStatus.process,
                assistant_type=assistant_type
            )
            session.add(support_session)
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                logger.warning(
                    "Конфликт id сессии %s (попытка %d/%d), пересчитываю номер",
                    session_id, attempt + 1, _max_attempts,
                )
                continue
            await session.refresh(support_session)
            return support_session

    raise RuntimeError(
        f"Не удалось создать сессию для chat_id={chat_id} за {_max_attempts} попыток"
    )


async def get_active_session(chat_id: str) -> SupportSession | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SupportSession)
            .where(
                SupportSession.chat_id == chat_id,
                SupportSession.status == SupportStatus.process,
            )
            .order_by(SupportSession.created_at.desc())
        )
        return result.scalars().first()


async def get_or_create_active_session(chat_id: str) -> SupportSession:
    """
    Получить активную сессию или создать новую.

    Args:
        chat_id: идентификатор чата

    Returns:
        Активная или новая сессия поддержки
    """
    active_session = await get_active_session(chat_id)

    if active_session is None:
        logger.info(f"Нет действующей сессии для chat_id={chat_id}, создание новой")
        return await create_support_session(chat_id=chat_id)

    logger.debug(f"Продолжение активной сессии {active_session.id}")
    return active_session


async def update_session_status(session_id: str, *, status: SupportStatus) -> Optional[SupportSession]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(SupportSession).where(SupportSession.id == session_id))
        support_session = result.scalar_one_or_none()
        if support_session is None:
            return None
        support_session.status = status
        await session.commit()
        await session.refresh(support_session)
        return support_session


async def update_session_assistant_type(session_id: str, *, assistant_type: AssistantType) -> Optional[SupportSession]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(SupportSession).where(SupportSession.id == session_id))
        support_session = result.scalar_one_or_none()
        if support_session is None:
            return None
        support_session.assistant_type = assistant_type
        await session.commit()
        await session.refresh(support_session)
        return support_session


async def add_message(
    support_session_id: str,
    content: str | None = None,
    *,
    role: MessageRole,
    assistant_type: AssistantType | None = None,
    type: MessageType = MessageType.text
) -> Message:
    async with AsyncSessionLocal() as session:
        now_iso = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
        message = Message(
            id=str(uuid.uuid4()),
            support_session_id=support_session_id,
            content=content,
            type=type,
            role=role,
            assistant_type=assistant_type,
            created_at_str=now_iso,
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)
        return message


async def get_all_messages(support_session_id: str) -> list[Message]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Message)
            .where(Message.support_session_id == support_session_id)
            .order_by(asc(Message.created_at_str))
        )
        return list(result.scalars().all())


async def get_all_messages_by_chat_id(chat_id: str) -> list[Message]:
    """Получить все сообщения по chat_id (из всех сессий)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Message)
            .join(SupportSession, Message.support_session_id == SupportSession.id)
            .where(SupportSession.chat_id == chat_id)
            .order_by(asc(Message.created_at_str))
        )
        return list(result.scalars().all())


async def reassign_message(message_id: str, new_session_id: str) -> Optional[Message]:
    """Перепривязать сообщение к другой сессии.

    Используется при смене интента: сообщение сохраняется при входе в текущей сессии,
    а при обнаружении новой темы переносится в созданную новую сессию.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Message).where(Message.id == message_id))
        message = result.scalar_one_or_none()
        if message is None:
            return None
        message.support_session_id = new_session_id
        await session.commit()
        await session.refresh(message)
        return message


async def _update_message_content(message_id: str, new_content: str) -> Optional[Message]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Message).where(Message.id == message_id))
        message = result.scalar_one_or_none()
        if message is None:
            return None
        message.content = new_content
        await session.commit()
        await session.refresh(message)
        return message


async def _delete_message(message_id: str) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Message).where(Message.id == message_id))
        message = result.scalar_one_or_none()
        if message is None:
            return False
        await session.delete(message)
        await session.commit()
        return True


async def get_all_chats_with_latest_sessions() -> list[tuple[Chat, SupportSession | None]]:
    """
    Получить все чаты с их последней сессией (один SQL-запрос).

    Returns:
        Список кортежей (Chat, SupportSession | None) для всех чатов.
    """
    async with AsyncSessionLocal() as session:
        # Подзапрос: максимальный created_at сессии для каждого чата
        latest_sq = (
            select(
                SupportSession.chat_id,
                func.max(SupportSession.created_at).label("max_created_at"),
            )
            .group_by(SupportSession.chat_id)
            .subquery()
        )

        result = await session.execute(
            select(Chat, SupportSession)
            .outerjoin(latest_sq, Chat.id == latest_sq.c.chat_id)
            .outerjoin(
                SupportSession,
                and_(
                    SupportSession.chat_id == latest_sq.c.chat_id,
                    SupportSession.created_at == latest_sq.c.max_created_at,
                ),
            )
            .order_by(Chat.username)
        )
        return [(row.Chat, row.SupportSession) for row in result]
