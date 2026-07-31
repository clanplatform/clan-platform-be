from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid

class Module(Base):
    __tablename__ = "modules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)  # internal name
    code = Column(String(50), unique=True, nullable=True)  # unique identifier (CLIENT_MGMT)
    key = Column(String(100), unique=True, nullable=True)  # e.g., analytics-module
    label = Column(String(150), nullable=True)  # display name (Analytics Module)
    section_title = Column(String(150), nullable=True)  # group title in UI
    description = Column(Text, nullable=True)
    icon = Column(String(100), nullable=True)
    badge = Column(String(50), nullable=True)
    route = Column(String(255), nullable=True)
    level = Column(Integer, default=2)  # hierarchy level
    order_index = Column(Integer, default=0)  # ordering
    is_active = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)
    access = Column(ARRAY(String), default=list, nullable=True)  # Array of access permissions
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by = Column(Integer, nullable=True)

    # Relationships
    application = relationship("Application", back_populates="modules")
    menus = relationship("Menu", back_populates="module", cascade="all, delete-orphan")
    tenant_modules = relationship("TenantModule", back_populates="module", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Module(id={self.id}, name={self.name}, code={self.code}, application_id={self.application_id})>"