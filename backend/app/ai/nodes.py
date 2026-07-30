import re
import logging
from sqlalchemy.orm import Session

from backend.app.ai.state import AgentState
from backend.app.services.ai_service import detect_student_intent, generate_faq_response, classify_complaint_details
from backend.app.services.rag_service import query_vector_database
from backend.app.database.connection import SessionLocal
from backend.app.models.models import Ticket, Department, Location, Complaint
from backend.app.api.tickets import get_department_code_by_category, calculate_resolution_hours

logger = logging.getLogger("campuspilot.workflow.nodes")

def detect_intent_node(state: AgentState) -> dict:
    logger.info("Node: detect_intent_node")
    intent_data = detect_student_intent(state["user_message"])
    
    return {
        "intent": intent_data.get("intent", "UNKNOWN"),
        "category": intent_data.get("category"),
        "priority": intent_data.get("priority"),
        "confidence": 0.95
    }

def retrieve_context_node(state: AgentState) -> dict:
    logger.info("Node: retrieve_context_node")
    search_results = query_vector_database(state["user_message"], k=3)
    
    return {
        "retrieved_documents": search_results
    }

def generate_answer_node(state: AgentState) -> dict:
    logger.info("Node: generate_answer_node")
    docs = state.get("retrieved_documents") or []
    
    if not docs:
        context = "No specific guidelines found in knowledge base."
        source = "None"
    else:
        context = "\n\n".join([f"[Source: {res['source']}, Page {res['page']}]: {res['text']}" for res in docs])
        source = docs[0]["source"]
        
    answer = generate_faq_response(state["user_message"], context)
    return {
        "answer": answer,
        "source": source
    }

def create_ticket_node(state: AgentState) -> dict:
    logger.info("Node: create_ticket_node")
    message = state["user_message"]
    
    # Classify complaint details (category, priority, reasoning)
    class_res = classify_complaint_details(message)
    category = class_res.get("category", "water_leakage")
    priority = class_res.get("priority", "MEDIUM")
    
    db: Session = SessionLocal()
    try:
        # Resolve Location by text match or default
        loc = None
        message_lower = message.lower()
        locations = db.query(Location).all()
        for l in locations:
            if l.name.lower() in message_lower:
                loc = l
                break
        if not loc:
            loc = db.query(Location).filter(Location.name == "Multi-Purpose Hall").first()
            if not loc:
                loc = db.query(Location).first() # fallback
                
        # Create Complaint
        new_complaint = Complaint(
            user_id=1, # Mock student ID
            location_id=loc.id if loc else 1,
            category=category,
            description=message,
            priority=priority
        )
        db.add(new_complaint)
        db.commit()
        db.refresh(new_complaint)
        
        # Resolve Department
        dept_code = get_department_code_by_category(category)
        dept = db.query(Department).filter(Department.code == dept_code).first()
        if not dept:
            dept = db.query(Department).filter(Department.code == "MAINT").first()
            
        # Estimate hours
        est_hours = calculate_resolution_hours(priority)
        
        # Create Ticket
        new_ticket = Ticket(
            complaint_id=new_complaint.id,
            title=f"Ticket for Complaint #{new_complaint.id}: {category.replace('_', ' ').title()}",
            description=message,
            status="OPEN",
            priority=priority,
            department_id=dept.id if dept else None,
            location_id=loc.id if loc else None,
            estimated_resolution_hours=est_hours
        )
        db.add(new_ticket)
        db.commit()
        db.refresh(new_ticket)
        
        dept_name = dept.name if dept else "General Administration"
        answer = (
            f"I have successfully created a ticket for your complaint.\n\n"
            f"**Ticket ID**: #{new_ticket.id}\n"
            f"**Department**: {dept_name}\n"
            f"**Assigned Priority**: {priority}\n"
            f"**Estimated Resolution**: {est_hours} hours\n\n"
            f"Our campus operations team has been notified."
        )
        
        return {
            "ticket_id": new_ticket.id,
            "department": dept_name,
            "category": category,
            "priority": priority,
            "location_id": loc.id if loc else None,
            "description": message,
            "answer": answer
        }
    except Exception as e:
        logger.error(f"Error creating ticket in workflow: {e}")
        db.rollback()
        return {
            "answer": "Sorry, I encountered a database error while attempting to file your complaint. Please try again later."
        }
    finally:
        db.close()

def fetch_ticket_status_node(state: AgentState) -> dict:
    logger.info("Node: fetch_ticket_status_node")
    message = state["user_message"]
    
    # Extract ticket ID number (e.g. #3 or just number 3)
    match = re.search(r'#?(\d+)', message)
    if not match:
        return {
            "answer": "Could you please provide the ticket reference number (e.g., #3 or Ticket 3) so I can verify its status for you?"
        }
        
    ticket_id = int(match.group(1))
    db: Session = SessionLocal()
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            return {
                "answer": f"I was unable to find any ticket with reference #{ticket_id}. Please verify your reference number and try again."
            }
            
        dept_name = ticket.department.name if ticket.department else "General Administration"
        answer = (
            f"Here is the status of your ticket #{ticket.id}:\n\n"
            f"**Title**: {ticket.title}\n"
            f"**Current Status**: {ticket.status}\n"
            f"**Priority**: {ticket.priority}\n"
            f"**Assigned Department**: {dept_name}\n"
            f"**Last Updated**: {ticket.updated_at.strftime('%Y-%m-%d %H:%M UTC')}"
        )
        return {
            "ticket_id": ticket.id,
            "answer": answer
        }
    except Exception as e:
        logger.error(f"Error fetching ticket status: {e}")
        return {
            "answer": "Sorry, I encountered an error while searching for your ticket status. Please try again later."
        }
    finally:
        db.close()

def general_response_node(state: AgentState) -> dict:
    logger.info("Node: general_response_node")
    from backend.app.ai.prompts import GENERAL_CHAT_SYSTEM
    prompt = (
        f"Conversational input: \"{state['user_message']}\"\n"
        f"Respond politely to the student."
    )
    answer = ai_client.generate_text(prompt, GENERAL_CHAT_SYSTEM)
    return {
        "answer": answer
    }
