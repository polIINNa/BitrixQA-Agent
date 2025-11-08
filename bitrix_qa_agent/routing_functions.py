from bitrix_qa_agent.state import BitrixQAState


async def message_type_routing(state: BitrixQAState):
    """Роутинг на тип сообщения"""
    return state.user_message_type
