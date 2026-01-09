#TODO: подумать над тем, чтобы сделать поход в базу (после knowledge_required проверки) сабграфом

import json
from typing import Literal

from langgraph.types import Command
from langgraph.runtime import Runtime
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.output_parsers import StrOutputParser

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
from bitrix_qa_agent.enum import (
    UserMessageType,
    NodeNames
)
from bitrix_qa_agent.output_parsers import BoolDigitOutputParser
from bitrix_qa_agent.utils import get_article_batches, get_sections_content


async def check_new_intent(
        state: BitrixQAState, runtime: Runtime[BitrixQAContext]
) -> Command[Literal['__end__', NodeNames.check_negative]]:
    """Проверить, сменилась ли тема диалога (новый интент)"""
    # Если история пуста - это первое сообщение в сессии, пропускаем проверку
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
    #TODO: сделать chain_with_retry
    need_reply = (await chain.ainvoke(
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


async def get_relevant_articles_ids(state: RAGState, runtime: Runtime[BitrixQAContext]) -> RAGState:
    """Получить релевантные ids по всем батчам"""
    context = runtime.context or BitrixQAContext()

    async def get_relevant_articles_ids_batch(_input: dict) -> list | None:
        """Получить ids по одному батчу"""
        chain = CHOOSE_ARTICLES_PROMPT | context.lite_model.with_structured_output(ArticleRelevantIDSModel)
        relevant_articles_ids_result = (await chain.ainvoke({
            "articles_metadata": _input["articles_metadata"],
            "query": _input["query"]
        })).relevant_articles_ids
        if relevant_articles_ids_result is not None:
            return [str(_id) for _id in relevant_articles_ids_result]
        return None

    with open(context.articles_metadata_path, "r", encoding="utf-8") as f:
        articles_metadata = json.load(f)
    article_batches = get_article_batches(articles_metadata=articles_metadata, batch_size=context.articles_batch_size)
    _inputs = [
        {"articles_metadata": batch_articles_metadata, "query": state.query}
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


async def generate_answer(state: RAGState, runtime: Runtime[BitrixQAContext]) -> BitrixQAState:
    """Сгенерировать ответ на вопрос"""
    context = runtime.context or BitrixQAContext()
    chain = GENERATE_ANSWER_PROMPT | context.lite_model | StrOutputParser()
    answer = await chain.ainvoke({"context": state.context, "query": state.query})
    return {"answer": answer}
