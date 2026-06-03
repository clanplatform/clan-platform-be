#!/usr/bin/env python3
"""
Drop all database tables (USE WITH CAUTION!)
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infrastructure.database.session import engine, check_db_connection
from app.infrastructure.database.base import Base
from app.core.config import settings

# Import all models
from app.domain_controls.models.domains import Domain
from app.domain_controls.models.applications import Application
from app.domain_controls.models.menus import Menu


def main():
    """Drop all database tables"""
    print("=" * 60)
    print("⚠️  WARNING: DROP ALL TABLES")
    print("=" * 60)
    print(f"📍 Database: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'N/A'}")
    print()
    print("⚠️  This will permanently delete ALL tables and data!")
    print()
    
    # Check database connection
    print("🔍 Checking database connection...")
    if not check_db_connection():
        print("❌ Database connection failed")
        sys.exit(1)
    
    print("✅ Database connection successful")
    print()
    
    # List tables to be dropped
    print("📋 Tables to be dropped:")
    for table_name in Base.metadata.tables.keys():
        print(f"   - {table_name}")
    print()
    
    # Confirmation
    print("⚠️  Type 'DROP ALL TABLES' to confirm:")
    response = input(">> ")
    
    if response != "DROP ALL TABLES":
        print("❌ Operation cancelled")
        sys.exit(0)
    
    # Drop tables
    try:
        print()
        print("🗑️  Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        print("✅ All tables dropped successfully")
        print()
        print("🎯 Database is now empty")
        
    except Exception as e:
        print(f"❌ Error dropping tables: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
