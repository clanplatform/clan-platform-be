from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.infrastructure.database.session import get_db
from app.core.security import get_current_user
from app.divisions.models.divisions import Division
from app.divisions.schemas.divisions import DivisionCreate, DivisionUpdate, DivisionResponse
from app.divisions.services import divisions as division_service
import uuid

router = APIRouter()

@router.get("/", response_model=List[DivisionResponse])
def get_divisions(
    skip: int = 0,
    limit: int = 100,
    client_id: Optional[uuid.UUID] = None,
    entity_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all divisions with pagination and optional client/entity filtering, sorted by newest first (FILO)"""
    try:
        divisions = division_service.get_all_divisions(
            db, client_id=client_id, entity_id=entity_id, skip=skip, limit=limit
        )
        return divisions
        
    except Exception as e:
        print(f"Error getting divisions: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get divisions: {str(e)}"
        )

@router.get("/by-department/{department_id}", response_model=List[DivisionResponse])
def get_divisions_by_department(
    department_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all divisions that are related to a specific department by entity/client"""
    try:
        divisions = division_service.get_divisions_by_department(
            db, department_id=department_id, skip=skip, limit=limit
        )
        return divisions
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting divisions by department: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get divisions by department: {str(e)}"
        )


@router.post("/", response_model=DivisionResponse, status_code=status.HTTP_201_CREATED)
def create_division(
    division_data: DivisionCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new division"""
    try:
        division = division_service.create_division(db, division=division_data)
        return division
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log the full error for debugging
        print(f"Error creating division: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Rollback the transaction
        db.rollback()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create division: {str(e)}"
        )

@router.put("/{division_id}", response_model=DivisionResponse)
def update_division(
    division_id: uuid.UUID,
    division_data: DivisionUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update a division"""
    try:
        division = division_service.update_division(
            db, division_id=division_id, division=division_data
        )
        return division
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating division: {str(e)}")
        import traceback
        traceback.print_exc()
        
        db.rollback()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update division: {str(e)}"
        )

@router.delete("/{division_id}")
async def delete_division(
    division_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Soft delete a division"""
    try:
        division_service.delete_division(db, division_id=division_id)
        return {"message": "Division deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting division: {str(e)}")
        import traceback
        traceback.print_exc()
        
        db.rollback()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete division: {str(e)}"
        )

