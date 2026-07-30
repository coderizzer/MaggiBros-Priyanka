from typing import TypedDict, Optional, List, Dict

class AgentState(TypedDict):
    user_message: str
    student_name: str
    student_email: str
    intent: Optional[str]
    category: Optional[str]
    priority: Optional[str]
    location_id: Optional[int]
    description: Optional[str]
    retrieved_documents: Optional[List[Dict]]
    answer: Optional[str]
    ticket_id: Optional[int]
    department: Optional[str]
    confidence: Optional[float]
    source: Optional[str]
