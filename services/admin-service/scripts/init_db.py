#!/usr/bin/env python3
"""
Initialize database: Create tables and optionally seed data
"""
import sys
import argparse
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infrastructure.database.session import engine, check_db_connection, SessionLocal
from app.infrastructure.database.base import Base
from app.core.config import settings

# Import all models
from app.domain_controls.models.domains import Domain
from app.domain_controls.models.applications import Application
from app.domain_controls.models.menus import Menu


def create_tables():
    """Create all database tables"""
    print("🔨 Creating database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Tables created successfully")
        return True
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return False


def seed_data():
    """Seed initial data"""
    print("🌱 Seeding initial data...")
    
    db = SessionLocal()
    
    try:
        # Check if data already exists
        domain_count = db.query(Domain).count()
        if domain_count > 0:
            print(f"⚠️  Database already contains {domain_count} domain(s)")
            response = input("   Overwrite existing data? (y/n): ")
            if response.lower() != 'y':
                print("   Skipping seed data")
                return True
        
        # Create sample domains
        domains = [
            Domain(
                code="PLATFORM",
                name="Platform Services",
                description="Core platform infrastructure services",
                domain_metadata={"category": "infrastructure", "priority": "critical"},
                is_active=True
            ),
            Domain(
                code="COMMERCE",
                name="Commerce Services",
                description="E-commerce and payment services",
                domain_metadata={"category": "business", "priority": "high"},
                is_active=True
            ),
            Domain(
                code="ANALYTICS",
                name="Analytics Services",
                description="Data analytics and reporting services",
                domain_metadata={"category": "analytics", "priority": "medium"},
                is_active=True
            )
        ]
        
        for domain in domains:
            # Check if domain already exists
            existing = db.query(Domain).filter(Domain.code == domain.code).first()
            if not existing:
                db.add(domain)
                print(f"   ✓ Added domain: {domain.name}")
            else:
                print(f"   ⊘ Domain already exists: {domain.name}")
        
        db.commit()
        
        # Create sample applications
        platform_domain = db.query(Domain).filter(Domain.code == "PLATFORM").first()
        
        if platform_domain:
            applications = [
                Application(
                    domain_id=platform_domain.id,
                    name="Admin Console",
                    description="Platform administration console",
                    version="1.0.0",
                    status="active",
                    key="admin-console",
                    label="Admin",
                    route="/admin",
                    level=1,
                    icon="settings",
                    order_index=1
                ),
                Application(
                    domain_id=platform_domain.id,
                    name="User Management",
                    description="User and access management",
                    version="1.0.0",
                    status="active",
                    key="user-mgmt",
                    label="Users",
                    route="/users",
                    level=1,
                    icon="users",
                    order_index=2
                )
            ]
            
            for app in applications:
                existing = db.query(Application).filter(
                    Application.domain_id == app.domain_id,
                    Application.key == app.key
                ).first()
                if not existing:
                    db.add(app)
                    print(f"   ✓ Added application: {app.name}")
                else:
                    print(f"   ⊘ Application already exists: {app.name}")
            
            db.commit()
        
        print("✅ Seed data added successfully")
        
        # Display summary
        domain_count = db.query(Domain).filter(Domain.is_deleted == False).count()
        app_count = db.query(Application).filter(Application.is_deleted == False).count()
        
        print()
        print("📊 Database Summary:")
        print(f"   Domains: {domain_count}")
        print(f"   Applications: {app_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error seeding data: {e}")
        db.rollback()
        return False
        
    finally:
        db.close()


def drop_tables():
    """Drop all database tables"""
    print("⚠️  WARNING: This will delete all tables and data!")
    response = input("Are you sure? Type 'yes' to confirm: ")
    
    if response.lower() != 'yes':
        print("❌ Operation cancelled")
        return False
    
    print("🗑️  Dropping all tables...")
    try:
        Base.metadata.drop_all(bind=engine)
        print("✅ All tables dropped successfully")
        return True
    except Exception as e:
        print(f"❌ Error dropping tables: {e}")
        return False


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Initialize admin service database")
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Seed initial data after creating tables"
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop all tables before creating (WARNING: destroys all data)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompts"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🗄️  Admin Service - Database Initialization")
    print("=" * 60)
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
    
    # Drop tables if requested
    if args.drop:
        if not drop_tables():
            sys.exit(1)
        print()
    
    # Create tables
    if not create_tables():
        sys.exit(1)
    print()
    
    # Seed data if requested
    if args.seed:
        if not seed_data():
            sys.exit(1)
        print()
    
    print("=" * 60)
    print("🎉 Database initialization completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
