from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, asc
from app.tenant_applications.models.tenant_application import TenantApplication
from app.tenant_applications.schemas.tenant_application import TenantApplicationCreate, TenantApplicationUpdate
from app.infrastructure.audit_tenant import fire_audit_log
import uuid


class TenantApplicationService:

    @staticmethod
    def assign_application(db: Session, data: TenantApplicationCreate, assigned_by: Optional[uuid.UUID] = None) -> TenantApplication:
        db_ta = TenantApplication(**data.model_dump(), assigned_by=assigned_by)
        db.add(db_ta)
        db.commit()
        db.refresh(db_ta)
        fire_audit_log(
            action="CREATE", object_type="TenantApplication", object_id=str(db_ta.id),
            new_values={"tenant_id": str(db_ta.tenant_id), "application_id": str(db_ta.application_id), "is_active": db_ta.is_active},
        )
        return db_ta

    @staticmethod
    def get_assignment(db: Session, assignment_id: str) -> Optional[TenantApplication]:
        return db.query(TenantApplication).filter(TenantApplication.id == assignment_id).first()

    @staticmethod
    def get_assignment_by_tenant_application(db: Session, tenant_id: str, application_id: str) -> Optional[TenantApplication]:
        return db.query(TenantApplication).filter(
            and_(TenantApplication.tenant_id == tenant_id, TenantApplication.application_id == application_id)
        ).first()

    @staticmethod
    def get_assignments(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[str] = None,
        application_id: Optional[str] = None,
        is_active: Optional[bool] = None,
        sort_by: str = "assigned_at",
        sort_order: str = "desc",
    ) -> tuple[List[TenantApplication], int]:
        query = db.query(TenantApplication)
        if tenant_id:
            query = query.filter(TenantApplication.tenant_id == tenant_id)
        if application_id:
            query = query.filter(TenantApplication.application_id == application_id)
        if is_active is not None:
            query = query.filter(TenantApplication.is_active == is_active)

        col = getattr(TenantApplication, sort_by, TenantApplication.assigned_at)
        query = query.order_by(desc(col) if sort_order.lower() == "desc" else asc(col))

        total = query.count()
        return query.offset(skip).limit(limit).all(), total

    @staticmethod
    def get_applications_for_tenant(db: Session, tenant_id: str, is_active: Optional[bool] = None) -> List[TenantApplication]:
        query = db.query(TenantApplication).filter(TenantApplication.tenant_id == tenant_id)
        if is_active is not None:
            query = query.filter(TenantApplication.is_active == is_active)
        return query.all()

    @staticmethod
    def get_tenants_for_application(db: Session, application_id: str, is_active: Optional[bool] = None) -> List[TenantApplication]:
        query = db.query(TenantApplication).filter(TenantApplication.application_id == application_id)
        if is_active is not None:
            query = query.filter(TenantApplication.is_active == is_active)
        return query.all()

    @staticmethod
    def update_assignment(
        db: Session, assignment_id: str, data: TenantApplicationUpdate, updated_by: Optional[uuid.UUID] = None
    ) -> Optional[TenantApplication]:
        db_ta = TenantApplicationService.get_assignment(db, assignment_id)
        if not db_ta:
            return None
        update_data = data.model_dump(exclude_unset=True)
        if updated_by:
            update_data["updated_by"] = updated_by
        for field, value in update_data.items():
            setattr(db_ta, field, value)
        db.commit()
        db.refresh(db_ta)
        fire_audit_log(action="UPDATE", object_type="TenantApplication", object_id=str(assignment_id), new_values=update_data)
        return db_ta

    @staticmethod
    def remove_assignment(db: Session, assignment_id: str) -> bool:
        db_ta = TenantApplicationService.get_assignment(db, assignment_id)
        if not db_ta:
            return False
        fire_audit_log(
            action="DELETE", object_type="TenantApplication", object_id=str(assignment_id),
            old_values={"tenant_id": str(db_ta.tenant_id), "application_id": str(db_ta.application_id)},
        )
        db.delete(db_ta)
        db.commit()
        return True
