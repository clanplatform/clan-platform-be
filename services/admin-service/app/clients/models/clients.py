from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid

class Client(Base):
    __tablename__ = "clients"

    client_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    client_name = Column(String(255), nullable=False)
    client_code = Column(String(100), nullable=True)
    contact_email = Column(String(255), nullable=False)
    contact_phone = Column(String(50), nullable=True)
    address = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    industry = Column(String(100), nullable=True)
    company_size = Column(String(50), nullable=True)
    subscription_plan = Column(String(100), nullable=True)
    onboarding_status = Column(String(50), nullable=True)
    employees_count = Column(Integer, nullable=True)
    location = Column(String(255), nullable=True)
    status = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=True, server_default='true')
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(UUID(as_uuid=True), nullable=True)

    # Relationships
    entities = relationship("Entity", back_populates="client")

    def __repr__(self):
        return f"<Client(client_name='{self.client_name}', is_active='{self.is_active}')>"
