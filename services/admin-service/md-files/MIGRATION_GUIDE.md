# Database Migration Guide

Complete guide for managing database migrations and schema in the Admin Service.

## Quick Start

### Option 1: Python Scripts (Recommended for Development)

```bash
# Navigate to service directory
cd services/admin-service

# Create tables and seed data
python scripts/init_db.py --seed

# That's it! 🎉
```

### Option 2: SQL Migrations (Recommended for Production)

```bash
# Run all SQL migration files
python scripts/run_migrations.py
```

## Available Methods

### Method 1: Python Scripts (SQLAlchemy)

**Pros:**
- ✅ Automatic schema generation from models
- ✅ Easy to use for development
- ✅ Handles relationships automatically
- ✅ Interactive seed data

**Cons:**
- ❌ No migration history tracking
- ❌ Less control over SQL
- ❌ Not ideal for production

**Commands:**

```bash
# Initialize database
python scripts/init_db.py

# Initialize with seed data
python scripts/init_db.py --seed

# Drop all tables and recreate
python scripts/init_db.py --drop --seed

# Just create tables
python scripts/create_tables.py

# Just seed data
python scripts/seed_data.py

# Drop all tables (dangerous!)
python scripts/drop_tables.py
```

### Method 2: SQL Migration Files

**Pros:**
- ✅ Explicit migration history
- ✅ Full SQL control
- ✅ Production-ready
- ✅ Versioned and trackable

**Cons:**
- ❌ Manual SQL writing
- ❌ Must keep in sync with models
- ❌ More verbose

**Commands:**

```bash
# Run all migrations
python scripts/run_migrations.py

# Or manually with psql
psql -U admin_user -d admin_db -f sql-files/000_init_database.sql
psql -U admin_user -d admin_db -f sql-files/001_create_domains_table.sql
psql -U admin_user -d admin_db -f sql-files/002_create_applications_table.sql
psql -U admin_user -d admin_db -f sql-files/003_create_menus_table.sql
psql -U admin_user -d admin_db -f sql-files/004_seed_initial_data.sql
```

### Method 3: Alembic (Best for Production)

**Coming soon** - Use Alembic for production database migrations with full version control.

## Database Schema

### Tables

1. **domains** - Platform domains
   - Primary key: `id` (UUID)
   - Unique: `code`, `name`
   - Soft delete: `is_deleted`, `deleted_at`
   - Metadata: `domain_metadata` (JSONB)

2. **applications** - Applications within domains
   - Primary key: `id` (UUID)
   - Foreign key: `domain_id` → domains.id
   - Soft delete: `is_deleted`, `deleted_at`
   - Navigation: `key`, `label`, `route`, `icon`, `order_index`

3. **menus** - Navigation menu hierarchy
   - Primary key: `id` (UUID)
   - Foreign key: `application_id` → applications.id
   - Self-referencing: `parent_menu_id` → menus.id
   - Hierarchy: `level`, `order_index`

### Relationships

```
domains (1) ──→ (N) applications (1) ──→ (N) menus
                                              ↓
                                        parent_menu_id
                                              ↓
                                            menus
```

## Usage Scenarios

### 1. First Time Setup (Development)

```bash
# Start database (if using Docker)
docker-compose up -d postgres

# Create tables and add sample data
python scripts/init_db.py --seed
```

### 2. Reset Database (Development)

```bash
# Drop everything and recreate
python scripts/init_db.py --drop --seed
```

### 3. Production Deployment

```bash
# Use SQL migrations for production
python scripts/run_migrations.py

# Verify tables
psql -U admin_user -d admin_db -c "\dt"
```

### 4. Add More Sample Data

```bash
# Add/update seed data
python scripts/seed_data.py

# Force update existing records
python scripts/seed_data.py --force
```

### 5. Check Current Schema

```bash
# Using Python
python scripts/create_tables.py

# Using psql
psql -U admin_user -d admin_db -c "\d domains"
psql -U admin_user -d admin_db -c "\d applications"
psql -U admin_user -d admin_db -c "\d menus"
```

## Migration Files

### SQL Files (in `sql-files/`)

| File | Description |
|------|-------------|
| `000_init_database.sql` | Enable extensions, set timezone |
| `001_create_domains_table.sql` | Create domains table with indexes |
| `002_create_applications_table.sql` | Create applications table |
| `003_create_menus_table.sql` | Create menus table with hierarchy |
| `004_seed_initial_data.sql` | Insert sample data |
| `999_rollback_all.sql` | Drop all tables (emergency rollback) |

### Python Scripts (in `scripts/`)

| Script | Purpose |
|--------|---------|
| `init_db.py` | Complete database initialization |
| `create_tables.py` | Create tables from SQLAlchemy models |
| `run_migrations.py` | Execute SQL migration files |
| `seed_data.py` | Insert sample data |
| `drop_tables.py` | Drop all tables (dangerous!) |

## Environment Configuration

Make sure your `.env` file has the correct database connection:

```bash
DATABASE_URL=postgresql://admin_user:admin_pass@localhost:5432/admin_db
```

## Docker Setup

### Using Docker Compose

```bash
# Start all services (includes PostgreSQL)
docker-compose up -d

# Run migrations inside container
docker exec admin-service python scripts/init_db.py --seed

# Or connect to database directly
docker exec -it admin-service-postgres psql -U admin_user -d admin_db
```

### Manual Database Container

```bash
# Start PostgreSQL
docker run -d \
  --name postgres \
  -e POSTGRES_DB=admin_db \
  -e POSTGRES_USER=admin_user \
  -e POSTGRES_PASSWORD=admin_pass \
  -p 5432:5432 \
  postgres:15-alpine

# Wait for PostgreSQL to be ready
sleep 5

# Run migrations
python scripts/init_db.py --seed
```

## Troubleshooting

### Connection Refused

```
❌ Database connection failed
```

**Solution:**
- Check DATABASE_URL in `.env`
- Ensure PostgreSQL is running: `docker ps` or `systemctl status postgresql`
- Verify port 5432 is not blocked
- Check credentials

### Permission Denied

```
ERROR: permission denied for schema public
```

**Solution:**
```sql
-- Connect as superuser and grant permissions
GRANT ALL ON SCHEMA public TO admin_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO admin_user;
```

### Table Already Exists

```
ERROR: relation "domains" already exists
```

**Solution:**
```bash
# Drop and recreate
python scripts/init_db.py --drop --seed

# Or use force flag
python scripts/init_db.py --force --seed
```

### Import Errors

```
ModuleNotFoundError: No module named 'app'
```

**Solution:**
```bash
# Ensure you're in the service directory
cd services/admin-service

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### SQL Syntax Errors

```
ERROR: syntax error at or near "..."
```

**Solution:**
- Check PostgreSQL version (need 12+)
- Verify UUID extension is enabled
- Review SQL file for syntax issues

## Best Practices

### Development
1. Use Python scripts for quick iterations
2. Drop and recreate database frequently
3. Keep seed data updated
4. Test migrations before pushing

### Production
1. **Always use SQL migrations**
2. **Backup database before migrations**
3. Test migrations on staging first
4. Never use `--drop` flag
5. Keep migration history
6. Use transactions
7. Have rollback plan

## Verification

After running migrations, verify the schema:

```bash
# Check tables exist
psql -U admin_user -d admin_db -c "\dt"

# Count records
psql -U admin_user -d admin_db -c "SELECT 
    (SELECT COUNT(*) FROM domains) as domains,
    (SELECT COUNT(*) FROM applications) as applications,
    (SELECT COUNT(*) FROM menus) as menus;"

# Check relationships
psql -U admin_user -d admin_db -c "
SELECT 
    d.name as domain,
    COUNT(a.id) as application_count
FROM domains d
LEFT JOIN applications a ON a.domain_id = d.id
WHERE d.is_deleted = FALSE
GROUP BY d.id, d.name
ORDER BY d.name;"
```

## Next Steps

After successful migration:

1. ✅ Start the application: `uvicorn app.main:app --reload`
2. ✅ Access Swagger docs: http://localhost:8000/docs
3. ✅ Test API endpoints
4. ✅ Verify data in database

## Getting Help

- Check logs: `docker-compose logs postgres`
- Review error messages carefully
- Ensure all dependencies are installed
- Verify database permissions
- Check PostgreSQL version compatibility

---

**Need more help?** Check the `scripts/README.md` for detailed script documentation.
