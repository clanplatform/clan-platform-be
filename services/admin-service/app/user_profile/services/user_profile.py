from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional
from uuid import UUID
from datetime import datetime

from app.user_profile.models.user_profile import UserProfile
from app.user_profile.schemas.user_profile import UserProfileCreate, UserProfileUpdate
from app.infrastructure.audit_tenant import fire_audit_log


def get_user_profile(db: Session, user_profile_id: UUID) -> Optional[UserProfile]:
    """Get a user profile by its primary key."""
    return db.query(UserProfile).filter(
        UserProfile.user_profile_id == user_profile_id,
        UserProfile.is_deleted == False
    ).first()


def get_user_profile_by_user(db: Session, user_id: UUID) -> Optional[UserProfile]:
    """Get the profile owned by a specific user (one profile per user)."""
    return db.query(UserProfile).filter(
        UserProfile.user_id == user_id,
        UserProfile.is_deleted == False
    ).first()


def get_all_user_profiles(db: Session, skip: int = 0, limit: int = 100) -> List[UserProfile]:
    """Get all user profiles with pagination."""
    return db.query(UserProfile).filter(
        UserProfile.is_deleted == False
    ).offset(skip).limit(limit).all()


def create_user_profile(db: Session, profile: UserProfileCreate, user_id: Optional[UUID] = None) -> UserProfile:
    """Create a new user profile. Enforces one profile per user."""
    existing = get_user_profile_by_user(db, profile.user_id)
    if existing:
        raise HTTPException(status_code=400, detail="A profile already exists for this user")

    profile_data = profile.model_dump()
    db_profile = UserProfile(
        user_id=profile_data["user_id"],
        tenant_id=profile_data.get("tenant_id"),
        theme=profile_data.get("theme", "light"),
        accent_color=profile_data.get("accent_color", "blue"),
        density=profile_data.get("density", "comfortable"),
        language=profile_data.get("language", "English"),
        direction=profile_data.get("direction", "ltr"),
        can_change_password=profile_data.get("can_change_password", True),
        session=profile_data.get("session"),
        is_active=profile_data.get("is_active", True),
        created_by=user_id,
        updated_by=user_id,
    )

    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)

    fire_audit_log(
        action="CREATE",
        object_type="UserProfile",
        object_id=str(db_profile.user_profile_id),
        tenant_id=str(db_profile.tenant_id) if db_profile.tenant_id else None,
        user_id=str(user_id) if user_id else None,
        new_values=profile_data,
    )

    return db_profile


def update_user_profile(
    db: Session,
    user_profile_id: UUID,
    profile: UserProfileUpdate,
    user_id: Optional[UUID] = None,
) -> Optional[UserProfile]:
    """Update an existing user profile."""
    db_profile = get_user_profile(db, user_profile_id=user_profile_id)
    if not db_profile:
        raise HTTPException(status_code=404, detail="User profile not found")

    update_data = profile.model_dump(exclude_unset=True)
    old_values = {key: getattr(db_profile, key) for key in update_data.keys() if hasattr(db_profile, key)}

    for key, value in update_data.items():
        setattr(db_profile, key, value)

    db_profile.updated_by = user_id

    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)

    fire_audit_log(
        action="UPDATE",
        object_type="UserProfile",
        object_id=str(user_profile_id),
        tenant_id=str(db_profile.tenant_id) if db_profile.tenant_id else None,
        user_id=str(user_id) if user_id else None,
        old_values=old_values,
        new_values=update_data,
    )

    return db_profile


def delete_user_profile(db: Session, user_profile_id: UUID, user_id: Optional[UUID] = None) -> bool:
    """Soft delete a user profile."""
    db_profile = get_user_profile(db, user_profile_id=user_profile_id)
    if not db_profile:
        raise HTTPException(status_code=404, detail="User profile not found")

    old_values = {
        "user_id": str(db_profile.user_id),
        "is_deleted": db_profile.is_deleted,
        "is_active": db_profile.is_active,
    }

    db_profile.is_deleted = True
    db_profile.is_active = False
    db_profile.deleted_at = datetime.utcnow()
    db_profile.updated_by = user_id

    db.add(db_profile)
    db.commit()

    fire_audit_log(
        action="DELETE",
        object_type="UserProfile",
        object_id=str(user_profile_id),
        tenant_id=str(db_profile.tenant_id) if db_profile.tenant_id else None,
        user_id=str(user_id) if user_id else None,
        old_values=old_values,
        new_values={"is_deleted": True, "is_active": False},
    )

    return True


def restore_user_profile(db: Session, user_profile_id: UUID, user_id: Optional[UUID] = None) -> Optional[UserProfile]:
    """Restore a soft-deleted user profile."""
    db_profile = db.query(UserProfile).filter(
        UserProfile.user_profile_id == user_profile_id
    ).first()

    if not db_profile:
        raise HTTPException(status_code=404, detail="User profile not found")

    if not db_profile.is_deleted:
        raise HTTPException(status_code=400, detail="User profile is not deleted")

    db_profile.is_deleted = False
    db_profile.is_active = True
    db_profile.deleted_at = None
    db_profile.updated_by = user_id

    db.add(db_profile)
    db.commit()
    db.refresh(db_profile)

    fire_audit_log(
        action="RESTORE",
        object_type="UserProfile",
        object_id=str(user_profile_id),
        tenant_id=str(db_profile.tenant_id) if db_profile.tenant_id else None,
        user_id=str(user_id) if user_id else None,
        old_values={"is_deleted": True},
        new_values={"is_deleted": False, "is_active": True},
    )

    return db_profile
