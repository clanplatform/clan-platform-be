"""
Database session management - SQLAlchemy engine and session configuration
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError
from typing import Generator, Optional
import logging
import os
from fastapi import Depends, HTTPException, status
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
    from app.tenants.models.tenants import Tenant
    from app.entities.models.entity import Entity
    from app.departments.models.departments import Department
    from app.divisions.models.divisions import Division
    from app.job_codes.models.job_codes import JobCode
    from app.user_role.models.user_role import UserRoleMain, UserRoleBasic, UserRolePermission, UserRoleConditional
    from app.user_setup.models.user_setup import UserSetup, UserSetupBasic, UserSetupRolesEntity, UserSetupPreference
    from app.user_role_form_permission.models.user_role_form_permission import RoleFormPermission
    from app.buttons.models.button import Button
    from app.tenant_modules.models.tenant_module import TenantModule

    try:
        Base.metadata.create_all(bind=engine, checkfirst=True)
    except IntegrityError:
        # Race condition: another worker already created the tables
        logger.warning("Tables already exist (created by another worker), skipping")


def _make_get_tenant_db() -> callable:
    from app.core.security import get_current_user
    from app.infrastructure.database.tenant_db_manager import tenant_db_manager

    REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "false").lower() == "true"

    def _get_tenant_db(
        current_user: dict = Depends(get_current_user),
    ) -> Generator[Session, None, None]:
        """
        Tenant-aware DB dependency.
        Reads tenant_id from JWT → looks up tenant_db_name in master DB →
        returns a session connected to that tenant's dedicated database.
        Falls back to master DB when REQUIRE_AUTH=false (dev/Swagger mode).
        """
        tenant_id: Optional[str] = (current_user or {}).get("tenant_id")

        if not tenant_id:
            if not REQUIRE_AUTH:
                # Dev fallback: no tenant in token → use master DB
                db = SessionLocal()
                try:
                    yield db
                except Exception as exc:
                    db.rollback()
                    raise exc
                finally:
                    db.close()
                return
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No tenant_id in token. Log in as a tenant user.",
            )

        # Look up this tenant's database name from the master DB
        master_db = SessionLocal()
        try:
            row = master_db.execute(
                text(
                    "SELECT tenant_db_name FROM tenants "
                    "WHERE gateway_tenant_ref = :tid AND is_active = true"
                ),
                {"tid": str(tenant_id)},
            ).fetchone()
        finally:
            master_db.close()

        if not row or not row.tenant_db_name:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"No database provisioned for tenant_id={tenant_id}. "
                    "Ask your administrator to run the provisioning script."
                ),
            )

        db = tenant_db_manager.get_session(row.tenant_db_name, settings.DATABASE_URL)
        try:
            yield db
        except Exception as exc:
            db.rollback()
            raise exc
        finally:
            db.close()

    return _get_tenant_db


# Overwrite the placeholder with the real dependency
get_tenant_db = _make_get_tenant_db()


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
