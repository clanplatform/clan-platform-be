from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text, Integer, JSON
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class Button(Base):
    __tablename__ = "buttons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    menu_id = Column(UUID(as_uuid=True), ForeignKey("menus.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(100), nullable=False)
    label = Column(String(150), nullable=False)
    key = Column(String(100), nullable=True)
    icon = Column(String(100), nullable=True)
    tooltip = Column(String(255), nullable=True)

    # Button appearance/behaviour
    variant = Column(String(50), nullable=True)   # e.g., "primary", "secondary", "danger"
    action_type = Column(String(100), nullable=True)  # e.g., "submit", "reset", "navigate", "modal"
    action_payload = Column(JSON, nullable=True)  # flexible payload for the action

    order_index = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    is_visible = Column(Boolean, default=True)
    is_deleted = Column(Boolean, default=False)

    access = Column(ARRAY(String), nullable=False, default=["read"])

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = Column(String(50), nullable=True)
    updated_by = Column(String(50), nullable=True)

    # Relationships
    menu = relationship("Menu", back_populates="buttons")

    def __repr__(self):
        return f"<Button(id={self.id}, name={self.name}, menu_id={self.menu_id}, action_type={self.action_type})>"
