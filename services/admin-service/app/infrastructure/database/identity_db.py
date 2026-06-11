"""
Identity Database Connection for Direct Sync
Connects to clan-identity-postgres (port 5433) for auth_users table sync
"""
from sqlalchemy import create_engine, Column, String, DateTime, Boolean, Text, Date, text
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func
from contextlib import contextmanager
from typing import Optional
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Base for identity database models
IdentityBase = declarative_base()


class AuthUser(IdentityBase):
    """
    Model for auth_users table in clan-identity-postgres database.
    This mirrors the structure of usersetup_basic table from admin-service.
    """
    __tablename__ = "auth_users"

    id = Column(UUID(as_uuid=True), primary_key=True)
    user_setup_id = Column(UUID(as_uuid=True), nullable=True)  # Reference to usersetup_basic.id
    firstname = Column(String(100), nullable=False)
    lastname = Column(String(100), nullable=False)
    employee_id = Column(String(50), nullable=False, unique=True)
    username = Column(String(100), nullable=False, unique=True)
    email = Column(String(255), nullable=False, unique=True)
    phone_number = Column(String(20), nullable=True)
    password_hash = Column(String(255), nullable=False)
    password_changed = Column(DateTime(timezone=True), nullable=True)
    is_password_change = Column(Boolean, default=False, nullable=False)
    status = Column(String(50), nullable=False, default='active')
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    tem_employee = Column(Boolean, default=False, nullable=False)
    department = Column(UUID(as_uuid=True), nullable=True)
    division = Column(UUID(as_uuid=True), nullable=True)
    job_code = Column(UUID(as_uuid=True), nullable=True)
    manage_roles = Column(ARRAY(UUID(as_uuid=True)), nullable=True)
    default_dept = Column(UUID(as_uuid=True), nullable=True)
    reporting_to = Column(UUID(as_uuid=True), nullable=True)
    entities = Column(ARRAY(UUID(as_uuid=True)), nullable=True)
    default_entity = Column(UUID(as_uuid=True), nullable=True)
    view = Column(String(50), nullable=True)
    dashboard_view = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<AuthUser(id={self.id}, username={self.username}, email={self.email})>"


class IdentityDatabase:
    """
    Manager for identity database connection.
    Provides session management for direct database sync.
    """
    
    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._initialized = False
    
    def initialize(self) -> bool:
        """
        Initialize the identity database connection.
        Returns True if successful, False if IDENTITY_DATABASE_URL is not configured.
        """
        logger.info("IDENTITY_DB: initialize() called")
        
        if self._initialized:
            logger.info("IDENTITY_DB: Already initialized, returning True")
            return True
            
        if not settings.IDENTITY_DATABASE_URL:
            logger.warning("IDENTITY_DB: IDENTITY_DATABASE_URL not configured. Identity sync disabled.")
            return False
        
        logger.info(f"IDENTITY_DB: IDENTITY_DATABASE_URL found: {settings.IDENTITY_DATABASE_URL[:50]}...")
        
        try:
            # Create engine for identity database
            logger.info("IDENTITY_DB: Creating database engine...")
            self.engine = create_engine(
                settings.IDENTITY_DATABASE_URL,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
                echo=False
            )
            
            # Create session factory
            logger.info("IDENTITY_DB: Creating session factory...")
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            # Test connection
            logger.info("IDENTITY_DB: Testing connection...")
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            self._initialized = True
            logger.info("IDENTITY_DB: Identity database connection initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"IDENTITY_DB: Failed to initialize identity database: {str(e)}")
            logger.error(f"IDENTITY_DB: Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"IDENTITY_DB: Traceback: {traceback.format_exc()}")
            return False
    
    def is_enabled(self) -> bool:
        """Check if identity sync is enabled and initialized"""
        logger.info(f"IDENTITY_DB: is_enabled() called, _initialized={self._initialized}")
        if not self._initialized:
            result = self.initialize()
            logger.info(f"IDENTITY_DB: is_enabled() initializing, result={result}")
            return result
        return self._initialized
    
    @contextmanager
    def get_session(self) -> Session:
        """
        Get a database session for identity database.
        Use as a context manager:
        
        with identity_db.get_session() as session:
            # perform database operations
        """
        if not self.is_enabled():
            raise RuntimeError("Identity database is not initialized")
        
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# Global identity database instance
identity_db = IdentityDatabase()


def get_identity_db() -> IdentityDatabase:
    """Get the global identity database instance"""
    return identity_db
