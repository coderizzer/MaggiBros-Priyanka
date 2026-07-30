from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import datetime
import logging

from backend.app.database.connection import get_db
from backend.app.models.models import Ticket, Department, Location, Complaint
from backend.app.schemas.schemas import (
    TicketOut, TicketCreate, TicketStatusUpdate, TicketDepartmentUpdate,
    DepartmentOut, LocationOut, ComplaintCreate, ComplaintOut,
    AnalyticsResponse, CategoryCount, StatusCount, DepartmentCount, HeatmapPoint,
    DashboardResponse, CategoryAnalytics, DepartmentAnalytics, LocationAnalytics,
    MapComplaintsResponse, MapLocationDetail
)

logger = logging.getLogger("campuspilot.tickets")
router = APIRouter(prefix="", tags=["Campus Operations (Tickets & Complaints)"])

# --- HELPERS ---

def get_department_code_by_category(category: str) -> str:
    mapping = {
        "water_leakage": "MAINT",
        "electricity": "MAINT",
        "wifi": "IT",
        "internet": "IT",
        "cleanliness": "HOSTEL",
        "academic": "ACAD",
        "exam": "EXAM",
        "security": "SECURITY"
    }
    return mapping.get(category.lower(), "MAINT")

def calculate_resolution_hours(priority: str) -> int:
    mapping = {
        "CRITICAL": 4,
        "HIGH": 12,
        "MEDIUM": 24,
        "LOW": 48
    }
    return mapping.get(priority.upper(), 24)


# --- DEPARTMENTS & LOCATIONS ---

@router.get("/departments", response_model=List[DepartmentOut])
def get_departments(db: Session = Depends(get_db)):
    return db.query(Department).all()

@router.get("/locations", response_model=List[LocationOut])
def get_locations(db: Session = Depends(get_db)):
    return db.query(Location).all()


# --- COMPLAINTS ---

@router.post("/complaints", response_model=ComplaintOut)
def create_complaint(complaint_in: ComplaintCreate, db: Session = Depends(get_db)):
    # Validate location
    loc = db.query(Location).filter(Location.id == complaint_in.location_id).first()
    if not loc:
        raise HTTPException(status_code=400, detail="Invalid location_id.")
        
    db_complaint = Complaint(
        user_id=complaint_in.user_id,
        location_id=complaint_in.location_id,
        category=complaint_in.category,
        description=complaint_in.description,
        priority=complaint_in.priority
    )
    db.add(db_complaint)
    db.commit()
    db.refresh(db_complaint)
    return db_complaint

@router.get("/complaints", response_model=List[ComplaintOut])
def get_complaints(db: Session = Depends(get_db)):
    return db.query(Complaint).order_by(Complaint.created_at.desc()).all()


# --- TICKETS CRUD ---

@router.post("/tickets", response_model=TicketOut)
def create_ticket(ticket_in: TicketCreate, db: Session = Depends(get_db)):
    # Look up associated complaint
    complaint = db.query(Complaint).filter(Complaint.id == ticket_in.complaint_id).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Associated complaint not found.")
        
    # Check if a ticket already exists for this complaint
    existing_ticket = db.query(Ticket).filter(Ticket.complaint_id == ticket_in.complaint_id).first()
    if existing_ticket:
        raise HTTPException(status_code=400, detail="A ticket is already associated with this complaint.")

    # Resolve Department based on category
    dept_code = get_department_code_by_category(complaint.category)
    dept = db.query(Department).filter(Department.code == dept_code).first()
    if not dept:
        # Default fallback
        dept = db.query(Department).filter(Department.code == "MAINT").first()

    # Calculate estimated resolution hours
    est_hours = calculate_resolution_hours(complaint.priority)

    # Title construction
    title = f"Ticket for Complaint #{complaint.id}: {complaint.category.replace('_', ' ').title()}"

    db_ticket = Ticket(
        complaint_id=complaint.id,
        title=title,
        description=complaint.description,
        status="OPEN",
        priority=complaint.priority,
        department_id=dept.id if dept else None,
        location_id=complaint.location_id,
        estimated_resolution_hours=est_hours
    )
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    return db_ticket

@router.get("/tickets", response_model=List[TicketOut])
def get_tickets(
    status: Optional[str] = None,
    department_id: Optional[int] = None,
    location_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Ticket)
    if status:
        query = query.filter(func.lower(Ticket.status) == status.lower())
    if department_id:
        query = query.filter(Ticket.department_id == department_id)
    if location_id:
        query = query.filter(Ticket.location_id == location_id)
    return query.order_by(Ticket.created_at.desc()).all()

@router.get("/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
    return ticket

@router.patch("/tickets/{ticket_id}/status", response_model=TicketOut)
def patch_ticket_status(ticket_id: int, status_update: TicketStatusUpdate, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
        
    status = status_update.status.upper()
    if status not in ["OPEN", "IN_PROGRESS", "RESOLVED"]:
        raise HTTPException(status_code=400, detail="Invalid status. Must be OPEN, IN_PROGRESS, or RESOLVED.")
        
    ticket.status = status
    ticket.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(ticket)
    return ticket

@router.patch("/tickets/{ticket_id}/department", response_model=TicketOut)
def patch_ticket_department(ticket_id: int, dept_update: TicketDepartmentUpdate, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found.")
        
    dept = db.query(Department).filter(Department.id == dept_update.department_id).first()
    if not dept:
        raise HTTPException(status_code=400, detail="Department not found.")
        
    ticket.department_id = dept.id
    ticket.updated_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(ticket)
    return ticket


# --- HEATMAP & ANALYTICS ---

@router.get("/heatmap", response_model=List[HeatmapPoint])
def get_heatmap_data(db: Session = Depends(get_db)):
    locations = db.query(Location).all()
    points = []
    
    priority_weights = {
        "LOW": 1.0,
        "MEDIUM": 2.0,
        "HIGH": 3.0,
        "CRITICAL": 5.0
    }
    
    for loc in locations:
        active_tickets = db.query(Ticket).filter(
            Ticket.location_id == loc.id,
            Ticket.status.in_(["OPEN", "IN_PROGRESS"])
        ).all()
        
        if not active_tickets:
            continue
            
        weight = sum(priority_weights.get(t.priority.upper(), 2.0) for t in active_tickets)
        
        points.append(
            HeatmapPoint(
                location_name=loc.name,
                latitude=loc.latitude,
                longitude=loc.longitude,
                weight=weight,
                active_tickets_count=len(active_tickets)
            )
        )
        
    return points

@router.get("/analytics", response_model=AnalyticsResponse)
def get_analytics(db: Session = Depends(get_db)):
    total = db.query(Ticket).count()
    open_count = db.query(Ticket).filter(Ticket.status == "OPEN").count()
    in_progress = db.query(Ticket).filter(Ticket.status == "IN_PROGRESS").count()
    resolved = db.query(Ticket).filter(Ticket.status == "RESOLVED").count()
    
    resolved_tickets = db.query(Ticket).filter(Ticket.status == "RESOLVED").all()
    total_hours = 0.0
    for t in resolved_tickets:
        delta = t.updated_at - t.created_at
        total_hours += delta.total_seconds() / 3600.0
    avg_res_time = (total_hours / len(resolved_tickets)) if resolved_tickets else 0.0
    
    # We can group tickets by category from their complaint or fallback to standard category
    # tickets don't have category field directly anymore, but we can resolve it from complaint
    # let's group by complaint.category
    categories = db.query(Complaint.category, func.count(Ticket.id)).join(Ticket).group_by(Complaint.category).all()
    by_category = [CategoryCount(category=c[0] or "Unassigned", count=c[1]) for c in categories]
    
    statuses = db.query(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status).all()
    by_status = [StatusCount(status=s[0], count=s[1]) for s in statuses]
    
    depts = db.query(Department.name, func.count(Ticket.id)).join(Ticket).group_by(Department.name).all()
    by_dept = [DepartmentCount(department_name=d[0], count=d[1]) for d in depts]
    
    heatmap = get_heatmap_data(db)
    
    # Simple insights builder
    insights = []
    h1_wifi_tickets = db.query(Ticket).join(Location).join(Complaint).filter(
        Location.name == "Hostel Block 1",
        Complaint.category == "wifi",
        Ticket.status.in_(["OPEN", "IN_PROGRESS"])
    ).count()
    
    maint_tickets = db.query(Ticket).join(Department).filter(
        Department.code == "MAINT",
        Ticket.status.in_(["OPEN", "IN_PROGRESS"])
    ).count()

    if h1_wifi_tickets > 0:
        insights.append(f"Network infrastructure bottleneck detected in Hostel Block 1 ({h1_wifi_tickets} active WiFi issues).")
    else:
        insights.append("WiFi network operations are performing within normal operational thresholds across campus hostels.")
        
    if maint_tickets > 2:
        insights.append(f"Spike in general plumbing & maintenance tickets ({maint_tickets} unresolved).")
    else:
        insights.append("Maintenance & Plumbing resolution timelines are stable.")

    return AnalyticsResponse(
        total_tickets=total,
        open_tickets=open_count,
        in_progress_tickets=in_progress,
        resolved_tickets=resolved,
        avg_resolution_time_hours=avg_res_time,
        by_category=by_category,
        by_status=by_status,
        by_department=by_dept,
        heatmap=heatmap,
        ai_insights=insights
    )

@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db)):
    total = db.query(Ticket).count()
    open_count = db.query(Ticket).filter(Ticket.status == "OPEN").count()
    
    # Resolved today
    today_start = datetime.datetime.combine(datetime.date.today(), datetime.time.min)
    resolved_today = db.query(Ticket).filter(
        Ticket.status == "RESOLVED",
        Ticket.updated_at >= today_start
    ).count()
    
    # Average resolution time
    resolved_tickets = db.query(Ticket).filter(Ticket.status == "RESOLVED").all()
    total_hours = 0.0
    for t in resolved_tickets:
        delta = t.updated_at - t.created_at
        total_hours += delta.total_seconds() / 3600.0
    avg_res_time = (total_hours / len(resolved_tickets)) if resolved_tickets else 0.0

    # Categories distribution from complaints
    categories_query = db.query(Complaint.category, func.count(Complaint.id)).group_by(Complaint.category).all()
    categories_dict = {c[0]: c[1] for c in categories_query if c[0]}
    
    # Departments distribution from tickets
    depts_query = db.query(Department.name, func.count(Ticket.id)).join(Ticket).group_by(Department.name).all()
    depts_dict = {d[0]: d[1] for d in depts_query if d[0]}
    
    # Top location based on complaint count
    top_loc_query = db.query(Location.name, func.count(Complaint.id)).join(Complaint).group_by(Location.name).order_by(func.count(Complaint.id).desc()).first()
    top_location = top_loc_query[0] if top_loc_query else None
    
    return DashboardResponse(
        total_tickets=total,
        open_tickets=open_count,
        resolved_today=resolved_today,
        average_resolution_time=avg_res_time,
        categories=categories_dict,
        departments=depts_dict,
        top_location=top_location
    )

@router.get("/analytics/categories", response_model=List[CategoryAnalytics])
def get_analytics_categories(db: Session = Depends(get_db)):
    categories = db.query(Complaint.category, func.count(Complaint.id)).group_by(Complaint.category).all()
    return [CategoryAnalytics(category=c[0], count=c[1]) for c in categories]

@router.get("/analytics/departments", response_model=List[DepartmentAnalytics])
def get_analytics_departments(db: Session = Depends(get_db)):
    depts = db.query(Department.name, func.count(Ticket.id)).join(Ticket).group_by(Department.name).all()
    return [DepartmentAnalytics(department_name=d[0], count=d[1]) for d in depts]

@router.get("/analytics/locations", response_model=List[LocationAnalytics])
def get_analytics_locations(db: Session = Depends(get_db)):
    locations = db.query(Location.name, func.count(Complaint.id)).join(Complaint).group_by(Location.name).all()
    return [LocationAnalytics(location_name=l[0], count=l[1]) for l in locations]

@router.get("/map/complaints", response_model=MapComplaintsResponse)
def get_map_complaints(db: Session = Depends(get_db)):
    locations = db.query(Location).all()
    map_details = []
    
    for loc in locations:
        complaints = db.query(Complaint).filter(Complaint.location_id == loc.id).all()
        if not complaints:
            continue
            
        categories_dict = {}
        for c in complaints:
            categories_dict[c.category] = categories_dict.get(c.category, 0) + 1
            
        map_details.append(
            MapLocationDetail(
                location_id=loc.id,
                name=loc.name,
                latitude=loc.latitude,
                longitude=loc.longitude,
                total_complaints=len(complaints),
                categories=categories_dict
            )
        )
        
    return MapComplaintsResponse(locations=map_details)
