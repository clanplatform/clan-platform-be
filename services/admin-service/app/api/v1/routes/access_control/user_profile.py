from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.infrastructure.database.session import get_tenant_db
from app.user_profile.schemas.user_profile import (
    UserProfileCreate,
    UserProfileUpdate,
    UserProfileResponse,
)
from app.user_profile.services import user_profile as user_profile_service
from app.core.security import get_current_user  # Optional auth support
from app.infrastructure.audit_helpers import (
    RISK_SCORE,
    get_client_ip,
    get_audit_org_context,
    get_user_id,
    get_session_id,
)
from app.infrastructure.audit_tenant import fire_audit_log
import uuid

router = APIRouter()


@router.get(
    "/",
    response_model=List[UserProfileResponse],
    summary="List user profiles",
    description="Get all user profiles with pagination.",
)
def list_user_profiles(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
):
    """Get all user profiles with pagination."""
    try:
        profiles = user_profile_service.get_all_user_profiles(db, skip=skip, limit=limit)

        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="READ",
                object_type="UserProfile",
                user_id=get_user_id(current_user),
                tenant_id=tenant_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score="LOW",
            )
        except Exception:
            pass
        return profiles

    except Exception as e:
        print(f"Error getting user profiles: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user profiles: {str(e)}",
        )


@router.get(
    "/by-user/{user_id}",
    response_model=UserProfileResponse,
    summary="Get a user's profile",
    description="Get the profile owned by a specific user (one profile per user).",
)
def get_user_profile_by_user(
    request: Request,
    user_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
):
    """Get the profile owned by a specific user."""
    try:
        profile = user_profile_service.get_user_profile_by_user(db, user_id=user_id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found",
            )
        return profile

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting user profile by user: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user profile: {str(e)}",
        )


@router.get(
    "/{user_profile_id}",
    response_model=UserProfileResponse,
    summary="Get a user profile by ID",
    description="Get a specific user profile by its primary key.",
)
def get_user_profile(
    request: Request,
    user_profile_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
):
    """Get a specific user profile by ID."""
    try:
        profile = user_profile_service.get_user_profile(db, user_profile_id=user_profile_id)
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found",
            )

        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="READ",
                object_type="UserProfile",
                object_id=str(user_profile_id),
                user_id=get_user_id(current_user),
                tenant_id=tenant_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score="LOW",
            )
        except Exception:
            pass
        return profile

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting user profile: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user profile: {str(e)}",
        )


@router.post(
    "/",
    response_model=UserProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user profile",
    description="Create a new user profile. Only one profile is allowed per user.",
)
def create_user_profile(
    request: Request,
    profile_data: UserProfileCreate,
    db: Session = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
):
    """Create a new user profile."""
    try:
        user_id = get_user_id(current_user)
        profile = user_profile_service.create_user_profile(
            db, profile=profile_data, user_id=user_id
        )

        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="CREATE",
                object_type="UserProfile",
                object_id=str(profile.user_profile_id),
                user_id=get_user_id(current_user),
                tenant_id=tenant_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["CREATE"],
                new_values={"user_id": str(profile.user_id)},
            )
        except Exception:
            pass

        return profile

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating user profile: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user profile: {str(e)}",
        )


@router.put(
    "/{user_profile_id}",
    response_model=UserProfileResponse,
    summary="Update a user profile",
    description="Update an existing user profile. Only provided fields are changed.",
)
def update_user_profile(
    request: Request,
    user_profile_id: uuid.UUID,
    profile_data: UserProfileUpdate,
    db: Session = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
):
    """Update a user profile."""
    try:
        user_id = get_user_id(current_user)
        profile = user_profile_service.update_user_profile(
            db, user_profile_id=user_profile_id, profile=profile_data, user_id=user_id
        )

        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="UPDATE",
                object_type="UserProfile",
                object_id=str(user_profile_id),
                user_id=get_user_id(current_user),
                tenant_id=tenant_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["UPDATE"],
                new_values={"user_id": str(profile.user_id)},
            )
        except Exception:
            pass

        return profile

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating user profile: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user profile: {str(e)}",
        )


@router.delete(
    "/{user_profile_id}",
    summary="Delete a user profile",
    description="Soft delete a user profile.",
)
def delete_user_profile(
    request: Request,
    user_profile_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    current_user=Depends(get_current_user),
):
    """Soft delete a user profile."""
    try:
        profile = user_profile_service.get_user_profile(db, user_profile_id=user_profile_id)
        if not profile:
            raise HTTPException(status_code=404, detail="User profile not found")

        old_user_id = str(profile.user_id)

        user_id = get_user_id(current_user)
        user_profile_service.delete_user_profile(
            db, user_profile_id=user_profile_id, user_id=user_id
        )

        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="DELETE",
                object_type="UserProfile",
                object_id=str(user_profile_id),
                user_id=get_user_id(current_user),
                tenant_id=tenant_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["DELETE"],
                old_values={"user_id": old_user_id, "id": str(user_profile_id)},
            )
        except Exception:
            pass

        return {"message": "User profile deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting user profile: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user profile: {str(e)}",
        )
