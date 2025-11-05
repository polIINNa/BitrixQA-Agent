import os

from dotenv import load_dotenv
from psycopg_pool import AsyncConnectionPool
from langchain_core.messages import HumanMessage

from bitrixqa_agent.state import InputState
from bitrixqa_agent.context import BitrixQAContext
from bitrixqa_agent.graph import get_graph_with_inmemory_checkpoint, get_graph_with_postgresql_checkpoint


load_dotenv()

async def get_answer(query: str, thread_id: str) -> str:
    """Основная функция для получения ответа"""
    connection_kwargs = {'autocommit': True, 'prepare_threshold': 0}
    async with AsyncConnectionPool(conninfo=os.getenv('DB_URI'), max_size=20, kwargs=connection_kwargs) as connection_pool:
        context = BitrixQAContext()
        bitrix_qa_graph = get_graph_with_postgresql_checkpoint(connection_pool=connection_pool)
        config = {"configurable": {"thread_id": thread_id}}
        _input = InputState(query=query, messages=[HumanMessage(content=query)])

        result = await bitrix_qa_graph.ainvoke(
            input=_input,
            context=context,
            config=config
        )
    print(result)
    if result["user_message_type"] == "objection":
        return "need_human"
    else:
        return result["answer"]