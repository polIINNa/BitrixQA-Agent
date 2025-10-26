from langgraph.graph import StateGraph
from langgraph.constants import START, END
from langgraph.checkpoint.memory import InMemorySaver

from state import BitrixQAState
from context import BitrixQAContext
from nodes import (
    get_relevant_articles_ids_batch, form_context, generate_answer, continue_to_get_relevant_articles_ids,
    classify_message_type, llm_chat, user_node, qa_node
)
from routing_functions import message_type_routing

builder = StateGraph(BitrixQAState, context_schema=BitrixQAContext)

builder.add_node(classify_message_type.__graphname__, classify_message_type)
builder.add_node(llm_chat.__graphname__, llm_chat)
builder.add_node(qa_node.__graphname__, qa_node)
builder.add_node(get_relevant_articles_ids_batch.__graphname__, get_relevant_articles_ids_batch)
builder.add_node(form_context.__graphname__, form_context)
builder.add_node(generate_answer.__graphname__, generate_answer)
builder.add_node(user_node.__graphname__, user_node)

builder.add_edge(START, classify_message_type.__graphname__)
builder.add_conditional_edges(
    classify_message_type.__graphname__,
    message_type_routing,
    {
        "small_talk": llm_chat.__graphname__,
        "objection": END,
        "end_dialogue": END,
        "knowledge_question": qa_node.__graphname__
    }
)
# часть графа с qa
builder.add_conditional_edges(
    qa_node.__graphname__,
    continue_to_get_relevant_articles_ids,
    [get_relevant_articles_ids_batch.__graphname__]
)
builder.add_edge(get_relevant_articles_ids_batch.__graphname__, form_context.__graphname__)
builder.add_edge(form_context.__graphname__, generate_answer.__graphname__)
builder.add_edge(generate_answer.__graphname__, user_node.__graphname__)

# часть графа для простого llm_chat
builder.add_edge(llm_chat.__graphname__, user_node.__graphname__)

# ребро для перехода от user_node
builder.add_edge(user_node.__graphname__, classify_message_type.__graphname__)

def get_simple_graph():
    return builder.compile()

def get_graph_with_inmemory_checkpoint():
    return builder.compile(checkpointer=InMemorySaver())