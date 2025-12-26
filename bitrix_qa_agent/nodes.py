import json

from langgraph.runtime import Runtime
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import AIMessage

from bitrix_qa_agent.context import BitrixQAContext
from bitrix_qa_agent.state import BitrixQAState, RAGState
from bitrix_qa_agent.utils import get_article_batches, get_sections_content
from bitrix_qa_agent.chains import (
    choose_article_chain, generate_answer_chain, admin_answer_chain, classify_message_chain, prepare_query_chain
)


async def admin_node(state: BitrixQAState, runtime: Runtime[BitrixQAContext]) -> BitrixQAState:
    """Просто ответить на сообщение пользователя в режиме чата"""
    context = runtime.context or BitrixQAContext()
    chat = f"{state.chat_history}\nПользователь: {state.last_user_message}"
    if state.user_message_type == "knowledge_question":
        answer = state.answer
    else:
        answer = "нет"
    answer = await admin_answer_chain(context.admin_answer_model).ainvoke(
        {
            "chat": chat,
            "raw_answer": answer
        }
    )
    return {"answer": answer, "messages": AIMessage(content=answer)}

admin_node.__graphname__ = "Ответить на сообщение пользователя в режиме чат"

async def classify_message_type(state: BitrixQAState, runtime: Runtime[BitrixQAContext]) -> BitrixQAState:
    """Получить тип сообщения пользователя"""
    context = runtime.context or BitrixQAContext()
    message_type = (await classify_message_chain(context.classify_message_model).ainvoke(
        {
            "chat_history": state.chat_history,
            "last_user_message": state.last_user_message
        }
    )).type
    return {"user_message_type": message_type}

classify_message_type.__graphname__ = "Получить тип сообщения пользователя"


async def prepare_search_query(state: BitrixQAState, runtime: Runtime[BitrixQAContext]) -> RAGState:
    """Получить текущий запрос пользователя из истории сообщений"""
    context = runtime.context or BitrixQAContext()
    if state.chat_history == "":
        return {"query": state.last_user_message}
    else:
        query = await prepare_query_chain(context.prepare_query_model).ainvoke(
            {
                "chat_history": state.chat_history,
                "last_user_message": state.last_user_message,
            }
        )
        return {"query": query}

prepare_search_query.__graphname__ = "Получить запрос для поиска по базе знаний"

async def get_relevant_articles_ids(state: RAGState, runtime: Runtime[BitrixQAContext]) -> RAGState:
    """Получить релевантные ids по всем батчам"""

    async def get_relevant_articles_ids_batch(_input: dict) -> list | None:
        """Получить ids по одному батчу"""
        relevant_articles_ids_result = (await choose_article_chain(_input["model"]).ainvoke({
            "articles_metadata": _input["articles_metadata"],
            "query": _input["query"]
        })).relevant_articles_ids
        if relevant_articles_ids_result is not None:
            return [str(_id) for _id in relevant_articles_ids_result]
        return None

    context = runtime.context or BitrixQAContext()
    with open(context.articles_metadata_path, "r", encoding="utf-8") as f:
        articles_metadata = json.load(f)
    article_batches = get_article_batches(articles_metadata=articles_metadata, batch_size=context.articles_batch_size)
    _inputs = [
        {"articles_metadata": batch_articles_metadata, "query": state.query, "model": context.get_relevant_articles_model}
        for batch_articles_metadata in article_batches
    ]
    relevant_articles_ids_all = []
    runnable = RunnableLambda(func=get_relevant_articles_ids_batch)
    async for idx, relevant_articles_ids in runnable.abatch_as_completed(_inputs, return_exceptions=True):
        if isinstance(relevant_articles_ids, Exception):
            continue
        if relevant_articles_ids is not None:
            relevant_articles_ids_all.extend(relevant_articles_ids)

    return {"relevant_articles_ids": relevant_articles_ids_all}

get_relevant_articles_ids.__graphname__ = "Получить IDs статей, которые релевантны запросу"

async def form_context(state: RAGState, runtime: Runtime[BitrixQAContext]) -> RAGState:
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

async def generate_answer(state: RAGState, runtime: Runtime[BitrixQAContext]) -> BitrixQAState:
    """Сгенерирвоать ответ на вопрос"""
    context = runtime.context or BitrixQAContext()
    answer = await generate_answer_chain(context.generate_answer_model).ainvoke({"context": state.context, "query": state.query})
    return {"answer": answer}

generate_answer.__graphname__ = "Сгенерировать ответ на вопрос по базе знаний"
