"""Публичный API для работы с QA агентом Bitrix."""
from bitrix_qa_agent.state import InputState
from bitrix_qa_agent.graph import get_simple_graph
from bitrix_qa_agent.context import BitrixQAContext


async def invoke_graph(
    chat_history: str | None,
    last_user_message: str,
    intent_check_only: bool = False,
) -> dict:
    """
    Запустить граф QA агента.
    
    Args:
        chat_history: История чата
        last_user_message: Последнее сообщение пользователя
        intent_check_only: Режим только проверки интента (без полной обработки).
                          Если True, граф завершится после проверки интента с типом
                          'intent_changed' или 'no_intent_change'.
        
    Returns:
        dict с ключами:
            - message_type: тип сообщения (negative, no_need_reply, positive_acknowledgement, 
                           knowledge_required, chat, intent_changed, no_intent_change)
            - answer: ответ на вопрос (может быть None)
    """
    context = BitrixQAContext()
    graph = get_simple_graph()
    
    if chat_history is None:
        chat_history = ""
    
    input_state = InputState(
        chat_history=chat_history,
        last_user_message=last_user_message,
        intent_check_only=intent_check_only,
    )
    
    result = await graph.ainvoke(input=input_state, context=context)
    
    return {
        "message_type": result["user_message_type"],
        "answer": result.get("answer"),
    }

