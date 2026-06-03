#!/usr/bin/env python3
"""
Seed database with sample data
"""
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.infrastructure.database.session import SessionLocal, check_db_connection
from app.core.config import settings

# Import models
from app.domain_controls.models.domains import Domain
from app.domain_controls.models.applications import Application
from app.domain_controls.models.menus import Menu


def seed_domains(db, force=False):
    """Seed domain data"""
    print("🌱 Seeding domains...")
    
    domains_data = [
        {
            "code": "PLATFORM",
            "name": "Platform Services",
            "description": "Core platform infrastructure services",
            "domain_metadata": {"category": "infrastructure", "priority": "critical"}
        },
        {
            "code": "COMMERCE",
            "name": "Commerce Services",
            "description": "E-commerce and payment services",
            "domain_metadata": {"category": "business", "priority": "high"}
        },
        {
            "code": "ANALYTICS",
            "name": "Analytics Services",
            "description": "Data analytics and reporting services",
            "domain_metadata": {"category": "analytics", "priority": "medium"}
        },
        {
            "code": "IDENTITY",
            "name": "Identity Services",
            "description": "Authentication and authorization services",
            "domain_metadata": {"category": "security", "priority": "critical"}
        }
    ]
    
    created_count = 0
    existing_count = 0
    
    for domain_data in domains_data:
        existing = db.query(Domain).filter(Domain.code == domain_data["code"]).first()
        
        if existing:
            existing_count += 1
            print(f"   ⊘ Domain already exists: {domain_data['name']}")
            if force:
                existing.name = domain_data["name"]
                existing.description = domain_data["description"]
                existing.domain_metadata = domain_data["domain_metadata"]
                print(f"   ↻ Updated domain: {domain_data['name']}")
        else:
            domain = Domain(**domain_data)
            db.add(domain)
            created_count += 1
            print(f"   ✓ Created domain: {domain_data['name']}")
    
    db.commit()
    print(f"✅ Domains: {created_count} created, {existing_count} existing")
    return created_count


def seed_applications(db, force=False):
    """Seed application data"""
    print("\n🌱 Seeding applications...")
    
    # Get domains
    platform_domain = db.query(Domain).filter(Domain.code == "PLATFORM").first()
    commerce_domain = db.query(Domain).filter(Domain.code == "COMMERCE").first()
    analytics_domain = db.query(Domain).filter(Domain.code == "ANALYTICS").first()
    
    if not all([platform_domain, commerce_domain, analytics_domain]):
        print("   ⚠️  Required domains not found. Run domain seed first.")
        return 0
    
    applications_data = [
        # Platform applications
        {
            "domain_id": platform_domain.id,
            "name": "Admin Console",
            "description": "Platform administration console",
            "key": "admin-console",
            "label": "Admin",
            "route": "/admin",
            "icon": "settings",
            "level": 1,
            "order_index": 1
        },
        {
            "domain_id": platform_domain.id,
            "name": "User Management",
            "description": "User and access management",
            "key": "user-mgmt",
            "label": "Users",
            "route": "/users",
            "icon": "users",
            "level": 1,
            "order_index": 2
        },
        {
            "domain_id": platform_domain.id,
            "name": "System Settings",
            "description": "System configuration and settings",
            "key": "settings",
            "label": "Settings",
            "route": "/settings",
            "icon": "cog",
            "level": 1,
            "order_index": 3
        },
        # Commerce applications
        {
            "domain_id": commerce_domain.id,
            "name": "Product Catalog",
            "description": "Product and inventory management",
            "key": "products",
            "label": "Products",
            "route": "/products",
            "icon": "shopping-cart",
            "level": 1,
            "order_index": 1
        },
        {
            "domain_id": commerce_domain.id,
            "name": "Order Management",
            "description": "Order processing and fulfillment",
            "key": "orders",
            "label": "Orders",
            "route": "/orders",
            "icon": "package",
            "level": 1,
            "order_index": 2
        },
        {
            "domain_id": commerce_domain.id,
            "name": "Payment Gateway",
            "description": "Payment processing and transactions",
            "key": "payments",
            "label": "Payments",
            "route": "/payments",
            "icon": "credit-card",
            "level": 1,
            "order_index": 3
        },
        # Analytics applications
        {
            "domain_id": analytics_domain.id,
            "name": "Reports",
            "description": "Business intelligence and reports",
            "key": "reports",
            "label": "Reports",
            "route": "/reports",
            "icon": "bar-chart",
            "level": 1,
            "order_index": 1
        },
        {
            "domain_id": analytics_domain.id,
            "name": "Dashboards",
            "description": "Real-time dashboards and metrics",
            "key": "dashboards",
            "label": "Dashboards",
            "route": "/dashboards",
            "icon": "pie-chart",
            "level": 1,
            "order_index": 2
        }
    ]
    
    created_count = 0
    existing_count = 0
    
    for app_data in applications_data:
        existing = db.query(Application).filter(
            Application.domain_id == app_data["domain_id"],
            Application.key == app_data["key"]
        ).first()
        
        if existing:
            existing_count += 1
            print(f"   ⊘ Application already exists: {app_data['name']}")
            if force:
                for key, value in app_data.items():
                    setattr(existing, key, value)
                print(f"   ↻ Updated application: {app_data['name']}")
        else:
            application = Application(**app_data)
            db.add(application)
            created_count += 1
            print(f"   ✓ Created application: {app_data['name']}")
    
    db.commit()
    print(f"✅ Applications: {created_count} created, {existing_count} existing")
    return created_count


def seed_menus(db, force=False):
    """Seed menu data"""
    print("\n🌱 Seeding menus...")
    
    # Get applications
    admin_app = db.query(Application).filter(Application.key == "admin-console").first()
    user_app = db.query(Application).filter(Application.key == "user-mgmt").first()
    products_app = db.query(Application).filter(Application.key == "products").first()
    
    if not all([admin_app, user_app, products_app]):
        print("   ⚠️  Required applications not found. Run application seed first.")
        return 0
    
    menus_data = [
        # Admin Console menus
        {
            "application_id": admin_app.id,
            "parent_menu_id": None,
            "name": "Dashboard",
            "key": "dashboard",
            "label": "Dashboard",
            "route": "/admin/dashboard",
            "icon": "home",
            "level": 1,
            "order_index": 1
        },
        {
            "application_id": admin_app.id,
            "parent_menu_id": None,
            "name": "Configuration",
            "key": "config",
            "label": "Configuration",
            "route": "/admin/config",
            "icon": "settings",
            "level": 1,
            "order_index": 2
        },
        # User Management menus
        {
            "application_id": user_app.id,
            "parent_menu_id": None,
            "name": "Users",
            "key": "users-list",
            "label": "All Users",
            "route": "/users/list",
            "icon": "users",
            "level": 1,
            "order_index": 1
        },
        {
            "application_id": user_app.id,
            "parent_menu_id": None,
            "name": "Roles",
            "key": "roles",
            "label": "Roles & Permissions",
            "route": "/users/roles",
            "icon": "shield",
            "level": 1,
            "order_index": 2
        },
        # Products menus
        {
            "application_id": products_app.id,
            "parent_menu_id": None,
            "name": "Products",
            "key": "products-list",
            "label": "All Products",
            "route": "/products/list",
            "icon": "box",
            "level": 1,
            "order_index": 1
        },
        {
            "application_id": products_app.id,
            "parent_menu_id": None,
            "name": "Categories",
            "key": "categories",
            "label": "Categories",
            "route": "/products/categories",
            "icon": "folder",
            "level": 1,
            "order_index": 2
        }
    ]
    
    created_count = 0
    existing_count = 0
    
    for menu_data in menus_data:
        existing = db.query(Menu).filter(
            Menu.application_id == menu_data["application_id"],
            Menu.key == menu_data["key"]
        ).first()
        
        if existing:
            existing_count += 1
            print(f"   ⊘ Menu already exists: {menu_data['name']}")
            if force:
                for key, value in menu_data.items():
                    setattr(existing, key, value)
                print(f"   ↻ Updated menu: {menu_data['name']}")
        else:
            menu = Menu(**menu_data)
            db.add(menu)
            created_count += 1
            print(f"   ✓ Created menu: {menu_data['name']}")
    
    db.commit()
    print(f"✅ Menus: {created_count} created, {existing_count} existing")
    return created_count


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Seed admin service database")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Update existing records with new data"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🌱 Admin Service - Database Seeding")
    print("=" * 60)
    print(f"📍 Database: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'N/A'}")
    print()
    
    # Check database connection
    print("🔍 Checking database connection...")
    if not check_db_connection():
        print("❌ Database connection failed")
        sys.exit(1)
    
    print("✅ Database connection successful")
    print()
    
    # Create session
    db = SessionLocal()
    
    try:
        # Seed data
        domains_created = seed_domains(db, force=args.force)
        apps_created = seed_applications(db, force=args.force)
        menus_created = seed_menus(db, force=args.force)
        
        # Display summary
        print()
        print("=" * 60)
        print("📊 Seeding Summary:")
        print(f"   Domains created: {domains_created}")
        print(f"   Applications created: {apps_created}")
        print(f"   Menus created: {menus_created}")
        print()
        
        # Display totals
        domain_count = db.query(Domain).filter(Domain.is_deleted == False).count()
        app_count = db.query(Application).filter(Application.is_deleted == False).count()
        menu_count = db.query(Menu).filter(Menu.deleted_at == None).count()
        
        print("📈 Database Totals:")
        print(f"   Total domains: {domain_count}")
        print(f"   Total applications: {app_count}")
        print(f"   Total menus: {menu_count}")
        print("=" * 60)
        print("🎉 Seeding completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error seeding data: {e}")
        db.rollback()
        sys.exit(1)
        
    finally:
        db.close()


if __name__ == "__main__":
    main()
