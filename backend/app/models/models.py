import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.database.connection import Base

class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    code = Column(String, nullable=False, unique=True)
    email = Column(String, nullable=True)

    tickets = relationship("Ticket", back_populates="department")


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    block = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    tickets = relationship("Ticket", back_populates="location")
    complaints = relationship("Complaint", back_populates="location")


class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    category = Column(String, nullable=False) # e.g. water_leakage, electricity, wifi, etc.
    description = Column(Text, nullable=False)
    priority = Column(String, default="MEDIUM") # LOW, MEDIUM, HIGH, CRITICAL
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    location = relationship("Location", back_populates="complaints")
    ticket = relationship("Ticket", uselist=False, back_populates="complaint")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id"), nullable=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String, default="OPEN") # OPEN, IN_PROGRESS, RESOLVED
    priority = Column(String, default="MEDIUM") # LOW, MEDIUM, HIGH, CRITICAL
    
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    estimated_resolution_hours = Column(Integer, default=24)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    complaint = relationship("Complaint", back_populates="ticket")
    department = relationship("Department", back_populates="tickets")
    location = relationship("Location", back_populates="tickets")


class RAGDocument(Base):
    __tablename__ = "rag_documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    sender = Column(String, nullable=False) # "user" or "assistant"
    message = Column(Text, nullable=False)
    intent = Column(String, nullable=True) # e.g. "FAQ", "COMPLAINT", etc.
    ticket_id = Column(Integer, nullable=True) # Link to ticket if generated
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
