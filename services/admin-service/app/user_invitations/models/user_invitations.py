"""
Invitation-email tracking for user_setup users.

One row per invitation attempt (a resend creates a NEW row, not an update to
the old one — keeps a full history of "invited 3 times, still pending" per
user rather than losing it on resend). `user_id` references user_setup.id
(the parent-table PK — see the user_role / user_setup id fixes elsewhere in
this module for why: {user_id} path params and FKs consistently mean the
parent table's own PK, not usersetup_basic's).

token_hash stores a SHA-256 hex digest ONLY — the raw token is generated,
put in the invitation email's accept-link, and never persisted (see
app.core.security.generate_invitation_token / hash_invitation_token). A DB
leak of this table alone can't be used to accept anyone's invitation.

Lives in every tenant DB (created fresh via Base.metadata.create_all() at
provisioning time) and in the master DB, same as every other admin-service
table — see the "4 import lists" this model is registered in: alembic/env.py,
scripts/create_postgres_tables.py, app/infrastructure/database/
tenant_db_manager.py, app/infrastructure/database/session.py.
"""
from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid

# Allowed values for `status` — enforced at the Pydantic layer (see
# app.user_invitations.schemas.user_invitations.INVITATION_STATUS_VALUES),
# same lightweight convention as tenants.initial_status / userrole_basic
# .access_scope elsewhere in this codebase (a plain String column, not a
# Postgres ENUM type, so adding a status never needs a migration).
INVITATION_STATUSES = ("pending", "sent", "accepted", "expired", "cancelled", "failed")


class UserInvitation(Base):
    __tablename__ = "user_invitations"
    __table_args__ = (
        Index("ix_user_invitations_user_id", "user_id"),
        Index("ix_user_invitations_tenant_id", "tenant_id"),
        Index("ix_user_invitations_status", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # user_setup.id (parent table) — NOT usersetup_basic.id.
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_setup.id", ondelete="CASCADE"), nullable=False)

    # Derived from the JWT (never accepted in the request body):
    #   NULL     -> master-DB caller (token has no tenant_id)
    #   a tenant -> tenant-DB caller (token's tenant_id)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=True)

    # Captured at send time (usersetup_basic.email as of then) — kept even if
    # the user's email is later changed, so this row still reflects what was
    # actually invited/who received the link.
    email = Column(String(255), nullable=False)

    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    status = Column(String(20), nullable=False, default="pending", server_default="pending")

    sent_at = Column(DateTime(timezone=True), nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user_setup = relationship("UserSetup", foreign_keys=[user_id])
    tenant = relationship("Tenant", foreign_keys=[tenant_id])

    def __repr__(self):
        return f"<UserInvitation(id={self.id}, user_id={self.user_id}, status={self.status})>"
