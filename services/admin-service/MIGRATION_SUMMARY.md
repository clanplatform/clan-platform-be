# User Role Form Permission Table - Migration Summary

## ✅ Migration Completed Successfully

**Date**: June 9, 2026  
**Migration ID**: 001  
**Table Name**: `user_role_form_permission`

---

## 📋 What Was Created

### 1. **Alembic Configuration Files**
- `alembic.ini` - Alembic configuration file
- `alembic/env.py` - Environment configuration with model imports
- `alembic/versions/001_create_user_role_form_permission_table.py` - Python migration script
- `alembic/versions/001_create_user_role_form_permission_table.sql` - Standalone SQL script

### 2. **Database Objects Created**

#### Table: `user_role_form_permission`
```sql
CREATE TABLE user_role_form_permission (
    id                      UUID PRIMARY KEY,
    sino                    INTEGER NOT NULL UNIQUE (auto-increment),
    user_role_id            UUID NOT NULL,
    userrole_basic_id       UUID NOT NULL,
    userrole_permission_id  UUID NOT NULL,
    form_permissions        JSONB NOT NULL DEFAULT '[]',
    form_access             VARCHAR(20) DEFAULT 'disable',
    created_at              TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

#### Sequence: `role_form_permission_sino_seq`
- Auto-incrementing sequence for the `sino` column
- Starts at 1, increments by 1

#### Indexes:
- `pk_user_role_form_permission` - Primary key on `id`
- `ix_user_role_form_permission_id` - Index on `id`
- `ix_user_role_form_permission_sino` - Index on `sino`
- `ix_user_role_form_permission_user_role_id` - Index on `user_role_id`
- `ix_user_role_form_permission_userrole_basic_id` - Index on `userrole_basic_id`
- `ix_user_role_form_permission_userrole_permission_id` - Index on `userrole_permission_id`
- `user_role_form_permission_sino_key` - Unique constraint on `sino`

#### Foreign Keys (with CASCADE delete):
- `fk_user_role_form_permission_user_role` → `user_role(id)`
- `fk_user_role_form_permission_userrole_basic` → `userrole_basic(id)`
- `fk_user_role_form_permission_userrole_permission` → `userrole_permission(id)`

#### Trigger:
- `trigger_user_role_form_permission_updated_at` - Automatically updates `updated_at` on record modification

#### Function:
- `update_user_role_form_permission_updated_at()` - PostgreSQL function to update timestamp

---

## 🔧 Configuration Updates

### Updated Files:
1. **app/core/config.py**
   - Added `extra = "ignore"` to Config class
   - Allows extra fields in .env file without validation errors

---

## 📊 Table Structure Details

### Columns:

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NOT NULL | auto-generated | Primary key |
| `sino` | INTEGER | NOT NULL | auto-increment | Serial number for ordering |
| `user_role_id` | UUID | NOT NULL | - | Reference to user_role table |
| `userrole_basic_id` | UUID | NOT NULL | - | Reference to userrole_basic table |
| `userrole_permission_id` | UUID | NOT NULL | - | Reference to userrole_permission table |
| `form_permissions` | JSONB | NOT NULL | `[]` | Array of form permissions |
| `form_access` | VARCHAR(20) | NULL | 'disable' | Highest access level |
| `created_at` | TIMESTAMP | NOT NULL | CURRENT_TIMESTAMP | Record creation time |
| `updated_at` | TIMESTAMP | NOT NULL | CURRENT_TIMESTAMP | Last update time |

### Form Permissions JSON Structure:
```json
[
  {
    "id": "form-uuid",
    "application_id": "app-uuid",
    "modules_id": "module-uuid",
    "access": ["read", "write"]
  }
]
```

### Form Access Values:
- `read` - Read-only access
- `write` - Full read/write access
- `disable` - No access (default)

---

## 🚀 Usage Commands

### Run Migration:
```bash
cd services/admin-service
alembic upgrade head
```

### Check Current Migration:
```bash
alembic current
```

### View Migration History:
```bash
alembic history
```

### Rollback Migration:
```bash
alembic downgrade -1
```

### Run SQL Script Directly:
```bash
psql -U postgres -d admin_service -f alembic/versions/001_create_user_role_form_permission_table.sql
```

---

## ✅ Verification Results

### Migration Status:
```
<base> -> 001 (head), create user_role_form_permission table
```

### Table Verified:
- ✅ All columns created correctly
- ✅ All indexes created
- ✅ All foreign keys with CASCADE delete
- ✅ Sequence created and working
- ✅ Trigger created and active
- ✅ Default values set correctly

---

## 📝 Notes

1. **Model Class**: `RoleFormPermission` in `app/user_role_form_permission/models/user_role_form_permission.py`
2. **Table Name**: `user_role_form_permission`
3. **Database**: `admin_service` on localhost:5432
4. **Relationships**: Links to `user_role`, `userrole_basic`, and `userrole_permission` tables
5. **Auto-Update**: `updated_at` timestamp updates automatically on record changes

---

## 🔄 Rollback Instructions

If you need to rollback this migration:

```bash
# Using Alembic
alembic downgrade -1

# Or using SQL directly
psql -U postgres -d admin_service -c "
DROP TRIGGER IF EXISTS trigger_user_role_form_permission_updated_at ON user_role_form_permission;
DROP FUNCTION IF EXISTS update_user_role_form_permission_updated_at();
DROP TABLE IF EXISTS user_role_form_permission CASCADE;
DROP SEQUENCE IF EXISTS role_form_permission_sino_seq;
"
```

---

## 📚 Related Files

- Model: `app/user_role_form_permission/models/user_role_form_permission.py`
- Migration: `alembic/versions/001_create_user_role_form_permission_table.py`
- SQL Script: `alembic/versions/001_create_user_role_form_permission_table.sql`
- Config: `alembic.ini`, `alembic/env.py`
- Settings: `app/core/config.py`

---

**Migration completed successfully! ✨**
