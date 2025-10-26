import asyncio

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from graph import get_graph_with_inmemory_checkpoint
from context import BitrixQAContext


load_dotenv(override=True)

async def get_answer(query: str, thread_id: str) -> str:
    """Основная функция для получения ответа"""
    context = BitrixQAContext()
    bitrix_qa_graph = get_graph_with_inmemory_checkpoint()
    config = {"configurable": {"thread_id": thread_id}}
    result = await bitrix_qa_graph.ainvoke(input={"query": query, "messages": HumanMessage(content=query)}, context=context, config=config)
    print(result)
    if "answer" in result:
        return result["answer"]
    elif result["user_message_type"] == "objection":
        return "need_human"
    else:
        return "end_dialogue"

if __name__ == '__main__':

    async def main():
        thread_id = "test123"
        while True:
            user_message = input("Пользователь: ")
            answer = await get_answer(query=user_message, thread_id=thread_id)
            if answer is not None:
                print("Агент: ", answer)
            else:
                print("Переключение на специалиста")

    asyncio.run(main())
