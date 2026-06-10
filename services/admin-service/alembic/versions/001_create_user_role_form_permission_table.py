"""create user_role_form_permission table

Revision ID: 001
Revises: 
Create Date: 2026-06-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid


# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create user_role_form_permission table with all required columns,
    foreign keys, indexes, and the sequence for sino column.
    """
    
    # Create sequence for sino column
    op.execute("""
        CREATE SEQUENCE IF NOT EXISTS role_form_permission_sino_seq
        START WITH 1
        INCREMENT BY 1
        NO MINVALUE
        NO MAXVALUE
        CACHE 1;
    """)
    
    # Create the user_role_form_permission table
    op.create_table(
        'user_role_form_permission',
        
        # Primary key
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False, 
                  default=uuid.uuid4, comment='Primary key UUID'),
        
        # Serial number for ordering/display
        sa.Column('sino', sa.Integer(), nullable=False, unique=True,
                  server_default=sa.text("nextval('role_form_permission_sino_seq'::regclass)"),
                  comment='Serial number for ordering'),
        
        # Foreign keys to user role tables
        sa.Column('user_role_id', UUID(as_uuid=True), nullable=False,
                  comment='Reference to user_role (UserRoleMain) table'),
        
        sa.Column('userrole_basic_id', UUID(as_uuid=True), nullable=False,
                  comment='Reference to userrole_basic table'),
        
        sa.Column('userrole_permission_id', UUID(as_uuid=True), nullable=False,
                  comment='Reference to userrole_permission table (required - to get menu selections)'),
        
        # Form permissions stored as JSONB array
        sa.Column('form_permissions', JSONB, nullable=False, 
                  server_default='[]',
                  comment='Array of form permissions with individual access levels'),
        
        # Highest form access level
        sa.Column('form_access', sa.String(20), nullable=True,
                  server_default='disable',
                  comment='Highest form access level: read, write, or disable'),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        
        sa.Column('updated_at', sa.DateTime(), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        
        # Primary key constraint
        sa.PrimaryKeyConstraint('id', name='pk_user_role_form_permission')
    )
    
    # Create foreign key constraints
    op.create_foreign_key(
        'fk_user_role_form_permission_user_role',
        'user_role_form_permission', 'user_role',
        ['user_role_id'], ['id'],
        ondelete='CASCADE'
    )
    
    op.create_foreign_key(
        'fk_user_role_form_permission_userrole_basic',
        'user_role_form_permission', 'userrole_basic',
        ['userrole_basic_id'], ['id'],
        ondelete='CASCADE'
    )
    
    op.create_foreign_key(
        'fk_user_role_form_permission_userrole_permission',
        'user_role_form_permission', 'userrole_permission',
        ['userrole_permission_id'], ['id'],
        ondelete='CASCADE'
    )
    
    # Create indexes
    op.create_index(
        'ix_user_role_form_permission_id',
        'user_role_form_permission',
        ['id']
    )
    
    op.create_index(
        'ix_user_role_form_permission_sino',
        'user_role_form_permission',
        ['sino']
    )
    
    op.create_index(
        'ix_user_role_form_permission_user_role_id',
        'user_role_form_permission',
        ['user_role_id']
    )
    
    op.create_index(
        'ix_user_role_form_permission_userrole_basic_id',
        'user_role_form_permission',
        ['userrole_basic_id']
    )
    
    op.create_index(
        'ix_user_role_form_permission_userrole_permission_id',
        'user_role_form_permission',
        ['userrole_permission_id']
    )
    
    # Create trigger function for updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_user_role_form_permission_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create trigger
    op.execute("""
        CREATE TRIGGER trigger_user_role_form_permission_updated_at
        BEFORE UPDATE ON user_role_form_permission
        FOR EACH ROW
        EXECUTE FUNCTION update_user_role_form_permission_updated_at();
    """)
    
    # Add comment to table
    op.execute("""
        COMMENT ON TABLE user_role_form_permission IS 
        'Stores form permissions for user roles separately from menu permissions';
    """)


def downgrade() -> None:
    """
    Drop user_role_form_permission table, related triggers, functions, and sequence.
    """
    
    # Drop trigger
    op.execute("""
        DROP TRIGGER IF EXISTS trigger_user_role_form_permission_updated_at 
        ON user_role_form_permission;
    """)
    
    # Drop trigger function
    op.execute("""
        DROP FUNCTION IF EXISTS update_user_role_form_permission_updated_at();
    """)
    
    # Drop indexes (will be automatically dropped with table, but explicit for clarity)
    op.drop_index('ix_user_role_form_permission_userrole_permission_id', 
                  table_name='user_role_form_permission')
    op.drop_index('ix_user_role_form_permission_userrole_basic_id', 
                  table_name='user_role_form_permission')
    op.drop_index('ix_user_role_form_permission_user_role_id', 
                  table_name='user_role_form_permission')
    op.drop_index('ix_user_role_form_permission_sino', 
                  table_name='user_role_form_permission')
    op.drop_index('ix_user_role_form_permission_id', 
                  table_name='user_role_form_permission')
    
    # Drop foreign key constraints (will be automatically dropped with table)
    op.drop_constraint('fk_user_role_form_permission_userrole_permission', 
                       'user_role_form_permission', type_='foreignkey')
    op.drop_constraint('fk_user_role_form_permission_userrole_basic', 
                       'user_role_form_permission', type_='foreignkey')
    op.drop_constraint('fk_user_role_form_permission_user_role', 
                       'user_role_form_permission', type_='foreignkey')
    
    # Drop table
    op.drop_table('user_role_form_permission')
    
    # Drop sequence
    op.execute("DROP SEQUENCE IF EXISTS role_form_permission_sino_seq;")
