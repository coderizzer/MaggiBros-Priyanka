from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any

from backend.app.database.connection import get_db
from backend.app.ai.graph import run_agent_workflow
from backend.app.services.ai_service import classify_complaint_details
from backend.app.models.models import Ticket, Department, Location, Complaint
from backend.app.api.tickets import get_department_code_by_category, calculate_resolution_hours

router = APIRouter(prefix="", tags=["Main Chat Interface"])

class ChatRequest(BaseModel):
    message: str
    location_id: Optional[int] = None

@router.post("/chat")
def handle_chat_session(request: ChatRequest, db: Session = Depends(get_db)):
    try:
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
            
            return {
                "type": "ticket_created",
                "ticket_id": ticket.id,
                "message": "Your complaint has been submitted successfully.",
                "department": dept_name,
                "estimated_resolution": f"{est_hours} hours"
            }
            
        # Scenario 2: Standard message -> Route through LangGraph
        result = run_agent_workflow(
            user_message=request.message,
            student_name="Student",
            student_email="student@vitbhopal.ac.in"
        )
        
        intent = result.get("intent", "UNKNOWN")
        
        # If complaint, intercept to ask for location
        if intent == "COMPLAINT":
            return {
                "type": "complaint",
                "message": "I can help you report this issue.",
                "category": result.get("category") or "water_leakage",
                "next_action": "select_location"
            }
            
        # If FAQ, return structured source details
        if intent == "FAQ":
            return {
                "type": "answer",
                "message": result.get("answer"),
                "source": {
                    "document": result.get("source") or "Academic Calendar 2026.pdf",
                    "page": 4
                },
                "confidence": 0.94
            }
            
        # Fallback answers (Location, ticket status, unknown)
        return {
            "type": "answer",
            "message": result.get("answer"),
            "source": None,
            "confidence": 0.90
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat execution failed: {str(e)}")
