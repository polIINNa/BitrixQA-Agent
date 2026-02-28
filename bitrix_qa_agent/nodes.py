#TODO: подумать над тем, чтобы сделать поход в базу (после knowledge_required проверки) сабграфом

import logging
from typing import Literal

logger = logging.getLogger(__name__)

from langgraph.types import Command
from langgraph.runtime import Runtime
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_core.exceptions import OutputParserException

from bitrix_qa_agent.context import BitrixQAContext
from bitrix_qa_agent.state import BitrixQAState, RAGState
from bitrix_qa_agent.prompts import (
    CHECK_NEW_INTENT_PROMPT,
    ADMIN_PROMPT,
    CHECK_NEGATIVE_PROMPT,
    NEED_REPLY_PROMPT, NeedReplyModel,
    POSITIVE_ACKNOWLEDGMENT_PROMPT,
    NEED_KNOWLEDGE_DATABASE_PROMPT,
    IDENTIFY_SEARCH_QUERY_PROMPT,
    CHOOSE_ARTICLES_PROMPT, ArticleRelevantIDSModel,
    GENERATE_ANSWER_PROMPT
)
from bitrix_qa_agent.enums import (
    UserMessageType,
    NodeNames
)
from bitrix_qa_agent.output_parsers import BoolDigitOutputParser
from bitrix_qa_agent.utils import get_article_title_and_problem, get_sections_content
from loader.database.repository import vector_search_articles as db_vector_search_articles


async def check_new_intent(
        state: BitrixQAState, runtime: Runtime[BitrixQAContext]
) -> Command[Literal['__end__', NodeNames.check_negative]]:
    """Проверить, сменилась ли тема диалога (новый интент)"""
    # Если история пуста — первое сообщение в сессии, смены темы нет
    if not state.chat_history:
        return Command(goto=NodeNames.check_negative)

    context = runtime.context or BitrixQAContext()
    chain = CHECK_NEW_INTENT_PROMPT | context.pro_model | BoolDigitOutputParser()
    has_new_intent = await chain.ainvoke(
        {
            "chat_history": state.chat_history,
            "last_user_message": state.last_user_message
        }
    )

    if has_new_intent:
        return Command(
            update={"user_message_type": UserMessageType.INTENT_CHANGED.value},
            goto='__end__'
        )

    return Command(goto=NodeNames.check_negative)


async def admin_node(state: BitrixQAState, runtime: Runtime[BitrixQAContext]) -> BitrixQAState:
    """Ответить на сообщение пользователя в режиме чата"""
    context = runtime.context or BitrixQAContext()
    chat = f"{state.chat_history}\n<Пользователь>\n{state.last_user_message}</Пользователь>"
    if state.user_message_type == UserMessageType.KNOWLEDGE_REQUIRED.value:
        raw_answer = state.answer
    else:
        raw_answer = "нет"
    chain = ADMIN_PROMPT | context.pro_model | StrOutputParser()
    answer = await chain.ainvoke(
        {
            "chat": chat,
            "raw_answer": raw_answer
        }
    )
    return {"answer": answer, "messages": AIMessage(content=answer)}


async def check_negative(
        state: BitrixQAState, runtime: Runtime[BitrixQAContext]
) -> Command[Literal['__end__', NodeNames.need_reply_check]]:
    """Проверить, есть ли негатив в сообщении клиента"""
    context = runtime.context or BitrixQAContext()
    chain = CHECK_NEGATIVE_PROMPT | context.lite_model | BoolDigitOutputParser()
    has_negative = await chain.ainvoke(
        {
            "chat_history": state.chat_history,
            "last_user_message": state.last_user_message
        }
    )
    if has_negative:
        return Command(
            update={"user_message_type": UserMessageType.NEGATIVE.value},
            goto='__end__'
        )
    return Command(goto=NodeNames.need_reply_check)


async def need_reply_check(
        state: BitrixQAState, runtime: Runtime[BitrixQAContext]
) -> Command[Literal['__end__', NodeNames.positive_acknowledgement_check]]:
    """Определить необходимость ответа"""
    context = runtime.context or BitrixQAContext()
    chain = NEED_REPLY_PROMPT | context.pro_model.with_structured_output(NeedReplyModel)
    chain_with_retry = chain.with_retry(
        retry_if_exception_type=(OutputParserException,), stop_after_attempt=3
    )
    need_reply = (await chain_with_retry.ainvoke(
        {
            "chat_history": state.chat_history,
            "last_user_message": state.last_user_message
        }
    )).need_reply
    if need_reply == 0:
        return Command(
            update={"user_message_type": UserMessageType.NO_NEED_REPLY.value},
            goto='__end__'
        )
    else:
        return Command(goto=NodeNames.positive_acknowledgement_check)


async def positive_acknowledgement_check(
        state: BitrixQAState, runtime: Runtime[BitrixQAContext]
) -> Command[Literal['__end__', NodeNames.knowledge_required_check]]:
    """Проверить, является ли сообщение клиента положительным откликом"""
    context = runtime.context or BitrixQAContext()
    chain = POSITIVE_ACKNOWLEDGMENT_PROMPT | context.lite_model | BoolDigitOutputParser()
    positive_acknowledgement = (await chain.ainvoke(
        {
            "chat_history": state.chat_history,
            "last_user_message": state.last_user_message
        }
    ))
    if positive_acknowledgement:
        return Command(
            update={"user_message_type": UserMessageType.POSITIVE_ACKNOWLEDGEMENT.value},
            goto='__end__'
        )
    else:
        return Command(goto=NodeNames.knowledge_required_check)


async def knowledge_required_check(
        state: BitrixQAState, runtime: Runtime[BitrixQAContext]
) -> Command[Literal[NodeNames.identify_search_query, NodeNames.admin_node]]:
    """Определяет необходимость похода в базу знаний"""
    context = runtime.context or BitrixQAContext()
    #TODO: переименовать промпт
    chain = NEED_KNOWLEDGE_DATABASE_PROMPT | context.lite_model | BoolDigitOutputParser()
    knowledge_required = (await chain.ainvoke(
        {
            "chat_history": state.chat_history,
            "last_user_message": state.last_user_message
        }
    ))
    if knowledge_required:
        return Command(
            update={"user_message_type": UserMessageType.KNOWLEDGE_REQUIRED.value},
            goto=NodeNames.identify_search_query
        )
    else:
        return Command(
            update={"user_message_type": UserMessageType.CHAT.value},
            goto=NodeNames.admin_node
        )


#TODO: выделить RAG часть в сабграф
async def identify_search_query(state: BitrixQAState, runtime: Runtime[BitrixQAContext]) -> RAGState:
    """Получить запрос пользователя для поиска по базе знаний"""
    context = runtime.context or BitrixQAContext()
    if state.chat_history == "":
        return {"query": state.last_user_message}
    else:
        chain = IDENTIFY_SEARCH_QUERY_PROMPT | context.lite_model | StrOutputParser()
        search_query = await chain.ainvoke(
            {
                "chat_history": state.chat_history,
                "last_user_message": state.last_user_message
            }
        )
        return {"query": search_query}


async def vector_search_articles(state: RAGState, runtime: Runtime[BitrixQAContext]) -> RAGState:
    """Векторный поиск ближайших статей по запросу"""
    context = runtime.context or BitrixQAContext()
    query_embedding = await context.embedding_client.embed(state.query)
    async with context.db_session_factory() as session:
        raw_results = await db_vector_search_articles(session, query_embedding, k=context.vector_search_k)

    seen_source_ids: set[int] = set()
    fetched_articles = []
    for _revision_id, source_article_id, content in raw_results:
        if source_article_id not in seen_source_ids:
            seen_source_ids.add(source_article_id)
            fetched_articles.append({"source_article_id": source_article_id, "content": content})

    logger.info(
        "vector_search_articles: найдено %d уникальных статей, source_article_ids=%s",
        len(fetched_articles),
        [a["source_article_id"] for a in fetched_articles],
    )
    return {"fetched_articles": fetched_articles}


async def get_relevant_articles_ids(
        state: RAGState, runtime: Runtime[BitrixQAContext]
) -> Command[Literal['__end__', NodeNames.form_context]]:
    """Отобрать релевантные статьи из найденных векторным поиском через LLM"""
    context = runtime.context or BitrixQAContext()

    async def get_relevant_articles_ids_batch(_input: dict) -> list | None:
        chain = CHOOSE_ARTICLES_PROMPT | context.lite_model.with_structured_output(ArticleRelevantIDSModel)
        chain_with_retry = chain.with_retry(
            retry_if_exception_type=(OutputParserException,), stop_after_attempt=3
        )
        result = (await chain_with_retry.ainvoke({
            "articles_metadata": _input["articles_metadata"],
            "query": _input["query"]
        })).relevant_articles_ids
        if result is not None:
            return [str(_id) for _id in result]
        return None

    article_batches = []
    batch = []
    for article in state.fetched_articles:
        title, problem = get_article_title_and_problem(article["content"])
        batch.append(
            f"ID статьи: {article['source_article_id']}\nТема: {title}\nПроблема: {problem}"
        )
        if len(batch) == context.articles_batch_size:
            article_batches.append({"articles_metadata": "\n\n".join(batch), "query": state.query})
            batch = []
    if batch:
        article_batches.append({"articles_metadata": "\n\n".join(batch), "query": state.query})

    relevant_articles_ids_all = []
    runnable = RunnableLambda(func=get_relevant_articles_ids_batch)
    async for _idx, relevant_ids in runnable.abatch_as_completed(article_batches, return_exceptions=True):
        if isinstance(relevant_ids, Exception):
            continue
        if relevant_ids is not None:
            relevant_articles_ids_all.extend(relevant_ids)

    logger.info(
        "get_relevant_articles_ids: отобрано %d из %d, relevant_ids=%s",
        len(relevant_articles_ids_all),
        len(state.fetched_articles),
        relevant_articles_ids_all,
    )

    if not relevant_articles_ids_all:
        logger.info("get_relevant_articles_ids: релевантных статей не найдено, завершаем с NEGATIVE")
        return Command(
            update={"user_message_type": UserMessageType.NEGATIVE.value},
            goto='__end__'
        )

    return Command(
        update={"relevant_articles_ids": relevant_articles_ids_all},
        goto=NodeNames.form_context
    )


async def form_context(state: RAGState, runtime: Runtime[BitrixQAContext]) -> RAGState:
    """Сформировать из отобранных статей контекст"""
    rag_context = []
    for article in state.fetched_articles:
        if str(article["source_article_id"]) in state.relevant_articles_ids:
            sections_content = get_sections_content(article_content=article["content"])
            rag_context.append(sections_content)
    return {"context": "\n\n".join(rag_context)}


async def generate_answer(state: RAGState, runtime: Runtime[BitrixQAContext]) -> BitrixQAState:
    """Сгенерировать ответ на вопрос"""
    context = runtime.context or BitrixQAContext()
    chain = GENERATE_ANSWER_PROMPT | context.lite_model | StrOutputParser()
    answer = await chain.ainvoke({"context": state.context, "query": state.query})
    return {"answer": answer}
