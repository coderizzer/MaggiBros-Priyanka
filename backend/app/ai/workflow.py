from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from sqlalchemy.orm import Session
from backend.app.ai.services import detect_user_intent, route_ticket_details
from backend.app.vectorstore.manager import vector_store
from backend.app.ai.client import ai_client
from backend.app.database.connection import SessionLocal
from backend.app.models.models import Ticket, Department, Location, Complaint

class AgentState(TypedDict):
    message: str
    student_name: str
    student_email: str
    intent: Optional[str]
    rag_context: Optional[str]
    response: Optional[str]
    ticket_created: bool
    ticket_id: Optional[int]
    category: Optional[str]
    priority: Optional[str]
    department_name: Optional[str]

# 1. Intent Detection Node
def detect_intent_node(state: AgentState) -> AgentState:
    print("--- DETECTING INTENT ---")
    intent_data = detect_user_intent(state["message"])
    return {
        **state,
        "intent": intent_data.intent
    }

# 2. RAG Retrieval Node
def retrieve_context_node(state: AgentState) -> AgentState:
    print("--- RETRIEVING CONTEXT ---")
    search_results = vector_store.search(state["message"], k=3)
    if search_results:
        context = "\n\n".join([f"[Source: {res['source']}, Page {res['page']}]: {res['text']}" for res in search_results])
    else:
        context = "No specific guidelines found in knowledge base."
        
    return {
        **state,
        "rag_context": context
    }

# 3. RAG Response Generation Node
def generate_rag_response_node(state: AgentState) -> AgentState:
    print("--- GENERATING ANSWER FROM CONTEXT ---")
    prompt = (
        f"You are CampusPilot, an AI Assistant for VIT Bhopal. Answer the student's question based on the context provided.\n"
        f"If the context doesn't have the answer, use your general knowledge but mention it is not explicitly from the handbook.\n\n"
        f"Context:\n{state['rag_context']}\n\n"
        f"Student Query: \"{state['message']}\"\n"
    )
    system_instruction = "You are a helpful and polite campus assistant. Keep answers clear, professional, and actionable."
    response = ai_client.generate_text(prompt, system_instruction)
    return {
        **state,
        "response": response
    }

# 4. Ticket Creator Node (Routes + Files in DB)
def create_ticket_node(state: AgentState) -> AgentState:
    print("--- CREATING TICKET ---")
    message = state["message"]
    
    # Auto route title and priority using LLM
    route_details = route_ticket_details(title=message[:50] + "...", description=message)
    
    db: Session = SessionLocal()
    try:
        # Resolve Department by code
        dept = db.query(Department).filter(Department.code == route_details.recommended_department_code).first()
        if not dept:
            dept = db.query(Department).filter(Department.code == "MAINT").first() # fallback
            
        # Resolve Location by simple text matching
        loc = None
        message_lower = message.lower()
        locations = db.query(Location).all()
        for l in locations:
            if l.name.lower() in message_lower:
                loc = l
                break
        if not loc:
            # Fallback to Multi-Purpose Hall
            loc = db.query(Location).filter(Location.name == "Multi-Purpose Hall").first()
            if not loc:
                loc = db.query(Location).first() # absolute fallback
                
        # Create complaint record first
        new_complaint = Complaint(
            user_id=1,  # Mock user ID for the current session
            location_id=loc.id if loc else 1,
            category=route_details.category,
            description=message,
            priority=route_details.recommended_priority
        )
        db.add(new_complaint)
        db.commit()
        db.refresh(new_complaint)

        # Estimate resolution hours
        from backend.app.api.tickets import calculate_resolution_hours
        est_hours = calculate_resolution_hours(new_complaint.priority)

        # Create ticket record associated with complaint
        new_ticket = Ticket(
            complaint_id=new_complaint.id,
            title=f"Ticket for Complaint #{new_complaint.id}: {new_complaint.category.replace('_', ' ').title()}",
            description=message,
            status="OPEN",
            priority=new_complaint.priority,
            department_id=dept.id if dept else None,
            location_id=loc.id if loc else None,
            estimated_resolution_hours=est_hours
        )
        db.add(new_ticket)
        db.commit()
        db.refresh(new_ticket)
        
        ticket_id = new_ticket.id
        dept_name = dept.name if dept else "General Administration"
        response = (
            f"Hello {state['student_name']}, I have automatically filed a support ticket for your issue.\n\n"
            f"**Ticket Reference**: #{ticket_id}\n"
            f"**Department**: {dept_name}\n"
            f"**Priority Assigned**: {new_ticket.priority}\n"
            f"**Status**: OPEN\n\n"
            f"An email notification has been dispatched to {state['student_email']} and {dept.email if dept else 'admin'}. "
            f"Our team will get back to you shortly."
        )
        
        return {
            **state,
            "ticket_created": True,
            "ticket_id": ticket_id,
            "category": route_details.category,
            "priority": new_ticket.priority,
            "department_name": dept_name,
            "response": response
        }
    except Exception as e:
        print(f"Error creating ticket in workflow: {e}")
        db.rollback()
        return {
            **state,
            "ticket_created": False,
            "response": "I encountered an error while trying to automatically create a support ticket. Please try again later."
        }
    finally:
        db.close()

# 5. General Smalltalk Response Node
def generate_general_response_node(state: AgentState) -> AgentState:
    print("--- GENERATING GENERAL RESPONSE ---")
    prompt = (
        f"The student sent a message that is conversational or greeting.\n"
        f"Message: \"{state['message']}\"\n"
        f"Answer them politely and let them know they can ask questions about campus guidelines or report problems (wifi, plumbing, electrical, etc.) to file a ticket."
    )
    system_instruction = "You are CampusPilot assistant. Introduce your capability to report issues and query guidelines."
    response = ai_client.generate_text(prompt, system_instruction)
    return {
        **state,
        "response": response
    }

# 6. Routing Decision Logic
def router_decision(state: AgentState):
    intent = state.get("intent")
    if intent == "TICKET":
        return "create_ticket"
    elif intent == "QUERY":
        return "retrieve_context"
    else:
        return "general_response"

# Build LangGraph workflow
workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("detect_intent", detect_intent_node)
workflow.add_node("retrieve_context", retrieve_context_node)
workflow.add_node("generate_rag_response", generate_rag_response_node)
workflow.add_node("create_ticket", create_ticket_node)
workflow.add_node("general_response", generate_general_response_node)

# Set Entry Point
workflow.set_entry_point("detect_intent")

# Add Conditional Edges
workflow.add_conditional_edges(
    "detect_intent",
    router_decision,
    {
        "create_ticket": "create_ticket",
        "retrieve_context": "retrieve_context",
        "general_response": "general_response"
    }
)

# Connect linear nodes
workflow.add_edge("retrieve_context", "generate_rag_response")
workflow.add_edge("generate_rag_response", END)
workflow.add_edge("create_ticket", END)
workflow.add_edge("general_response", END)

# Compile Graph
graph_app = workflow.compile()

def run_campus_pilot_workflow(message: str, student_name: str, student_email: str) -> dict:
    initial_state = {
        "message": message,
        "student_name": student_name,
        "student_email": student_email,
        "intent": None,
        "rag_context": None,
        "response": None,
        "ticket_created": False,
        "ticket_id": None,
        "category": None,
        "priority": None,
        "department_name": None
    }
    
    # Execute graph synchronously
    result = graph_app.invoke(initial_state)
    return result
