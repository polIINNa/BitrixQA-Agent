"""Публичный API для работы с QA агентом Bitrix."""
from bitrix_qa_agent.state import InputState
from bitrix_qa_agent.graph import get_simple_graph
from bitrix_qa_agent.context import BitrixQAContext


async def invoke_graph(
    chat_history: str | None,
    last_user_message: str,
) -> dict:
    """
    Запустить граф QA агента.

    Args:
        chat_history: История чата (без текущего сообщения)
        last_user_message: Последнее сообщение пользователя

    Returns:
        dict с ключами:
            - message_type: тип сообщения (negative, no_need_reply, positive_acknowledgement,
                           knowledge_required, chat, intent_changed)
            - answer: ответ на вопрос (может быть None)
    """
    context = BitrixQAContext()
    graph = get_simple_graph()

    input_state = InputState(
        chat_history=chat_history or "",
        last_user_message=last_user_message,
    )

    result = await graph.ainvoke(input=input_state, context=context)

    return {
        "message_type": result["user_message_type"],
        "answer": result.get("answer"),
    }

