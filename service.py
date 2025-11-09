from dotenv import load_dotenv

from bitrix_qa_agent.state import InputState
from bitrix_qa_agent.context import BitrixQAContext
from bitrix_qa_agent.chains.chains import is_support_session_end_chain
from bitrix_qa_agent.graph import get_simple_graph


load_dotenv()


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

async def get_answer_test(chat_history: str | None, last_user_message: str):
    from bitrix_qa_agent.chains.chains import admin_answer_chain

    context = BitrixQAContext()
    if "специалист" in last_user_message:
        return "need_human"
    else:
        if chat_history:
            chat = f"{chat_history}\nПользователь: {last_user_message}"
        else:
            chat = last_user_message
        return await admin_answer_chain(context.model).ainvoke({"chat": chat, "raw_answer": "нет"})


async def check_support_session_end(chat: str) -> bool:
    """Определить, завершена сессия поддержки или нет"""
    context = BitrixQAContext()
    result = (await is_support_session_end_chain(model=context.pro_model).ainvoke(
        {
            "chat": chat
        }
    )).is_support_session_end
    if result == 1:
        return True
    else:
        return False