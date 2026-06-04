from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.infrastructure.database.session import get_db
from app.core.security import get_current_user
from app.user_setup.models.user_setup import User
from app.user_setup.schemas.user_setup import UserSetupService
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
def create_user_setup_with_details(
    user_data: UserSetupCreateWithDetails,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a user setup with roles, entities, and preferences in one request"""
    return UserSetupService.create_user_setup_with_details(db, user_data)





@router.get("/{user_id}/details", response_model=UserSetupWithDetails)
def get_user_setup_with_details(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a user setup with all related data (roles, entities, preferences)"""
    return UserSetupService.get_user_setup_with_details(db, user_id)


@router.put("/{user_id}", response_model=UserSetupBasicResponse)
def update_user_setup(
    user_id: UUID,
    user_data: UserSetupBasicUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a user setup"""
    return UserSetupService.update_user_setup(db, user_id, user_data)


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
def delete_user_setup(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a user setup (cascades to roles_entities and preferences)"""
    return UserSetupService.delete_user_setup(db, user_id)




