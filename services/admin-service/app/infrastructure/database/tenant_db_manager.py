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

    def provision(self, tenant_db_name: str, master_url: str, allowed_tables: list | None = None) -> bool:
        """
        CREATE DATABASE if it doesn't exist, then create tables.

        If *allowed_tables* is given (non-empty), only those tables are created
        plus any tables they reference through FK constraints (to satisfy
        referential integrity).  Pass None or [] to create every table.

        Called once when a new tenant is registered.
        Returns True on success, False on failure.
        """
        try:
            self._create_database(tenant_db_name, master_url)
            engine = self._init_engine(tenant_db_name, master_url)
            self._create_tables(engine, allowed_tables or None)
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

    def _create_tables(self, engine, allowed_tables: list | None = None) -> None:
        """
        Create tables in the tenant database.

        If *allowed_tables* is provided, only those tables are created plus any
        tables they depend on via FK constraints (resolved transitively so that
        referential integrity is maintained without manual FK tracking).
        When *allowed_tables* is None/empty every table is created (original behaviour).
        """
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
            UserSetup, UserSetupBasic, UserSetupPreference
        )
        from app.buttons.models.button import Button                                         # noqa: F401
        from app.tenant_modules.models.tenant_module import TenantModule                     # noqa: F401
        from app.tenant_applications.models.tenant_application import TenantApplication      # noqa: F401
        from app.subscription.models.subscription import Subscription                        # noqa: F401
        from app.security.models.security import Security                                     # noqa: F401

        if not allowed_tables:
            # No restriction — create every table (default / backwards-compatible)
            Base.metadata.create_all(bind=engine, checkfirst=True)
            return

        # --- Resolve transitive FK dependencies ----------------------------
        # Start from the permitted table names and walk FK references until the
        # set stabilises.  This ensures every table that a permitted table
        # points to also exists, satisfying FK constraints.
        meta_tables = Base.metadata.tables
        resolved: set[str] = set()
        queue = list(allowed_tables)
        while queue:
            name = queue.pop()
            if name in resolved or name not in meta_tables:
                continue
            resolved.add(name)
            for fk in meta_tables[name].foreign_keys:
                dep = fk.column.table.name
                if dep not in resolved:
                    queue.append(dep)

        tables_to_create = [meta_tables[n] for n in resolved if n in meta_tables]
        Base.metadata.create_all(bind=engine, tables=tables_to_create, checkfirst=True)
        logger.info(
            "Created %d tables for %s: %s",
            len(tables_to_create), engine.url.database, sorted(resolved)
        )


# Process-level singleton — imported everywhere
tenant_db_manager = TenantDatabaseManager()
