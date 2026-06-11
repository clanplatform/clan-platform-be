"""
Direct Database Sync Service for Identity Domain
Writes user data directly to clan-identity-postgres auth_users table
"""
from uuid import UUID
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
from sqlalchemy.exc import IntegrityError

from app.infrastructure.database.identity_db import get_identity_db, AuthUser

logger = logging.getLogger(__name__)


class IdentityDbSyncError(Exception):
    """Custom exception for identity database sync errors"""
    pass


class IdentityDbSync:
    """
    Service for syncing user setup data directly to identity database.
    Writes to auth_users table in clan-identity-postgres.
    """

    @staticmethod
    def sync_enabled() -> bool:
        """Check if identity database sync is enabled"""
        result = get_identity_db().is_enabled()
        logger.info(f"IDENTITY_DB_SYNC: sync_enabled() called, returning: {result}")
        return result

    @staticmethod
    def create_auth_user(
        user_id: UUID,
        username: str,
        email: str,
        password_hash: str,
        firstname: str,
        lastname: str,
        employee_id: str,
        phone_number: Optional[str] = None,
        status: str = 'active',
        start_date: Optional[Any] = None,
        end_date: Optional[Any] = None,
        tem_employee: bool = False,
        department: Optional[UUID] = None,
        division: Optional[UUID] = None,
        job_code: Optional[UUID] = None,
        manage_roles: Optional[List[UUID]] = None,
        default_dept: Optional[UUID] = None,
        reporting_to: Optional[UUID] = None,
        entities: Optional[List[UUID]] = None,
        default_entity: Optional[UUID] = None,
        view: Optional[str] = None,
        dashboard_view: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a user directly in the identity database auth_users table.
        
        Args:
            user_id: UUID from admin-service usersetup_basic.id
            username: Username for authentication
            email: Email address
            password_hash: Already hashed password
            firstname: First name
            lastname: Last name
            employee_id: Employee ID
            phone_number: Optional phone number
            status: Employment status (default: 'active')
            start_date: Employment start date
            end_date: Employment end date
            tem_employee: Temporary employee flag
            department: Department UUID
            division: Division UUID
            job_code: Job code UUID
            manage_roles: List of role UUIDs
            default_dept: Default department UUID
            reporting_to: Manager's UUID
            entities: List of entity UUIDs
            default_entity: Default entity UUID
            view: View preference
            dashboard_view: Dashboard view preference
            
        Returns:
            Dict with sync status
            
        Raises:
            IdentityDbSyncError: If sync fails
        """
        if not IdentityDbSync.sync_enabled():
            logger.error("IDENTITY_DB_SYNC: create_auth_user called but sync is not enabled!")
            raise IdentityDbSyncError("Identity database sync is not enabled")
        
        logger.info("IDENTITY_DB_SYNC: create_auth_user called")
        logger.info(f"IDENTITY_DB_SYNC: Creating user - ID: {user_id}, Username: {username}, Email: {email}")
        
        try:
            identity_db = get_identity_db()
            logger.info("IDENTITY_DB_SYNC: Got identity_db instance")
            
            with identity_db.get_session() as session:
                logger.info("IDENTITY_DB_SYNC: Session opened successfully")
                # Check if user already exists
                existing_user = session.query(AuthUser).filter(
                    (AuthUser.id == user_id) | 
                    (AuthUser.username == username) | 
                    (AuthUser.email == email) |
                    (AuthUser.employee_id == employee_id)
                ).first()
                
                if existing_user:
                    logger.warning(f"IDENTITY_DB_SYNC: User already exists in identity database: {username}")
                    return {
                        "status": "already_exists",
                        "user_id": str(user_id),
                        "message": "User already exists in identity database"
                    }
                
                logger.info("IDENTITY_DB_SYNC: User does not exist, creating new auth_user...")
                # Create new auth user with all fields
                auth_user = AuthUser(
                    id=user_id,
                    user_setup_id=user_id,  # Same as usersetup_basic.id
                    firstname=firstname,
                    lastname=lastname,
                    employee_id=employee_id,
                    username=username,
                    email=email,
                    phone_number=phone_number,
                    password_hash=password_hash,
                    is_password_change=False,
                    status=status,
                    start_date=start_date,
                    end_date=end_date,
                    tem_employee=tem_employee,
                    department=department,
                    division=division,
                    job_code=job_code,
                    manage_roles=manage_roles,  # Already a list of UUIDs
                    default_dept=default_dept,
                    reporting_to=reporting_to,
                    entities=entities,  # Already a list of UUIDs
                    default_entity=default_entity,
                    view=view,
                    dashboard_view=dashboard_view
                )
                
                session.add(auth_user)
                session.flush()
                
                logger.info(f"IDENTITY_DB_SYNC: Successfully created user {username} (ID: {user_id}) in identity database")
                
                return {
                    "status": "created",
                    "user_id": str(user_id),
                    "username": username,
                    "email": email,
                    "message": "User successfully created in identity database"
                }
                
        except IntegrityError as e:
            logger.error(f"IDENTITY_DB_SYNC: Integrity error while creating user {username}: {str(e)}")
            raise IdentityDbSyncError(f"User with same username, email, or employee_id already exists: {str(e)}")
        except Exception as e:
            logger.error(f"IDENTITY_DB_SYNC: Unexpected error while creating user {username}: {str(e)}")
            logger.error(f"IDENTITY_DB_SYNC: Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"IDENTITY_DB_SYNC: Traceback: {traceback.format_exc()}")
            raise IdentityDbSyncError(f"Failed to create user in identity database: {str(e)}")

    @staticmethod
    def update_auth_user(
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
        Update a user directly in the identity database auth_users table.
        
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
            Dict with sync status
            
        Raises:
            IdentityDbSyncError: If sync fails
        """
        if not IdentityDbSync.sync_enabled():
            raise IdentityDbSyncError("Identity database sync is not enabled")
        
        try:
            identity_db = get_identity_db()
            
            with identity_db.get_session() as session:
                # Find the user
                auth_user = session.query(AuthUser).filter(AuthUser.id == user_id).first()
                
                if not auth_user:
                    logger.warning(f"User {user_id} not found in identity database")
                    return {
                        "status": "not_found",
                        "user_id": str(user_id),
                        "message": "User not found in identity database"
                    }
                
                # Update fields if provided
                updated_fields = []
                if username is not None:
                    auth_user.username = username
                    updated_fields.append("username")
                if email is not None:
                    auth_user.email = email
                    updated_fields.append("email")
                if password_hash is not None:
                    auth_user.password_hash = password_hash
                    updated_fields.append("password")
                if firstname is not None:
                    auth_user.firstname = firstname
                    updated_fields.append("firstname")
                if lastname is not None:
                    auth_user.lastname = lastname
                    updated_fields.append("lastname")
                if phone_number is not None:
                    auth_user.phone_number = phone_number
                    updated_fields.append("phone_number")
                if is_active is not None:
                    auth_user.is_active = is_active
                    updated_fields.append("is_active")
                
                if not updated_fields:
                    logger.info(f"No fields to update for user {user_id} in identity database")
                    return {
                        "status": "no_changes",
                        "user_id": str(user_id),
                        "message": "No fields to update"
                    }
                
                auth_user.updated_at = datetime.utcnow()
                session.flush()
                
                logger.info(f"Successfully updated user {user_id} in identity database: {', '.join(updated_fields)}")
                
                return {
                    "status": "updated",
                    "user_id": str(user_id),
                    "updated_fields": updated_fields,
                    "message": "User successfully updated in identity database"
                }
                
        except IntegrityError as e:
            logger.error(f"Integrity error while updating user {user_id} in identity database: {str(e)}")
            raise IdentityDbSyncError(f"Update failed due to duplicate username or email: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error while updating user {user_id} in identity database: {str(e)}")
            raise IdentityDbSyncError(f"Failed to update user in identity database: {str(e)}")

    @staticmethod
    def delete_auth_user(user_id: UUID) -> Dict[str, Any]:
        """
        Delete a user directly from the identity database auth_users table.
        
        Args:
            user_id: UUID of the user to delete
            
        Returns:
            Dict with sync status
            
        Raises:
            IdentityDbSyncError: If sync fails
        """
        if not IdentityDbSync.sync_enabled():
            raise IdentityDbSyncError("Identity database sync is not enabled")
        
        try:
            identity_db = get_identity_db()
            
            with identity_db.get_session() as session:
                # Find the user
                auth_user = session.query(AuthUser).filter(AuthUser.id == user_id).first()
                
                if not auth_user:
                    logger.warning(f"User {user_id} not found in identity database")
                    return {
                        "status": "not_found",
                        "user_id": str(user_id),
                        "message": "User not found in identity database"
                    }
                
                # Delete the user
                session.delete(auth_user)
                session.flush()
                
                logger.info(f"Successfully deleted user {user_id} from identity database")
                
                return {
                    "status": "deleted",
                    "user_id": str(user_id),
                    "message": "User successfully deleted from identity database"
                }
                
        except Exception as e:
            logger.error(f"Unexpected error while deleting user {user_id} from identity database: {str(e)}")
            raise IdentityDbSyncError(f"Failed to delete user from identity database: {str(e)}")
