"""
Manual User Sync Utility
Syncs existing users from admin-service usersetup_basic to auth-service auth_users table.

This is useful for:
1. Initial sync of existing users after implementing the sync feature
2. Re-syncing users that failed to sync during creation
3. Recovering from auth-service database failures

Usage:
    # Sync all users
    python scripts/sync_existing_users.py --all
    
    # Sync specific users by ID
    python scripts/sync_existing_users.py --user-ids uuid1,uuid2,uuid3
    
    # Sync users by status
    python scripts/sync_existing_users.py --status active
    
    # Dry run (show what would be synced without actually syncing)
    python scripts/sync_existing_users.py --all --dry-run
"""
import sys
import os
import asyncio
import argparse
from typing import List, Optional
from uuid import UUID

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.infrastructure.database.session import SessionLocal
from app.user_setup.models.user_setup import UserSetupBasic
from app.user_setup.services.auth_service_sync import AuthServiceSync, AuthServiceSyncError


class UserSyncUtility:
    """Utility for manually syncing users to auth-service"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.success_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        self.failed_users = []
    
    async def sync_user(self, db: Session, user: UserSetupBasic) -> bool:
        """Sync a single user to auth-service"""
        print(f"\n{'[DRY RUN] ' if self.dry_run else ''}Syncing user: {user.username} (ID: {user.id})")
        print(f"  Email: {user.email}")
        print(f"  Name: {user.firstname} {user.lastname}")
        print(f"  Status: {user.status}")
        
        if self.dry_run:
            print("  ✅ Would sync this user (dry run mode)")
            self.success_count += 1
            return True
        
        try:
            result = await AuthServiceSync.create_auth_user(
                user_id=user.id,
                username=user.username,
                email=user.email,
                password_hash=user.password_hash,
                firstname=user.firstname,
                lastname=user.lastname,
                phone_number=user.phone_number,
                is_active=(user.status == 'active'),
                employee_id=user.employee_id
            )
            
            if result.get('status') == 'already_exists':
                print(f"  ⚠️  User already exists in auth-service")
                self.skipped_count += 1
                return True
            else:
                print(f"  ✅ Successfully synced to auth-service")
                self.success_count += 1
                return True
                
        except AuthServiceSyncError as e:
            print(f"  ❌ Sync failed: {str(e)}")
            self.failed_count += 1
            self.failed_users.append({
                'id': user.id,
                'username': user.username,
                'error': str(e)
            })
            return False
        except Exception as e:
            print(f"  ❌ Unexpected error: {str(e)}")
            self.failed_count += 1
            self.failed_users.append({
                'id': user.id,
                'username': user.username,
                'error': str(e)
            })
            return False
    
    async def sync_all_users(self, status_filter: Optional[str] = None):
        """Sync all users from admin-service to auth-service"""
        db = SessionLocal()
        try:
            # Build query
            query = db.query(UserSetupBasic)
            if status_filter:
                query = query.filter(UserSetupBasic.status == status_filter)
            
            users = query.all()
            total_users = len(users)
            
            print(f"\n{'='*80}")
            print(f"{'DRY RUN MODE - ' if self.dry_run else ''}SYNCING {total_users} USERS")
            if status_filter:
                print(f"Status filter: {status_filter}")
            print(f"{'='*80}")
            
            if not AuthServiceSync.sync_enabled():
                print("\n❌ ERROR: Auth sync is not enabled")
                print("   Please set IDENTITY_SERVICE_URL in your .env file")
                return
            
            # Sync each user
            for i, user in enumerate(users, 1):
                print(f"\n[{i}/{total_users}]", end=" ")
                await self.sync_user(db, user)
                
                # Small delay to avoid overwhelming the auth-service
                if not self.dry_run:
                    await asyncio.sleep(0.1)
            
            # Print summary
            self.print_summary()
            
        finally:
            db.close()
    
    async def sync_specific_users(self, user_ids: List[UUID]):
        """Sync specific users by their IDs"""
        db = SessionLocal()
        try:
            print(f"\n{'='*80}")
            print(f"{'DRY RUN MODE - ' if self.dry_run else ''}SYNCING {len(user_ids)} SPECIFIC USERS")
            print(f"{'='*80}")
            
            if not AuthServiceSync.sync_enabled():
                print("\n❌ ERROR: Auth sync is not enabled")
                print("   Please set IDENTITY_SERVICE_URL in your .env file")
                return
            
            for i, user_id in enumerate(user_ids, 1):
                print(f"\n[{i}/{len(user_ids)}]", end=" ")
                user = db.query(UserSetupBasic).filter(UserSetupBasic.id == user_id).first()
                
                if not user:
                    print(f"❌ User with ID {user_id} not found in admin-service")
                    self.failed_count += 1
                    continue
                
                await self.sync_user(db, user)
                
                # Small delay to avoid overwhelming the auth-service
                if not self.dry_run:
                    await asyncio.sleep(0.1)
            
            # Print summary
            self.print_summary()
            
        finally:
            db.close()
    
    def print_summary(self):
        """Print sync summary"""
        print(f"\n{'='*80}")
        print("SYNC SUMMARY")
        print(f"{'='*80}")
        print(f"✅ Successfully synced: {self.success_count}")
        print(f"⚠️  Already existed: {self.skipped_count}")
        print(f"❌ Failed: {self.failed_count}")
        print(f"{'='*80}")
        
        if self.failed_users:
            print("\nFailed Users:")
            for user in self.failed_users:
                print(f"  • {user['username']} (ID: {user['id']})")
                print(f"    Error: {user['error']}")


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Sync users from admin-service to auth-service',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Sync all users
  python scripts/sync_existing_users.py --all
  
  # Sync only active users
  python scripts/sync_existing_users.py --all --status active
  
  # Sync specific users
  python scripts/sync_existing_users.py --user-ids "uuid1,uuid2,uuid3"
  
  # Dry run to see what would be synced
  python scripts/sync_existing_users.py --all --dry-run
        """
    )
    
    parser.add_argument('--all', action='store_true', help='Sync all users')
    parser.add_argument('--user-ids', type=str, help='Comma-separated list of user IDs to sync')
    parser.add_argument('--status', type=str, choices=['active', 'inactive', 'suspended'], 
                       help='Filter users by status (only with --all)')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be synced without actually syncing')
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.all and not args.user_ids:
        parser.error('Either --all or --user-ids must be specified')
    
    if args.status and not args.all:
        parser.error('--status can only be used with --all')
    
    # Create utility
    utility = UserSyncUtility(dry_run=args.dry_run)
    
    # Run sync
    if args.all:
        await utility.sync_all_users(status_filter=args.status)
    elif args.user_ids:
        try:
            user_ids = [UUID(uid.strip()) for uid in args.user_ids.split(',')]
            await utility.sync_specific_users(user_ids)
        except ValueError as e:
            print(f"❌ Invalid user ID format: {str(e)}")
            print("   User IDs must be valid UUIDs")
            sys.exit(1)


if __name__ == "__main__":
    print("\n🚀 Manual User Sync Utility\n")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Sync interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
