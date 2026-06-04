"""
Run SQL Migration Script
========================

This script executes the create_tables_manual.sql file against PostgreSQL.

Usage:
    python services/admin-service/scripts/run_sql_migration.py
"""

import os
import psycopg2
from pathlib import Path

# Database connection parameters
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'admin_service',
    'user': 'postgres',
    'password': 'root'
}

def main():
    print("=" * 70)
    print("  PostgreSQL Table Creation - SQL Migration")
    print("=" * 70)
    
    # Read SQL file
    sql_file = Path(__file__).parent / 'create_tables_manual.sql'
    
    if not sql_file.exists():
        print(f"❌ SQL file not found: {sql_file}")
        return 1
    
    print(f"\n📄 Reading SQL file: {sql_file.name}")
    
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    print(f"✅ SQL file loaded ({len(sql_content)} characters)")
    
    # Connect to database
    print(f"\n🔌 Connecting to PostgreSQL...")
    print(f"   Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"   Database: {DB_CONFIG['database']}")
    print(f"   User: {DB_CONFIG['user']}")
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()
        print("✅ Connected successfully")
        
        # Execute SQL
        print("\n🔨 Executing SQL migration...")
        cursor.execute(sql_content)
        
        # Get table count
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """)
        table_count = cursor.fetchone()[0]
        
        print(f"✅ Migration completed successfully")
        print(f"\n📊 Total tables in database: {table_count}")
        
        # List all tables
        cursor.execute("""
            SELECT 
                table_name,
                (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) AS column_count
            FROM information_schema.tables t
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        
        tables = cursor.fetchall()
        print("\n📋 Created Tables:")
        for table_name, col_count in tables:
            print(f"   ✓ {table_name:<30} ({col_count} columns)")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 70)
        print("  ✅ Migration Complete!")
        print("=" * 70)
        
        return 0
        
    except psycopg2.Error as e:
        print(f"\n❌ Database error: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
