# Auth Service Endpoint Specification

## 🎯 Required Endpoint in Auth-Service

The **clan-identity-domain** auth-service must implement the following endpoint to receive user sync data from the admin-service.

---

## Endpoint: Create/Sync User

### `POST /api/v1/auth/users/sync`

Creates or updates a user in the `auth_users` table from admin-service sync.

---

## Request

### Headers
```
Content-Type: application/json
```

### Body Schema
```json
{
  "id": "string (UUID)",               // Required - UUID from admin-service
  "username": "string",                // Required - Unique username
  "email": "string (email)",           // Required - Unique email
  "password_hash": "string",           // Required - Pre-hashed bcrypt password
  "first_name": "string",              // Required
  "last_name": "string",               // Required
  "phone_number": "string",            // Optional
  "is_active": "boolean",              // Required - Default: true
  "employee_id": "string",             // Optional - For tracking
  "created_from": "string"             // Required - Always "admin-service"
}
```

### Example Request
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "username": "john.doe",
  "email": "john.doe@example.com",
  "password_hash": "$2b$12$KIiLx5bXxGd8wH8Xh.123456789012345678901234567890123456",
  "first_name": "John",
  "last_name": "Doe",
  "phone_number": "+1234567890",
  "is_active": true,
  "employee_id": "EMP001",
  "created_from": "admin-service"
}
```

---

## Response

### Success: `201 Created`
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "username": "john.doe",
  "email": "john.doe@example.com",
  "first_name": "John",
  "last_name": "Doe",
  "is_active": true,
  "created_at": "2026-06-09T10:00:00Z",
  "message": "User created successfully"
}
```

### Conflict: `409 Conflict`
When user with same `id`, `username`, or `email` already exists:
```json
{
  "detail": "User with this username already exists",
  "existing_user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### Bad Request: `400 Bad Request`
When validation fails:
```json
{
  "detail": "Validation error",
  "errors": [
    {
      "field": "email",
      "message": "Invalid email format"
    }
  ]
}
```

### Internal Error: `500 Internal Server Error`
```json
{
  "detail": "Internal server error",
  "message": "Failed to create user in database"
}
```

---

## Database Schema: `auth_users` Table

The auth-service should have an `auth_users` table with the following structure:

```sql
CREATE TABLE auth_users (
    id UUID PRIMARY KEY,                           -- From admin-service
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,           -- Bcrypt hash
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    employee_id VARCHAR(50),                       -- Reference to admin-service
    created_from VARCHAR(50) DEFAULT 'admin-service',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    login_count INTEGER DEFAULT 0
);

-- Indexes
CREATE INDEX idx_auth_users_username ON auth_users(username);
CREATE INDEX idx_auth_users_email ON auth_users(email);
CREATE INDEX idx_auth_users_employee_id ON auth_users(employee_id);
CREATE INDEX idx_auth_users_is_active ON auth_users(is_active);
```

---

## Implementation Example (FastAPI)

### Python Model (SQLAlchemy)
```python
from sqlalchemy import Column, String, Boolean, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
import uuid

class AuthUser(Base):
    __tablename__ = "auth_users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone_number = Column(String(20))
    is_active = Column(Boolean, default=True, index=True)
    employee_id = Column(String(50), index=True)
    created_from = Column(String(50), default='admin-service')
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))
    login_count = Column(Integer, default=0)
```

### Pydantic Schema
```python
from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from typing import Optional

class UserSyncCreate(BaseModel):
    id: UUID = Field(..., description="User ID from admin-service")
    username: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password_hash: str = Field(..., description="Pre-hashed bcrypt password")
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone_number: Optional[str] = Field(None, max_length=20)
    is_active: bool = Field(default=True)
    employee_id: Optional[str] = Field(None, max_length=50)
    created_from: str = Field(default="admin-service")
```

### Route Handler
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

router = APIRouter()

@router.post("/api/v1/auth/users/sync", status_code=status.HTTP_201_CREATED)
def sync_user_from_admin_service(
    user_data: UserSyncCreate,
    db: Session = Depends(get_db)
):
    """
    Sync user from admin-service to auth-service.
    Creates a new user in the auth_users table with pre-hashed password.
    """
    try:
        # Check if user already exists
        existing_user = db.query(AuthUser).filter(
            (AuthUser.id == user_data.id) |
            (AuthUser.username == user_data.username) |
            (AuthUser.email == user_data.email)
        ).first()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "User already exists",
                    "existing_user_id": str(existing_user.id)
                }
            )
        
        # Create new user with pre-hashed password
        db_user = AuthUser(
            id=user_data.id,  # Use the same UUID from admin-service
            username=user_data.username,
            email=user_data.email,
            password_hash=user_data.password_hash,  # Already hashed
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            phone_number=user_data.phone_number,
            is_active=user_data.is_active,
            employee_id=user_data.employee_id,
            created_from=user_data.created_from
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        return {
            "id": str(db_user.id),
            "username": db_user.username,
            "email": db_user.email,
            "first_name": db_user.first_name,
            "last_name": db_user.last_name,
            "is_active": db_user.is_active,
            "created_at": db_user.created_at.isoformat(),
            "message": "User synced successfully"
        }
        
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Database constraint violation: {str(e.orig)}"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync user: {str(e)}"
        )
```

---

## Optional: Update Endpoint

### `PUT /api/v1/auth/users/{user_id}/sync`

Updates an existing user (for future use when admin-service updates user details).

### Request Body
```json
{
  "username": "string (optional)",
  "email": "string (optional)",
  "password_hash": "string (optional)",
  "first_name": "string (optional)",
  "last_name": "string (optional)",
  "phone_number": "string (optional)",
  "is_active": "boolean (optional)"
}
```

### Response
- `200 OK`: User updated
- `404 Not Found`: User doesn't exist

---

## Optional: Delete Endpoint

### `DELETE /api/v1/auth/users/{user_id}/sync`

Deletes or deactivates a user (for future use when admin-service deletes users).

### Response
- `200 OK` or `204 No Content`: User deleted/deactivated
- `404 Not Found`: User doesn't exist

---

## Security Considerations

### 1. Password Handling
- ✅ **DO** accept pre-hashed passwords from admin-service
- ✅ **DO** validate the hash format (bcrypt: `$2b$12$...`)
- ❌ **DO NOT** re-hash the password
- ❌ **DO NOT** accept plain-text passwords in this endpoint

### 2. Authentication
- 🔐 Consider adding API key authentication between services
- 🔐 Use internal network or VPN for service-to-service communication
- 🔐 Implement rate limiting to prevent abuse

### 3. Validation
- ✅ Validate all required fields
- ✅ Check email format
- ✅ Check username format (no special characters)
- ✅ Verify UUID format

### 4. Logging
- 📝 Log all sync operations
- 📝 Log failures with details
- 📝 Include source IP and timestamp
- 📝 Track sync source (`created_from` field)

---

## Testing the Endpoint

### cURL Example
```bash
curl -X POST http://localhost:8001/api/v1/auth/users/sync \
  -H "Content-Type: application/json" \
  -d '{
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "username": "test.user",
    "email": "test@example.com",
    "password_hash": "$2b$12$abcdefghijklmnopqrstuvwxyz1234567890123456789012",
    "first_name": "Test",
    "last_name": "User",
    "is_active": true,
    "employee_id": "EMP001",
    "created_from": "admin-service"
  }'
```

### Python Test
```python
import httpx

response = httpx.post(
    "http://localhost:8001/api/v1/auth/users/sync",
    json={
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "username": "test.user",
        "email": "test@example.com",
        "password_hash": "$2b$12$abcd...",
        "first_name": "Test",
        "last_name": "User",
        "is_active": True,
        "employee_id": "EMP001",
        "created_from": "admin-service"
    }
)

print(response.status_code)  # Should be 201
print(response.json())
```

---

## Monitoring & Alerts

### Metrics to Track
- Total sync requests received
- Success rate
- Failure rate (by error type)
- Average response time
- Duplicate user attempts

### Alert Conditions
- Sync success rate < 95%
- Response time > 500ms
- Multiple failed attempts for same user
- Database connection failures

---

## ✅ Checklist for Auth-Service Implementation

- [ ] Create `auth_users` table with proper schema
- [ ] Implement `POST /api/v1/auth/users/sync` endpoint
- [ ] Add validation for all required fields
- [ ] Handle duplicate users gracefully (409 Conflict)
- [ ] Store password_hash without re-hashing
- [ ] Add proper error handling
- [ ] Implement logging for all sync operations
- [ ] Add monitoring/metrics
- [ ] Test with sample data from admin-service
- [ ] Document the endpoint in auth-service API docs
- [ ] (Optional) Add API key authentication
- [ ] (Optional) Implement update and delete endpoints

---

**This specification ensures seamless integration between admin-service and auth-service!**
