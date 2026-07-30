from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from backend.app.database.connection import get_db
from backend.app.schemas.schemas import WorkflowQueryRequest, WorkflowQueryResponse, TicketOut
from backend.app.ai.graph import run_agent_workflow
from backend.app.models.models import Ticket

router = APIRouter(prefix="/agent", tags=["AI Agent Workflow"])

@router.post("/chat", response_model=WorkflowQueryResponse)
def chat_with_campus_pilot(request: WorkflowQueryRequest, db: Session = Depends(get_db)):
    try:
        # Run the new LangGraph agent workflow
        result = run_agent_workflow(
            user_message=request.message,
            student_name=request.student_name,
            student_email=request.student_email
        )
        
        ticket_id = result.get("ticket_id")
        ticket_out = None
        if ticket_id:
            ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
            if ticket:
                ticket_out = TicketOut.from_orm(ticket)
                
        return WorkflowQueryResponse(
            intent=result.get("intent", "UNKNOWN"),
            response=result.get("answer", "No response generated."),
            ticket_created=True if ticket_id else False,
            ticket=ticket_out
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow execution failed: {str(e)}")
