# Quick Start - Database Setup

The fastest way to set up your database.

## 🚀 One-Command Setup

### Linux/Mac

```bash
chmod +x setup_database.sh
./setup_database.sh --seed
```

### Windows

```cmd
setup_database.bat --seed
```

That's it! Your database is ready with sample data! 🎉

## 📋 What This Does

The setup script automatically:

1. ✅ Checks for `.env` file (creates from example if missing)
2. ✅ Verifies Python installation
3. ✅ Creates virtual environment (if needed)
4. ✅ Installs dependencies
5. ✅ Tests database connection
6. ✅ Creates all tables
7. ✅ Seeds sample data (with `--seed`)
8. ✅ Shows next steps

## 🎯 Quick Commands

### First Time Setup

```bash
# Linux/Mac
./setup_database.sh --seed

# Windows
setup_database.bat --seed
```

### Reset Database

```bash
# Linux/Mac
./setup_database.sh --reset --seed

# Windows
setup_database.bat --reset --seed
```

### Use SQL Migrations

```bash
# Linux/Mac
./setup_database.sh --sql

# Windows
setup_database.bat --sql
```

## 🔧 Manual Setup (Alternative)

If you prefer manual control:

```bash
# 1. Create virtual environment
python -m venv venv

# 2. Activate it
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Setup database
python scripts/init_db.py --seed
```

## 🐳 Using Docker

### Option 1: Full Stack

```bash
# Start all services (app + databases)
docker-compose up -d

# Initialize database
docker exec admin-service python scripts/init_db.py --seed
```

### Option 2: Database Only

```bash
# Start only PostgreSQL
docker-compose up -d postgres

# Setup database locally
./setup_database.sh --seed
```

## ✅ Verify Setup

### Check Tables

```bash
# Using Python
python scripts/create_tables.py

# Using psql
psql -U admin_user -d admin_db -c "\dt"
```

### Check Data

```bash
# Count records
psql -U admin_user -d admin_db -c "
  SELECT 
    (SELECT COUNT(*) FROM domains) as domains,
    (SELECT COUNT(*) FROM applications) as apps,
    (SELECT COUNT(*) FROM menus) as menus;
"
```

### Start Application

```bash
uvicorn app.main:app --reload
```

Access at:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

## 🆘 Troubleshooting

### Database Connection Failed

```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Start PostgreSQL
docker-compose up -d postgres

# Check DATABASE_URL in .env
cat .env | grep DATABASE_URL
```

### Permission Denied (Linux/Mac)

```bash
# Make script executable
chmod +x setup_database.sh

# Then run it
./setup_database.sh --seed
```

### Python Not Found

```bash
# Check Python installation
python --version
python3 --version

# Install Python 3.11+
# See: https://www.python.org/downloads/
```

### Import Errors

```bash
# Ensure you're in the correct directory
cd services/admin-service

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

## 📚 More Information

- **Detailed Guide**: `MIGRATION_GUIDE.md`
- **Complete Summary**: `DATABASE_SETUP_SUMMARY.md`
- **Script Documentation**: `scripts/README.md`
- **SQL Files**: `sql-files/README.md`

## 🎬 Complete Example

```bash
# 1. Clone/navigate to project
cd services/admin-service

# 2. Setup database (one command!)
./setup_database.sh --seed

# 3. Start application
uvicorn app.main:app --reload

# 4. Open browser
# http://localhost:8000/docs

# 5. Test API
curl http://localhost:8000/health
```

## 💡 Tips

- Use `--seed` for development (includes sample data)
- Use `--reset` to start fresh (drops all tables)
- Use `--sql` for production-like migrations
- Check `.env` file for database configuration
- Review logs if setup fails

## ✨ That's It!

Your database is ready! Start building! 🚀

---

**Need help?** Check `MIGRATION_GUIDE.md` for detailed documentation.
