import json

from langgraph.runtime import Runtime
from langgraph.types import Send, interrupt
from langchain_core.messages import HumanMessage, AIMessage

from bitrixqa_agent.context import BitrixQAContext
from bitrixqa_agent.state import BitrixQAState, GetRelevantArticlesState
from bitrixqa_agent.utils import get_article_batches, get_sections_content
from bitrixqa_agent.chains import choose_article_chain, generate_answer_chain, llm_chat_chain, classify_message_chain


async def classify_message_type(state: BitrixQAState, runtime: Runtime[BitrixQAContext]):
    """Получить тип сообщения пользователя"""

    context = runtime.context or BitrixQAContext()
    message_type = (await classify_message_chain(context.model).ainvoke({"user_message": state.query})).type

    return {"user_message_type": message_type}

classify_message_type.__graphname__ = "Получить тип сообщения пользователя"


async def llm_chat(state: BitrixQAState, runtime: Runtime[BitrixQAContext]):
    """Сгенерировать ответ на сообщение пользователя, без контекста, простой ответ"""

    context = runtime.context or BitrixQAContext()
    answer = await llm_chat_chain(context.model).ainvoke({"user_message": state.query})

    return {"answer": answer, "messages": AIMessage(content=answer)}

llm_chat.__graphname__ = "Получить простой ответ на сообщение, просто чат без QA"


async def qa_node(state: BitrixQAState):
    """Промежуточная нода для перехода к части с QA и Send"""
    return state

qa_node.__graphname__ = "Нода для перехода к Send"


async def get_relevant_articles_ids_batch(state: GetRelevantArticlesState, runtime: Runtime[BitrixQAContext]):
    """Получить релевантные статьи из батча"""

    context = runtime.context or BitrixQAContext()
    relevant_articles_ids_result = (await choose_article_chain(context.model).ainvoke({
        "articles_metadata": state.articles_metadata,
        "query": state.query
    })).relevant_articles_ids

    if relevant_articles_ids_result is not None:
        relevant_articles_ids = [str(_id) for _id in relevant_articles_ids_result]
        return {"relevant_articles_ids": relevant_articles_ids}

get_relevant_articles_ids_batch.__graphname__ = "Получить IDs релевантных статей"


async def continue_to_get_relevant_articles_ids(state: BitrixQAState, runtime: Runtime[BitrixQAContext]):
    """Разбивает статьи по батчам для параллельной обработки"""

    context = runtime.context or BitrixQAContext()
    with open(context.articles_metadata_path, "r", encoding="utf-8") as f:
        articles_metadata = json.load(f)
    article_batches = get_article_batches(articles_metadata=articles_metadata, batch_size=context.articles_batch_size)

    return [
        Send(
            get_relevant_articles_ids_batch.__graphname__,
            GetRelevantArticlesState(query=state.query, articles_metadata=batch_articles_metadata)
        )
        for batch_articles_metadata in article_batches
    ]


async def form_context(state: BitrixQAState, runtime: Runtime[BitrixQAContext]):
    """Сформировать из найденных статей контекст"""

    rag_context = []
    context = runtime.context or BitrixQAContext()
    with open(context.articles_metadata_path, "r", encoding="utf-8") as f:
        articles_metadata = json.load(f)

    for _id, metadata in articles_metadata.items():
        if _id in state.relevant_articles_ids:
            with open(f"{context.articles_files_path}/{metadata['article_filename']}", "r", encoding="utf-8") as f:
                article_content = f.read()
            sections_article_content = get_sections_content(article_content=article_content)
            rag_context.append(sections_article_content)

    return {"context": "\n\n".join(rag_context)}

form_context.__graphname__ = "Сформировать контекст для ответа на вопрос"


async def generate_answer(state: BitrixQAState, runtime: Runtime[BitrixQAContext]):
    """Сгенерирвоать ответ на вопрос"""

    context = runtime.context or BitrixQAContext()
    answer = await generate_answer_chain(context.model).ainvoke({"context": state.context, "query": state.query})

    return {"answer": answer, "messages": AIMessage(content=answer)}

generate_answer.__graphname__ = "Сгенерировать ответ на вопрос"


async def user_node(state: BitrixQAState):
    """Нода для получения сообщения от пользователя"""

    message_to_user = interrupt(state.answer)

    return {"messages": [HumanMessage(content=message_to_user)]}

user_node.__graphname__ = "Отправить ответ пользователю (ожидание ответа от него)"