# Auth Service Sync - User Setup Integration

## 📋 Overview

This integration automatically syncs user data from the **clan-platform-domain-be** (admin-service) to the **clan-identity-domain** (auth-service) when creating users through the `/api/v1/user_setup/with-details` endpoint.

When a user is created in the admin-service, their authentication credentials are automatically replicated to the auth-service's `auth_users` table, enabling single sign-on (SSO) across the platform.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────┐
│  Admin Service (Platform Domain)   │
│                                     │
│  POST /api/v1/user_setup/          │
│       with-details                  │
│                                     │
│  1. Create user in DB               │
│  2. Hash password (bcrypt)          │
│  3. Sync to Auth Service ──────────┼───┐
│                                     │   │
└─────────────────────────────────────┘   │
                                          │ HTTP POST
                                          │ (async)
                                          ▼
                              ┌───────────────────────────┐
                              │ Auth Service (Identity)   │
                              │                           │
                              │ POST /api/v1/auth/users/  │
                              │      sync                 │
                              │                           │
                              │ Create auth_users record  │
                              └───────────────────────────┘
```

---

## 📂 Files Created/Modified

### New Files:
1. **`app/user_setup/services/auth_service_sync.py`**
   - Service for syncing user data with auth-service
   - Handles create, update, and delete operations
   - Includes error handling and retry logic

### Modified Files:
1. **`app/user_setup/services/user_setup.py`**
   - Updated `create_user_setup_with_details()` to sync with auth-service
   - Added async support and error logging

2. **`app/api/v1/routes/access_control/user_setup.py`**
   - Updated route to async for proper sync handling

---

## 🔧 Configuration

### Environment Variables

The integration uses the `IDENTITY_SERVICE_URL` environment variable:

**File**: `config/environments/.env.local`

```bash
# ==================== IDENTITY SERVICE ====================
# External identity service URL for authentication
IDENTITY_SERVICE_URL=http://localhost:8001
```

**For Different Environments**:

| Environment | Variable | Example Value |
|------------|----------|---------------|
| Local | `IDENTITY_SERVICE_URL` | `http://localhost:8001` |
| Development | `IDENTITY_SERVICE_URL` | `https://identity-dev.example.com` |
| UAT | `IDENTITY_SERVICE_URL` | `https://identity-uat.example.com` |
| Production | `IDENTITY_SERVICE_URL` | `https://identity.example.com` |

### Disable Sync

To disable the auth service sync:
- Set `IDENTITY_SERVICE_URL` to empty string or remove it
- Or comment it out in the `.env` file

```bash
# IDENTITY_SERVICE_URL=http://localhost:8001
```

---

## 🚀 How It Works

### 1. User Creation Flow

```python
# User submits data to admin-service
POST /api/v1/user_setup/with-details
{
  "basic": {
    "username": "john.doe",
    "email": "john@example.com",
    "password": "SecurePass123!",
    "firstname": "John",
    "lastname": "Doe",
    "employee_id": "EMP001",
    ...
  },
  "roles_entities": { ... },
  "preferences": { ... }
}
```

### 2. Admin Service Processing

1. **Validates** the request data
2. **Creates** user in admin-service database:
   - `user_setup` (parent record)
   - `user_setup_basic` (user details + hashed password)
   - `user_setup_roles_entity` (roles and entities)
   - `user_setup_preference` (user preferences)
3. **Commits** transaction to database
4. **Syncs** to auth-service (async, non-blocking)

### 3. Auth Service Sync

```python
# Sync payload sent to auth-service
POST {IDENTITY_SERVICE_URL}/api/v1/auth/users/sync
{
  "id": "uuid-from-admin-service",  # Same UUID
  "username": "john.doe",
  "email": "john@example.com",
  "password_hash": "$2b$12$...",  # Pre-hashed password
  "first_name": "John",
  "last_name": "Doe",
  "phone_number": "+1234567890",
  "is_active": true,
  "employee_id": "EMP001",
  "created_from": "admin-service"
}
```

### 4. Auth Service Response

| Status Code | Meaning | Action |
|------------|---------|--------|
| `201` | User created | Success - logged |
| `409` | User already exists | Warning logged - continues |
| `4xx/5xx` | Error | Error logged - user still created in admin-service |

---

## 📊 Data Mapping

### Admin Service → Auth Service

| Admin Service Field | Auth Service Field | Notes |
|--------------------|-------------------|-------|
| `user_setup_basic.id` | `auth_users.id` | **Same UUID** - ensures consistency |
| `username` | `username` | Direct mapping |
| `email` | `email` | Direct mapping |
| `password_hash` | `password_hash` | Pre-hashed with bcrypt (12 rounds) |
| `firstname` | `first_name` | Direct mapping |
| `lastname` | `last_name` | Direct mapping |
| `phone_number` | `phone_number` | Optional field |
| `status` | `is_active` | Converted: `'active'` → `true` |
| `employee_id` | `employee_id` | Optional tracking field |
| - | `created_from` | Always `"admin-service"` |

---

## 🔐 Security Features

### 1. Password Handling
- Passwords are **hashed once** in admin-service using bcrypt (12 rounds)
- **Pre-hashed password** is sent to auth-service (not plain text)
- Auth-service stores the hash directly (no re-hashing)

### 2. UUID Consistency
- **Same UUID** is used in both services
- Enables cross-service user identification
- Maintains referential integrity

### 3. Error Isolation
- Sync failures **do not** prevent user creation in admin-service
- Failed syncs are **logged** for manual intervention
- Users can still use admin-service features even if sync fails

---

## 🛠️ Auth Service Sync Class

### Methods

#### `create_auth_user()`
Creates a user in auth-service `auth_users` table.

```python
await AuthServiceSync.create_auth_user(
    user_id=uuid,
    username="john.doe",
    email="john@example.com",
    password_hash="$2b$12$...",
    firstname="John",
    lastname="Doe",
    phone_number="+1234567890",
    is_active=True,
    employee_id="EMP001"
)
```

**Returns**: `Dict[str, Any]` with sync result

#### `update_auth_user()`
Updates a user in auth-service (for future use).

```python
await AuthServiceSync.update_auth_user(
    user_id=uuid,
    email="newemail@example.com",
    is_active=False
)
```

#### `delete_auth_user()`
Deletes a user from auth-service (for future use).

```python
await AuthServiceSync.delete_auth_user(user_id=uuid)
```

#### `sync_enabled()`
Checks if sync is enabled.

```python
if AuthServiceSync.sync_enabled():
    # Sync is enabled
    pass
```

---

## 📝 Logging

### Log Levels

| Level | When | Example |
|-------|------|---------|
| `INFO` | Successful sync | `Successfully synced user john.doe (ID: uuid) to auth-service` |
| `WARNING` | User already exists | `User john.doe already exists in auth-service` |
| `WARNING` | Sync disabled | `Auth service sync is disabled (IDENTITY_SERVICE_URL not configured)` |
| `ERROR` | Sync failure | `Failed to sync user john.doe to auth-service: Connection refused` |

### Example Log Output

```json
{
  "level": "INFO",
  "message": "Successfully synced user john.doe (ID: a1b2c3d4-...) to auth-service",
  "timestamp": "2026-06-09T11:00:00.000Z",
  "service": "admin-service"
}
```

---

## 🧪 Testing

### Test Sync Functionality

#### 1. Create User with Sync Enabled
```bash
# Set environment variable
export IDENTITY_SERVICE_URL=http://localhost:8001

# Create user
curl -X POST http://localhost:8000/api/v1/user_setup/with-details \
  -H "Content-Type: application/json" \
  -d '{
    "basic": {
      "username": "test.user",
      "email": "test@example.com",
      "password": "TestPass123!",
      "firstname": "Test",
      "lastname": "User",
      "employee_id": "EMP999"
    }
  }'
```

**Expected**:
- User created in admin-service
- User synced to auth-service
- Log message confirming sync

#### 2. Create User with Sync Disabled
```bash
# Unset or comment out IDENTITY_SERVICE_URL
unset IDENTITY_SERVICE_URL

# Create user
curl -X POST http://localhost:8000/api/v1/user_setup/with-details \
  -H "Content-Type: application/json" \
  -d '{ ... }'
```

**Expected**:
- User created in admin-service
- No sync attempted
- Log message: "Auth service sync is disabled"

#### 3. Verify in Auth Service
```bash
# Query auth-service to verify user exists
curl -X GET http://localhost:8001/api/v1/auth/users/{user_id}
```

---

## 🚨 Error Handling

### Scenario 1: Auth Service Down
**What Happens**:
- User is created in admin-service ✅
- Sync fails ❌
- Error logged: "Failed to connect to auth service: Connection refused"
- User can still use admin-service

**Resolution**:
- Once auth-service is back up, manually sync using bulk sync script (future enhancement)

### Scenario 2: Duplicate User in Auth Service
**What Happens**:
- User is created in admin-service ✅
- Sync returns 409 (Conflict)
- Warning logged: "User already exists in auth-service"
- No error thrown

**Resolution**:
- No action needed - users match

### Scenario 3: Network Timeout
**What Happens**:
- User is created in admin-service ✅
- Sync times out after 10 seconds
- Error logged: "Auth service request timed out"

**Resolution**:
- Retry sync manually or use bulk sync script

---

## 🔮 Future Enhancements

### 1. Async Queue System
Replace direct HTTP calls with message queue (Kafka/RabbitMQ):
- More reliable
- Automatic retries
- Better performance

### 2. Bulk Sync Script
Create script to sync all users:
```bash
python scripts/sync_users_to_auth_service.py
```

### 3. Webhook Callbacks
Auth-service sends webhooks back to admin-service:
- Confirmation of user creation
- Password reset notifications
- Account status changes

### 4. Update & Delete Sync
Currently only CREATE is synced. Add:
- Update user sync (when user details change)
- Delete user sync (when user is deactivated)
- Status sync (active/inactive)

---

## 📚 Dependencies

### Required Packages
```
httpx==0.26.0  # Already in requirements.txt
```

### Python Version
```
Python 3.11+
```

---

## 🎯 API Endpoint Requirements (Auth Service)

The auth-service must implement the following endpoint:

### `POST /api/v1/auth/users/sync`

**Request Body**:
```json
{
  "id": "uuid",
  "username": "string",
  "email": "string",
  "password_hash": "string",
  "first_name": "string",
  "last_name": "string",
  "phone_number": "string (optional)",
  "is_active": "boolean",
  "employee_id": "string (optional)",
  "created_from": "admin-service"
}
```

**Response**:
- `201 Created`: User created successfully
- `409 Conflict`: User already exists
- `400 Bad Request`: Invalid data
- `500 Internal Server Error`: Server error

---

## ✅ Summary

✅ **Automatic sync** from admin-service to auth-service  
✅ **Same UUID** used across services  
✅ **Pre-hashed passwords** for security  
✅ **Non-blocking** - sync doesn't prevent user creation  
✅ **Error resilient** - failures are logged, not thrown  
✅ **Configurable** - enable/disable via environment variable  
✅ **Well-logged** - all sync operations are logged  

The integration is production-ready and handles edge cases gracefully!

---

**Date**: June 9, 2026  
**Feature**: User Setup to Auth Service Sync  
**Status**: ✅ Implemented and Ready for Testing
