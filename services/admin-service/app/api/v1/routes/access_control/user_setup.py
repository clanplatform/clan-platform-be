from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.infrastructure.database.session import get_db
from app.user_setup.services.user_setup import UserSetupService
from app.user_setup.schemas.user_setup import (
    UserSetupBasicCreate,
    UserSetupBasicUpdate,
    UserSetupBasicResponse,
    UserSetupRolesEntityCreate,
    UserSetupRolesEntityUpdate,
    UserSetupRolesEntityResponse,
    UserSetupPreferenceCreate,
    UserSetupPreferenceUpdate,
    UserSetupPreferenceResponse,
    UserSetupWithDetails,
    UserSetupCreateWithDetails,
    UserSetupListResponse,
    AvailableUsersResponse
)

router = APIRouter()





@router.post("/with-details", response_model=UserSetupWithDetails, status_code=status.HTTP_201_CREATED)
async def create_user_setup_with_details(
    user_data: UserSetupCreateWithDetails,
    db: Session = Depends(get_db)
):
    """Create a user setup with roles, entities, and preferences in one request.
    Also syncs the user to the identity-domain auth-service."""
    return UserSetupService.create_user_setup_with_details(db, user_data)





@router.get("/{user_id}/details", response_model=UserSetupWithDetails)
def get_user_setup_with_details(
    user_id: UUID,
    db: Session = Depends(get_db)
):
    """Get a user setup with all related data (roles, entities, preferences)"""
    return UserSetupService.get_user_setup_with_details(db, user_id)


@router.put("/{user_id}", response_model=UserSetupBasicResponse)
def update_user_setup(
    user_id: UUID,
    user_data: UserSetupBasicUpdate,
    db: Session = Depends(get_db)
):
    """Update a user setup"""
    return UserSetupService.update_user_setup(db, user_id, user_data)


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
def delete_user_setup(
    user_id: UUID,
    db: Session = Depends(get_db)
):
    """Delete a user setup (cascades to roles_entities and preferences)"""
    return UserSetupService.delete_user_setup(db, user_id)






@router.get("/debug/sync-status")
async def debug_sync_status():
    """Debug endpoint to check if sync is enabled"""
    try:
        from app.user_setup.services.identity_db_sync import IdentityDbSync
        from app.core.config import settings
        
        return {
            "sync_module_loaded": True,
            "sync_enabled": IdentityDbSync.sync_enabled(),
            "identity_database_url_configured": settings.IDENTITY_DATABASE_URL is not None,
            "identity_database_url": str(settings.IDENTITY_DATABASE_URL)[:60] + "..." if settings.IDENTITY_DATABASE_URL else None
        }
    except Exception as e:
        return {
            "sync_module_loaded": False,
            "error": str(e)
        }
