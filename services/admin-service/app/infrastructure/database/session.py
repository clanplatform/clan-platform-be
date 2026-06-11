"""
Database session management - SQLAlchemy engine and session configuration
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.core.config import settings

# Create SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG if hasattr(settings, 'DEBUG') else False
)

# Create sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Database dependency for FastAPI endpoints.
    Provides a SQLAlchemy session that automatically closes after request.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def create_tables():
    """
    Create all tables in the database.
    Called during application startup.
    """
    from app.infrastructure.database.base import Base
    # Import all models to ensure they're registered with Base
    from app.domains.models.domain import Domain
    from app.applications.models.application import Application
    from app.modules.models.module import Module
    from app.menus.models.menu import Menu
    from app.user_role.models.user_role import UserRoleMain, UserRoleBasic, UserRolePermission, UserRoleConditional
    from app.user_setup.models.user_setup import UserSetup, UserSetupBasic, UserSetupRolesEntity, UserSetupPreference
    
    # Note: UserRoleFormPermission is handled by Alembic migration
    # Do not import it here to avoid sequence dependency issues
    
    Base.metadata.create_all(bind=engine)


def check_db_connection() -> bool:
    """
    Check if database connection is working.
    Returns True if connection is successful, False otherwise.
    """
    try:
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False
