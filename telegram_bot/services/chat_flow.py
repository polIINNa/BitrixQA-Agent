"""Логика ведения диалога с клиентом: условия отправки сообщений и напоминания."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot, types
from aiogram.types import ReplyParameters

from telegram_bot.database import crud
from telegram_bot.database.models import Message
from telegram_bot.constants import (
    AUTO_REPLY,
    POSITIVE_ACKNOWLEDGEMENT_REPLY_WITH_AD,
    CHECK_USER_MESSAGE,
)
from telegram_bot.enums import ChatType, MessageRole, AssistantType, SupportStatus

logger = logging.getLogger(__name__)


# =============================================================================
# Условия отправки сообщений
# =============================================================================

async def should_send_auto_reply(chat_id: str) -> bool:
    """Определяет, нужно ли отправить автоответ."""
    all_messages = await crud.get_all_messages_by_chat_id(chat_id)

    # Если AUTO_REPLY ещё не отправлялся в этом чате
    if not any(m.content == AUTO_REPLY for m in all_messages):
        return True

    # Если с предыдущего сообщения прошло больше 14 дней
    previous_message = _get_previous_user_message(all_messages)
    if previous_message is None:
        return True

    return _is_message_older_than_days(previous_message, days=14)


async def should_show_ad_on_positive_acknowledgement(chat_id: str) -> bool:
    """Определяет, показывать ли рекламу при положительном отклике."""
    all_messages = await crud.get_all_messages_by_chat_id(chat_id)

    # Если реклама ещё не показывалась в этом чате
    if not any(m.content == POSITIVE_ACKNOWLEDGEMENT_REPLY_WITH_AD for m in all_messages):
        return True

    # Если с предыдущего сообщения прошло больше 10 дней
    previous_message = _get_previous_user_message(all_messages)
    if previous_message is None:
        return True

    return _is_message_older_than_days(previous_message, days=10)


# =============================================================================
# Напоминания (followup) — персистентные, в БД
# =============================================================================
# Раньше напоминание жило в памяти как asyncio.Task и терялось при рестарте.
# Теперь: при отправке ответа создаём запись followups(status=pending, scheduled_at);
# при новом сообщении клиента помечаем pending -> cancelled; фоновый sweep
# (run_followup_sweep) раз в интервал досылает наступившие. Переживает рестарт.

FOLLOWUP_DELAY_SECONDS = 1800        # 30 минут до напоминания
FOLLOWUP_SWEEP_INTERVAL_SECONDS = 60  # как часто проверять наступившие


def _utcnow_naive() -> datetime:
    """Текущее время UTC без таймзоны (для сравнения с TIMESTAMP-колонкой)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def schedule_followup(
    support_session,
    chat_type: ChatType,
    message: types.Message,
) -> None:
    """Запланировать напоминание через FOLLOWUP_DELAY_SECONDS (запись в БД).

    Прежние ожидающие напоминания этого чата отменяются — одно активное на чат.
    Контекст отправки (куда/как слать) сохраняется в записи, чтобы sweep мог
    доставить напоминание даже после рестарта, без исходного объекта message.
    """
    scheduled_at = _utcnow_naive() + timedelta(seconds=FOLLOWUP_DELAY_SECONDS)

    if chat_type == ChatType.PRIVATE:
        send_chat_id = support_session.chat_id                 # = telegram chat id
        business_connection_id = message.business_connection_id
        reply_to_message_id = None
    else:
        send_chat_id = str(message.chat.id)                    # telegram id группы
        business_connection_id = None
        reply_to_message_id = message.message_id

    await crud.cancel_pending_followups(support_session.chat_id)
    await crud.create_followup(
        support_session_id=support_session.id,
        chat_id=support_session.chat_id,
        send_chat_id=send_chat_id,
        text=CHECK_USER_MESSAGE,
        scheduled_at=scheduled_at,
        business_connection_id=business_connection_id,
        reply_to_message_id=reply_to_message_id,
    )


async def cancel_followup(chat_id: str) -> None:
    """Отменить ожидающее напоминание чата (клиент прислал новое сообщение)."""
    await crud.cancel_pending_followups(chat_id)


# =============================================================================
# Фоновый sweep напоминаний
# =============================================================================

async def run_followup_sweep(bot: Bot) -> None:
    """Фоновый цикл: периодически досылает наступившие follow-up. Переживает рестарт."""
    logger.info("Follow-up sweep запущен (интервал %dс)", FOLLOWUP_SWEEP_INTERVAL_SECONDS)
    while True:
        try:
            await asyncio.sleep(FOLLOWUP_SWEEP_INTERVAL_SECONDS)
            await _process_due_followups(bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Ошибка в цикле follow-up sweep")


async def _process_due_followups(bot: Bot) -> None:
    due = await crud.claim_due_followups(_utcnow_naive())
    if due:
        logger.info("Follow-up sweep: к отправке %d напоминаний", len(due))
    for followup in due:
        try:
            await _deliver_followup(bot, followup)
        except Exception:
            logger.exception("Не удалось отправить follow-up %s", followup.get("id"))


async def _deliver_followup(bot: Bot, followup: dict) -> None:
    """Отправить одно напоминание (если сессия всё ещё активна и в AI-режиме)."""
    session = await crud.get_support_session(followup["support_session_id"])
    if session is None or session.status != SupportStatus.process or session.assistant_type != AssistantType.ai:
        logger.info("Follow-up %s пропущен: сессия неактивна или её ведёт специалист", followup["id"])
        return

    if followup["business_connection_id"]:
        await bot.send_message(
            chat_id=int(followup["send_chat_id"]),
            text=followup["text"],
            business_connection_id=followup["business_connection_id"],
        )
    elif followup["reply_to_message_id"]:
        await bot.send_message(
            chat_id=int(followup["send_chat_id"]),
            text=followup["text"],
            reply_parameters=ReplyParameters(message_id=followup["reply_to_message_id"]),
        )
    else:
        await bot.send_message(chat_id=int(followup["send_chat_id"]), text=followup["text"])

    # Записываем как системное сообщение уже после успешной отправки
    await crud.add_message(
        support_session_id=followup["support_session_id"],
        content=followup["text"],
        role=MessageRole.system,
    )


# =============================================================================
# Вспомогательные функции
# =============================================================================

def _get_previous_user_message(messages: list[Message]) -> Message | None:
    """Получить предпоследнее сообщение клиента (до текущего)."""
    user_messages = [m for m in messages if m.role == MessageRole.user]
    if len(user_messages) < 2:
        return None
    return user_messages[-2]


def _is_message_older_than_days(message: Message, days: int) -> bool:
    """Проверить, старше ли сообщение указанного количества дней."""
    if not message.created_at_str:
        return True
    try:
        message_date = datetime.fromisoformat(message.created_at_str)
        return datetime.now() - message_date >= timedelta(days=days)
    except Exception as e:
        logger.warning(f"Ошибка парсинга даты: {e}")
        return True
