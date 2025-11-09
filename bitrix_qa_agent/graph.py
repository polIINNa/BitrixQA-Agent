from langgraph.graph import StateGraph
from langgraph.constants import START, END

from bitrix_qa_agent.state import BitrixQAState
from bitrix_qa_agent.context import BitrixQAContext
from bitrix_qa_agent.nodes import (
    prepare_search_query, get_relevant_articles_ids, form_context, generate_answer,
    classify_message_type, admin_node
)
from bitrix_qa_agent.routing_functions import message_type_routing

builder = StateGraph(BitrixQAState, context_schema=BitrixQAContext)


builder.add_node(prepare_search_query.__graphname__, prepare_search_query)
builder.add_node(classify_message_type.__graphname__, classify_message_type)
builder.add_node(admin_node.__graphname__, admin_node)
builder.add_node(get_relevant_articles_ids.__graphname__, get_relevant_articles_ids)
builder.add_node(form_context.__graphname__, form_context)
builder.add_node(generate_answer.__graphname__, generate_answer)

builder.add_edge(START, classify_message_type.__graphname__)
builder.add_conditional_edges(
    classify_message_type.__graphname__,
    message_type_routing,
    {
        "chat": admin_node.__graphname__,
        "objection": END,
        "knowledge_question": prepare_search_query.__graphname__
    }
)
# часть графа с qa
builder.add_edge(prepare_search_query.__graphname__, get_relevant_articles_ids.__graphname__)
builder.add_edge(get_relevant_articles_ids.__graphname__, form_context.__graphname__)
builder.add_edge(form_context.__graphname__, generate_answer.__graphname__)
builder.add_edge(generate_answer.__graphname__, admin_node.__graphname__)

# часть графа для получения ответа на сообщение
builder.add_edge(admin_node.__graphname__, END)

def get_simple_graph():
    """Создать простой граф без памяти"""
    return builder.compile()
