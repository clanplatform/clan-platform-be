"""add sso/mfa/lockout fields to security

Onboarding's "Security" step reveals extra fields once Enable SSO / Require
MFA are toggled on (SSO provider/entity id/sign-in URL/metadata URL/
auto-provision/force-for-all-users/signing certificate; MFA allowed methods/
enforce-for scope/enrollment grace days) plus a Lockout threshold field in
the session & password policy panel — none of these existed on the security
table before.

Revision ID: 028
Revises: 027
Create Date: 2026-08-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("security", sa.Column("sso_provider", sa.String(50), nullable=True))
    op.add_column("security", sa.Column("sso_entity_id", sa.String(255), nullable=True))
    op.add_column("security", sa.Column("sso_sign_in_url", sa.String(500), nullable=True))
    op.add_column("security", sa.Column("sso_metadata_url", sa.String(500), nullable=True))
    op.add_column(
        "security",
        sa.Column("sso_auto_provision_users", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "security",
        sa.Column("sso_force_for_all_users", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("security", sa.Column("sso_signing_certificate", sa.Text(), nullable=True))

    op.add_column(
        "security",
        sa.Column("mfa_allowed_methods", postgresql.ARRAY(sa.Text()), nullable=True),
    )
    op.add_column("security", sa.Column("mfa_enforce_for", sa.String(50), nullable=True))
    op.add_column("security", sa.Column("mfa_enrollment_grace_days", sa.Integer(), nullable=True))

    op.add_column("security", sa.Column("lockout_threshold", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("security", "lockout_threshold")
    op.drop_column("security", "mfa_enrollment_grace_days")
    op.drop_column("security", "mfa_enforce_for")
    op.drop_column("security", "mfa_allowed_methods")
    op.drop_column("security", "sso_signing_certificate")
    op.drop_column("security", "sso_force_for_all_users")
    op.drop_column("security", "sso_auto_provision_users")
    op.drop_column("security", "sso_metadata_url")
    op.drop_column("security", "sso_sign_in_url")
    op.drop_column("security", "sso_entity_id")
    op.drop_column("security", "sso_provider")
