"""
MongoDB Migration: Add Profile Menu Items with Routes (Synchronous Version)
===========================================================================

This script updates the profileSection in the MongoDB navigation document
to include default menu items with route fields using synchronous MongoDB client.

Usage:
    python services/admin-service/scripts/migrations/update_profile_menu_items_sync.py

This will:
- Connect to MongoDB (synchronous)
- Find the master navigation document
- Add default menu items to profileSection if not already present
- Each menu item includes: key, route, label, icon, children
"""

import sys
import os
from pathlib import Path
import argparse

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Set environment variables before importing app modules
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:root@localhost:5432/clan_platform')
os.environ.setdefault('REDIS_URL', 'redis://localhost:6379/0')
os.environ.setdefault('MONGODB_URL', 'mongodb://admin:admin_pass@localhost:27017')
os.environ.setdefault('MONGODB_DB_NAME', 'clan_platform')
os.environ.setdefault('SECRET_KEY', 'local-dev-secret-key-for-script-execution-only')
os.environ.setdefault('ENVIRONMENT', 'local')

from bson import ObjectId
from pymongo import MongoClient
from app.core.config import settings


# Default profile menu items with routes
DEFAULT_PROFILE_MENU_ITEMS = [
  {
    "type": "item",
    "key": "profile",
    "route": "/profile",
    "label": "Profile",
    "icon": "ri-user-line",
    "children": []
  },
  {
    "type": "item",
    "key": "upgrade",
    "route": "/upgrade",
    "label": "Upgrade to Pro",
    "icon": "ri-star-line",
    "badge": {
      "count": "NEW",
      "color": "gold"
    },
    "children": []
  },
  {
    "type": "divider",
    "key": "profile-divider",
    "route": "/divider",
  },
  {
    "type": "item",
    "key": "logout",
    "route": "/logout",
    "label": "Logout",
    "icon": "ri-logout-box-line",
    "children": []
  }
]


def update_profile_menu_items(skip_confirmation=False):
    """
    Update the profileSection in MongoDB navigation document with menu items
    
    Args:
        skip_confirmation: If True, skip the confirmation prompt
    """
    print("\n" + "="*70)
    print("MongoDB Migration: Add Profile Menu Items with Routes")
    print("="*70 + "\n")
    
    client = None
    
    try:
        # Connect to MongoDB
        print("📡 Connecting to MongoDB...")
        print(f"   URL: {settings.MONGODB_URL}")
        print(f"   Database: {settings.MONGODB_DB_NAME}")
        
        client = MongoClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=5000
        )
        
        # Test connection
        client.server_info()
        print("✅ Connected to MongoDB successfully\n")
        
        # Get database
        db = client[settings.MONGODB_DB_NAME]
        
        # Known master navigation document ID
        master_doc_id = ObjectId("69074724f217ab8fcb2e3b24")
        
        print(f"🔍 Looking for master navigation document: {master_doc_id}")
        
        # Find the master document
        master_doc = db.menu_details.find_one({"_id": master_doc_id})
        
        if not master_doc:
            print(f"❌ Master navigation document not found with ID: {master_doc_id}")
            print("   Please verify the document ID exists in your MongoDB database.")
            return False
        
        print(f"✅ Found master navigation document\n")
        
        # Check current profileSection
        profile_section = master_doc.get("profileSection", {})
        current_menu_items = profile_section.get("menuItems", [])
        
        print(f"📊 Current profileSection status:")
        print(f"   - Has profileSection: {bool(profile_section)}")
        print(f"   - Current menuItems count: {len(current_menu_items)}")
        
        if current_menu_items:
            print(f"   - Existing menu items:")
            for idx, item in enumerate(current_menu_items, 1):
                print(f"     {idx}. {item.get('label', 'Unknown')} (key: {item.get('key', 'N/A')}, route: {item.get('route', 'N/A')})")
        
        # Ask for confirmation
        print("\n" + "="*70)
        
        if skip_confirmation:
            print("\n✅ Auto-confirmation enabled, proceeding with update...")
            response = 'yes'
        else:
            response = input("\n⚠️  Do you want to update profileSection with default menu items? (yes/no): ").strip().lower()
        
        if response not in ['yes', 'y']:
            print("❌ Migration cancelled by user")
            return False
        
        # Prepare the update
        if not profile_section:
            # Create new profileSection
            profile_section = {
                "type": "profile",
                "key": "profile-section",
                "userData": {
                    "name": "Default User",
                    "email": "user@example.com",
                    "avatar": "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=32&h=32&fit=crop",
                    "role": "User",
                    "status": "online"
                },
                "menuItems": DEFAULT_PROFILE_MENU_ITEMS
            }
        else:
            # Update existing profileSection
            profile_section["menuItems"] = DEFAULT_PROFILE_MENU_ITEMS
        
        print("\n🔄 Updating MongoDB document...")
        
        # Update the document
        result = db.menu_details.update_one(
            {"_id": master_doc_id},
            {"$set": {"profileSection": profile_section}}
        )
        
        if result.modified_count > 0:
            print("✅ Successfully updated profileSection with menu items!")
            print(f"\n📋 Added {len(DEFAULT_PROFILE_MENU_ITEMS)} menu items:")
            for idx, item in enumerate(DEFAULT_PROFILE_MENU_ITEMS, 1):
                print(f"   {idx}. {item['label']}")
                print(f"      - Key: {item['key']}")
                print(f"      - Route: {item['route']}")
                print(f"      - Icon: {item['icon']}")
        else:
            print("⚠️  No changes were made (document may already have the same data)")
        
        # Verify the update
        print("\n🔍 Verifying update...")
        updated_doc = db.menu_details.find_one({"_id": master_doc_id})
        updated_profile_section = updated_doc.get("profileSection", {})
        updated_menu_items = updated_profile_section.get("menuItems", [])
        
        print(f"✅ Verification complete:")
        print(f"   - Updated menuItems count: {len(updated_menu_items)}")
        
        print("\n" + "="*70)
        print("✅ Migration completed successfully!")
        print("="*70 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error during migration: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        if client:
            client.close()
            print("🔌 Disconnected from MongoDB")


def main():
    """Main entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Update MongoDB profileSection with menu items')
    parser.add_argument('--yes', '-y', action='store_true', 
                       help='Skip confirmation prompt and proceed automatically')
    args = parser.parse_args()
    
    success = update_profile_menu_items(skip_confirmation=args.yes)
    
    if success:
        print("\n✅ All done! The profileSection now has default menu items with routes.")
        print("   You can verify this by calling the /api/v1/menus endpoint.")
    else:
        print("\n❌ Migration failed. Please check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
