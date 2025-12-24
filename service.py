from dotenv import load_dotenv

from bitrix_qa_agent.state import InputState
from bitrix_qa_agent.context import BitrixQAContext
from bitrix_qa_agent.graph import get_simple_graph
from orchestrator.chains import is_support_session_end_chain


async def get_answer(chat_history: str | None, last_user_message) -> str:
    """Основная функция для получения ответа"""
    context = BitrixQAContext()
    bitrix_qa_graph = get_simple_graph()
    if chat_history is None:
        chat_history = ""
    _input = InputState(chat_history=chat_history, last_user_message=last_user_message)
    result = await bitrix_qa_graph.ainvoke(
        input=_input,
        context=context
    )
    if result["user_message_type"] == "objection":
        return "need_human"
    else:
        return result["answer"]


async def check_support_session_end(chat: str) -> bool:
    """Определить, завершена сессия поддержки или нет"""
    context = BitrixQAContext()
    result = await is_support_session_end_chain(model=context.pro_model).ainvoke(
        {
            "chat": chat
        }
    )
    if result == "1":
        return True
    else:
        return False