from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status
from typing import List, Optional
from uuid import UUID
import asyncio
import logging

from app.user_setup.models.user_setup import UserSetup, UserSetupBasic, UserSetupRolesEntity, UserSetupPreference
from app.user_setup.schemas.user_setup import (
    UserSetupBasicCreate,
    UserSetupBasicUpdate,
    UserSetupRolesEntityCreate,
    UserSetupRolesEntityUpdate,
    UserSetupPreferenceCreate,
    UserSetupPreferenceUpdate,
    UserSetupCreateWithDetails,
    UserSetupListResponse,
    AvailableUsersResponse,
    UserReference
)
from app.core.security import get_password_hash
from app.user_setup.services.auth_service_sync import AuthServiceSync, AuthServiceSyncError

logger = logging.getLogger(__name__)


class UserSetupService:
    """Service class for managing user setup operations"""

    # ============================================================================
    # UserSetupBasic Operations
    # ============================================================================

    @staticmethod
    def create_user_setup(db: Session, user_data: UserSetupBasicCreate) -> UserSetupBasic:
        """Create a new user setup with parent UserSetup record"""
        try:
            # Validate reporting_to if provided
            if user_data.reporting_to:
                manager = db.query(UserSetupBasic).filter(UserSetupBasic.id == user_data.reporting_to).first()
                if not manager:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Manager with ID {user_data.reporting_to} not found. Please create the manager user first or leave reporting_to empty."
                    )

            # Create parent UserSetup record first
            db_user_setup = UserSetup()
            db.add(db_user_setup)
            db.flush()  # Get the ID without committing

            # Hash the password before storing
            user_dict = user_data.model_dump()
            password = user_dict.pop('password')  # Remove password from dict
            password_hash = get_password_hash(password)  # Hash the password

            # Create UserSetupBasic record with reference to parent
            db_user_basic = UserSetupBasic(
                user_setup_id=db_user_setup.id,
                password_hash=password_hash,  # Store hashed password
                **user_dict
            )
            db.add(db_user_basic)
            db.commit()
            db.refresh(db_user_basic)
            return db_user_basic
        except IntegrityError as e:
            db.rollback()
            if "employee_id" in str(e.orig):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Employee ID already exists"
                )
            elif "username" in str(e.orig):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Username already exists"
                )
            elif "email" in str(e.orig):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Email already exists"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to create user setup: {str(e.orig)}"
                )

    @staticmethod
    def get_user_setup(db: Session, user_id: UUID) -> Optional[UserSetupBasic]:
        """Get user setup by ID"""
        user = db.query(UserSetupBasic).filter(UserSetupBasic.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User setup with ID {user_id} not found"
            )
        return user

    @staticmethod
    def get_user_setup_with_details(db: Session, user_id: UUID) -> UserSetupBasic:
        """Get user setup with all related data (roles, entities, preferences)"""
        # First get the UserSetupBasic record
        user_basic = db.query(UserSetupBasic).filter(UserSetupBasic.id == user_id).first()

        if not user_basic:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User setup with ID {user_id} not found"
            )

        # Load the parent UserSetup with all relationships
        user_setup = db.query(UserSetup).options(
            joinedload(UserSetup.basic),
            joinedload(UserSetup.roles_entities),
            joinedload(UserSetup.preferences)
        ).filter(UserSetup.id == user_basic.user_setup_id).first()

        # Return the basic record (relationships are accessible via user_basic.user_setup)
        return user_basic

    @staticmethod
    def get_all_user_setups(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        status_filter: Optional[str] = None,
        department_filter: Optional[UUID] = None
    ) -> UserSetupListResponse:
        """Get all user setups with pagination and filtering"""
        query = db.query(UserSetupBasic)
        
        # Apply filters
        if status_filter:
            query = query.filter(UserSetupBasic.status == status_filter)
        if department_filter:
            query = query.filter(UserSetupBasic.department == department_filter)
        
        total = query.count()
        users = query.offset(skip).limit(limit).all()
        
        return UserSetupListResponse(
            total=total,
            users=users,
            page=skip // limit + 1 if limit > 0 else 1,
            page_size=limit
        )

    @staticmethod
    def update_user_setup(db: Session, user_id: UUID, user_data: UserSetupBasicUpdate) -> UserSetupBasic:
        """Update user setup"""
        db_user = UserSetupService.get_user_setup(db, user_id)

        try:
            update_data = user_data.model_dump(exclude_unset=True)

            # Validate reporting_to if being updated
            if "reporting_to" in update_data and update_data["reporting_to"]:
                # Prevent self-reference
                if update_data["reporting_to"] == user_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="A user cannot report to themselves"
                    )

                manager = db.query(UserSetupBasic).filter(UserSetupBasic.id == update_data["reporting_to"]).first()
                if not manager:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Manager with ID {update_data['reporting_to']} not found"
                    )

            # Hash password if being updated
            if "password" in update_data:
                password = update_data.pop('password')
                update_data['password_hash'] = get_password_hash(password)

            for field, value in update_data.items():
                setattr(db_user, field, value)

            db.commit()
            db.refresh(db_user)
            return db_user
        except IntegrityError as e:
            db.rollback()
            if "employee_id" in str(e.orig):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Employee ID already exists"
                )
            elif "username" in str(e.orig):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Username already exists"
                )
            elif "email" in str(e.orig):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Email already exists"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to update user setup: {str(e.orig)}"
                )

    @staticmethod
    def delete_user_setup(db: Session, user_id: UUID) -> dict:
        """Delete user setup (cascades to roles_entities and preferences)"""
        db_user = UserSetupService.get_user_setup(db, user_id)
        
        db.delete(db_user)
        db.commit()
        return {"message": f"User setup {user_id} deleted successfully"}

    # ============================================================================
    # UserSetupRolesEntity Operations
    # ============================================================================

    @staticmethod
    def create_roles_entity(db: Session, roles_entity_data: UserSetupRolesEntityCreate) -> UserSetupRolesEntity:
        """Create roles and entities assignment for a user"""
        # Verify user_setup exists
        db_user_setup = db.query(UserSetup).filter(UserSetup.id == roles_entity_data.user_setup_id).first()
        if not db_user_setup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User setup with ID {roles_entity_data.user_setup_id} not found"
            )

        try:
            db_roles_entity = UserSetupRolesEntity(**roles_entity_data.model_dump())
            db.add(db_roles_entity)
            db.commit()
            db.refresh(db_roles_entity)
            return db_roles_entity
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create roles/entities assignment: {str(e.orig)}"
            )

    @staticmethod
    def get_roles_entities_by_user(db: Session, user_id: UUID) -> List[UserSetupRolesEntity]:
        """Get all roles and entities assignments for a user (user_id is UserSetupBasic.id)"""
        # Get the user_setup_id from UserSetupBasic
        db_user_basic = UserSetupService.get_user_setup(db, user_id)
        return db.query(UserSetupRolesEntity).filter(UserSetupRolesEntity.user_setup_id == db_user_basic.user_setup_id).all()

    @staticmethod
    def update_roles_entity(db: Session, roles_entity_id: UUID, roles_entity_data: UserSetupRolesEntityUpdate) -> UserSetupRolesEntity:
        """Update roles and entities assignment"""
        db_roles_entity = db.query(UserSetupRolesEntity).filter(UserSetupRolesEntity.id == roles_entity_id).first()
        if not db_roles_entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Roles/entities assignment with ID {roles_entity_id} not found"
            )
        
        try:
            update_data = roles_entity_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_roles_entity, field, value)
            
            db.commit()
            db.refresh(db_roles_entity)
            return db_roles_entity
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update roles/entities assignment: {str(e.orig)}"
            )

    @staticmethod
    def delete_roles_entity(db: Session, roles_entity_id: UUID) -> dict:
        """Delete roles and entities assignment"""
        db_roles_entity = db.query(UserSetupRolesEntity).filter(UserSetupRolesEntity.id == roles_entity_id).first()
        if not db_roles_entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Roles/entities assignment with ID {roles_entity_id} not found"
            )
        
        db.delete(db_roles_entity)
        db.commit()
        return {"message": f"Roles/entities assignment {roles_entity_id} deleted successfully"}

    # ============================================================================
    # UserSetupPreference Operations
    # ============================================================================

    @staticmethod
    def create_preference(db: Session, preference_data: UserSetupPreferenceCreate) -> UserSetupPreference:
        """Create user preferences"""
        # Verify user_setup exists
        db_user_setup = db.query(UserSetup).filter(UserSetup.id == preference_data.user_setup_id).first()
        if not db_user_setup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User setup with ID {preference_data.user_setup_id} not found"
            )

        try:
            db_preference = UserSetupPreference(**preference_data.model_dump())
            db.add(db_preference)
            db.commit()
            db.refresh(db_preference)
            return db_preference
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create user preferences: {str(e.orig)}"
            )

    @staticmethod
    def get_preferences_by_user(db: Session, user_id: UUID) -> List[UserSetupPreference]:
        """Get all preferences for a user (user_id is UserSetupBasic.id)"""
        # Get the user_setup_id from UserSetupBasic
        db_user_basic = UserSetupService.get_user_setup(db, user_id)
        return db.query(UserSetupPreference).filter(UserSetupPreference.user_setup_id == db_user_basic.user_setup_id).all()

    @staticmethod
    def update_preference(db: Session, preference_id: UUID, preference_data: UserSetupPreferenceUpdate) -> UserSetupPreference:
        """Update user preferences"""
        db_preference = db.query(UserSetupPreference).filter(UserSetupPreference.id == preference_id).first()
        if not db_preference:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User preference with ID {preference_id} not found"
            )
        
        try:
            update_data = preference_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_preference, field, value)
            
            db.commit()
            db.refresh(db_preference)
            return db_preference
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to update user preferences: {str(e.orig)}"
            )

    @staticmethod
    def delete_preference(db: Session, preference_id: UUID) -> dict:
        """Delete user preferences"""
        db_preference = db.query(UserSetupPreference).filter(UserSetupPreference.id == preference_id).first()
        if not db_preference:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User preference with ID {preference_id} not found"
            )

        db.delete(db_preference)
        db.commit()
        return {"message": f"User preference {preference_id} deleted successfully"}

    # ============================================================================
    # Combined Operations
    # ============================================================================

    @staticmethod
    def create_user_setup_with_details(db: Session, user_data: UserSetupCreateWithDetails) -> UserSetupBasic:
        """Create a user setup with roles, entities, and preferences in one transaction"""
        try:
            # Validate reporting_to if provided
            if user_data.basic.reporting_to:
                manager = db.query(UserSetupBasic).filter(UserSetupBasic.id == user_data.basic.reporting_to).first()
                if not manager:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Manager with ID {user_data.basic.reporting_to} not found. Please create the manager user first or leave reporting_to empty."
                    )

            # Create parent UserSetup record first
            db_user_setup = UserSetup()
            db.add(db_user_setup)
            db.flush()  # Get the ID without committing

            # Hash the password before storing
            user_dict = user_data.basic.model_dump()
            password = user_dict.pop('password')  # Remove password from dict
            password_hash = get_password_hash(password)  # Hash the password

            # Create basic user setup with reference to parent
            db_user_basic = UserSetupBasic(
                user_setup_id=db_user_setup.id,
                password_hash=password_hash,  # Store hashed password
                **user_dict
            )
            db.add(db_user_basic)
            db.flush()  # Get the ID without committing

            # Create roles and entities assignment if provided
            if user_data.roles_entities:
                db_roles_entity = UserSetupRolesEntity(
                    user_setup_id=db_user_setup.id,
                    usersetup_basic_id=db_user_basic.id,
                    **user_data.roles_entities.model_dump()
                )
                db.add(db_roles_entity)
                db.flush()  # Get the ID for preferences

            # Create preferences if provided
            if user_data.preferences:
                # Get the roles_entity record to link to preferences
                roles_entity_id = db_roles_entity.id if user_data.roles_entities else None
                if not roles_entity_id:
                    # If no roles_entities provided, create a default one
                    db_roles_entity = UserSetupRolesEntity(
                        user_setup_id=db_user_setup.id,
                        usersetup_basic_id=db_user_basic.id,
                        assigned_roles=None,
                        assigned_entities=None
                    )
                    db.add(db_roles_entity)
                    db.flush()
                    roles_entity_id = db_roles_entity.id

                db_preference = UserSetupPreference(
                    user_setup_id=db_user_setup.id,
                    usersetup_roles_entity_id=roles_entity_id,
                    usersetup_basic_id=db_user_basic.id,
                    **user_data.preferences.model_dump()
                )
                db.add(db_preference)

            # Commit the transaction to admin-service database
            db.commit()
            db.refresh(db_user_basic)
            
            # Sync with auth-service (async operation)
            if AuthServiceSync.sync_enabled():
                try:
                    # Run the async sync operation
                    sync_result = asyncio.run(AuthServiceSync.create_auth_user(
                        user_id=db_user_basic.id,
                        username=db_user_basic.username,
                        email=db_user_basic.email,
                        password_hash=password_hash,
                        firstname=db_user_basic.firstname,
                        lastname=db_user_basic.lastname,
                        phone_number=db_user_basic.phone_number,
                        is_active=(db_user_basic.status == 'active'),
                        employee_id=db_user_basic.employee_id
                    ))
                    logger.info(f"User {db_user_basic.username} synced to auth-service: {sync_result}")
                except AuthServiceSyncError as e:
                    # Log the error but don't fail the user creation
                    logger.error(f"Failed to sync user {db_user_basic.username} to auth-service: {str(e)}")
                    logger.warning("User created in admin-service but not synced to auth-service. Manual sync may be required.")
            else:
                logger.info("Auth service sync is disabled (IDENTITY_SERVICE_URL not configured)")
            
            return UserSetupService.get_user_setup_with_details(db, db_user_basic.id)
        except IntegrityError as e:
            db.rollback()
            if "employee_id" in str(e.orig):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Employee ID already exists"
                )
            elif "username" in str(e.orig):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Username already exists"
                )
            elif "email" in str(e.orig):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Email already exists"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to create user setup: {str(e.orig)}"
                )

    @staticmethod
    def get_available_users(db: Session, status_filter: Optional[str] = 'active') -> AvailableUsersResponse:
        """Get all available users for dropdowns/references"""
        query = db.query(UserSetupBasic)

        if status_filter:
            query = query.filter(UserSetupBasic.status == status_filter)

        users = query.all()
        user_refs = [
            UserReference(
                id=user.id,
                username=user.username,
                firstname=user.firstname,
                lastname=user.lastname,
                email=user.email,
                status=user.status
            )
            for user in users
        ]

        return AvailableUsersResponse(users=user_refs)

