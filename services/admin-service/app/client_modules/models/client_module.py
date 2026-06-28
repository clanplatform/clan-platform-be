from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class ClientModule(Base):
    """
    Junction table — many-to-many between clients and modules.
    One module (e.g. Scheduling) can be assigned to many clients.
    One client can have many modules.
    """
    __tablename__ = "client_modules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey("clients.client_id", ondelete="CASCADE"), nullable=False, index=True)
    module_id = Column(UUID(as_uuid=True), ForeignKey("modules.id", ondelete="CASCADE"), nullable=False, index=True)

    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)

    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    assigned_by = Column(UUID(as_uuid=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by = Column(UUID(as_uuid=True), nullable=True)

    # Relationships
    client = relationship("Client", back_populates="client_modules")
    module = relationship("Module", back_populates="client_modules")

    __table_args__ = (
        UniqueConstraint("client_id", "module_id", name="uq_client_module"),
    )

    def __repr__(self):
        return f"<ClientModule(client_id={self.client_id}, module_id={self.module_id}, is_active={self.is_active})>"
