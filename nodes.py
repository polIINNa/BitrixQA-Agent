import json

from langgraph.runtime import Runtime
from langgraph.types import Send

from context import BitrixQAContext
from chains import choose_article_chain, generate_answer_chain
from state import BitrixQAState, GetRelevantArticlesState
from utils import get_article_batches, get_sections_content


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

    return {"answer": answer}

generate_answer.__graphname__ = "Сгенерировать ответ на вопрос"