from sqlalchemy import create_engine
from backend.app.database.connection import Base
from backend.app.models.models import Department, Location, Ticket

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(bind=engine)

print("Metadata tables keys:", Base.metadata.tables.keys())

# Inspect the database to see what tables exist
from sqlalchemy import inspect
inspector = inspect(engine)
print("Database tables:", inspector.get_table_names())
