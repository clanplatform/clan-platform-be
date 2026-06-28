from sqlalchemy import Column, String, DateTime, Text, Boolean, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy import JSON
from sqlalchemy.orm import relationship,backref
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class Menu(Base):
    __tablename__ = "menus"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_id = Column(UUID(as_uuid=True), ForeignKey("applications.id"), nullable=False)
    module_id = Column(UUID(as_uuid=True), ForeignKey("modules.id"), nullable=True)  # New: Module reference
    # Store MongoDB ObjectId as 24-char hex string
    mongo_id = Column(String(24), nullable=True, index=True)
    name = Column(String(100), nullable=False)
    label = Column(String(100), nullable=False)
    icon = Column(String(50), nullable=True)
    route = Column(String(200), nullable=True)
    component = Column(String(100), nullable=True)
    order_index = Column(Integer, default=0)
    level = Column(Integer, default=3)  # Updated default: Level 3 for menus (1=App, 2=Module, 3=Menu, 4=Children)
    is_visible = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    menu_metadata = Column(JSON, nullable=True, default=dict)
    showtopbar = Column(Boolean, default=True)
    showsidebar = Column(Boolean, default=True)

    # ✅ New navigation/UI fields
    key = Column(String(100), nullable=True)
    # ✅ Badge stored as JSON to support both string and object formats
    # Can be: "NEW" or {"count": "NEW", "color": "gold"}
    badge = Column(JSON, nullable=True)
    section_title = Column(String(200), nullable=True)
    menus_description = Column(Text, nullable=True)  # PostgreSQL column name
    parent_menu_id = Column(UUID(as_uuid=True), ForeignKey("menus.id"), nullable=True, index=True)
   

    # ✅ Access permission field (root level - NOT NULL, default=['read'])
    # This is the root of the permission hierarchy
    # Array of strings to support multiple access permissions
    access = Column(
        ARRAY(String),
        nullable=False,
        default=["read"]
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    application = relationship("Application")
    module = relationship("Module", back_populates="menus")  # New: Module relationship
    children = relationship(
        "Menu",
        backref=backref("parent", remote_side=[id]),
        foreign_keys=[parent_menu_id],
        cascade="all, delete-orphan"
    )

    forms = relationship("Form", back_populates="menu")
    buttons = relationship("Button", back_populates="menu", cascade="all, delete-orphan")

    def get_effective_access(self):
        """
        Get the effective access permissions for this menu.
        Menu is the root, so it always uses its own access value.
        Returns a list of access permissions.
        """
        return self.access if self.access else ["read"]

    def __repr__(self):
        return f"<Menu(id={self.id}, name={self.name}, route={self.route}, module_id={self.module_id}, mongo_id={self.mongo_id}, access={self.access})>"
