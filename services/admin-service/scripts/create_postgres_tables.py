"""
PostgreSQL Database Table Creation Script
==========================================

This script creates all required tables for the Admin Service in PostgreSQL.
It handles table creation in the correct order based on foreign key dependencies.

Usage:
    python services/admin-service/scripts/create_postgres_tables.py

Environment Variables Required:
    DATABASE_URL - PostgreSQL connection string
    
Example:
    DATABASE_URL=postgresql://postgres:root@localhost:5432/clan_platform

Tables Created (in dependency order):
    1. tenants
    2. domains
    3. entities
    4. departments
    5. divisions
    6. applications
    7. modules
    8. menus
    9. forms
    10. buttons
    11. job_codes
    12. jobcode_basicinfo
    13. jobcode_skills
    14. tenant_modules
    15. tenant_applications
    16. audit_logs
"""

import sys
import os
from pathlib import Path

# Add the service root to Python path
service_root = Path(__file__).parent.parent
sys.path.insert(0, str(service_root))

from sqlalchemy import create_engine, MetaData, inspect, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.infrastructure.database.base import Base

# Import all models to register them with Base.metadata
from app.tenants.models.tenants import Tenant
from app.domains.models.domain import Domain
from app.entities.models.entity import Entity
from app.departments.models.departments import Department
from app.divisions.models.divisions import Division
from app.applications.models.application import Application
from app.modules.models.module import Module
from app.menus.models.menu import Menu
from app.forms.models.forms import Form
from app.job_codes.models.job_codes import (
    JobCode,
    JobCodeBasicInfo,
    JobCodeSkills,
)
from app.tenant_modules.models.tenant_module import TenantModule
from app.tenant_applications.models.tenant_application import TenantApplication


def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_info(text):
    """Print info message"""
    print(f"ℹ️  {text}")


def print_success(text):
    """Print success message"""
    print(f"✅ {text}")


def print_error(text):
    """Print error message"""
    print(f"❌ {text}")


def print_warning(text):
    """Print warning message"""
    print(f"⚠️  {text}")


def check_database_connection(engine):
    """Check if database connection is working"""
    print_info("Testing database connection...")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print_success("Database connection successful")
        return True
    except Exception as e:
        print_error(f"Database connection failed: {e}")
        return False


def get_existing_tables(engine):
    """Get list of existing tables in the database"""
    inspector = inspect(engine)
    return set(inspector.get_table_names())


def get_table_dependency_order():
    """
    Return tables in the order they should be created based on foreign key dependencies.
    Tables with no dependencies come first.
    """
    return [
        'tenants',              # No dependencies
        'domains',              # No dependencies
        'entities',             # Depends on: tenants
        'departments',          # Depends on: tenants, entities, (self-referencing)
        'divisions',            # Depends on: tenants, entities, departments, (self-referencing)
        'applications',         # Depends on: domains
        'modules',              # Depends on: applications
        'menus',                # Depends on: applications, modules, (self-referencing)
        'forms',                # Depends on: menus
        'buttons',              # Depends on: menus
        'job_codes',            # No dependencies
        'jobcode_basicinfo',    # Depends on: job_codes, tenants, entities, departments, divisions
        'jobcode_skills',       # Depends on: job_codes
        'tenant_modules',       # Depends on: tenants, modules
        'tenant_applications',  # Depends on: tenants, applications
        'audit_logs',           # Depends on: tenants, entities (users not in scope)
    ]


def create_tables(engine, drop_existing=False):
    """
    Create all tables in the database.
    
    Args:
        engine: SQLAlchemy engine instance
        drop_existing: If True, drop existing tables before creating new ones
    """
    print_header("PostgreSQL Table Creation")
    
    # Get existing tables
    existing_tables = get_existing_tables(engine)
    table_order = get_table_dependency_order()
    
    if existing_tables:
        print_info(f"Found {len(existing_tables)} existing tables: {', '.join(sorted(existing_tables))}")
        
        if drop_existing:
            print_warning("Dropping existing tables...")
            try:
                Base.metadata.drop_all(bind=engine)
                print_success("All existing tables dropped")
                existing_tables = set()
            except Exception as e:
                print_error(f"Failed to drop tables: {e}")
                return False
    else:
        print_info("No existing tables found")
    
    # Create tables
    print_info("Creating tables in dependency order...")
    
    try:
        # Create all tables at once (SQLAlchemy handles the order)
        Base.metadata.create_all(bind=engine)
        
        # Verify table creation
        new_tables = get_existing_tables(engine)
        created_tables = new_tables - existing_tables
        
        if created_tables:
            print_success(f"Successfully created {len(created_tables)} tables")
            print("\nCreated tables (in dependency order):")
            for table_name in table_order:
                if table_name in created_tables:
                    # Get table object from metadata
                    if table_name in Base.metadata.tables:
                        table = Base.metadata.tables[table_name]
                        column_count = len(table.columns)
                        fk_count = len([fk for fk in table.foreign_keys])
                        print(f"  ✓ {table_name:<25} ({column_count} columns, {fk_count} foreign keys)")
                    else:
                        print(f"  ✓ {table_name}")
        else:
            print_warning("No new tables were created (all tables already exist)")
        
        return True
        
    except Exception as e:
        print_error(f"Failed to create tables: {e}")
        import traceback
        traceback.print_exc()
        return False


def print_table_summary(engine):
    """Print a summary of all tables in the database"""
    print_header("Database Schema Summary")
    
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    if not tables:
        print_warning("No tables found in database")
        return
    
    print(f"\nTotal tables: {len(tables)}\n")
    
    for table_name in sorted(tables):
        columns = inspector.get_columns(table_name)
        foreign_keys = inspector.get_foreign_keys(table_name)
        indexes = inspector.get_indexes(table_name)
        pk = inspector.get_pk_constraint(table_name)
        
        print(f"📊 Table: {table_name}")
        print(f"   ├─ Columns: {len(columns)}")
        print(f"   ├─ Primary Key: {', '.join(pk['constrained_columns']) if pk['constrained_columns'] else 'None'}")
        print(f"   ├─ Foreign Keys: {len(foreign_keys)}")
        print(f"   └─ Indexes: {len(indexes)}")
        
        if foreign_keys:
            for fk in foreign_keys:
                ref_table = fk['referred_table']
                ref_cols = ', '.join(fk['referred_columns'])
                local_cols = ', '.join(fk['constrained_columns'])
                print(f"      └─ FK: {local_cols} → {ref_table}({ref_cols})")
        print()


def main():
    """Main execution function"""
    print_header("Admin Service - PostgreSQL Table Creation Script")
    
    # Print configuration
    print("\n📝 Configuration:")
    print(f"   Database URL: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'N/A'}")
    print(f"   Environment: {settings.ENVIRONMENT}")
    print(f"   Debug Mode: {settings.DEBUG}")
    
    # Create engine
    try:
        engine = create_engine(
            settings.DATABASE_URL,
            echo=settings.DEBUG,
            pool_pre_ping=True
        )
        print_success("Database engine created")
    except Exception as e:
        print_error(f"Failed to create database engine: {e}")
        return 1
    
    # Check connection
    if not check_database_connection(engine):
        return 1
    
    # Ask for confirmation
    print("\n" + "-" * 70)
    response = input("\n🔧 Do you want to create the tables? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y']:
        print_info("Operation cancelled")
        return 0
    
    # Ask if should drop existing tables
    drop_existing = False
    existing_tables = get_existing_tables(engine)
    if existing_tables:
        response = input("\n⚠️  Drop existing tables first? (yes/no): ").strip().lower()
        drop_existing = response in ['yes', 'y']
    
    # Create tables
    success = create_tables(engine, drop_existing=drop_existing)
    
    if not success:
        return 1
    
    # Print summary
    print_table_summary(engine)
    
    print_header("✨ Table Creation Complete")
    print("\n💡 Next Steps:")
    print("   1. Verify table structure using a database client")
    print("   2. Run data migrations if needed")
    print("   3. Seed initial data if required")
    print("\n📖 Connection Info:")
    print("   Host: localhost")
    print("   Port: 5432")
    print("   Database: clan_platform")
    print("   Username: postgres")
    print("   Password: root")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
