# SQL Migration Files

PostgreSQL migration scripts for the Admin Service database schema.

## Migration Files

### Initialization
- **000_init_database.sql** - Initialize database, enable extensions

### Core Tables
- **001_create_domains_table.sql** - Create domains table with indexes and triggers
- **002_create_applications_table.sql** - Create applications table with foreign keys
- **003_create_menus_table.sql** - Create menus table with self-referencing hierarchy

### Seed Data
- **004_seed_initial_data.sql** - Insert sample data for development/testing

### Rollback
- **999_rollback_all.sql** - Drop all tables (USE WITH CAUTION!)

## Running Migrations

### Using psql

```bash
# Run all migrations in order
psql -U admin_user -d admin_db -f sql-files/000_init_database.sql
psql -U admin_user -d admin_db -f sql-files/001_create_domains_table.sql
psql -U admin_user -d admin_db -f sql-files/002_create_applications_table.sql
psql -U admin_user -d admin_db -f sql-files/003_create_menus_table.sql
psql -U admin_user -d admin_db -f sql-files/004_seed_initial_data.sql

# Or run all at once
for file in sql-files/*.sql; do
  if [[ "$file" != *"999_rollback"* ]]; then
    echo "Executing $file..."
    psql -U admin_user -d admin_db -f "$file"
  fi
done
```

### Using Python Script

```bash
python scripts/run_migrations.py
```

### Using Docker

```bash
# Copy SQL files to container
docker cp sql-files/ admin-service-postgres:/tmp/

# Execute migrations
docker exec -it admin-service-postgres psql -U admin_user -d admin_db -f /tmp/sql-files/000_init_database.sql
# ... repeat for each file
```

## Migration Order

**IMPORTANT**: Migrations must be run in numerical order due to foreign key dependencies:

1. 000 - Initialize database
2. 001 - Create domains (no dependencies)
3. 002 - Create applications (depends on domains)
4. 003 - Create menus (depends on applications)
5. 004 - Seed data (optional, for development)

## Rollback

To rollback all changes:

```bash
psql -U admin_user -d admin_db -f sql-files/999_rollback_all.sql
```

⚠️ **WARNING**: This will delete ALL data!

## Table Relationships

```
domains
  ├─> applications (domain_id)
      ├─> menus (application_id)
          └─> menus (parent_menu_id) [self-referencing]
```

## Indexes

### Domains
- `idx_domains_code` - Unique code lookup
- `idx_domains_name` - Unique name lookup
- `idx_domains_is_active` - Filter active domains
- `idx_domains_is_deleted` - Filter deleted domains
- `idx_domains_created_at` - Sort by creation date (DESC)

### Applications
- `idx_applications_domain_id` - Domain lookups
- `idx_applications_name` - Name search
- `idx_applications_key` - Key lookup
- `idx_applications_domain_order` - Domain + order composite
- `idx_applications_created_at` - Sort by creation date

### Menus
- `idx_menus_application_id` - Application lookups
- `idx_menus_parent_menu_id` - Parent menu lookups
- `idx_menus_key` - Key lookup
- `idx_menus_app_parent_order` - Composite for hierarchical queries
- `idx_menus_hierarchy` - Efficient hierarchy traversal

## Triggers

- **update_updated_at_column()** - Automatically updates `updated_at` timestamp on UPDATE operations for domains and applications tables

## Notes

- All timestamps use `TIMESTAMPTZ` for timezone awareness
- UUIDs are used for primary keys for better distributed system support
- Soft deletes are used (is_deleted flag) instead of hard deletes
- JSONB is used for flexible metadata and configuration storage
- Indexes are optimized for common query patterns
