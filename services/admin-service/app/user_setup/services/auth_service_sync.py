"""
Service for syncing user data with the Identity Domain Auth Service
"""
import httpx
from typing import Dict, Any, Optional
from uuid import UUID
import logging
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)


class AuthServiceSyncError(Exception):
    """Custom exception for auth service sync errors"""
    pass


class AuthServiceSync:
    """
    Service for syncing user setup data with the Identity Domain Auth Service.
    Creates auth_users records in the clan-identity-domain auth-service database.
    """

    @staticmethod
    def _get_auth_service_url() -> str:
        """Get and validate the auth service URL"""
        if not settings.IDENTITY_SERVICE_URL:
            raise AuthServiceSyncError(
                "IDENTITY_SERVICE_URL is not configured. "
                "Please set it in your environment variables."
            )
        return settings.IDENTITY_SERVICE_URL.rstrip('/')

    @staticmethod
    async def create_auth_user(
        user_id: UUID,
        user_setup_id: UUID,  # Added: parent user_setup ID
        username: str,
        email: str,
        password_hash: str,
        firstname: str,
        lastname: str,
        phone_number: Optional[str] = None,
        is_active: bool = True,
        employee_id: Optional[str] = None,
        is_password_change: bool = False,
        tenant_id: Optional[UUID] = None,
        can_change_password: bool = True
    ) -> Dict[str, Any]:
        """
        Create a user in the auth-service auth_users table.
        
        Args:
            user_id: UUID from admin-service user_setup_basic table
            username: Username for authentication
            email: Email address
            password_hash: Bcrypt hashed password
            firstname: First name
            lastname: Last name
            phone_number: Optional phone number
            is_active: User active status (default: True)
            employee_id: Optional employee ID
            
        Returns:
            Response from auth-service
            
        Raises:
            AuthServiceSyncError: If sync fails
        """
        try:
            auth_service_url = AuthServiceSync._get_auth_service_url()
            
            # Prepare payload for auth-service
            # Auth-service uses 'status' field, not 'is_active'
            payload = {
                "id": str(user_id),  # Use the same UUID from admin-service
                "user_setup_id": str(user_setup_id),  # Parent user_setup ID
                "username": username,
                "email": email,
                "password_hash": password_hash,  # Pass the already hashed password
                "firstname": firstname,  # No underscore!
                "lastname": lastname,   # No underscore!
                "phone_number": phone_number,
                "status": "active" if is_active else "inactive",  # Map is_active to status
                "employee_id": employee_id,
                # False = force password change on first login; True = log in directly
                "is_password_change": is_password_change,
                # True → first-login password-change flow; False → straight to the app
                "can_change_password": can_change_password,
                # Tenant context — auth-service uses it to validate tenant logins
                # and resolve the post-login redirect (tenants.allowed_origins)
                "tenant_id": str(tenant_id) if tenant_id else None,
                "created_from": "admin-service"  # Track the source
            }
            
            # Remove None values
            payload = {k: v for k, v in payload.items() if v is not None}
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{auth_service_url}/api/v1/auth/users/sync",
                    json=payload
                )
                
                if response.status_code in [200, 201]:  # Accept both 200 and 201
                    logger.info(f"Successfully synced user {username} (ID: {user_id}) to auth-service")
                    return response.json()
                elif response.status_code == 409:
                    # User already exists in auth-service
                    logger.warning(f"User {username} already exists in auth-service")
                    return {"status": "already_exists", "user_id": str(user_id)}
                else:
                    error_detail = response.text
                    logger.error(f"Failed to sync user to auth-service: {response.status_code} - {error_detail}")
                    raise AuthServiceSyncError(
                        f"Auth service returned status {response.status_code}: {error_detail}"
                    )
                    
        except httpx.TimeoutException:
            logger.error(f"Timeout while syncing user {username} to auth-service")
            raise AuthServiceSyncError("Auth service request timed out")
        except httpx.RequestError as e:
            logger.error(f"Request error while syncing user {username} to auth-service: {str(e)}")
            raise AuthServiceSyncError(f"Failed to connect to auth service: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error while syncing user {username} to auth-service: {str(e)}")
            raise AuthServiceSyncError(f"Unexpected error during sync: {str(e)}")

    @staticmethod
    async def update_auth_user(
        user_id: UUID,
        username: Optional[str] = None,
        email: Optional[str] = None,
        password_hash: Optional[str] = None,
        firstname: Optional[str] = None,
        lastname: Optional[str] = None,
        phone_number: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Update a user in the auth-service auth_users table.
        
        Args:
            user_id: UUID of the user
            username: Optional updated username
            email: Optional updated email
            password_hash: Optional updated password hash
            firstname: Optional updated first name
            lastname: Optional updated last name
            phone_number: Optional updated phone number
            is_active: Optional updated active status
            
        Returns:
            Response from auth-service
            
        Raises:
            AuthServiceSyncError: If sync fails
        """
        try:
            auth_service_url = AuthServiceSync._get_auth_service_url()
            
            # Prepare payload with only provided fields
            payload = {}
            if username is not None:
                payload["username"] = username
            if email is not None:
                payload["email"] = email
            if password_hash is not None:
                payload["password_hash"] = password_hash
            if firstname is not None:
                payload["firstname"] = firstname
            if lastname is not None:
                payload["lastname"] = lastname
            if phone_number is not None:
                payload["phone_number"] = phone_number
            if is_active is not None:
                payload["is_active"] = is_active
            
            if not payload:
                logger.info(f"No fields to update for user {user_id} in auth-service")
                return {"status": "no_changes"}
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.put(
                    f"{auth_service_url}/api/v1/auth/users/{user_id}/sync",
                    json=payload
                )
                
                if response.status_code == 200:
                    logger.info(f"Successfully updated user {user_id} in auth-service")
                    return response.json()
                elif response.status_code == 404:
                    logger.warning(f"User {user_id} not found in auth-service")
                    return {"status": "not_found", "user_id": str(user_id)}
                else:
                    error_detail = response.text
                    logger.error(f"Failed to update user in auth-service: {response.status_code} - {error_detail}")
                    raise AuthServiceSyncError(
                        f"Auth service returned status {response.status_code}: {error_detail}"
                    )
                    
        except httpx.TimeoutException:
            logger.error(f"Timeout while updating user {user_id} in auth-service")
            raise AuthServiceSyncError("Auth service request timed out")
        except httpx.RequestError as e:
            logger.error(f"Request error while updating user {user_id} in auth-service: {str(e)}")
            raise AuthServiceSyncError(f"Failed to connect to auth service: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error while updating user {user_id} in auth-service: {str(e)}")
            raise AuthServiceSyncError(f"Unexpected error during sync: {str(e)}")

    @staticmethod
    async def delete_auth_user(user_id: UUID) -> Dict[str, Any]:
        """
        Delete a user from the auth-service auth_users table.
        
        Args:
            user_id: UUID of the user to delete
            
        Returns:
            Response from auth-service
            
        Raises:
            AuthServiceSyncError: If sync fails
        """
        try:
            auth_service_url = AuthServiceSync._get_auth_service_url()
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.delete(
                    f"{auth_service_url}/api/v1/auth/users/{user_id}/sync"
                )
                
                if response.status_code in (200, 204):
                    logger.info(f"Successfully deleted user {user_id} from auth-service")
                    return {"status": "deleted", "user_id": str(user_id)}
                elif response.status_code == 404:
                    logger.warning(f"User {user_id} not found in auth-service")
                    return {"status": "not_found", "user_id": str(user_id)}
                else:
                    error_detail = response.text
                    logger.error(f"Failed to delete user from auth-service: {response.status_code} - {error_detail}")
                    raise AuthServiceSyncError(
                        f"Auth service returned status {response.status_code}: {error_detail}"
                    )
                    
        except httpx.TimeoutException:
            logger.error(f"Timeout while deleting user {user_id} from auth-service")
            raise AuthServiceSyncError("Auth service request timed out")
        except httpx.RequestError as e:
            logger.error(f"Request error while deleting user {user_id} from auth-service: {str(e)}")
            raise AuthServiceSyncError(f"Failed to connect to auth service: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error while deleting user {user_id} from auth-service: {str(e)}")
            raise AuthServiceSyncError(f"Unexpected error during sync: {str(e)}")

    @staticmethod
    def sync_enabled() -> bool:
        """Check if auth service sync is enabled"""
        return bool(settings.IDENTITY_SERVICE_URL)
