"""
014: Add appearance preferences (accent_color, density) to usersetup_preference.

These carry over from the removed per-user user_profile table. Both are NOT NULL
with server defaults so existing rows backfill. (theme and language already live
on usersetup_preference; can_change_password stays on usersetup_basic and is not
duplicated here.)
"""
from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "usersetup_preference",
        sa.Column("accent_color", sa.String(length=50), nullable=False, server_default="blue"),
    )
    op.add_column(
        "usersetup_preference",
        sa.Column("density", sa.String(length=20), nullable=False, server_default="comfortable"),
    )


def downgrade() -> None:
    op.drop_column("usersetup_preference", "density")
    op.drop_column("usersetup_preference", "accent_color")
