from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

security = HTTPBearer(auto_error=False)


def decode_access_token(token: str) -> dict:
    try:
        key = settings.JWT_PUBLIC_KEY if (
            settings.JWT_ALGORITHM.startswith("RS") and settings.JWT_PUBLIC_KEY
        ) else settings.SECRET_KEY
        return jwt.decode(token, key, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired")
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_access_token(credentials.credentials)
    user_id: str = payload.get("sub") or payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token claims")

    return {
        "user_id": payload.get("user_id"),
        "id": user_id,
        "username": payload.get("username"),
        "email": payload.get("email"),
        "roles": payload.get("roles", []),
    }
