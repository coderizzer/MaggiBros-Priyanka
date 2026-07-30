from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict
from datetime import datetime

# Department schemas
class DepartmentBase(BaseModel):
    name: str
    code: str
    email: Optional[EmailStr] = None

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentOut(DepartmentBase):
    id: int

    class Config:
        from_attributes = True


# Location schemas
class LocationBase(BaseModel):
    name: str
    block: str
    latitude: float
    longitude: float

class LocationCreate(LocationBase):
    pass

class LocationOut(LocationBase):
    id: int

    class Config:
        from_attributes = True


# Complaint schemas
class ComplaintBase(BaseModel):
    user_id: int
    location_id: int
    category: str
    description: str
    priority: Optional[str] = "MEDIUM"

class ComplaintCreate(ComplaintBase):
    pass

class ComplaintOut(ComplaintBase):
    id: int
    created_at: datetime
    location: Optional[LocationOut] = None

    class Config:
        from_attributes = True


# Ticket schemas
class TicketCreate(BaseModel):
    complaint_id: int

class TicketOut(BaseModel):
    id: int
    complaint_id: Optional[int] = None
    title: str
    description: str
    status: str
    priority: str
    estimated_resolution_hours: int
    created_at: datetime
    updated_at: datetime
    location: Optional[LocationOut] = None
    department: Optional[DepartmentOut] = None
    complaint: Optional[ComplaintOut] = None

    class Config:
        from_attributes = True

class TicketStatusUpdate(BaseModel):
    status: str

class TicketDepartmentUpdate(BaseModel):
    department_id: int


# RAG/Knowledge base schemas
class DocumentOut(BaseModel):
    id: int
    title: str
    file_path: str
    uploaded_at: datetime

    class Config:
        from_attributes = True

class RAGQueryRequest(BaseModel):
    query: str
    k: Optional[int] = 4

class RAGSearchResult(BaseModel):
    text: str
    source: str
    page: int
    score: float

class RAGQueryResponse(BaseModel):
    query: str
    results: List[RAGSearchResult]


# AI Workflow schemas
class WorkflowQueryRequest(BaseModel):
    message: str
    student_name: str
    student_email: EmailStr

class WorkflowQueryResponse(BaseModel):
    intent: str
    response: str
    ticket_created: bool
    ticket: Optional[TicketOut] = None


# Analytics & Dashboard schemas
class CategoryAnalytics(BaseModel):
    category: str
    count: int

class DepartmentAnalytics(BaseModel):
    department_name: str
    count: int

class LocationAnalytics(BaseModel):
    location_name: str
    count: int

class DashboardResponse(BaseModel):
    total_tickets: int
    open_tickets: int
    resolved_today: int
    average_resolution_time: float
    categories: Dict[str, int]
    departments: Dict[str, int]
    top_location: Optional[str] = None

class MapLocationDetail(BaseModel):
    location_id: int
    name: str
    latitude: float
    longitude: float
    total_complaints: int
    categories: Dict[str, int]

class MapComplaintsResponse(BaseModel):
    locations: List[MapLocationDetail]


# Legacy schemas (kept for backwards compatibility)
class CategoryCount(BaseModel):
    category: str
    count: int

class StatusCount(BaseModel):
    status: str
    count: int

class DepartmentCount(BaseModel):
    department_name: str
    count: int

class HeatmapPoint(BaseModel):
    location_name: str
    latitude: float
    longitude: float
    weight: float
    active_tickets_count: int

class AnalyticsResponse(BaseModel):
    total_tickets: int
    open_tickets: int
    in_progress_tickets: int
    resolved_tickets: int
    avg_resolution_time_hours: float
    by_category: List[CategoryCount]
    by_status: List[StatusCount]
    by_department: List[DepartmentCount]
    heatmap: List[HeatmapPoint]
    ai_insights: List[str]

class InsightItem(BaseModel):
    title: str
    description: str
    severity: str

class InsightsResponse(BaseModel):
    insights: List[InsightItem]
