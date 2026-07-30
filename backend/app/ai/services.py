from pydantic import BaseModel, Field
from backend.app.ai.client import ai_client

class IntentDetectionSchema(BaseModel):
    intent: str = Field(description="Must be one of: 'TICKET' (if user wants to submit a complaint, report an issue, or fix something), 'QUERY' (if user asks a question about campus policies, timings, rules or general information), or 'GENERAL' (for greetings, conversational smalltalk, or miscellaneous messages).")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(description="Brief explanation of why this intent was selected")

class TicketRoutingSchema(BaseModel):
    category: str = Field(description="Category of the ticket (e.g. WiFi, Plumbing, Electrical, Hostel Operations, Academics)")
    recommended_department_code: str = Field(description="Must match one of the department codes: 'IT', 'MAINT', 'ELEC', 'HOSTEL', 'ACAD'")
    recommended_priority: str = Field(description="Must be one of: 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    reasoning: str = Field(description="Reason for routing to this department and assigning this priority")

def detect_user_intent(message: str) -> IntentDetectionSchema:
    prompt = (
        f"Analyze the following student message and determine their operational intent.\n"
        f"User Message: \"{message}\"\n"
    )
    system_instruction = "You are CampusPilot's AI Dispatcher. Your job is to classify student inputs into TICKET, QUERY, or GENERAL."
    data = ai_client.generate_structured_json(prompt, IntentDetectionSchema, system_instruction)
    return IntentDetectionSchema(**data)

def route_ticket_details(title: str, description: str) -> TicketRoutingSchema:
    prompt = (
        f"Analyze the ticket title and description to route it to the correct department.\n"
        f"Ticket Title: {title}\n"
        f"Description: {description}\n"
    )
    system_instruction = (
        "You are CampusPilot's Ticket Router. Evaluate the issue, categorise it, "
        "and suggest the correct department (IT, MAINT, ELEC, HOSTEL, ACAD) and priority (LOW, MEDIUM, HIGH, CRITICAL)."
    )
    data = ai_client.generate_structured_json(prompt, TicketRoutingSchema, system_instruction)
    return TicketRoutingSchema(**data)
