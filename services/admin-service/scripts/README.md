# Database Scripts

Python scripts for managing the Admin Service database.

## Available Scripts

### 1. Initialize Database (`init_db.py`)

Initialize the database with tables and optionally seed data.

```bash
# Create tables only
python scripts/init_db.py

# Create tables and seed initial data
python scripts/init_db.py --seed

# Drop existing tables and recreate (WARNING: destroys data)
python scripts/init_db.py --drop --seed

# Skip confirmation prompts
python scripts/init_db.py --seed --force
```

**Options:**
- `--seed`: Insert sample data after creating tables
- `--drop`: Drop all tables before creating (destroys all data)
- `--force`: Skip confirmation prompts

### 2. Create Tables (`create_tables.py`)

Create database tables using SQLAlchemy models.

```bash
python scripts/create_tables.py
```

This script:
- Checks database connection
- Lists registered models
- Creates all tables
- Shows created tables

### 3. Run SQL Migrations (`run_migrations.py`)

Execute SQL migration files in order.

```bash
python scripts/run_migrations.py
```

This script:
- Finds all SQL files in `sql-files/` directory
- Executes them in numerical order
- Uses transactions (rollback on error)
- Shows progress and summary
- Prompts to continue if a migration fails

### 4. Seed Data (`seed_data.py`)

Insert sample data for development/testing.

```bash
python scripts/seed_data.py

# Force overwrite existing data
python scripts/seed_data.py --force
```

### 5. Drop Tables (`drop_tables.py`)

**⚠️ USE WITH EXTREME CAUTION! ⚠️**

Drop all database tables and data.

```bash
python scripts/drop_tables.py
```

Requires typing "DROP ALL TABLES" to confirm.

## Quick Start

### First Time Setup

```bash
# Option 1: Using Python scripts (SQLAlchemy)
python scripts/init_db.py --seed

# Option 2: Using SQL migrations
python scripts/run_migrations.py
```

### Reset Database

```bash
# Drop all tables and recreate with seed data
python scripts/init_db.py --drop --seed
```

### Add Sample Data

```bash
python scripts/seed_data.py
```

## Environment Variables

All scripts use configuration from `.env` file:

```bash
DATABASE_URL=postgresql://user:pass@localhost:5432/admin_db
```

Make sure `.env` is properly configured before running scripts.

## Script Order

1. **init_db.py** - Best for first-time setup
2. **create_tables.py** - Create tables using models
3. **run_migrations.py** - Execute SQL files
4. **seed_data.py** - Add sample data
5. **drop_tables.py** - Clean up (destructive)

## Using with Docker

### Execute inside container:

```bash
# Access container
docker exec -it admin-service bash

# Run scripts
python scripts/init_db.py --seed
```

### Execute from host:

```bash
# Run script in container
docker exec admin-service python scripts/init_db.py --seed
```

## Troubleshooting

### Connection Failed

```
❌ Database connection failed
```

**Solution:**
- Check DATABASE_URL in `.env`
- Ensure PostgreSQL is running
- Verify credentials
- Check network/firewall

### Import Errors

```
ModuleNotFoundError: No module named 'app'
```

**Solution:**
- Run scripts from service root directory
- Ensure virtual environment is activated
- Install dependencies: `pip install -r requirements.txt`

### Permission Errors

```
permission denied for schema public
```

**Solution:**
- Ensure database user has CREATE privileges
- Grant permissions: `GRANT ALL ON SCHEMA public TO admin_user;`

### Tables Already Exist

```
relation "domains" already exists
```

**Solution:**
- Use `--drop` flag to recreate: `python scripts/init_db.py --drop --seed`
- Or manually drop tables first

## Migration vs SQLAlchemy

### Use SQL Migrations when:
- You need fine-grained control over schema
- You want explicit migration history
- Working in production environments
- Need custom SQL features

### Use SQLAlchemy (create_tables.py) when:
- Rapid development
- Local development/testing
- Schema matches models exactly
- Don't need migration history

## Best Practices

1. **Always backup** before running destructive operations
2. **Use migrations** for production deployments
3. **Test scripts** on development database first
4. **Version control** all migration files
5. **Document changes** in migration comments
6. **Use transactions** to ensure atomicity

## Examples

### Complete Fresh Setup

```bash
# 1. Drop everything (if exists)
python scripts/drop_tables.py

# 2. Create tables
python scripts/init_db.py

# 3. Seed sample data
python scripts/seed_data.py
```

### Production Deployment

```bash
# Use SQL migrations for production
python scripts/run_migrations.py
```

### Development Reset

```bash
# Quick reset with sample data
python scripts/init_db.py --drop --seed
```
