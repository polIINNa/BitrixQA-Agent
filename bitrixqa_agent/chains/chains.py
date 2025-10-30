from langchain_core.runnables import Runnable
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser

from bitrixqa_agent.chains.prompts import (
    choose_article_prompt, ArticleRelevantIDS, generate_answer_prompt,
    message_type_classification_prompt, MessageTypeClassification, llm_chat_prompt
)


def choose_article_chain(model: BaseChatModel) -> Runnable:
    """Цепочка для выбора релевантных статей"""
    return choose_article_prompt | model.with_structured_output(ArticleRelevantIDS)


def generate_answer_chain(model: BaseChatModel) -> Runnable:
    """Цепочка для генерации ответа на вопрос"""
    return generate_answer_prompt | model | StrOutputParser()


def classify_message_chain(model: BaseChatModel) -> Runnable:
    """Цепочка для получения типа сообщения пользователя"""
    return message_type_classification_prompt | model.with_structured_output(MessageTypeClassification)


def llm_chat_chain(model: BaseChatModel) -> Runnable:
    """Цепочка для получения простого чата, не для ответа по QA"""
    return llm_chat_prompt | model | StrOutputParser()
