from sqlalchemy import Column, Boolean, DateTime, Text, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class ClientApplication(Base):
    """
    Junction table — many-to-many between clients and applications.

    Licensing tiers:
      - Tier 1: A client buys individual modules    → use client_modules
      - Tier 2: A client buys an entire application → use client_applications
      - Tier 3: A client buys the full platform     → set subscription_plan='platform' on clients

    When a ClientApplication row exists (and is_active=True), the client has
    access to ALL modules under that application without needing individual
    client_modules rows.
    """

    __tablename__ = "client_applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(
        UUID(as_uuid=True),
        ForeignKey("clients.client_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    application_id = Column(
        UUID(as_uuid=True),
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)

    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    assigned_by = Column(UUID(as_uuid=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by = Column(UUID(as_uuid=True), nullable=True)

    client = relationship("Client", backref="client_applications")
    application = relationship("Application", backref="client_applications")

    __table_args__ = (
        UniqueConstraint("client_id", "application_id", name="uq_client_application"),
    )
