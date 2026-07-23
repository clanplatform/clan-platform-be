# JWT Token Authentication Troubleshooting Guide

## Problem: "Could not validate credentials" Error

When you receive a 401 error with "Could not validate credentials", it means the JWT token validation is failing. Here's how to fix it:

## Root Cause

The **SECRET_KEY** used by the admin-service to verify JWT tokens **MUST MATCH** the secret key used by your identity/auth service to sign the tokens.

## Solution Steps

### 1. Find Your Auth Service's Secret Key

Your auth/identity service (likely running on port 8001 based on `.env.local`) is signing JWT tokens with a specific secret key.

**Option A: Check Identity Service .env file**
```bash
# Look for the identity/auth service .env file
# Common locations:
# - clan-identity-domain/.env.local
# - services/identity-service/.env.local
# - services/auth-service/.env.local

# Find the JWT_SECRET_KEY or SECRET_KEY value
```

**Option B: Check with your team**
Ask the team managing the identity/auth service for the JWT secret key.

### 2. Update Admin Service Secret Key

Edit: `config/environments/.env.local`

```env
# BEFORE (default placeholder)
SECRET_KEY=your-jwt-secret-key-change-in-production

# AFTER (replace with actual secret from identity service)
SECRET_KEY=<actual-secret-key-from-identity-service>
```

**CRITICAL**: The SECRET_KEY must be **EXACTLY** the same on both services!

### 3. Verify JWT Algorithm Matches

Both services must use the same JWT algorithm:

**Admin Service** (`config/environments/.env.local`):
```env
JWT_ALGORITHM=HS256
```

**Identity Service** (check their config):
```env
JWT_ALGORITHM=HS256  # Must match!
```

### 4. Restart the Admin Service

After updating `.env.local`, restart the service:
```bash
# If running locally
cd services/admin-service
python -m uvicorn app.main:app --reload --port 8000

# If using docker-compose
docker-compose restart admin-service
```

## Verification Steps

### 1. Check Token Structure

Decode your JWT token (without verification) at [jwt.io](https://jwt.io) to see:
- Algorithm used (should be HS256)
- Expiration time
- User claims (sub, username, email, etc.)

### 2. Test Authentication

```bash
# Get a valid token from identity service
curl -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "your-username", "password": "your-password"}'

# Use the token to call admin service
curl -X GET http://localhost:8000/api/v1/applications/ \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### 3. Check Logs

With the improved error logging, check the admin service logs for detailed error messages:

```
[JWT] Using HS256 shared secret verification
[JWT] Algorithm: HS256
[JWT] Secret key (first 10 chars): your-jwt-s...
[JWT] Token validation error: JWTError: Signature verification failed
```

This will tell you exactly what went wrong.

## Common Issues and Solutions

### Issue: "Signature verification failed"
**Cause**: SECRET_KEY mismatch
**Solution**: Ensure both services use the EXACT same SECRET_KEY

### Issue: "Token has expired"
**Cause**: Token is too old
**Solution**: Get a fresh token from the identity service

### Issue: "Invalid token claims"
**Cause**: Token format doesn't match expected structure
**Solution**: Verify the identity service is creating tokens with the correct claims (sub, username, email, roles)

### Issue: Algorithm mismatch
**Cause**: Identity service uses RS256, admin service expects HS256 (or vice versa)
**Solution**: 
- For development: Use HS256 on both services with shared SECRET_KEY
- For production: Use RS256 and set JWT_PUBLIC_KEY in admin service

## Production Configuration (RS256)

For production, you should use RS256 with public/private key pairs:

**Identity Service**:
```env
JWT_ALGORITHM=RS256
JWT_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----...
```

**Admin Service**:
```env
JWT_ALGORITHM=RS256
JWT_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----...
SECRET_KEY=any-random-string-for-other-purposes
```

## Need More Help?

1. Check if the identity/auth service is running: `curl http://localhost:8001/health`
2. Verify you're getting a valid token from the identity service
3. Check the admin service logs for detailed JWT error messages
4. Ensure no proxy/gateway is modifying the Authorization header
