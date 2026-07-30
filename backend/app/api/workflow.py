from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from backend.app.database.connection import get_db
from backend.app.schemas.schemas import WorkflowQueryRequest, WorkflowQueryResponse, TicketOut
from backend.app.ai.workflow import run_campus_pilot_workflow
from backend.app.models.models import Ticket

router = APIRouter(prefix="/agent", tags=["AI Agent Workflow"])

@router.post("/chat", response_model=WorkflowQueryResponse)
def chat_with_campus_pilot(request: WorkflowQueryRequest, db: Session = Depends(get_db)):
    try:
        # Run the LangGraph agent workflow
        result = run_campus_pilot_workflow(
            message=request.message,
            student_name=request.student_name,
            student_email=request.student_email
        )
        
        ticket_out = None
        if result.get("ticket_created") and result.get("ticket_id"):
            ticket = db.query(Ticket).filter(Ticket.id == result["ticket_id"]).first()
            if ticket:
                ticket_out = TicketOut.from_orm(ticket)
                
        return WorkflowQueryResponse(
            intent=result.get("intent", "GENERAL"),
            response=result.get("response", "No response generated."),
            ticket_created=result.get("ticket_created", False),
            ticket=ticket_out
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow execution failed: {str(e)}")
