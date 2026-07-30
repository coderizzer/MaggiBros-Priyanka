import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.database.connection import Base, get_db
from backend.app.models.models import Department, Location, Ticket

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
        dept = Department(name="IT Support", code="IT", email="it@vitbhopal.ac.in")
        loc = Location(name="Hostel Block 1", block="Hostels", latitude=23.0765, longitude=77.6080)
        db.add(dept)
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
    assert len(response.json()) == 1
    assert response.json()[0]["code"] == "IT"

def test_get_locations(client):
    response = client.get("/api/locations")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "Hostel Block 1"

def test_create_ticket(client, db_session):
    # Resolve IDs
    loc = db_session.query(Location).first()
    dept = db_session.query(Department).first()
    
    payload = {
        "title": "Broken light in room 101",
        "description": "The overhead tube light has burned out and needs replacement.",
        "category": "Electrical",
        "priority": "MEDIUM",
        "student_name": "Test Student",
        "student_email": "test@student.vitbhopal.ac.in",
        "location_id": loc.id,
        "department_id": dept.id
    }
    
    response = client.post("/api/tickets", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Broken light in room 101"
    assert data["status"] == "OPEN"
    assert data["id"] is not None

def test_update_ticket_status(client, db_session):
    # Create ticket
    ticket = Ticket(
        title="Test Ticket",
        description="Description",
        category="General",
        student_name="Name",
        student_email="email@test.com",
        status="OPEN"
    )
    db_session.add(ticket)
    db_session.commit()
    db_session.refresh(ticket)
    
    response = client.put(f"/api/tickets/{ticket.id}/status", json={"status": "IN_PROGRESS"})
    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROGRESS"

def test_analytics_and_heatmap(client, db_session):
    loc = db_session.query(Location).first()
    dept = db_session.query(Department).first()
    
    # Create open ticket
    t = Ticket(
        title="WiFi issue",
        description="No signal",
        category="WiFi",
        student_name="Name",
        student_email="email@test.com",
        status="OPEN",
        priority="HIGH",
        location_id=loc.id,
        department_id=dept.id
    )
    db_session.add(t)
    db_session.commit()
    
    response = client.get("/api/analytics")
    assert response.status_code == 200
    data = response.json()
    assert data["total_tickets"] == 1
    assert data["open_tickets"] == 1
    assert len(data["heatmap"]) == 1
    assert data["heatmap"][0]["weight"] == 3.0 # HIGH priority weight is 3.0

def test_workflow_chat_fallback(client):
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
