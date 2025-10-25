from langgraph.constants import START, END
from langgraph.graph import StateGraph

from state import BitrixQAState
from context import BitrixQAContext
from nodes import get_relevant_articles_ids_batch, form_context, generate_answer, continue_to_get_relevant_articles_ids

builder = StateGraph(BitrixQAState, context_schema=BitrixQAContext)

builder.add_node(get_relevant_articles_ids_batch.__graphname__, get_relevant_articles_ids_batch)
builder.add_node(form_context.__graphname__, form_context)
builder.add_node(generate_answer.__graphname__, generate_answer)

builder.add_conditional_edges(
    START,
    continue_to_get_relevant_articles_ids,
    [get_relevant_articles_ids_batch.__graphname__]
)
builder.add_edge(get_relevant_articles_ids_batch.__graphname__, form_context.__graphname__)
builder.add_edge(form_context.__graphname__, generate_answer.__graphname__)
builder.add_edge(generate_answer.__graphname__, END)

bitrix_qa_graph = builder.compile()
