"""
Run once to create the audit_logs table in PostgreSQL.

Usage (from audit-service root):
    python scripts/create_tables.py
"""
import sys
import os

# Allow imports from service root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, inspect, text
from app.infrastructure.database.base import Base
from app.audit_logs.models.audit_logs import AuditLog  # registers model with Base
from app.core.config import settings


def main():
    print(f"[create_tables] Connecting to: {settings.DATABASE_URL}")
    engine = create_engine(settings.DATABASE_URL)

    # Verify connection
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("[create_tables] Connection OK")

    # Create tables (idempotent — won't drop existing ones)
    Base.metadata.create_all(bind=engine)

    # Confirm table exists
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    if "audit_logs" in tables:
        cols = [c["name"] for c in inspector.get_columns("audit_logs")]
        print(f"[create_tables] audit_logs table created. Columns: {cols}")
    else:
        print("[create_tables] ERROR: audit_logs table not found after create_all")
        sys.exit(1)


if __name__ == "__main__":
    main()
