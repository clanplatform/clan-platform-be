"""
Simple Database Initialization Script
=====================================

This script initializes all PostgreSQL tables using the existing
infrastructure from the application.

Usage:
    python services/admin-service/scripts/init_database.py

This will:
- Create all tables if they don't exist
- Skip tables that already exist
- Show a summary of the database schema
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set environment variables before importing app modules
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:root@localhost:5432/admin_service')
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/0')
os.environ.setdefault('MONGODB_URL', 'mongodb://admin:admin_pass@localhost:27017')
os.environ.setdefault('MONGODB_DB_NAME', 'admin_service')
os.environ.setdefault('SECRET_KEY', 'local-dev-secret-key-for-script-execution-only')
os.environ.setdefault('ENVIRONMENT', 'local')

from app.infrastructure.database.session import engine, create_tables
from app.infrastructure.database.base import Base
from sqlalchemy import inspect, text

# Import all models
from app.clients.models.clients import Client
from app.domains.models.domain import Domain
from app.entities.models.entity import Entity
from app.departments.models.departments import Department, AuditLog
from app.divisions.models.divisions import Division
from app.applications.models.application import Application
from app.modules.models.module import Module
from app.menus.models.menu import Menu
from app.forms.models.forms import Form

# Import job code models (folder name uses hyphen)
import importlib
job_codes_models = importlib.import_module('app.job-codes.models.job_codes')
JobCode = job_codes_models.JobCode
JobCodeBasicInfo = job_codes_models.JobCodeBasicInfo
JobCodeSkills = job_codes_models.JobCodeSkills
JobCodeBenefits = job_codes_models.JobCodeBenefits


def check_connection():
    """Test database connection"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print(f"✅ Connected to PostgreSQL: {version.split(',')[0]}")
            return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


def get_table_info():
    """Get information about existing tables"""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    return tables


def main():
    print("=" * 70)
    print("  PostgreSQL Database Initialization")
    print("=" * 70)
    
    # Check connection
    if not check_connection():
        return 1
    
    # Get existing tables
    existing_tables = get_table_info()
    print(f"\n📊 Found {len(existing_tables)} existing tables")
    if existing_tables:
        for table in sorted(existing_tables):
            print(f"   • {table}")
    
    # Create tables
    print("\n🔨 Creating tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Table creation completed")
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return 1
    
    # Get updated table list
    new_tables = get_table_info()
    created_count = len(set(new_tables) - set(existing_tables))
    
    print(f"\n📈 Database now has {len(new_tables)} tables")
    if created_count > 0:
        print(f"   ✨ {created_count} new tables created")
    
    # Show all tables with details
    print("\n" + "=" * 70)
    print("  Table Summary")
    print("=" * 70)
    
    inspector = inspect(engine)
    for table_name in sorted(new_tables):
        columns = inspector.get_columns(table_name)
        fks = inspector.get_foreign_keys(table_name)
        pk = inspector.get_pk_constraint(table_name)
        
        print(f"\n📋 {table_name}")
        print(f"   Columns: {len(columns)}")
        print(f"   Primary Key: {', '.join(pk['constrained_columns'])}")
        if fks:
            print(f"   Foreign Keys: {len(fks)}")
            for fk in fks:
                local = ', '.join(fk['constrained_columns'])
                ref = fk['referred_table']
                ref_cols = ', '.join(fk['referred_columns'])
                print(f"      → {local} → {ref}({ref_cols})")
    
    print("\n" + "=" * 70)
    print("  ✅ Database initialization complete!")
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
