import datetime
from backend.app.database.connection import engine, Base, SessionLocal
from backend.app.models.models import Department, Location, Ticket

def seed_db():
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Check if already seeded
        if db.query(Department).first():
            print("Database already seeded.")
            return

        # Seed Departments
        dept_it = Department(name="IT Support Department", code="IT", email="it.support@vitbhopal.ac.in")
        dept_maint = Department(name="Maintenance & Plumbing", code="MAINT", email="maintenance@vitbhopal.ac.in")
        dept_elec = Department(name="Electrical Office", code="ELEC", email="electrical@vitbhopal.ac.in")
        dept_hostel = Department(name="Hostel Warden Office", code="HOSTEL", email="hostel.warden@vitbhopal.ac.in")
        dept_acad = Department(name="Academic Registry", code="ACAD", email="academic.registry@vitbhopal.ac.in")

        db.add_all([dept_it, dept_maint, dept_elec, dept_hostel, dept_acad])
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

        # Seed Some Initial Tickets
        t1 = Ticket(
            title="Hostel Block 1 WiFi down",
            description="The internet connection on 3rd floor wing A of Hostel Block 1 is extremely slow and keeps dropping since yesterday.",
            category="WiFi",
            status="OPEN",
            priority="HIGH",
            student_name="Aarav Sharma",
            student_email="aarav.sharma2023@vitbhopal.ac.in",
            department_id=dept_it.id,
            location_id=loc_h1.id,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=5)
        )
        t2 = Ticket(
            title="Water leakage in Hostel Block 2",
            description="There is a major water pipe leakage in the ground floor common washroom of Hostel Block 2, causing water logging.",
            category="Plumbing",
            status="IN_PROGRESS",
            priority="CRITICAL",
            student_name="Priyansh Patel",
            student_email="priyansh.patel2022@vitbhopal.ac.in",
            department_id=dept_maint.id,
            location_id=loc_h2.id,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(days=1)
        )
        t3 = Ticket(
            title="AC not working in Library 2nd floor",
            description="The air conditioning units in the reading room of the library on the second floor are not blowing cool air. It gets very stuffy.",
            category="Electrical",
            status="OPEN",
            priority="MEDIUM",
            student_name="Ananya Sen",
            student_email="ananya.sen2024@vitbhopal.ac.in",
            department_id=dept_elec.id,
            location_id=loc_lib.id,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=10)
        )
        t4 = Ticket(
            title="Food quality concern at boys mess",
            description="The lunch served today had undercooked rice and the cleanliness of the serving area was sub-standard.",
            category="Hostel Operations",
            status="OPEN",
            priority="LOW",
            student_name="Kabir Mehta",
            student_email="kabir.mehta2023@vitbhopal.ac.in",
            department_id=dept_hostel.id,
            location_id=loc_mess.id,
            created_at=datetime.datetime.utcnow() - datetime.timedelta(hours=2)
        )

        db.add_all([t1, t2, t3, t4])
        db.commit()
        print("Database successfully seeded with default departments, locations, and sample tickets!")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()
