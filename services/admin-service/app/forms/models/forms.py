from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text, JSON
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid

class Form(Base):
    __tablename__ = "forms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    menu_id = Column(UUID(as_uuid=True), ForeignKey("menus.id", ondelete="CASCADE"), nullable=False)
    # Store MongoDB ObjectId as 24-char hex string
    mongo_id = Column(String(24), nullable=True, index=True)
    
    # Form metadata
    name = Column(String(100), nullable=False)
    version = Column(String(20), default="1.0.0")
    trigger_when = Column(String(255), nullable=True)  # triggerwhen field
    
    # Form structure - store the complete forms JSON array
    forms = Column(JSON, nullable=False)  # Complete forms array from JSON
    actions = Column(JSON, nullable=True, default=dict)  # Actions object
    access = Column(ARRAY(String), nullable=False, default=["read"])  # Access permissions
    
    # UI Configuration
    modal_type = Column(String(50), default="AntModalAdapter")
    tooltip_type = Column(String(50), default="AntTooltip")
    error_type = Column(String(50), default="AntErrorMessage")
    
    # Localization
    localization = Column(JSON, nullable=True, default=dict)
    languages = Column(JSON, nullable=True, default=list)
    default_language = Column(String(10), default="en-US")
    
    # Status and metadata
    is_active = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = Column(String(50), nullable=True)
    updated_by = Column(String(50), nullable=True)

    # Relationships
    menu = relationship("Menu", back_populates="forms")

    def get_effective_access(self):
        """
        Get the effective access permissions for this menu.
        Menu is the root, so it always uses its own access value.
        Returns a list of access permissions.
        """
        return self.access if self.access else ["read"]
    
    def __repr__(self):
        return f"<Form(id={self.id}, name={self.name}, version={self.version}, menu_id={self.menu_id},access={self.access})>"