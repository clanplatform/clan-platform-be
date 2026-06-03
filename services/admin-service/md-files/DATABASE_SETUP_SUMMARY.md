# Database Setup Summary

Complete PostgreSQL database schema and migration system for Admin Service.

## 📦 What Was Created

### SQL Migration Files (`sql-files/`)

✅ **7 SQL migration files** for PostgreSQL schema:

1. `000_init_database.sql` - Initialize database, enable UUID extension
2. `001_create_domains_table.sql` - Domains table with triggers and indexes
3. `002_create_applications_table.sql` - Applications table with foreign keys
4. `003_create_menus_table.sql` - Menus table with self-referencing hierarchy
5. `004_seed_initial_data.sql` - Sample data (3 domains, 8 apps, 8 menus)
6. `999_rollback_all.sql` - Emergency rollback (drop all tables)
7. `README.md` - SQL migration documentation

### Python Migration Scripts (`scripts/`)

✅ **6 Python scripts** for database management:

1. `init_db.py` - Complete database initialization (recommended)
2. `create_tables.py` - Create tables from SQLAlchemy models
3. `run_migrations.py` - Execute SQL migration files in order
4. `seed_data.py` - Insert comprehensive sample data
5. `drop_tables.py` - Drop all tables (with confirmation)
6. `README.md` - Detailed script documentation

### Database Models

✅ **3 SQLAlchemy models** created/updated:

1. `app/domain_controls/models/domains.py` - Domain model ✅
2. `app/domain_controls/models/applications.py` - Application model ✅
3. `app/domain_controls/models/menus.py` - Menu model (NEW) ✅

### Documentation

✅ **2 comprehensive guides**:

1. `MIGRATION_GUIDE.md` - Complete migration guide
2. `DATABASE_SETUP_SUMMARY.md` - This file

## 🗄️ Database Schema

### Tables Overview

```
┌─────────────────┐
│    domains      │  (Platform domains)
│  - id (UUID)    │
│  - code         │
│  - name         │
└────────┬────────┘
         │ 1:N
         ▼
┌─────────────────┐
│  applications   │  (Domain applications)
│  - id (UUID)    │
│  - domain_id    │──┐
│  - name         │  │
│  - key          │  │
└────────┬────────┘  │
         │ 1:N       │
         ▼           │
┌─────────────────┐  │
│     menus       │  │
│  - id (UUID)    │  │
│  - app_id       │──┘
│  - parent_id    │──┐ (self-ref)
│  - name         │  │
└─────────────────┘  │
         ▲           │
         └───────────┘
```

### Domain Table

```sql
CREATE TABLE domains (
    id UUID PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    domain_metadata JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Indexes:**
- `idx_domains_code` (unique)
- `idx_domains_name` (unique)
- `idx_domains_is_active`
- `idx_domains_is_deleted`
- `idx_domains_created_at` (DESC)

### Applications Table

```sql
CREATE TABLE applications (
    id UUID PRIMARY KEY,
    domain_id UUID REFERENCES domains(id),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    version VARCHAR(20) DEFAULT '1.0.0',
    status VARCHAR(50) DEFAULT 'active',
    config JSONB DEFAULT '{}',
    
    -- Navigation fields
    key VARCHAR(100),
    label VARCHAR(100),
    route VARCHAR(200),
    level INTEGER DEFAULT 1,
    icon VARCHAR(100),
    badge VARCHAR(50),
    section_title VARCHAR(200),
    access TEXT[],
    order_index INTEGER DEFAULT 0,
    
    -- Soft delete
    is_active BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Indexes:**
- `idx_applications_domain_id`
- `idx_applications_name`
- `idx_applications_key`
- `idx_applications_domain_order` (composite)

### Menus Table

```sql
CREATE TABLE menus (
    id UUID PRIMARY KEY,
    application_id UUID REFERENCES applications(id),
    parent_menu_id UUID REFERENCES menus(id),
    name VARCHAR(100) NOT NULL,
    key VARCHAR(100) NOT NULL,
    label VARCHAR(100),
    icon VARCHAR(100),
    route VARCHAR(200),
    component VARCHAR(200),
    level INTEGER DEFAULT 1,
    order_index INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Indexes:**
- `idx_menus_application_id`
- `idx_menus_parent_menu_id`
- `idx_menus_key`
- `idx_menus_app_parent_order` (composite)
- `idx_menus_hierarchy` (composite)

## 🚀 Quick Start

### Method 1: All-in-One (Recommended)

```bash
# From services/admin-service/
python scripts/init_db.py --seed
```

This will:
1. ✅ Check database connection
2. ✅ Create all tables
3. ✅ Set up indexes and triggers
4. ✅ Insert sample data
5. ✅ Show summary

### Method 2: SQL Migrations

```bash
# From services/admin-service/
python scripts/run_migrations.py
```

This will:
1. ✅ Execute SQL files in order
2. ✅ Use transactions (rollback on error)
3. ✅ Show progress for each file

## 📊 Sample Data

When using `--seed` or running `004_seed_initial_data.sql`:

### Domains (3)
- **PLATFORM** - Platform Services
- **COMMERCE** - Commerce Services  
- **ANALYTICS** - Analytics Services

### Applications (8)
- Admin Console (PLATFORM)
- User Management (PLATFORM)
- System Settings (PLATFORM)
- Product Catalog (COMMERCE)
- Order Management (COMMERCE)
- Payment Gateway (COMMERCE)
- Reports (ANALYTICS)
- Dashboards (ANALYTICS)

### Menus (8)
- Dashboard, Configuration (Admin Console)
- Users, Roles (User Management)
- Products, Categories (Product Catalog)

## 🔧 Common Commands

### Create Database

```bash
# Using Python (development)
python scripts/init_db.py --seed

# Using SQL (production)
python scripts/run_migrations.py
```

### Reset Database

```bash
# Drop and recreate
python scripts/init_db.py --drop --seed
```

### Add Sample Data

```bash
# First time
python scripts/seed_data.py

# Update existing
python scripts/seed_data.py --force
```

### Verify Schema

```bash
# Check tables
python scripts/create_tables.py

# Using psql
psql -U admin_user -d admin_db -c "\dt"

# Count records
psql -U admin_user -d admin_db -c "
  SELECT 
    (SELECT COUNT(*) FROM domains) as domains,
    (SELECT COUNT(*) FROM applications) as apps,
    (SELECT COUNT(*) FROM menus) as menus;
"
```

### Drop All Tables

```bash
# With confirmation
python scripts/drop_tables.py

# Using SQL
psql -U admin_user -d admin_db -f sql-files/999_rollback_all.sql
```

## 🐳 Docker Usage

### With Docker Compose

```bash
# Start all services
docker-compose up -d

# Initialize database
docker exec admin-service python scripts/init_db.py --seed

# Check database
docker exec -it admin-service-postgres psql -U admin_user -d admin_db -c "\dt"
```

### Standalone PostgreSQL Container

```bash
# Run PostgreSQL
docker run -d \
  --name postgres \
  -e POSTGRES_DB=admin_db \
  -e POSTGRES_USER=admin_user \
  -e POSTGRES_PASSWORD=admin_pass \
  -p 5432:5432 \
  postgres:15-alpine

# Initialize
sleep 5
python scripts/init_db.py --seed
```

## ✅ Features

### Indexes
- **Unique indexes** on domain code and name
- **Composite indexes** for common query patterns
- **Partial indexes** excluding soft-deleted records
- **DESC indexes** for FILO ordering

### Triggers
- **auto_update_timestamp** - Automatically updates `updated_at` on UPDATE
- Applied to domains and applications tables

### Constraints
- **Foreign keys** with CASCADE delete
- **NOT NULL** constraints on required fields
- **UNIQUE** constraints on codes and names
- **CHECK** constraint preventing self-referencing menus

### Soft Delete
- `is_deleted` flag
- `deleted_at` timestamp
- Cascade from domains to applications
- Queries exclude soft-deleted records by default

### JSON Support
- `domain_metadata` - Flexible domain metadata
- `config` - Application configuration
- JSONB type for efficient querying

## 📁 File Structure

```
services/admin-service/
├── sql-files/
│   ├── 000_init_database.sql          ✅
│   ├── 001_create_domains_table.sql   ✅
│   ├── 002_create_applications_table.sql ✅
│   ├── 003_create_menus_table.sql     ✅
│   ├── 004_seed_initial_data.sql      ✅
│   ├── 999_rollback_all.sql           ✅
│   └── README.md                       ✅
├── scripts/
│   ├── init_db.py                     ✅
│   ├── create_tables.py               ✅
│   ├── run_migrations.py              ✅
│   ├── seed_data.py                   ✅
│   ├── drop_tables.py                 ✅
│   └── README.md                       ✅
├── app/domain_controls/models/
│   ├── domains.py                     ✅
│   ├── applications.py                ✅
│   └── menus.py                       ✅ NEW
├── MIGRATION_GUIDE.md                 ✅
└── DATABASE_SETUP_SUMMARY.md          ✅ (this file)
```

## 🎯 Next Steps

After database setup:

1. ✅ Start the application:
   ```bash
   uvicorn app.main:app --reload
   ```

2. ✅ Access API docs:
   - Swagger: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

3. ✅ Test endpoints:
   ```bash
   # Health check
   curl http://localhost:8000/health
   
   # Get domains (requires auth)
   curl -H "Authorization: Bearer TOKEN" \
     http://localhost:8000/api/v1/domains
   ```

4. ✅ Verify data:
   ```bash
   psql -U admin_user -d admin_db
   
   # Query domains
   SELECT * FROM domains WHERE is_deleted = FALSE;
   
   # Query with relationships
   SELECT d.name, COUNT(a.id) as app_count
   FROM domains d
   LEFT JOIN applications a ON a.domain_id = d.id
   WHERE d.is_deleted = FALSE
   GROUP BY d.id, d.name;
   ```

## 🔍 Verification Checklist

After running migrations:

- [ ] Database connection successful
- [ ] All 3 tables created (domains, applications, menus)
- [ ] Indexes created
- [ ] Triggers working (updated_at auto-updates)
- [ ] Foreign keys enforced
- [ ] Sample data inserted (if --seed used)
- [ ] Soft delete works correctly
- [ ] Application starts without errors
- [ ] API endpoints accessible
- [ ] Swagger docs display correctly

## 🆘 Troubleshooting

### Connection Issues
```bash
# Check PostgreSQL is running
docker ps | grep postgres
systemctl status postgresql

# Test connection
psql -U admin_user -d admin_db -c "SELECT 1"
```

### Permission Issues
```sql
-- Grant all permissions
GRANT ALL ON SCHEMA public TO admin_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO admin_user;
```

### Import Errors
```bash
# Ensure dependencies installed
pip install -r requirements.txt

# Check Python path
cd services/admin-service
python scripts/init_db.py --seed
```

## 📚 Documentation

- **Quick Start**: This file
- **Detailed Scripts**: `scripts/README.md`
- **SQL Migrations**: `sql-files/README.md`
- **Complete Guide**: `MIGRATION_GUIDE.md`

## ✨ Summary

**Created**: 18 files (7 SQL + 6 Python + 3 Models + 2 Docs)

**Ready to use**:
- ✅ Complete PostgreSQL schema
- ✅ Migration scripts (SQL + Python)
- ✅ Sample data
- ✅ Comprehensive documentation

**Run this to get started**:
```bash
python scripts/init_db.py --seed
```

That's it! Your database is ready! 🎉
