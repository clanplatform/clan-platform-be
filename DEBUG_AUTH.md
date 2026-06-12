# Authentication Debug Guide

## Current Situation
You're getting `401 Unauthorized` with "Could not validate credentials" when calling admin service endpoints.

## Step-by-Step Debugging

### Step 1: Verify the Token You're Using

First, let's see what token you have. Run this command to test your token:

```bash
cd services/admin-service
python test_jwt.py "YOUR_TOKEN_HERE"
```

Replace `YOUR_TOKEN_HERE` with the actual JWT token you're using.

This will show you:
- Token algorithm (should be HS256)
- Token claims (user info)
- Expiration time
- Whether the token can be verified with the current SECRET_KEY

### Step 2: Check if Admin Service Restarted

The admin service needs to be restarted after changing `.env.local` for the new SECRET_KEY to take effect.

**Check which Python process is the admin service:**
```powershell
Get-Process python | ForEach-Object { 
    $_.Id, $_.StartTime, (Get-NetTCPConnection -OwningProcess $_.Id -LocalPort 8000 -ErrorAction SilentlyContinue).LocalPort 
}
```

**Restart the service:**
1. Stop the current admin service (Ctrl+C in the terminal running it, or kill the process)
2. Start it again:
```bash
cd services/admin-service
python -m uvicorn app.main:app --reload --port 8000
```

### Step 3: Watch the Logs

With the improved logging, you should see detailed messages in the console when authentication fails:

```
[AUTH] get_current_user called
[AUTH] Token received (first 20 chars): eyJhbGciOiJIUzI1NiI...
[JWT] Using HS256 shared secret verification
[JWT] Algorithm: HS256
[JWT] Secret key (first 10 chars): your-jwt-s...
[JWT] Token validation error: JWTError: Signature verification failed
```

### Step 4: Common Issues

#### Issue 1: Token Not Provided
**Log:** `[AUTH] No credentials provided`
**Solution:** Make sure your request includes the Authorization header:
```
Authorization: Bearer YOUR_TOKEN_HERE
```

#### Issue 2: Secret Key Mismatch
**Log:** `[JWT] Token validation error: JWTError: Signature verification failed`
**Solution:** The SECRET_KEY in admin service doesn't match the auth service
- Admin service: `config/environments/.env.local` → SECRET_KEY
- Auth service: Check what key was used to sign the token

#### Issue 3: Token Expired
**Log:** `[JWT] Token expired`
**Solution:** Get a fresh token from the auth service

#### Issue 4: Service Not Restarted
**Problem:** Changed .env.local but service still uses old config
**Solution:** Restart the admin service

### Step 5: Test with Curl

Test the authentication with curl to isolate the issue:

```bash
# Get a fresh token from auth service
curl -X POST http://localhost:8001/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username": "your-username", "password": "your-password"}'

# This will return something like:
# {"access_token": "eyJhbG...", "token_type": "bearer"}

# Use the token with admin service
curl -X GET "http://localhost:8000/api/v1/domains?skip=0&limit=100" \
  -H "Authorization: Bearer eyJhbG..."
```

### Step 6: Verify Config is Loaded

Check if the admin service is actually loading the correct SECRET_KEY:

When the service starts, you should see in the logs:
```
[JWT] Secret key (first 10 chars): your-jwt-s...
```

This should match the first 10 characters of:
```
your-jwt-secret-key-change-in-production
```

If it shows something different, the service hasn't picked up the new config.

## Quick Test Checklist

- [ ] SECRET_KEY in admin service .env.local = `your-jwt-secret-key-change-in-production`
- [ ] Admin service has been restarted after config change
- [ ] Token is not expired (check with test_jwt.py)
- [ ] Authorization header is included in request: `Authorization: Bearer TOKEN`
- [ ] Token was issued by the auth service running on localhost:8001
- [ ] Both services use HS256 algorithm

## Still Not Working?

If you've verified all the above and it still doesn't work, please provide:

1. Output from `python test_jwt.py "YOUR_TOKEN"`
2. Logs from admin service console when you make the request
3. How you're making the request (Postman, curl, browser, etc.)
4. The exact Authorization header you're sending
