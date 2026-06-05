from sqlalchemy import Column, String, DateTime, Text, Boolean, ForeignKey, Date
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base
import uuid


class UserSetup(Base):
    """
    Main user setup table (parent table).
    Contains the primary key that all child tables reference.
    """
    __tablename__ = "user_setup"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Child relationships
    basic = relationship("UserSetupBasic", back_populates="user_setup", cascade="all, delete-orphan", uselist=False)
    roles_entities = relationship("UserSetupRolesEntity", back_populates="user_setup", cascade="all, delete-orphan")
    preferences = relationship("UserSetupPreference", back_populates="user_setup", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<UserSetup(id={self.id})>"


class UserSetupBasic(Base):
    """
    Basic user setup information table (child table 1).
    Stores fundamental user details like name, employee info, contact, department, etc.
    References user_setup.id as foreign key.
    """
    __tablename__ = "usersetup_basic"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_setup_id = Column(UUID(as_uuid=True), ForeignKey("user_setup.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Personal Information
    firstname = Column(String(100), nullable=False)
    lastname = Column(String(100), nullable=False)
    employee_id = Column(String(50), nullable=False, unique=True)
    username = Column(String(100), nullable=False, unique=True)
    email = Column(String(255), nullable=False, unique=True)
    phone_number = Column(String(20), nullable=True)
    password_hash = Column(String(255), nullable=False)  # Hashed password
    password_changed = Column(DateTime(timezone=True), nullable=True)  # Last password change timestamp
    is_password_change = Column(Boolean, default=False, nullable=False)  # Flag to indicate if user needs to change password

    # Employment Status
    status = Column(String(50), nullable=False, default='active')  # active, inactive, suspended, etc.
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    tem_employee = Column(Boolean, default=False, nullable=False)  # Temporary employee flag

    # Organizational Structure - Foreign Keys
    department = Column(UUID(as_uuid=True), ForeignKey("departments.department_id"), nullable=True)
    division = Column(UUID(as_uuid=True), ForeignKey("divisions.id"), nullable=True)
    job_code = Column(UUID(as_uuid=True), ForeignKey("job_codes.id"), nullable=True)

    # Role Management
    manage_roles = Column(ARRAY(UUID(as_uuid=True)), nullable=True)  # Array of role IDs user can manage

    # Default Settings
    default_dept = Column(UUID(as_uuid=True), ForeignKey("departments.department_id"), nullable=True)
    reporting_to = Column(UUID(as_uuid=True), ForeignKey("usersetup_basic.id"), nullable=True)  # Self-referencing

    # Entity Access (dropdown selection)
    entities = Column(ARRAY(UUID(as_uuid=True)), nullable=True)  # Array of entity IDs
    default_entity = Column(UUID(as_uuid=True), ForeignKey("entities.entity_id"), nullable=True)

    # View Preferences
    view = Column(String(50), nullable=True)  # e.g., 'grid', 'list', 'card'
    dashboard_view = Column(String(50), nullable=True)  # e.g., 'default', 'compact', 'detailed'

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user_setup = relationship("UserSetup", back_populates="basic")
    department_rel = relationship("Department", foreign_keys=[department])
    default_dept_rel = relationship("Department", foreign_keys=[default_dept])
    division_rel = relationship("Division", foreign_keys=[division])
    job_code_rel = relationship("JobCode", foreign_keys=[job_code])
    default_entity_rel = relationship("Entity", foreign_keys=[default_entity])

    # Self-referencing relationship for reporting_to
    manager = relationship("UserSetupBasic", remote_side=[id], foreign_keys=[reporting_to])

    def __repr__(self):
        return f"<UserSetupBasic(id={self.id}, user_setup_id={self.user_setup_id}, username={self.username}, email={self.email}, status={self.status})>"

    def is_admin(self) -> bool:
        """Check if user is admin based on assigned roles"""
        # Check if email contains 'admin' (for development/testing)
        if self.email and 'admin' in self.email.lower():
            return True
        
        # Check if user has admin roles assigned
        if hasattr(self, 'roles_entities') and self.roles_entities:
            from app.models.user_role import UserRoleBasic
            from app.db.database import SessionLocal
            
            db = SessionLocal()
            try:
                for role_entity in self.roles_entities:
                    if role_entity.assigned_roles:
                        # Query the roles to check if any are admin roles
                        admin_roles = db.query(UserRoleBasic).filter(
                            UserRoleBasic.id.in_(role_entity.assigned_roles),
                            UserRoleBasic.is_admin == True,
                            UserRoleBasic.active == True
                        ).first()
                        
                        if admin_roles:
                            return True
            finally:
                db.close()
        
        return False

    @property
    def client_id(self):
        """Get client_id from roles_entities relationship"""
        if hasattr(self, 'roles_entities') and self.roles_entities:
            for role_entity in self.roles_entities:
                if role_entity.assigned_client_id:
                    return role_entity.assigned_client_id
        return None


class UserSetupRolesEntity(Base):
    """
    User setup roles and entity assignments table (child table 2).
    Stores assigned roles and entities for each user.
    References user_setup.id and usersetup_basic.id as foreign keys.
    """
    __tablename__ = "usersetup_roles_entity"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_setup_id = Column(UUID(as_uuid=True), ForeignKey("user_setup.id", ondelete="CASCADE"), nullable=False)
    usersetup_basic_id = Column(UUID(as_uuid=True), ForeignKey("usersetup_basic.id", ondelete="CASCADE"), nullable=False)

    # Assigned Roles - Array of role IDs from userrole_basic table
    assigned_roles = Column(ARRAY(UUID(as_uuid=True)), nullable=True)

    # Assigned Entities - Array of entity IDs
    assigned_entities = Column(ARRAY(UUID(as_uuid=True)), nullable=True)

    # Assigned Client - Foreign key to clients table
    assigned_client_id = Column(UUID(as_uuid=True), ForeignKey("clients.client_id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user_setup = relationship("UserSetup", back_populates="roles_entities")
    usersetup_basic = relationship("UserSetupBasic", backref="roles_entities")
    assigned_client = relationship("Client", foreign_keys=[assigned_client_id])

    def __repr__(self):
        return f"<UserSetupRolesEntity(id={self.id}, user_setup_id={self.user_setup_id}, usersetup_basic_id={self.usersetup_basic_id}, assigned_roles={self.assigned_roles}, assigned_client_id={self.assigned_client_id})>"


class UserSetupPreference(Base):
    """
    User setup preferences table (child table 3).
    Stores user preferences like language, timezone, and theme.
    References user_setup.id, usersetup_roles_entity.id, and usersetup_basic.id as foreign keys.
    """
    __tablename__ = "usersetup_preference"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_setup_id = Column(UUID(as_uuid=True), ForeignKey("user_setup.id", ondelete="CASCADE"), nullable=False)
    usersetup_roles_entity_id = Column(UUID(as_uuid=True), ForeignKey("usersetup_roles_entity.id", ondelete="CASCADE"), nullable=False)
    usersetup_basic_id = Column(UUID(as_uuid=True), ForeignKey("usersetup_basic.id", ondelete="CASCADE"), nullable=False)

    # User Preferences
    language = Column(String(10), nullable=False, default='en')  # e.g., 'en', 'es', 'fr'
    timezone = Column(String(50), nullable=False, default='UTC')  # e.g., 'America/New_York', 'UTC'
    theme = Column(String(20), nullable=False, default='light')  # e.g., 'light', 'dark', 'auto'

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user_setup = relationship("UserSetup", back_populates="preferences")
    usersetup_roles_entity = relationship("UserSetupRolesEntity", backref="preferences")
    usersetup_basic = relationship("UserSetupBasic", backref="preferences")

    def __repr__(self):
        return f"<UserSetupPreference(id={self.id}, user_setup_id={self.user_setup_id}, usersetup_roles_entity_id={self.usersetup_roles_entity_id}, language={self.language}, timezone={self.timezone}, theme={self.theme})>"

