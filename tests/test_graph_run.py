import asyncio

from dotenv import load_dotenv

from graph import bitrix_qa_graph
from context import BitrixQAContext


load_dotenv(override=True)

async def get_answer(query: str):
    context = BitrixQAContext()
    result = await bitrix_qa_graph.ainvoke(input={"query": query}, context=context)
    return result

if __name__ == '__main__':
    query = "Как перенести данные из excel в Битрикс?"
    print(asyncio.run(get_answer(query=query)))

