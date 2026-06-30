"""
Tenant Database Manager — one PostgreSQL database per tenant.

Naming convention: clan_platform_{tenant_code_slug}
  e.g. tenant_code="RajeshNero"  →  clan_platform_rajeshnero

Engine/session-factory instances are cached in-process so each tenant pays
connection-pool setup cost only on their first request.
"""
from typing import Dict
from threading import Lock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(value: str) -> str:
    """Convert a string to a safe PostgreSQL identifier fragment."""
    import re
    return re.sub(r"[^a-z0-9_]", "_", value.lower())


def _swap_db_name(master_url: str, db_name: str) -> str:
    """Replace the database portion of a SQLAlchemy URL."""
    # Works for both  postgresql://user:pw@host:5432/old_db
    # and             postgresql+psycopg2://...
    parts = master_url.rsplit("/", 1)
    return f"{parts[0]}/{db_name}"


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class TenantDatabaseManager:
    """
    Manages per-tenant SQLAlchemy engines and session factories.
    Thread-safe: uses a lock around first-time engine creation.
    """

    def __init__(self) -> None:
        self._engines: Dict[str, object] = {}
        self._factories: Dict[str, sessionmaker] = {}
        self._lock = Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_session(self, tenant_db_name: str, master_url: str) -> Session:
        """Return a new SQLAlchemy Session connected to the tenant database."""
        if tenant_db_name not in self._factories:
            self._init_engine(tenant_db_name, master_url)
        return self._factories[tenant_db_name]()

    def provision(self, tenant_db_name: str, master_url: str) -> bool:
        """
        CREATE DATABASE if it doesn't exist, then create all tables.
        Called once when a new tenant is registered.
        Returns True on success, False on failure.
        """
        try:
            self._create_database(tenant_db_name, master_url)
            engine = self._init_engine(tenant_db_name, master_url)
            self._create_tables(engine)
            logger.info("Provisioned tenant database: %s", tenant_db_name)
            return True
        except Exception as exc:
            logger.error("Failed to provision tenant database %s: %s", tenant_db_name, exc, exc_info=True)
            return False

    @staticmethod
    def make_db_name(tenant_code: str) -> str:
        """Derive a database name from a tenant code."""
        return f"clan_platform_{_slugify(tenant_code)}"

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _init_engine(self, tenant_db_name: str, master_url: str):
        """Create (or return cached) engine + session factory for this tenant."""
        with self._lock:
            if tenant_db_name not in self._engines:
                db_url = _swap_db_name(master_url, tenant_db_name)
                engine = create_engine(
                    db_url,
                    pool_pre_ping=True,
                    pool_size=5,
                    max_overflow=10,
                )
                self._engines[tenant_db_name] = engine
                self._factories[tenant_db_name] = sessionmaker(
                    autocommit=False, autoflush=False, bind=engine
                )
                logger.info("Engine created for tenant DB: %s", tenant_db_name)
        return self._engines[tenant_db_name]

    def _create_database(self, tenant_db_name: str, master_url: str) -> None:
        """
        Connect to the 'postgres' system database and CREATE DATABASE.
        Uses AUTOCOMMIT because CREATE DATABASE cannot run inside a transaction.
        """
        admin_url = _swap_db_name(master_url, "postgres")
        admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        try:
            with admin_engine.connect() as conn:
                exists = conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :n"),
                    {"n": tenant_db_name},
                ).fetchone()
                if not exists:
                    # Identifier already slugified — safe to embed directly
                    conn.execute(text(f'CREATE DATABASE "{tenant_db_name}"'))
                    logger.info("Created PostgreSQL database: %s", tenant_db_name)
                else:
                    logger.debug("Database already exists: %s", tenant_db_name)
        finally:
            admin_engine.dispose()

    def _create_tables(self, engine) -> None:
        """Run create_all for all application models in this tenant's database."""
        from app.infrastructure.database.base import Base

        # Import every model so SQLAlchemy registers it with Base.metadata
        from app.domains.models.domain import Domain                                        # noqa: F401
        from app.applications.models.application import Application                          # noqa: F401
        from app.modules.models.module import Module                                         # noqa: F401
        from app.menus.models.menu import Menu                                               # noqa: F401
        from app.forms.models.forms import Form                                              # noqa: F401
        from app.tenants.models.tenants import Tenant                                        # noqa: F401
        from app.entities.models.entity import Entity                                        # noqa: F401
        from app.departments.models.departments import Department                             # noqa: F401
        from app.divisions.models.divisions import Division                                   # noqa: F401
        from app.job_codes.models.job_codes import JobCode                                   # noqa: F401
        from app.user_role.models.user_role import (                                         # noqa: F401
            UserRoleMain, UserRoleBasic, UserRolePermission, UserRoleConditional
        )
        from app.user_setup.models.user_setup import (                                       # noqa: F401
            UserSetup, UserSetupBasic, UserSetupRolesEntity, UserSetupPreference
        )
        from app.user_role_form_permission.models.user_role_form_permission import (         # noqa: F401
            RoleFormPermission
        )
        from app.buttons.models.button import Button                                         # noqa: F401
        from app.tenant_modules.models.tenant_module import TenantModule                     # noqa: F401

        Base.metadata.create_all(bind=engine, checkfirst=True)


# Process-level singleton — imported everywhere
tenant_db_manager = TenantDatabaseManager()
