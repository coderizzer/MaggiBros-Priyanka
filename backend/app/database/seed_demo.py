import os
import random
import datetime
from sqlalchemy.orm import Session
from backend.app.database.connection import SessionLocal, Base, engine
from backend.app.models.models import Location, Department, Complaint, Ticket
from backend.app.api.tickets import get_department_code_by_category, calculate_resolution_hours

# Seed dictionaries for realistic student complaints
COMPLAINT_TEMPLATES = {
    "water_leakage": [
        "Water leaking from the washroom ceiling on the 2nd floor.",
        "AC unit in room 104 is dripping water onto the floor.",
        "Wash basin tap won't shut off completely and is leaking.",
        "Dampness spreading across the wall near room 305.",
        "Geyser connection pipe in the common bathroom is dripping.",
        "Main pipeline in the corridor has a minor crack and is spraying water.",
        "Water logging in the shower stalls due to blockages.",
        "Flush tank in washroom B is continuously running.",
    ],
    "wifi": [
        "Cannot authenticate connection with secure student portal.",
        "WiFi signal strength drops significantly after 8 PM in Room 204.",
        "Frequent packet loss making online lectures impossible to stream.",
        "Router in corridor 3B seems to be offline (red light flashing).",
        "High latency spikes during online lab sessions.",
        "WiFi disconnects automatically every 10 minutes.",
        "Speed is restricted to less than 100Kbps on block A corridor.",
    ],
    "electricity": [
        "Short circuit happened in room light switchboard.",
        "Ceiling fan in room 212 is making a loud clicking sound and rotating slowly.",
        "Power socket on the right wall has no voltage output.",
        "Tube light keeps flickering continuously in room 318.",
        "Geyser in washroom C is not heating water.",
        "Corridor backup light is completely dead.",
        "Exhaust fan in common washroom is not running.",
    ],
    "cleanliness": [
        "Dustbins in the 3rd floor corridor have not been emptied for two days.",
        "Common washrooms have muddy floors and need immediate cleaning.",
        "Corridor windows are covered in dust and cobwebs.",
        "Garbage pile accumulating near the fire exit stairs.",
        "Drinking water dispenser tray is dirty and clogged.",
        "Water accumulation in front of the lobby entrance is breeding mosquitoes.",
    ],
    "academic": [
        "Queries regarding credit transfer eligibility for the summer semester.",
        "Mismatch in GPA calculations on the student portal profile.",
        "Requesting deadline extension for submission of project files.",
        "Elective subject allocation list is missing my student registration ID.",
        "Attendance corrections pending for digital logic design class.",
    ],
    "exam": [
        "Mid-semester exam schedule clashes with external hackathon dates.",
        "Revaluation results are not visible on the results dashboard.",
        "Duplicate fee deduction for back-paper examination registration.",
        "Hall ticket is displaying incorrect register number and photo.",
        "Requesting duplicate grade card print for scholarship application.",
    ],
    "security": [
        "Bicycle parking lock was found tampered with near block B.",
        "Lost my student ID card near the multi-purpose hall parking lot.",
        "Suspicious tailgating activity noticed at the hostel rear gate.",
        "Lighting near the library parking zone is insufficient at night.",
        "Unauthorized visitors spotted inside the academic block corridor.",
    ]
}

def seed_demo_data():
    db: Session = SessionLocal()
    print("Resetting database for clean demo seeding...")
    
    # Drop all existing complaint & ticket records to keep script idempotent
    db.query(Ticket).delete()
    db.query(Complaint).delete()
    db.query(Location).delete()
    db.query(Department).delete()
    db.commit()
    
    # 1. Re-seed default Departments (no description column in DB)
    departments_data = [
        {"name": "Maintenance", "code": "MAINT", "email": "maint@vitbhopal.ac.in"},
        {"name": "IT Support", "code": "IT", "email": "it@vitbhopal.ac.in"},
        {"name": "Hostel Administration", "code": "HOSTEL", "email": "hostel@vitbhopal.ac.in"},
        {"name": "Academic Affairs", "code": "ACAD", "email": "acad@vitbhopal.ac.in"},
        {"name": "Examination Cell", "code": "EXAM", "email": "exam@vitbhopal.ac.in"},
        {"name": "Security", "code": "SEC", "email": "security@vitbhopal.ac.in"}
    ]
    for dept in departments_data:
        db_dept = Department(**dept)
        db.add(db_dept)
    db.commit()
    
    # 2. Re-seed default Locations (block is required)
    locations_data = [
        {"name": "Girls Hostel", "block": "Block A", "latitude": 23.2599, "longitude": 77.4126},
        {"name": "Boys Hostel Blocks", "block": "Block B", "latitude": 23.2605, "longitude": 77.4132},
        {"name": "Hostel Office", "block": "Central Block", "latitude": 23.2612, "longitude": 77.4110},
        {"name": "Academic Block-1", "block": "Block 1", "latitude": 23.2618, "longitude": 77.4105},
        {"name": "Academic Block-2", "block": "Block 1", "latitude": 23.2620, "longitude": 77.4100},
        {"name": "Boys Playground", "block": "Outdoor", "latitude": 23.2585, "longitude": 77.4140},
        {"name": "Special Building", "block": "Gate 2", "latitude": 23.2590, "longitude": 77.4115}
    ]
    locations = {}
    for loc in locations_data:
        db_loc = Location(**loc)
        db.add(db_loc)
        db.commit()
        locations[db_loc.name] = db_loc
        
    print("Database structures and primary tables initialized.")
    
    # Track distributions
    total_generated = 0
    
    # A. Seed Target Specific Distribution for Boys Hostel Blocks:
    # Water leakage: 17, WiFi: 8, Electricity: 4, Cleanliness: 2
    hotspot_loc = locations["Boys Hostel Blocks"]
    hotspot_targets = [
        ("water_leakage", 17),
        ("wifi", 8),
        ("electricity", 4),
        ("cleanliness", 2)
    ]
    
    for category, count in hotspot_targets:
        for _ in range(count):
            _create_historic_complaint(db, hotspot_loc, category, user_id=random.randint(10, 200))
            total_generated += 1
            
    # B. Generate the remaining ~80-100 random tickets across other locations
    other_locations = [locations[name] for name in locations if name != "Boys Hostel Blocks"]
    categories_list = list(COMPLAINT_TEMPLATES.keys())
    
    remaining_to_generate = random.randint(80, 100)
    for _ in range(remaining_to_generate):
        loc = random.choice(other_locations)
        category = random.choice(categories_list)
        _create_historic_complaint(db, loc, category, user_id=random.randint(10, 200))
        total_generated += 1
        
    print(f"Seeding completed successfully! Total {total_generated} demo tickets registered.")
    db.close()


def _create_historic_complaint(db: Session, location: Location, category: str, user_id: int):
    # Retrieve template description
    desc = random.choice(COMPLAINT_TEMPLATES[category])
    
    # Assign realistic statuses
    status_choices = ["RESOLVED", "CLOSED", "IN_PROGRESS", "OPEN"]
    status_weights = [0.55, 0.20, 0.15, 0.10]
    status = random.choices(status_choices, weights=status_weights, k=1)[0]
    
    # Assign priorities based on category seriousness
    priority_map = {
        "water_leakage": ["HIGH", "CRITICAL", "MEDIUM"],
        "electricity": ["HIGH", "CRITICAL", "MEDIUM"],
        "wifi": ["HIGH", "MEDIUM", "LOW"],
        "security": ["CRITICAL", "HIGH", "MEDIUM"],
        "cleanliness": ["LOW", "MEDIUM"],
        "academic": ["MEDIUM", "LOW"],
        "exam": ["HIGH", "MEDIUM"]
    }
    priority = random.choice(priority_map[category])
    
    # Generate timestamp spread over the last 30 days
    days_ago = random.randint(0, 30)
    hours_ago = random.randint(0, 24)
    created_time = datetime.datetime.utcnow() - datetime.timedelta(days=days_ago, hours=hours_ago)
    
    # Create Complaint record
    complaint = Complaint(
        user_id=user_id,
        location_id=location.id,
        category=category,
        description=desc,
        priority=priority,
        created_at=created_time
    )
    db.add(complaint)
    db.commit()
    db.refresh(complaint)
    
    # Resolve Department Routing
    dept_code = get_department_code_by_category(category)
    dept = db.query(Department).filter(Department.code == dept_code).first()
    if not dept:
        dept = db.query(Department).filter(Department.code == "MAINT").first()
        
    est_hours = calculate_resolution_hours(priority)
    
    # Generate update times for resolved tickets
    update_time = created_time
    if status in ["RESOLVED", "CLOSED"]:
        resolution_delay = random.randint(1, est_hours or 24)
        update_time = created_time + datetime.timedelta(hours=resolution_delay)
        
    # Create Ticket record
    ticket = Ticket(
        complaint_id=complaint.id,
        title=f"Demo Ticket: {category.replace('_', ' ').title()}",
        description=desc,
        status=status,
        priority=priority,
        department_id=dept.id if dept else None,
        location_id=location.id,
        estimated_resolution_hours=est_hours,
        created_at=created_time,
        updated_at=update_time
    )
    db.add(ticket)
    db.commit()


if __name__ == "__main__":
    seed_demo_data()
