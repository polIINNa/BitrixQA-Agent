import uuid
from typing import Optional

from sqlalchemy import select, asc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from telegram_bot.database.base import AsyncSessionLocal
from telegram_bot.database.models import (
    Chat,
    SupportSession,
    Message,
    SupportStatus,
    MessageType,
    MessageRole,
    AssistantType,
)


async def get_session() -> AsyncSession:
    return AsyncSessionLocal()


async def create_chat(chat_id: str) -> Chat:
    async with AsyncSessionLocal() as session:
        chat = Chat(id=chat_id)
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


async def get_chat(chat_id: str) -> Optional[Chat]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Chat).where(Chat.id == chat_id))
        return result.scalar_one_or_none()


async def get_or_create_chat(chat_id: str) -> Chat:
    chat = await get_chat(chat_id)
    if chat is None:
        chat = await create_chat(chat_id)
    return chat


async def exists_chat(chat_id: str) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Chat.id).where(Chat.id == chat_id))
        return result.scalar_one_or_none() is not None

async def create_support_session(
    chat_id: str,
    assistant_type: AssistantType = AssistantType.ai
) -> SupportSession:
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
        next_number = max_number + 1
        session_id = f"{chat_id}_{next_number}"
        support_session = SupportSession(
            id=session_id,
            chat_id=chat_id,
            status=SupportStatus.process,
            assistant_type=assistant_type
        )
        session.add(support_session)
        await session.commit()
        await session.refresh(support_session)
        return support_session


async def get_active_session(chat_id: str) -> Optional[SupportSession]:
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
    import datetime

    async with AsyncSessionLocal() as session:
        now_iso = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
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
            .order_by(asc(Message.created_at_str))  # сортировка по времени
        )
        return list(result.scalars().all())


async def update_message_content(message_id: str, new_content: str) -> Optional[Message]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Message).where(Message.id == message_id))
        message = result.scalar_one_or_none()
        if message is None:
            return None
        message.content = new_content
        await session.commit()
        await session.refresh(message)
        return message


async def delete_message(message_id: str) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Message).where(Message.id == message_id))
        message = result.scalar_one_or_none()
        if message is None:
            return False
        await session.delete(message)
        await session.commit()
        return True


