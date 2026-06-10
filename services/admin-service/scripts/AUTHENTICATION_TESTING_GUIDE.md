# Authentication Bypass for Swagger Testing

## Overview
Authentication has been temporarily disabled for all APIs in the admin-service to facilitate Swagger UI testing.

## What Was Changed

### 1. Core Security Module (`app/core/security.py`)
- Added a global flag: `DISABLE_AUTH_FOR_TESTING = True`
- Modified three authentication functions to bypass authentication when the flag is enabled:
  - `get_current_user_id()` - Returns a test user ID: `"test-user-id-123"`
  - `get_current_user()` - Returns a test user object with admin and user roles
  - The functions already had `get_optional_user_id()` which was optional by design

### 2. Menu Navigation Route (`app/api/v1/routes/navigation/menu.py`)
- Fixed missing `verify_token` function (was undefined, now uses `decode_access_token`)
- Added authentication bypass for the `/login-user-menus` endpoint
- Made credentials parameter optional when auth is disabled
- Returns test user data when authentication is bypassed

## How to Use Swagger UI

### Access Swagger Documentation
1. Start the admin-service
2. Open your browser and navigate to: `http://localhost:8000/docs`
3. All API endpoints are now accessible without authentication

### Testing APIs
- No Bearer token is required
- Simply click "Try it out" on any endpoint
- Fill in the required parameters
- Click "Execute" to test the API

## Test User Details (When Auth is Disabled)

```json
{
  "id": "test-user-id-123",
  "username": "test_user",
  "email": "test@example.com",
  "roles": ["admin", "user"]
}
```

For the `/login-user-menus` endpoint:
- Email: `test@example.com`
- Username: `test_user`
- These will be used to look up an actual user in the database

## How to Re-Enable Authentication

When you're done testing and want to re-enable authentication:

### Step 1: Edit `app/core/security.py`
Change line 17 from:
```python
DISABLE_AUTH_FOR_TESTING = True
```
to:
```python
DISABLE_AUTH_FOR_TESTING = False
```

### Step 2: Restart the Service
Restart the admin-service for the changes to take effect.

## Security Warning

⚠️ **IMPORTANT**: This configuration is for **DEVELOPMENT/TESTING ONLY**

- **DO NOT** deploy this to production with `DISABLE_AUTH_FOR_TESTING = True`
- **DO NOT** commit this change to the main branch without changing it back to `False`
- Always ensure authentication is properly configured before deploying to any environment

## Files Modified

1. `services/admin-service/app/core/security.py`
   - Added `DISABLE_AUTH_FOR_TESTING` flag
   - Modified `get_current_user_id()` function
   - Modified `get_current_user()` function

2. `services/admin-service/app/api/v1/routes/navigation/menu.py`
   - Fixed `verify_token` bug (replaced with `decode_access_token`)
   - Added import for `DISABLE_AUTH_FOR_TESTING` flag
   - Modified `get_login_user_menus()` endpoint to support auth bypass
   - Made credentials parameter optional

## Verification

To verify authentication is disabled:
1. Open Swagger UI: `http://localhost:8000/docs`
2. Try any endpoint (e.g., GET `/api/v1/domains`)
3. The endpoint should work without requiring a Bearer token
4. Check the server logs - you should see "Authentication is DISABLED for testing" messages

## Rollback Instructions

If you need to quickly rollback these changes:

```bash
# Revert the security.py file
git checkout services/admin-service/app/core/security.py

# Revert the menu.py file (contains the verify_token fix)
# Note: You may want to keep the bug fix, only revert the bypass logic
git checkout services/admin-service/app/api/v1/routes/navigation/menu.py
```

## Additional Notes

- The authentication bypass affects **ALL** API endpoints that use the authentication dependencies
- Redis caching and database connections remain fully functional
- All business logic remains unchanged
- Only the authentication check is bypassed
