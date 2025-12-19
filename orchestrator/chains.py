from langchain_core.runnables import Runnable
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser

from orchestrator.prompts import support_session_end_prompt


def is_support_session_end_chain(model: BaseChatModel) -> Runnable:
    """Цепочка для определения окончания сессии поддержки"""
    return support_session_end_prompt | model | StrOutputParser()