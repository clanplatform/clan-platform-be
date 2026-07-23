"""Add client_id to userrole_basic and scope role name/code uniqueness per client

Revision ID: 002
Revises: 001
Create Date: 2026-06-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- userrole_basic: add client_id column ---
    op.add_column(
        'userrole_basic',
        sa.Column(
            'client_id',
            UUID(as_uuid=True),
            sa.ForeignKey('clients.client_id', ondelete='SET NULL'),
            nullable=True,
        )
    )

    op.create_index('ix_userrole_basic_client_id', 'userrole_basic', ['client_id'])

    # Drop old global unique constraints (SQLAlchemy names them <table>_<col>_key)
    op.drop_constraint('userrole_basic_role_name_key', 'userrole_basic', type_='unique')
    op.drop_constraint('userrole_basic_role_code_key', 'userrole_basic', type_='unique')

    # Add per-client unique constraints
    op.create_unique_constraint(
        'uq_userrole_basic_client_role_name',
        'userrole_basic',
        ['client_id', 'role_name']
    )
    op.create_unique_constraint(
        'uq_userrole_basic_client_role_code',
        'userrole_basic',
        ['client_id', 'role_code']
    )


def downgrade() -> None:
    op.drop_constraint('uq_userrole_basic_client_role_code', 'userrole_basic', type_='unique')
    op.drop_constraint('uq_userrole_basic_client_role_name', 'userrole_basic', type_='unique')

    # Restore global unique constraints
    # NOTE: if existing data has duplicate role_name/role_code across clients, this will fail.
    op.create_unique_constraint('userrole_basic_role_name_key', 'userrole_basic', ['role_name'])
    op.create_unique_constraint('userrole_basic_role_code_key', 'userrole_basic', ['role_code'])

    op.drop_index('ix_userrole_basic_client_id', table_name='userrole_basic')
    op.drop_column('userrole_basic', 'client_id')
