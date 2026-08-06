from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import JSON
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class AuditLog(Base):
    """Mirrors clan-audit-be's audit_logs table so each tenant database gets
    its own copy for tenant-scoped audit trail entries (created here so
    TenantDatabaseManager.provision() includes it for every new tenant DB)."""
    __tablename__ = "audit_logs"

    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=True)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    action = Column(String(100), nullable=False)
    object_type = Column(String(100), nullable=False)
    object_id = Column(String(255), nullable=True)
    old_values = Column(JSON, default=dict)
    new_values = Column(JSON, default=dict)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    session_id = Column(String(255), nullable=True)
    risk_score = Column(String(20), nullable=True)
    compliance_tags = Column(JSON, default=list)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<AuditLog(id={self.log_id}, action={self.action}, user_id={self.user_id})>"
