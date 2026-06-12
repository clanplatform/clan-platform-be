"""
Authentication and security utilities
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password string
        
    Note:
        bcrypt has a 72-byte limit. Passwords longer than 72 bytes are automatically truncated.
    """
    # Convert password to bytes and truncate to 72 bytes (bcrypt limitation)
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    # Generate salt and hash
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against
        
    Returns:
        True if password matches, False otherwise
        
    Note:
        bcrypt has a 72-byte limit. Passwords longer than 72 bytes are automatically truncated.
    """
    # Convert password to bytes and truncate to 72 bytes (bcrypt limitation)
    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    
    # Convert hashed password to bytes if it's a string
    if isinstance(hashed_password, str):
        hashed_password = hashed_password.encode('utf-8')
    
    # Verify password
    return bcrypt.checkpw(password_bytes, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Dictionary of claims to encode in the token
        expires_delta: Optional expiration time delta
        
    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT access token.
    Supports both HS256 (shared secret) and RS256 (public key) algorithms.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        # Determine the key to use for verification
        if settings.JWT_ALGORITHM.startswith("RS") and settings.JWT_PUBLIC_KEY:
            # Use public key for RS256/RS384/RS512
            key = settings.JWT_PUBLIC_KEY
            print(f"[JWT] Using RS256 public key verification")
        else:
            # Use shared secret for HS256/HS384/HS512
            key = settings.SECRET_KEY
            print(f"[JWT] Using HS256 shared secret verification")
            print(f"[JWT] Algorithm: {settings.JWT_ALGORITHM}")
            print(f"[JWT] Secret key (first 10 chars): {key[:10]}...")
        
        payload = jwt.decode(token, key, algorithms=[settings.JWT_ALGORITHM])
        print(f"[JWT] Token decoded successfully. User: {payload.get('sub')}")
        return payload
    except jwt.ExpiredSignatureError as e:
        print(f"[JWT] Token expired: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTClaimsError as e:
        print(f"[JWT] Invalid token claims: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token claims",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as e:
        print(f"[JWT] Token validation error: {type(e).__name__}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {type(e).__name__}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """
    Dependency to get the current authenticated user ID.
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        User ID extracted from the token
        
    Raises:
        HTTPException: If credentials are missing or invalid
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    payload = decode_access_token(token)
    
    # Support both 'sub' (JWT standard) and 'user_id' (custom claim)
    user_id: str = payload.get("sub") or payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials - missing user identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_id


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """
    Dependency to get the current authenticated user object.
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        User object/dict extracted from the token
        
    Raises:
        HTTPException: If credentials are missing or invalid
    """
    print(f"[AUTH] get_current_user called")
    
    if not credentials:
        print(f"[AUTH] No credentials provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    print(f"[AUTH] Token received (first 20 chars): {token[:20]}...")
    
    payload = decode_access_token(token)
    
    # Support both 'sub' (JWT standard) and 'user_id' (custom claim)
    user_id: str = payload.get("sub") or payload.get("user_id")
    if user_id is None:
        print(f"[AUTH] Token payload missing both 'sub' and 'user_id' fields. Payload keys: {list(payload.keys())}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials - missing user identifier",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Return user principal object with all available claims
    user = {
        "id": user_id,
        "user_id": payload.get("user_id"),  # Keep original user_id if present
        "username": payload.get("username"),
        "email": payload.get("email"),
        "roles": payload.get("roles", []),
        "user_setup_id": payload.get("user_setup_id")  # Include user_setup_id from token
    }
    
    print(f"[AUTH] User authenticated: {user_id} (username: {user.get('username')})")
    
    return user


async def get_optional_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """
    Optional authentication dependency - returns user ID if authenticated, None otherwise.
    Does not raise exception if not authenticated.
    
    Args:
        credentials: HTTP Bearer token credentials
        
    Returns:
        User ID if authenticated, None otherwise
    """
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        payload = decode_access_token(token)
        return payload.get("sub")
    except HTTPException:
        return None
