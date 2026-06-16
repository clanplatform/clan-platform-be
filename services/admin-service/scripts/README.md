# Admin Service Scripts

This directory contains utility scripts for the admin service.

---

## Available Scripts

### 1. `sync_existing_users.py`

**Purpose**: Manually sync existing users from admin-service to auth-service.

**Use Cases**:
- Initial sync of existing users after implementing the sync feature
- Re-syncing users that failed to sync during creation
- Recovering from auth-service database failures
- Bulk sync operations

**Examples**:

```bash
# Sync all users
python scripts/sync_existing_users.py --all

# Sync only active users
python scripts/sync_existing_users.py --all --status active

# Sync specific users by ID
python scripts/sync_existing_users.py --user-ids "uuid1,uuid2,uuid3"

# Dry run to see what would be synced without actually syncing
python scripts/sync_existing_users.py --all --dry-run

# Sync all inactive users
python scripts/sync_existing_users.py --all --status inactive
```

**Output**:
```
[1/50] Syncing user: john_doe (ID: 123e4567-e89b-12d3-a456-426614174000)
  Email: john@example.com
  Name: John Doe
  Status: active
  ✅ Successfully synced to auth-service

[2/50] Syncing user: jane_smith (ID: 223e4567-e89b-12d3-a456-426614174001)
  Email: jane@example.com
  Name: Jane Smith
  Status: active
  ⚠️  User already exists in auth-service

...

================================================================================
SYNC SUMMARY
================================================================================
✅ Successfully synced: 45
⚠️  Already existed: 3
❌ Failed: 2
================================================================================
```

**Requirements**:
- `IDENTITY_SERVICE_URL` must be configured in `.env` file
- Auth service must be running and accessible
- Admin service database must be accessible

---

### 2. `check_databases.ps1`

**Purpose**: Check database connectivity and status.

**Examples**:

```powershell
# Check if databases are accessible
.\scripts\check_databases.ps1
```

---

## Common Issues and Solutions

### Issue: "Auth sync is not enabled"

**Solution**: Set `IDENTITY_SERVICE_URL` in your `.env` file:
```env
IDENTITY_SERVICE_URL=http://localhost:8001
```

### Issue: "Failed to connect to auth service"

**Possible causes**:
1. Auth service is not running
2. Wrong URL in `IDENTITY_SERVICE_URL`
3. Network connectivity issues

**Solution**:
```bash
# Check if auth service is running
curl http://localhost:8001/health

# Check if the sync endpoint exists
curl -X POST http://localhost:8001/api/v1/auth/users/sync
```

### Issue: "User already exists in auth-service (409)"

**Explanation**: This is not an error. The user already exists in the auth service, which means it was already synced.

**Action**: No action needed. The script will mark it as "Already existed" and continue.

### Issue: Database connection errors

**Solution**: Verify database configuration in `.env`:
```env
DATABASE_URL=postgresql://postgres:root@localhost:5432/admin_service
```

---

## Running Scripts from Different Directories

### From project root:
```bash
cd /path/to/clan-platform-domain-be
python services/admin-service/scripts/sync_existing_users.py --all
```

### From admin-service directory:
```bash
cd services/admin-service
python scripts/sync_existing_users.py --all
```

### From scripts directory:
```bash
cd services/admin-service/scripts
python sync_existing_users.py --all
```

---

## Script Development Guidelines

When creating new scripts in this directory:

1. **Add proper documentation**: Include docstrings and help text
2. **Use command-line arguments**: Use `argparse` for flexibility
3. **Handle errors gracefully**: Catch exceptions and provide helpful error messages
4. **Support dry-run mode**: Allow users to preview changes before applying
5. **Provide progress feedback**: Use progress indicators for long-running operations
6. **Log important actions**: Use Python's `logging` module
7. **Add to this README**: Document the new script's purpose and usage

---

## Script Template

```python
"""
Script description here.

Usage:
    python scripts/script_name.py [options]
"""
import sys
import os
import argparse

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Script description')
    parser.add_argument('--option', type=str, help='Option description')
    args = parser.parse_args()
    
    # Script logic here
    print("Script executed successfully")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⚠️  Script interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
```

---

## Additional Resources

- **Main Documentation**: See `/USERSETUP_AUTH_SYNC_IMPLEMENTATION.md`
- **SQL Queries**: See `/SQL_VERIFICATION_QUERIES.md`
- **Test Script**: See `/test_user_sync.py`

---

## Getting Help

If you encounter issues with any script:

1. Check the script's help: `python scripts/script_name.py --help`
2. Run with `--dry-run` to see what would happen
3. Check the application logs
4. Verify environment configuration in `.env` file
5. Ensure all required services are running
