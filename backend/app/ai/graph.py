import logging
from langgraph.graph import StateGraph, END

from backend.app.ai.state import AgentState
from backend.app.ai.nodes import (
    detect_intent_node,
    retrieve_context_node,
    generate_answer_node,
    create_ticket_node,
    fetch_ticket_status_node,
    general_response_node
)

logger = logging.getLogger("campuspilot.workflow.graph")

def router_decision(state: AgentState) -> str:
    intent = state.get("intent", "UNKNOWN")
    logger.info(f"Router decision: intent={intent}")
    
    if intent == "FAQ":
        return "retrieve_context"
    elif intent == "COMPLAINT":
        return "create_ticket"
    elif intent == "TICKET_STATUS":
        return "fetch_ticket_status"
    else:
        return "general_response"

# Construct state graph
workflow = StateGraph(AgentState)

# Register nodes
workflow.add_node("detect_intent", detect_intent_node)
workflow.add_node("retrieve_context", retrieve_context_node)
workflow.add_node("generate_answer", generate_answer_node)
workflow.add_node("create_ticket", create_ticket_node)
workflow.add_node("fetch_ticket_status", fetch_ticket_status_node)
workflow.add_node("general_response", general_response_node)

# Set Entry Point
workflow.set_entry_point("detect_intent")

# Add conditional edges from intent detection
workflow.add_conditional_edges(
    "detect_intent",
    router_decision,
    {
        "retrieve_context": "retrieve_context",
        "create_ticket": "create_ticket",
        "fetch_ticket_status": "fetch_ticket_status",
        "general_response": "general_response"
    }
)

# Set up linear routing
workflow.add_edge("retrieve_context", "generate_answer")
workflow.add_edge("generate_answer", END)
workflow.add_edge("create_ticket", END)
workflow.add_edge("fetch_ticket_status", END)
workflow.add_edge("general_response", END)

# Compile LangGraph
compiled_graph = workflow.compile()

def run_agent_workflow(user_message: str, student_name: str, student_email: str) -> dict:
    """
    Executes the compiled LangGraph workflow synchronously.
    """
    initial_state = {
        "user_message": user_message,
        "student_name": student_name,
        "student_email": student_email,
        "intent": None,
        "category": None,
        "priority": None,
        "location_id": None,
        "description": None,
        "retrieved_documents": None,
        "answer": None,
        "ticket_id": None,
        "department": None,
        "confidence": None,
        "source": None
    }
    
    result = compiled_graph.invoke(initial_state)
    return result
