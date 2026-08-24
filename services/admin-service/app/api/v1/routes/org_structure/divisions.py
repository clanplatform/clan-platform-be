from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.infrastructure.database.session import get_db, get_tenant_db
from app.core.security import get_current_user
from app.divisions.models.divisions import Division
from app.divisions.schemas.divisions import DivisionCreate, DivisionUpdate, DivisionResponse
from app.divisions.services import divisions as division_service
from app.infrastructure.audit_helpers import RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id
from app.infrastructure.audit_tenant import fire_audit_log
from app.infrastructure.scope_helpers import resolve_scope_filter, scoped_division_ids, require_whole_org_admin
import uuid

router = APIRouter()

@router.get("/", response_model=List[DivisionResponse])
def get_divisions(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    tenant_id: Optional[uuid.UUID] = None,
    entity_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_tenant_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all divisions with pagination and optional tenant/entity filtering, sorted by newest first (FILO)"""
    try:
        scope_filter = resolve_scope_filter(db, get_user_id(current_user))
        scoped_ids = scoped_division_ids(db, scope_filter)

        divisions = division_service.get_all_divisions(
            db, tenant_id=tenant_id, entity_id=entity_id, skip=skip, limit=limit,
            scoped_ids=scoped_ids,
        )
        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="READ",
                object_type="Division",
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
    request: Request,
    department_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_tenant_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all divisions that are related to a specific department by entity/client"""
    try:
        divisions = division_service.get_divisions_by_department(
            db, department_id=department_id, skip=skip, limit=limit
        )
        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="READ",
                object_type="Division",
                object_id=str(department_id),
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
    request: Request,
    division_data: DivisionCreate,
    db: Session = Depends(get_tenant_db),
    current_user: dict = Depends(require_whole_org_admin)
):
    """Create a new division.

    Restricted to a role with is_admin=True AND access_scope=
    'whole_organization' — see require_whole_org_admin.
    """
    # tenant_id is taken from the JWT, never the body. None => master-DB user.
    tenant_id = current_user.get("tenant_id") if isinstance(current_user, dict) else None
    try:
        division = division_service.create_division(db, division=division_data, tenant_id=tenant_id)

        # Audit log: division created
        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="CREATE",
                object_type="Division",
                object_id=str(division.id),
                user_id=get_user_id(current_user),
                tenant_id=tenant_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["CREATE"],
                new_values={"name": division.division_name},
            )
        except Exception:
            pass

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
    request: Request,
    division_id: uuid.UUID,
    division_data: DivisionUpdate,
    db: Session = Depends(get_tenant_db),
    current_user: dict = Depends(require_whole_org_admin)
):
    """Update a division"""
    try:
        division = division_service.update_division(
            db, division_id=division_id, division=division_data
        )

        # Audit log: division updated
        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="UPDATE",
                object_type="Division",
                object_id=str(division_id),
                user_id=get_user_id(current_user),
                tenant_id=tenant_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["UPDATE"],
                new_values={"name": division.division_name},
            )
        except Exception:
            pass

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
    request: Request,
    division_id: uuid.UUID,
    db: Session = Depends(get_tenant_db),
    current_user: dict = Depends(require_whole_org_admin)
):
    """Soft delete a division"""
    try:
        # Query before delete to capture snapshot for audit
        division_snapshot = db.query(Division).filter(Division.id == division_id).first()
        old_division_name = division_snapshot.division_name if division_snapshot else None

        division_service.delete_division(db, division_id=division_id)

        # Audit log: division deleted
        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="DELETE",
                object_type="Division",
                object_id=str(division_id),
                user_id=get_user_id(current_user),
                tenant_id=tenant_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["DELETE"],
                old_values={"name": old_division_name, "id": str(division_id)},
            )
        except Exception:
            pass

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

