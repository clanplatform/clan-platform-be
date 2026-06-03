from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid

class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_id = Column(UUID(as_uuid=True), ForeignKey("domains.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    version = Column(String(20), default="1.0.0")
    status = Column(String(50), default="active")
    config = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # ✅ New fields for navigation/UI display
    key = Column(String(100), nullable=True)
    label = Column(String(100), nullable=True)
    route = Column(String(200), nullable=True)
    level = Column(Integer, default=1)
    icon = Column(String(100), nullable=True)
    badge = Column(String(50), nullable=True)
    section_title = Column(String(200), nullable=True)
    access = Column(ARRAY(String), default=list, nullable=True)  # Array of access permissions
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    domain = relationship("Domain", back_populates="applications")
    menus = relationship("Menu", back_populates="application", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Application(id={self.id}, name={self.name}, domain_id={self.domain_id})>"
