from sqlalchemy import Column, String, DateTime, Text, Boolean, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid

class Domain(Base):
    __tablename__ = "domains"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    # For industry-vertical domains: the branch-form compliance section this
    # vertical unlocks — must exactly equal one of the nested keys on
    # OnboardingBranch / EntityBase (e.g. "entities_healthcare") and the
    # SQLAlchemy __tablename__ of that section's model. NULL for verticals with
    # no compliance section and for the legacy "application domains".
    branch_compliance_key = Column(String(64), nullable=True, index=True)
    is_active = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    applications = relationship("Application", back_populates="domain")
    # Note: clients relationship removed as there's no foreign key in clients table
    
    def __repr__(self):
        return f"<Domain(id={self.id}, name={self.name})>"
