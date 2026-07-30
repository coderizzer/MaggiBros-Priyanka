import datetime
from backend.app.database.connection import engine, Base, SessionLocal
from backend.app.models.models import Department, Location, Ticket, Complaint

def seed_db():
    # Re-create tables to ensure correct schema is loaded
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Check if already seeded
        if db.query(Department).first():
            print("Database already seeded.")
            return

        # Seed Departments
        dept_maint = Department(name="Maintenance", code="MAINT", email="maintenance@vitbhopal.ac.in")
        dept_it = Department(name="IT Support", code="IT", email="it.support@vitbhopal.ac.in")
        dept_hostel = Department(name="Hostel Administration", code="HOSTEL", email="hostel.admin@vitbhopal.ac.in")
        dept_acad = Department(name="Academic Affairs", code="ACAD", email="academic.affairs@vitbhopal.ac.in")
        dept_exam = Department(name="Examination Cell", code="EXAM", email="examination@vitbhopal.ac.in")
        dept_security = Department(name="Security", code="SECURITY", email="security@vitbhopal.ac.in")

        db.add_all([dept_maint, dept_it, dept_hostel, dept_acad, dept_exam, dept_security])
        db.commit()

        # Seed Locations
        loc_h1 = Location(name="Hostel Block 1", block="Hostels", latitude=23.0765, longitude=77.6080)
        loc_h2 = Location(name="Hostel Block 2", block="Hostels", latitude=23.0772, longitude=77.6085)
        loc_ab1 = Location(name="Academic Block 1", block="Academic", latitude=23.0780, longitude=77.6095)
        loc_lib = Location(name="Central Library", block="Academic", latitude=23.0785, longitude=77.6090)
        loc_mph = Location(name="Multi-Purpose Hall", block="Common", latitude=23.0755, longitude=77.6075)
        loc_mess = Location(name="Boys Mess Hall", block="Hostels", latitude=23.0768, longitude=77.6082)

        db.add_all([loc_h1, loc_h2, loc_ab1, loc_lib, loc_mph, loc_mess])
        db.commit()

        # Seed Some Sample Complaints & Associated Tickets
        c1 = Complaint(
            user_id=1,
            location_id=loc_h1.id,
            category="wifi",
            description="The internet connection on 3rd floor wing A of Hostel Block 1 is dropping constantly.",
            priority="HIGH",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=5)
        )
        c2 = Complaint(
            user_id=2,
            location_id=loc_h2.id,
            category="water_leakage",
            description="Water leaking from ground floor washroom ceiling in Hostel Block 2.",
            priority="CRITICAL",
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=1)
        )
        db.add_all([c1, c2])
        db.commit()

        t1 = Ticket(
            complaint_id=c1.id,
            title=f"Ticket for complaint #{c1.id}: wifi",
            description=c1.description,
            status="OPEN",
            priority="HIGH",
            department_id=dept_it.id,
            location_id=loc_h1.id,
            estimated_resolution_hours=12,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=5)
        )
        t2 = Ticket(
            complaint_id=c2.id,
            title=f"Ticket for complaint #{c2.id}: water_leakage",
            description=c2.description,
            status="IN_PROGRESS",
            priority="CRITICAL",
            department_id=dept_maint.id,
            location_id=loc_h2.id,
            estimated_resolution_hours=4,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=1)
        )
        db.add_all([t1, t2])
        db.commit()

        print("Database successfully seeded with new department mapping, complaints, and tickets!")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()
