from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, Field
from langchain_core.runnables import Runnable
from langchain_core.language_models import BaseChatModel

from prompts import choose_article_prompt, generate_answer_prompt


def choose_article_chain(model: BaseChatModel) -> Runnable:
    """Цепочка для выбора релевантных статей"""

    class ArticleRelevantIDS(BaseModel):
        """ID релевантных статей"""
        relevant_articles_ids: list[int] | None = Field(description="ID статей из документации, которые содержат релевантную информацию по вопросу. Если НИ ОДНА из статей не подходит - верни null.")
    chain = choose_article_prompt | model.with_structured_output(ArticleRelevantIDS)
    return chain


def generate_answer_chain(model: BaseChatModel) -> Runnable:
    """Цепочка для генерации ответа на вопрос"""
    return generate_answer_prompt | model | StrOutputParser()
