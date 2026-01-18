"""Роутер и команды в боте для специалиста."""
import logging

from aiogram import types, Router, F
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from telegram_bot.config import get_config
from telegram_bot.database import crud
from telegram_bot.enums import AssistantType, ChatType

config = get_config()

logger = logging.getLogger(__name__)

# Роутер для команд специалиста
specialist_router = Router(name="specialist")


# =============================================================================
# CallbackData классы для inline-кнопок
# =============================================================================

class TakeoverChatTypeCallback(CallbackData, prefix="takeover_chat"):
    """Callback для выбора типа чата в /takeover."""
    chat_type: str  # "private" или "group"


class TakeoverAssistantTypeCallback(CallbackData, prefix="takeover_assist"):
    """Callback для выбора типа ассистента в /takeover."""
    assistant_type: str  # "human" или "ai"


class StatusChatTypeCallback(CallbackData, prefix="status_chat"):
    """Callback для выбора типа чата в /status."""
    chat_type: str  # "private" или "group"


# =============================================================================
# Клавиатуры
# =============================================================================

def get_chat_type_keyboard(callback_class: type[CallbackData]) -> InlineKeyboardMarkup:
    """Создать клавиатуру выбора типа чата."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="👤 Личные сообщения",
                callback_data=callback_class(chat_type="private").pack()
            ),
            InlineKeyboardButton(
                text="👥 Групповой чат",
                callback_data=callback_class(chat_type="group").pack()
            )
        ]
    ])


def get_assistant_type_keyboard() -> InlineKeyboardMarkup:
    """Создать клавиатуру выбора типа ассистента."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="👨‍💼 Специалист (human)",
                callback_data=TakeoverAssistantTypeCallback(assistant_type="human").pack()
            ),
            InlineKeyboardButton(
                text="🤖 Бот (ai)",
                callback_data=TakeoverAssistantTypeCallback(assistant_type="ai").pack()
            )
        ]
    ])


class SwitchAssistantTypeStates(StatesGroup):
    """Состояния FSM для команды /takeover."""
    waiting_for_username = State()
    waiting_for_chat_type = State()
    waiting_for_assistant_type = State()


class CheckStatusStates(StatesGroup):
    """Состояния FSM для команды /status."""
    waiting_for_username = State()
    waiting_for_chat_type = State()


def _is_operator(user_id: int) -> bool:
    """Проверить, является ли пользователь оператором."""
    return str(user_id) == config.tech_support_account_id


# =============================================================================
# Команда /cancel — отмена текущей операции (должна быть ПЕРЕД хендлерами FSM!)
# =============================================================================

@specialist_router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext) -> None:
    """Отмена текущей операции."""
    if not _is_operator(message.from_user.id):
        return
    
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активной операции для отмены.")
        return
    
    await state.clear()
    await message.answer("❌ Операция отменена.")


# =============================================================================
# Команда /takeover — переключение режима сессии
# =============================================================================

@specialist_router.message(Command("takeover"))
async def cmd_takeover_start(message: types.Message, state: FSMContext) -> None:
    """Старт команды переключения режима сессии."""
    if not _is_operator(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к этой команде.")
        return
    
    await message.answer(
        "🔄 <b>Переключение режима сессии</b>\n\n"
        "Введите username пользователя (с @ или без):"
    )
    await state.set_state(SwitchAssistantTypeStates.waiting_for_username)


@specialist_router.message(SwitchAssistantTypeStates.waiting_for_username)
async def process_username(message: types.Message, state: FSMContext) -> None:
    """Обработка введённого username."""
    if not _is_operator(message.from_user.id):
        await state.clear()
        return
    
    username = message.text.strip()
    
    if not username:
        await message.answer("❌ Username не может быть пустым. Попробуйте ещё раз:")
        return
    
    # Сохраняем username в состоянии
    await state.update_data(username=username.lstrip("@"))
    
    await message.answer(
        f"👤 Пользователь: <b>@{username.lstrip('@')}</b>\n\n"
        "Выберите тип чата:",
        reply_markup=get_chat_type_keyboard(TakeoverChatTypeCallback)
    )
    await state.set_state(SwitchAssistantTypeStates.waiting_for_chat_type)


@specialist_router.callback_query(TakeoverChatTypeCallback.filter(), SwitchAssistantTypeStates.waiting_for_chat_type)
async def process_chat_type(callback: types.CallbackQuery, callback_data: TakeoverChatTypeCallback, state: FSMContext) -> None:
    """Обработка выбранного типа чата."""
    if not _is_operator(callback.from_user.id):
        await state.clear()
        await callback.answer("⛔ У вас нет доступа.", show_alert=True)
        return
    
    await callback.answer()
    
    # Сохраняем chat_type в состоянии
    chat_type = ChatType.PRIVATE if callback_data.chat_type == "private" else ChatType.GROUP
    await state.update_data(chat_type=chat_type)
    
    chat_type_name = "личные сообщения" if chat_type == ChatType.PRIVATE else "групповой чат"
    data = await state.get_data()
    username = data.get("username")
    
    await callback.message.edit_text(
        f"👤 Пользователь: <b>@{username}</b>\n"
        f"💬 Тип чата: <b>{chat_type_name}</b>\n\n"
        "Выберите режим, на который нужно переключить сессию:",
        reply_markup=get_assistant_type_keyboard()
    )
    await state.set_state(SwitchAssistantTypeStates.waiting_for_assistant_type)


@specialist_router.callback_query(TakeoverAssistantTypeCallback.filter(), SwitchAssistantTypeStates.waiting_for_assistant_type)
async def process_assistant_type(callback: types.CallbackQuery, callback_data: TakeoverAssistantTypeCallback, state: FSMContext) -> None:
    """Обработка выбранного assistant_type и выполнение переключения."""
    if not _is_operator(callback.from_user.id):
        await state.clear()
        await callback.answer("⛔ У вас нет доступа.", show_alert=True)
        return
    
    await callback.answer()
    
    # Получаем сохранённые данные
    data = await state.get_data()
    username = data.get("username")
    chat_type: ChatType = data.get("chat_type")
    target_assistant_type = AssistantType.human if callback_data.assistant_type == "human" else AssistantType.ai
    
    # Получаем чат и активную сессию этого чата по username и типу чата
    chat = await crud.get_chat(username=username, chat_type=chat_type)
    
    if chat is None:
        chat_type_name = "личных сообщениях" if chat_type == ChatType.PRIVATE else "групповом чате"
        await state.clear()
        await callback.message.edit_text(f"❌ Пользователь @{username} не найден в {chat_type_name}.")
        return
    
    active_session = await crud.get_active_session(chat.id)
    
    if active_session is None:
        chat_type_name = "личных сообщениях" if chat_type == ChatType.PRIVATE else "групповом чате"
        await state.clear()
        await callback.message.edit_text(f"❌ У пользователя @{username} нет активной сессии в {chat_type_name}.")
        return
    
    previous_assistant_type = active_session.assistant_type
    
    # Проверяем, не установлен ли уже этот assistant_type
    if previous_assistant_type == target_assistant_type:
        await state.clear()
        await callback.message.edit_text(f"⚠️ Сессия @{username} уже в режиме {target_assistant_type.value}.")
        return
    
    # Переключаем assistant_type
    await crud.update_session_assistant_type(session_id=active_session.id, assistant_type=target_assistant_type)
    
    chat_type_name = "личные сообщения" if chat_type == ChatType.PRIVATE else "групповой чат"
    await state.clear()
    await callback.message.edit_text(
        f"✅ Режим сессии @{username} ({chat_type_name}) переключён: "
        f"{previous_assistant_type.value} → {target_assistant_type.value}."
    )


# =============================================================================
# Команда /status — проверка статуса сессии
# =============================================================================

@specialist_router.message(Command("status"))
async def cmd_status_start(message: types.Message, state: FSMContext) -> None:
    """Начало процесса проверки статуса сессии."""
    if not _is_operator(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к этой команде.")
        return
    
    await message.answer(
        "🔍 <b>Проверка статуса сессии</b>\n\n"
        "Введите username пользователя (с @ или без):"
    )
    await state.set_state(CheckStatusStates.waiting_for_username)


@specialist_router.message(CheckStatusStates.waiting_for_username)
async def process_status_username(message: types.Message, state: FSMContext) -> None:
    """Обработка введённого username."""
    if not _is_operator(message.from_user.id):
        await state.clear()
        return
    
    username = message.text.strip()
    
    if not username:
        await message.answer("❌ Username не может быть пустым. Попробуйте ещё раз:")
        return
    
    # Сохраняем username в состоянии
    await state.update_data(username=username.lstrip("@"))
    
    await message.answer(
        f"👤 Пользователь: <b>@{username.lstrip('@')}</b>\n\n"
        "Выберите тип чата:",
        reply_markup=get_chat_type_keyboard(StatusChatTypeCallback)
    )
    await state.set_state(CheckStatusStates.waiting_for_chat_type)


@specialist_router.callback_query(StatusChatTypeCallback.filter(), CheckStatusStates.waiting_for_chat_type)
async def process_status_chat_type(callback: types.CallbackQuery, callback_data: StatusChatTypeCallback, state: FSMContext) -> None:
    """Обработка выбранного типа чата и вывод статуса сессии."""
    if not _is_operator(callback.from_user.id):
        await state.clear()
        await callback.answer("⛔ У вас нет доступа.", show_alert=True)
        return
    
    await callback.answer()
    
    # Получаем сохранённые данные
    data = await state.get_data()
    username = data.get("username")
    chat_type = ChatType.PRIVATE if callback_data.chat_type == "private" else ChatType.GROUP
    chat_type_name = "личные сообщения" if chat_type == ChatType.PRIVATE else "групповой чат"
    
    # Получаем чат и активную сессию по username и типу чата
    chat = await crud.get_chat(username=username, chat_type=chat_type)
    
    if chat is None:
        await state.clear()
        await callback.message.edit_text(f"❌ Пользователь @{username} не найден в чате типа «{chat_type_name}».")
        return
    
    active_session = await crud.get_active_session(chat.id)
    
    if active_session is None:
        await state.clear()
        await callback.message.edit_text(f"❌ У пользователя @{username} нет активной сессии в чате типа «{chat_type_name}».")
        return
    
    current_assistant_type = active_session.assistant_type
    assistant_type_emoji = "🤖" if current_assistant_type == AssistantType.ai else "👤"
    assistant_type_name = "бот (AI)" if current_assistant_type == AssistantType.ai else "специалист (human)"
    
    await state.clear()
    await callback.message.edit_text(
        f"📊 <b>Статус сессии @{username}</b>\n"
        f"💬 Тип чата: <b>{chat_type_name}</b>\n\n"
        f"{assistant_type_emoji} Текущий режим: <b>{assistant_type_name}</b>"
    )


# =============================================================================
# Команда /sessions_mode — список всех чатов с типом ассистента
# =============================================================================

@specialist_router.message(Command("sessions_mode"))
async def cmd_list_sessions(message: types.Message) -> None:
    """Вывести список всех чатов с типом ассистента."""
    if not _is_operator(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к этой команде.")
        return
    
    chats_with_sessions = await crud.get_all_chats_with_latest_sessions()
    
    if not chats_with_sessions:
        await message.answer("📭 Нет чатов.")
        return
    
    lines = ["📋 <b>Список чатов:</b>\n"]
    
    for chat, session in chats_with_sessions:
        username_display = f"@{chat.username}" if chat.username else f"ID: {chat.id}"
        
        # Тип чата
        if chat.chat_type == ChatType.PRIVATE:
            chat_type_emoji = "👤"
            chat_type_name = "private"
        elif chat.chat_type == ChatType.GROUP:
            chat_type_emoji = "👥"
            chat_type_name = "group"
        else:
            chat_type_emoji = "❓"
            chat_type_name = "unknown"
        
        # Тип ассистента
        if session is None:
            assistant_emoji = "➖"
            assistant_name = "нет сессии"
        elif session.assistant_type == AssistantType.ai:
            assistant_emoji = "🤖"
            assistant_name = "ai"
        else:
            assistant_emoji = "👨‍💼"
            assistant_name = "human"
        
        lines.append(
            f"• <b>{username_display}</b> — {chat_type_emoji} {chat_type_name} / {assistant_emoji} {assistant_name}"
        )
    
    await message.answer("\n".join(lines))
