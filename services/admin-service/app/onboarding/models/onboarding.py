from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base


class OnboardingDraft(Base):
    """
    Auto-saved onboarding step-form data.

    POST /onboarding/ is one atomic all-or-nothing call; if it fails partway
    (validation error, duplicate client, etc.) the submitted payload is saved
    here under the client-generated draft_id instead of being lost, so the
    form can be resumed. Lives only in the master DB — a tenant (and its
    tenant database) doesn't exist yet while a draft is still incomplete.
    """
    __tablename__ = "onboarding_drafts"

    draft_id = Column(UUID(as_uuid=True), primary_key=True)  # client-generated, not server-assigned
    payload = Column(JSONB, nullable=False)
    error_message = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="draft", server_default="draft")  # draft | completed
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=True)
    created_by = Column(UUID(as_uuid=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<OnboardingDraft(draft_id={self.draft_id}, status={self.status})>"
