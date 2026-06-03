#!/usr/bin/env python3
"""
Run SQL migrations in order
"""
import os
import sys
import psycopg2
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings


def get_db_connection():
    """Get database connection from DATABASE_URL"""
    try:
        conn = psycopg2.connect(settings.DATABASE_URL)
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        sys.exit(1)


def run_sql_file(cursor, filepath: Path):
    """Execute a SQL file"""
    try:
        print(f"📄 Executing {filepath.name}...")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # Execute the SQL file
        cursor.execute(sql_content)
        
        print(f"✅ {filepath.name} executed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error executing {filepath.name}: {e}")
        return False


def get_migration_files(sql_dir: Path):
    """Get all SQL migration files in order, excluding rollback"""
    files = []
    for file in sorted(sql_dir.glob("*.sql")):
        # Skip rollback file
        if "999_rollback" in file.name:
            continue
        files.append(file)
    return files


def main():
    """Run all migrations"""
    print("🚀 Starting database migrations...")
    print(f"📍 Database: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'N/A'}")
    print()
    
    # Get SQL files directory
    script_dir = Path(__file__).parent
    sql_dir = script_dir.parent / "sql-files"
    
    if not sql_dir.exists():
        print(f"❌ SQL directory not found: {sql_dir}")
        sys.exit(1)
    
    # Get migration files
    migration_files = get_migration_files(sql_dir)
    
    if not migration_files:
        print("❌ No migration files found")
        sys.exit(1)
    
    print(f"📋 Found {len(migration_files)} migration file(s):")
    for file in migration_files:
        print(f"   - {file.name}")
    print()
    
    # Connect to database
    conn = get_db_connection()
    conn.autocommit = False  # Use transactions
    cursor = conn.cursor()
    
    success_count = 0
    failed_count = 0
    
    try:
        # Run each migration
        for filepath in migration_files:
            if run_sql_file(cursor, filepath):
                success_count += 1
                conn.commit()
                print()
            else:
                failed_count += 1
                conn.rollback()
                print(f"⚠️  Rolling back transaction for {filepath.name}")
                print()
                
                # Ask if we should continue
                response = input("❓ Continue with remaining migrations? (y/n): ")
                if response.lower() != 'y':
                    print("🛑 Migration process stopped")
                    break
        
        # Summary
        print("=" * 60)
        print("📊 Migration Summary:")
        print(f"   ✅ Successful: {success_count}")
        print(f"   ❌ Failed: {failed_count}")
        print(f"   📝 Total: {len(migration_files)}")
        print("=" * 60)
        
        if failed_count == 0:
            print("🎉 All migrations completed successfully!")
        else:
            print(f"⚠️  {failed_count} migration(s) failed")
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Migration interrupted by user")
        conn.rollback()
        
    finally:
        cursor.close()
        conn.close()
        print("\n👋 Database connection closed")


if __name__ == "__main__":
    main()
