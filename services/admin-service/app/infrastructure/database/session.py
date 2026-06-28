"""
Database session management - SQLAlchemy engine and session configuration
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError
from typing import Generator
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

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
    from app.forms.models.forms import Form
    from app.clients.models.clients import Client
    from app.entities.models.entity import Entity
    from app.user_role.models.user_role import UserRoleMain, UserRoleBasic, UserRolePermission, UserRoleConditional
    from app.user_setup.models.user_setup import UserSetup, UserSetupBasic, UserSetupRolesEntity, UserSetupPreference
    from app.user_role_form_permission.models.user_role_form_permission import RoleFormPermission
    from app.buttons.models.button import Button
    from app.client_modules.models.client_module import ClientModule

    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
    except IntegrityError:
        # Race condition: another worker already created the tables
        logger.warning("Tables already exist (created by another worker), skipping")


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
