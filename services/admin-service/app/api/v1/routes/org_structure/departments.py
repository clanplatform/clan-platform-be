from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.infrastructure.database.session import get_db
from app.departments.models.departments import Department
from app.departments.schemas.departments import DepartmentCreate, DepartmentUpdate, DepartmentResponse
from app.departments.services import departments as department_service
from app.core.security import get_current_user  # Uses optional auth support
from app.infrastructure.audit_helpers import RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id
from app.infrastructure.audit_client import fire_audit_log
import uuid

router = APIRouter()

@router.get("/", response_model=List[DepartmentResponse])
def get_departments(
    skip: int = 0,
    limit: int = 100,
    entity_id: Optional[uuid.UUID] = None,
    parent_department_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get all departments with pagination and optional filtering"""
    try:
        if entity_id:
            departments = department_service.get_departments_by_entity(
                db, entity_id=entity_id, skip=skip, limit=limit
            )
        elif parent_department_id:
            departments = department_service.get_departments_by_parent(
                db, parent_department_id=parent_department_id, skip=skip, limit=limit
            )
        else:
            departments = department_service.get_all_departments(db, skip=skip, limit=limit)
        
        return departments
        
    except Exception as e:
        print(f"Error getting departments: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get departments: {str(e)}"
        )

@router.get("/{department_id}", response_model=DepartmentResponse)
def get_department(
    department_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get a specific department by ID"""
    try:
        department = department_service.get_department(db, department_id=department_id)
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Department not found"
            )
        return department
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting department: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get department: {str(e)}"
        )


@router.post("/", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
def create_department(
    request: Request,
    department_data: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create a new department"""
    try:
        user_id = current_user.user_id if hasattr(current_user, 'user_id') else None
        department = department_service.create_department(
            db, department=department_data, user_id=user_id
        )

        # Audit log: department created
        try:
            client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="CREATE",
                object_type="Department",
                object_id=str(department.department_id),
                user_id=get_user_id(current_user),
                client_id=client_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["CREATE"],
                new_values={"name": department.name},
            )
        except Exception:
            pass

        return department

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log the full error for debugging
        print(f"Error creating department: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Rollback the transaction
        db.rollback()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create department: {str(e)}"
        )

@router.put("/{department_id}", response_model=DepartmentResponse)
def update_department(
    request: Request,
    department_id: uuid.UUID,
    department_data: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Update a department"""
    try:
        user_id = current_user.user_id if hasattr(current_user, 'user_id') else None
        department = department_service.update_department(
            db, department_id=department_id, department=department_data, user_id=user_id
        )

        # Audit log: department updated
        try:
            client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="UPDATE",
                object_type="Department",
                object_id=str(department_id),
                user_id=get_user_id(current_user),
                client_id=client_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["UPDATE"],
                new_values={"name": department.name},
            )
        except Exception:
            pass

        return department

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating department: {str(e)}")
        import traceback
        traceback.print_exc()
        
        db.rollback()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update department: {str(e)}"
        )

@router.delete("/{department_id}")
async def delete_department(
    request: Request,
    department_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Soft delete department"""
    try:
        # Check access control for non-admin users
        department = department_service.get_department(db, department_id=department_id)
        if not department:
            raise HTTPException(status_code=404, detail="Department not found")

        if hasattr(current_user, 'is_admin') and not current_user.is_admin():
            if hasattr(current_user, 'client_id') and department.client_id != current_user.client_id:
                raise HTTPException(status_code=403, detail="Access denied")

        # Snapshot name before delete for audit
        old_dept_name = department.name

        user_id = current_user.user_id if hasattr(current_user, 'user_id') else None
        department_service.delete_department(db, department_id=department_id, user_id=user_id)

        # Audit log: department deleted
        try:
            client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="DELETE",
                object_type="Department",
                object_id=str(department_id),
                user_id=get_user_id(current_user),
                client_id=client_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["DELETE"],
                old_values={"name": old_dept_name, "id": str(department_id)},
            )
        except Exception:
            pass

        return {"message": "Department deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting department: {str(e)}")
        import traceback
        traceback.print_exc()
        
        db.rollback()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete department: {str(e)}"
        )

@router.get("/by-client/{client_id}", response_model=List[DepartmentResponse])
def get_departments_by_client(
    client_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    entity_id: Optional[uuid.UUID] = None,
    parent_department_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get all departments for a specific client (supports both entity-based and entity-less clients)"""
    try:
        # Check if user has access to this client
        if hasattr(current_user, 'is_admin') and not current_user.is_admin() and hasattr(current_user, 'client_id') and current_user.client_id != client_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Use service layer with appropriate filters
        if entity_id:
            departments = department_service.get_departments_by_entity(
                db, entity_id=entity_id, skip=skip, limit=limit
            )
            # Additional filter by parent if specified
            if parent_department_id:
                departments = [d for d in departments if d.parent_department_id == parent_department_id]
        elif parent_department_id:
            departments = department_service.get_departments_by_parent(
                db, parent_department_id=parent_department_id, skip=skip, limit=limit
            )
        else:
            departments = department_service.get_departments_by_client(
                db, client_id=client_id, skip=skip, limit=limit
            )
        
        return departments
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting departments by client: {str(e)}")
        import traceback
        traceback.print_exc()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get departments by client: {str(e)}"
        )
