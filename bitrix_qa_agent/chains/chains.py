from langchain_core.runnables import Runnable
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser

from bitrix_qa_agent.chains.prompts import (
    choose_article_prompt, ArticleRelevantIDS, generate_answer_prompt,
    message_type_classification_prompt, MessageTypeClassification, admin_prompt, prepare_query_prompt
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


def admin_answer_chain(model: BaseChatModel) -> Runnable:
    """Цепочка для получения финального ответа пользователя"""
    return admin_prompt | model | StrOutputParser()


def prepare_query_chain(model: BaseChatModel) -> Runnable:
    """Цепочка для получения ответа на вопрос пользователя"""
    return prepare_query_prompt | model | StrOutputParser()