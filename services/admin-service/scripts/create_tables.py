#!/usr/bin/env python3
"""
Create all database tables using SQLAlchemy models
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infrastructure.database.session import engine, create_tables, check_db_connection
from app.infrastructure.database.base import Base
from app.core.config import settings

# Import all models to register them with Base
from app.domain_controls.models.domains import Domain
from app.domain_controls.models.applications import Application
from app.domain_controls.models.menus import Menu


def main():
    """Create all database tables"""
    print("🚀 Starting table creation using SQLAlchemy...")
    print(f"📍 Database: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'N/A'}")
    print()
    
    # Check database connection
    print("🔍 Checking database connection...")
    if not check_db_connection():
        print("❌ Database connection failed")
        print("   Please check your DATABASE_URL configuration")
        sys.exit(1)
    
    print("✅ Database connection successful")
    print()
    
    # Display registered models
    print("📋 Registered models:")
    for table_name in Base.metadata.tables.keys():
        print(f"   - {table_name}")
    print()
    
    # Create tables
    try:
        print("🔨 Creating tables...")
        create_tables()
        print("✅ All tables created successfully")
        print()
        
        # Display created tables
        print("📊 Tables in database:")
        from sqlalchemy import inspect
        inspector = inspect(engine)
        for table_name in inspector.get_table_names():
            print(f"   ✓ {table_name}")
        
        print()
        print("🎉 Table creation completed successfully!")
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
