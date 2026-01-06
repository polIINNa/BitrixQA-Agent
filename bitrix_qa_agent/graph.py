from langgraph.graph import StateGraph
from langgraph.constants import START, END

from bitrix_qa_agent.enum import NodeNames
from bitrix_qa_agent.state import BitrixQAState
from bitrix_qa_agent.context import BitrixQAContext
from bitrix_qa_agent.nodes import (
    check_new_intent,
    admin_node,
    check_negative,
    need_reply_check,
    positive_acknowledgement_check,
    knowledge_required_check,
    identify_search_query,
    get_relevant_articles_ids,
    form_context,
    generate_answer
)


builder = StateGraph(BitrixQAState, context_schema=BitrixQAContext)

builder.add_node(NodeNames.check_new_intent, check_new_intent)
builder.add_node(NodeNames.admin_node, admin_node)
builder.add_node(NodeNames.check_negative, check_negative)
builder.add_node(NodeNames.need_reply_check, need_reply_check)
builder.add_node(NodeNames.positive_acknowledgement_check, positive_acknowledgement_check)
builder.add_node(NodeNames.knowledge_required_check, knowledge_required_check)
builder.add_node(NodeNames.identify_search_query, identify_search_query)
builder.add_node(NodeNames.get_relevant_articles_ids, get_relevant_articles_ids)
builder.add_node(NodeNames.form_context, form_context)
builder.add_node(NodeNames.generate_answer, generate_answer)

builder.add_edge(START, NodeNames.check_new_intent)
builder.add_edge(NodeNames.identify_search_query, NodeNames.get_relevant_articles_ids)
builder.add_edge(NodeNames.get_relevant_articles_ids, NodeNames.form_context)
builder.add_edge(NodeNames.form_context, NodeNames.generate_answer)
builder.add_edge(NodeNames.generate_answer, NodeNames.admin_node)
builder.add_edge(NodeNames.admin_node, END)


def get_simple_graph():
    """Создать простой граф без памяти"""
    return builder.compile()
