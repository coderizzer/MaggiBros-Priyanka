from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any

from backend.app.database.connection import get_db
from backend.app.ai.graph import run_agent_workflow
from backend.app.services.ai_service import classify_complaint_details
from backend.app.models.models import Ticket, Department, Location, Complaint, ChatMessage
from backend.app.api.tickets import get_department_code_by_category, calculate_resolution_hours

router = APIRouter(prefix="", tags=["Main Chat Interface"])

class ChatRequest(BaseModel):
    message: str
    location_id: Optional[int] = None

@router.post("/chat")
def handle_chat_session(request: ChatRequest, db: Session = Depends(get_db)):
    try:
        # Register User Query in database
        user_message_log = ChatMessage(
            sender="user",
            message=request.message
        )
        db.add(user_message_log)
        db.commit()
        db.refresh(user_message_log)

        # Scenario 1: Location provided directly -> Create Ticket
        if request.location_id is not None:
            # Verify location exists
            loc = db.query(Location).filter(Location.id == request.location_id).first()
            if not loc:
                raise HTTPException(status_code=400, detail="Invalid location_id provided.")
                
            # Classify complaint details via AI classification
            class_res = classify_complaint_details(request.message)
            category = class_res.get("category", "water_leakage")
            priority = class_res.get("priority", "MEDIUM")
            
            # Create Complaint
            complaint = Complaint(
                user_id=1,  # Default student profile
                location_id=loc.id,
                category=category,
                description=request.message,
                priority=priority
            )
            db.add(complaint)
            db.commit()
            db.refresh(complaint)
            
            # Resolve routing
            dept_code = get_department_code_by_category(category)
            dept = db.query(Department).filter(Department.code == dept_code).first()
            if not dept:
                dept = db.query(Department).filter(Department.code == "MAINT").first()
                
            est_hours = calculate_resolution_hours(priority)
            
            # Create Ticket
            ticket = Ticket(
                complaint_id=complaint.id,
                title=f"Ticket for Complaint #{complaint.id}: {category.replace('_', ' ').title()}",
                description=request.message,
                status="OPEN",
                priority=priority,
                department_id=dept.id if dept else None,
                location_id=loc.id,
                estimated_resolution_hours=est_hours
            )
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            
            dept_name = dept.name if dept else "Maintenance"
            
            response_data = {
                "type": "ticket_created",
                "ticket_id": ticket.id,
                "message": "Your complaint has been submitted successfully.",
                "department": dept_name,
                "estimated_resolution": f"{est_hours} hours"
            }
            
            # Register Assistant Reply
            asst_message_log = ChatMessage(
                sender="assistant",
                message=f"Ticket #{ticket.id} created.",
                intent="COMPLAINT",
                ticket_id=ticket.id
            )
            db.add(asst_message_log)
            db.commit()
            
            return response_data
            
        # Scenario 2: Standard message -> Route through LangGraph
        result = run_agent_workflow(
            user_message=request.message,
            student_name="Student",
            student_email="student@vitbhopal.ac.in"
        )
        
        intent = result.get("intent", "UNKNOWN")
        
        # If complaint, intercept to ask for location
        if intent == "COMPLAINT":
            response_data = {
                "type": "complaint",
                "message": "I can help you report this issue.",
                "category": result.get("category") or "water_leakage",
                "next_action": "select_location"
            }
            
            # Register Assistant Reply
            asst_message_log = ChatMessage(
                sender="assistant",
                message="Awaiting location selection.",
                intent="COMPLAINT"
            )
            db.add(asst_message_log)
            db.commit()
            
            return response_data
            
        # If ticket status request
        if intent == "TICKET_STATUS":
            ticket_id = result.get("ticket_id")
            if ticket_id:
                ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
                if ticket:
                    dept_name = ticket.department.name if ticket.department else "Maintenance"
                    response_data = {
                        "type": "ticket_status",
                        "ticket_id": ticket.id,
                        "status": ticket.status,
                        "department": dept_name,
                        "estimated_resolution": f"{ticket.estimated_resolution_hours} hours"
                    }
                    
                    # Register Assistant Reply
                    asst_message_log = ChatMessage(
                        sender="assistant",
                        message=f"Status retrieved for ticket #{ticket.id}.",
                        intent="TICKET_STATUS",
                        ticket_id=ticket.id
                    )
                    db.add(asst_message_log)
                    db.commit()
                    
                    return response_data
            
            # If not found or ticket_id could not be resolved, return the node's graceful answer
            response_data = {
                "type": "answer",
                "message": result.get("answer"),
                "source": None,
                "confidence": 0.95
            }
            
            asst_message_log = ChatMessage(
                sender="assistant",
                message=result.get("answer"),
                intent="TICKET_STATUS"
            )
            db.add(asst_message_log)
            db.commit()
            
            return response_data
            
        # If FAQ, return structured source details
        if intent == "FAQ":
            response_data = {
                "type": "answer",
                "message": result.get("answer"),
                "source": {
                    "document": result.get("source") or "Academic Calendar 2026.pdf",
                    "page": 4
                },
                "confidence": 0.94
            }
            
            asst_message_log = ChatMessage(
                sender="assistant",
                message=result.get("answer"),
                intent="FAQ"
            )
            db.add(asst_message_log)
            db.commit()
            
            return response_data
            
        # Fallback answers (Location, ticket status, unknown)
        response_data = {
            "type": "answer",
            "message": result.get("answer"),
            "source": None,
            "confidence": 0.90
        }
        
        asst_message_log = ChatMessage(
            sender="assistant",
            message=result.get("answer"),
            intent=intent
        )
        db.add(asst_message_log)
        db.commit()
        
        return response_data
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat execution failed: {str(e)}")
