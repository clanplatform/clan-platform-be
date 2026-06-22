"""
Authentication and security utilities
"""
from datetime import datetime, timedelta
from typing import Optional
import hashlib
import time
import base64

from jose import JWTError, jwt
import bcrypt
import requests as _requests
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

# ---------------------------------------------------------------------------
# JWKS cache — re-fetched every 5 minutes so key rotations are picked up.
# Only used when JWT_PUBLIC_KEY is not set (local dev via JWKS_URI).
# ---------------------------------------------------------------------------
_jwks_cache: dict = {"keys": [], "ts": 0.0}
_JWKS_TTL = 300


def _b64_to_int(b64: str) -> int:
    padded = b64 + "=" * (-len(b64) % 4)
    return int.from_bytes(base64.urlsafe_b64decode(padded), "big")


def _jwk_to_pem(jwk_key: dict) -> str:
    n = _b64_to_int(jwk_key["n"])
    e = _b64_to_int(jwk_key["e"])
    pub = RSAPublicNumbers(e, n).public_key(default_backend())
    return pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()


def _get_rsa_key(token: str) -> str:
    """
    Return the RSA public key (PEM) for verifying `token`.

    Priority:
      1. JWT_PUBLIC_KEY env var  → production, static PEM in .env.prod
      2. JWKS_URI env var        → local dev, auto-fetched from auth-service
    """
    if settings.JWT_PUBLIC_KEY:
        return settings.JWT_PUBLIC_KEY

    if not settings.JWKS_URI:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RS256 requires JWT_PUBLIC_KEY or JWKS_URI to be configured",
        )

    now = time.time()
    if not _jwks_cache["keys"] or now - _jwks_cache["ts"] > _JWKS_TTL:
        try:
            resp = _requests.get(settings.JWKS_URI, timeout=5.0)
            resp.raise_for_status()
            _jwks_cache["keys"] = resp.json().get("keys", [])
            _jwks_cache["ts"] = now
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Unable to fetch JWKS from {settings.JWKS_URI}: {exc}",
            )

    try:
        kid = jwt.get_unverified_header(token).get("kid")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token header")

    for jwk_key in _jwks_cache["keys"]:
        if not kid or jwk_key.get("kid") == kid:
            return _jwk_to_pem(jwk_key)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No matching key found in JWKS — auth-service may have restarted; retry",
    )

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

    Algorithm routing:
      RS256 → _get_rsa_key() (JWT_PUBLIC_KEY in prod, JWKS_URI in local)
      HS256 → SECRET_KEY (shared secret, local dev only)

    Also validates iss/aud when JWT_ISSUER/JWT_AUDIENCE are configured.
    """
    try:
        if settings.JWT_ALGORITHM.startswith("RS"):
            key = _get_rsa_key(token)
        else:
            key = settings.SECRET_KEY

        print(f"[AUTH] decode alg={settings.JWT_ALGORITHM} issuer={settings.JWT_ISSUER} audience={settings.JWT_AUDIENCE} key_prefix={str(key)[:10]}")
        decode_kwargs: dict = {"algorithms": [settings.JWT_ALGORITHM]}
        if settings.JWT_ISSUER:
            decode_kwargs["issuer"] = settings.JWT_ISSUER
        if settings.JWT_AUDIENCE:
            decode_kwargs["audience"] = settings.JWT_AUDIENCE

        payload = jwt.decode(token, key, **decode_kwargs)
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTClaimsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token claims: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {type(e).__name__}: {e}",
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
    
    # Stable per-token session ID: SHA-256 of the raw token (first 32 hex chars)
    session_id = hashlib.sha256(token.encode()).hexdigest()[:32]

    # Return user principal object with all available claims
    user = {
        "id": user_id,
        "user_id": payload.get("user_id"),
        "username": payload.get("username"),
        "email": payload.get("email"),
        "roles": payload.get("roles", []),
        "user_setup_id": payload.get("user_setup_id"),
        "client_id": payload.get("client_id"),
        "session_id": payload.get("jti") or session_id,
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
