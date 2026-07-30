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
    assert data["intent"] == "TICKET"
    assert data["ticket_created"] is True
    assert "Ticket Reference" in data["response"]
