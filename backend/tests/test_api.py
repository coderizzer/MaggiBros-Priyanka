import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.database.connection import Base, get_db
from backend.app.models.models import Department, Location, Ticket, Complaint

# Use an absolute path for the temporary test database (avoids SQLite connection and sandbox relative path write issues)
TEST_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_temp.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    # Remove existing temp DB if any
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass
            
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        # Seed default departments and locations
        dept_maint = Department(name="Maintenance", code="MAINT", email="maint@vitbhopal.ac.in")
        dept_it = Department(name="IT Support", code="IT", email="it@vitbhopal.ac.in")
        loc = Location(name="Hostel Block 1", block="Hostels", latitude=23.0765, longitude=77.6080)
        db.add(dept_maint)
        db.add(dept_it)
        db.add(loc)
        db.commit()
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()  # Dispose of connection pool to release file lock
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except Exception:
                pass

@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "online"

def test_get_departments(client):
    response = client.get("/api/departments")
    assert response.status_code == 200
    assert len(response.json()) == 2
    codes = [d["code"] for d in response.json()]
    assert "IT" in codes
    assert "MAINT" in codes

def test_get_locations(client):
    response = client.get("/api/locations")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "Hostel Block 1"

def test_complaints_and_tickets_workflow(client, db_session):
    # 1. Verify we can fetch locations
    loc = db_session.query(Location).first()
    
    # 2. Create a complaint
    complaint_payload = {
        "user_id": 1,
        "location_id": loc.id,
        "category": "water_leakage",
        "description": "There is water leaking from the ceiling",
        "priority": "HIGH"
    }
    response = client.post("/api/complaints", json=complaint_payload)
    assert response.status_code == 200
    complaint_data = response.json()
    assert complaint_data["category"] == "water_leakage"
    assert complaint_data["id"] is not None
    complaint_id = complaint_data["id"]
    
    # 3. Fetch complaints
    response = client.get("/api/complaints")
    assert response.status_code == 200
    assert len(response.json()) == 1
    
    # 4. Create a ticket associated with that complaint
    ticket_payload = {
        "complaint_id": complaint_id
    }
    response = client.post("/api/tickets", json=ticket_payload)
    assert response.status_code == 200
    ticket_data = response.json()
    assert ticket_data["complaint_id"] == complaint_id
    assert ticket_data["priority"] == "HIGH"
    assert ticket_data["status"] == "OPEN"
    # Auto-department for "water_leakage" is Maintenance ("MAINT")
    assert ticket_data["department"]["code"] == "MAINT"
    # Auto-estimated hours for HIGH priority is 12
    assert ticket_data["estimated_resolution_hours"] == 12
    ticket_id = ticket_data["id"]
    
    # 5. Fetch all tickets and single ticket
    response = client.get("/api/tickets")
    assert response.status_code == 200
    assert len(response.json()) == 1
    
    response = client.get(f"/api/tickets/{ticket_id}")
    assert response.status_code == 200
    assert response.json()["title"] == f"Ticket for Complaint #{complaint_id}: Water Leakage"
    
    # 6. PATCH ticket status
    response = client.patch(f"/api/tickets/{ticket_id}/status", json={"status": "IN_PROGRESS"})
    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROGRESS"
    
    # 7. PATCH ticket department (change from MAINT to IT)
    it_dept = db_session.query(Department).filter(Department.code == "IT").first()
    response = client.patch(f"/api/tickets/{ticket_id}/department", json={"department_id": it_dept.id})
    assert response.status_code == 200
    assert response.json()["department"]["code"] == "IT"

def test_workflow_chat_fallback(client):
    # This matches the chat agent ticket filing fallback path
    payload = {
        "message": "Water leakage in Hostel Block 1 washroom, water overflowing",
        "student_name": "Aarav Sharma",
        "student_email": "aarav@student.vitbhopal.ac.in"
    }
    response = client.post("/api/agent/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "COMPLAINT"
    assert data["ticket_created"] is True
    assert "Ticket ID" in data["response"]

def test_analytics_and_dashboard_aggregation(client, db_session):
    loc = db_session.query(Location).first()
    dept = db_session.query(Department).filter(Department.code == "MAINT").first()
    
    # 1. Create a complaint & ticket
    c = Complaint(
        user_id=10,
        location_id=loc.id,
        category="water_leakage",
        description="Leaking pipeline in Block A",
        priority="HIGH"
    )
    db_session.add(c)
    db_session.commit()
    
    t = Ticket(
        complaint_id=c.id,
        title="Pipeline Leakage",
        description="Leaking pipeline in Block A",
        status="OPEN",
        priority="HIGH",
        location_id=loc.id,
        department_id=dept.id
    )
    db_session.add(t)
    db_session.commit()
    
    # 2. Test /dashboard
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    dash = response.json()
    assert dash["total_tickets"] == 1
    assert dash["open_tickets"] == 1
    assert dash["categories"]["water_leakage"] == 1
    assert dash["departments"]["Maintenance"] == 1
    assert dash["top_location"] == loc.name
    
    # 3. Test /analytics/categories
    response = client.get("/api/analytics/categories")
    assert response.status_code == 200
    cats = response.json()
    assert len(cats) == 1
    assert cats[0]["category"] == "water_leakage"
    assert cats[0]["count"] == 1
    
    # 4. Test /analytics/departments
    response = client.get("/api/analytics/departments")
    assert response.status_code == 200
    depts = response.json()
    assert len(depts) == 1
    assert depts[0]["department_name"] == "Maintenance"
    assert depts[0]["count"] == 1
    
    # 5. Test /analytics/locations
    response = client.get("/api/analytics/locations")
    assert response.status_code == 200
    locs = response.json()
    assert len(locs) == 1
    assert locs[0]["location_name"] == loc.name
    assert locs[0]["count"] == 1
    
    # 6. Test /map/complaints
    response = client.get("/api/map/complaints")
    assert response.status_code == 200
    map_data = response.json()
    assert len(map_data["locations"]) == 1
    loc_detail = map_data["locations"][0]
    assert loc_detail["name"] == loc.name
    assert loc_detail["total_complaints"] == 1
    assert loc_detail["categories"]["water_leakage"] == 1

def test_knowledge_search_empty(client):
    # Tests behavior when vector store is empty / no documents ingested
    payload = {
        "query": "When is the revaluation deadline?",
        "k": 2
    }
    response = client.post("/api/knowledge/search", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    # Should return empty list gracefully
    assert len(data["results"]) == 0

def test_ai_services_functions():
    from backend.app.services.ai_service import detect_student_intent, generate_faq_response, classify_complaint_details
    
    # 1. Test student intent detection
    res1 = detect_student_intent("My room has a water leak from the AC")
    assert res1["intent"] == "COMPLAINT"
    assert res1["category"] == "water_leakage"
    assert res1["priority"] in ["HIGH", "CRITICAL", "MEDIUM"]
    
    res2 = detect_student_intent("What is the registration deadline for next sem?")
    assert res2["intent"] == "FAQ"
    
    # 2. Test RAG FAQ response constraints
    faq_res = generate_faq_response(
        query="When is the deadline?", 
        context="No specific details found in university documents."
    )
    # Checks system prompt constraint is respected (mentions not found/cannot find)
    assert any(k in faq_res.lower() for k in ["cannot", "not find", "unavailable", "welcome", "operational help"])
    
    # 3. Test complaint classification details
    class_res = classify_complaint_details("The WiFi router is completely flashing red and no one can connect")
    assert class_res["category"] == "wifi"
    assert class_res["priority"] == "HIGH"

def test_main_chat_endpoint(client, db_session):
    # 1. Test FAQ path
    faq_payload = {"message": "When is the revaluation deadline?"}
    response = client.post("/chat", json=faq_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "answer"
    assert "source" in data
    assert data["source"]["document"] is not None
    
    # 2. Test Complaint interception (no location)
    complaint_payload = {"message": "My hostel has water leakage."}
    response = client.post("/chat", json=complaint_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "complaint"
    assert data["category"] == "water_leakage"
    assert data["next_action"] == "select_location"
    
    # 3. Test direct ticket filing (with location)
    loc = db_session.query(Location).first()
    ticket_payload = {
        "message": "Water is leaking from the ceiling",
        "location_id": loc.id
    }
    response = client.post("/chat", json=ticket_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "ticket_created"
    assert "ticket_id" in data
    assert data["department"] == "Maintenance"
    assert "hours" in data["estimated_resolution"]
    created_id = data["ticket_id"]
    
    # 4. Test Ticket Status Retrieval (valid)
    status_payload = {"message": f"What is the status of ticket {created_id}?"}
    response = client.post("/chat", json=status_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "ticket_status"
    assert data["ticket_id"] == created_id
    assert data["status"] == "OPEN"
    assert data["department"] == "Maintenance"
    
    # 5. Test Ticket Status Retrieval (invalid nonexistent)
    invalid_payload = {"message": "What is the status of ticket 99999?"}
    response = client.post("/chat", json=invalid_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == "answer"
    assert "unable to find" in data["message"].lower() or "cannot find" in data["message"].lower()




