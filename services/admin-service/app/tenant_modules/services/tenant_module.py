from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, asc
from app.tenant_modules.models.tenant_module import TenantModule
from app.tenant_modules.schemas.tenant_module import TenantModuleCreate, TenantModuleUpdate
from app.infrastructure.audit_client import fire_audit_log
import uuid


class TenantModuleService:

    @staticmethod
    def assign_module(db: Session, data: TenantModuleCreate, assigned_by: Optional[uuid.UUID] = None) -> TenantModule:
        db_tm = TenantModule(**data.model_dump(), assigned_by=assigned_by)
        db.add(db_tm)
        db.commit()
        db.refresh(db_tm)
        fire_audit_log(
            action="CREATE", object_type="TenantModule", object_id=str(db_tm.id),
            new_values={"tenant_id": str(db_tm.tenant_id), "module_id": str(db_tm.module_id), "is_active": db_tm.is_active},
        )
        return db_tm

    @staticmethod
    def get_assignment(db: Session, assignment_id: str) -> Optional[TenantModule]:
        return db.query(TenantModule).filter(TenantModule.id == assignment_id).first()

    @staticmethod
    def get_assignment_by_tenant_module(db: Session, tenant_id: str, module_id: str) -> Optional[TenantModule]:
        return db.query(TenantModule).filter(
            and_(TenantModule.tenant_id == tenant_id, TenantModule.module_id == module_id)
        ).first()

    @staticmethod
    def get_assignments(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        tenant_id: Optional[str] = None,
        module_id: Optional[str] = None,
        is_active: Optional[bool] = None,
        sort_by: str = "assigned_at",
        sort_order: str = "desc",
    ) -> tuple[List[TenantModule], int]:
        query = db.query(TenantModule)
        if tenant_id:
            query = query.filter(TenantModule.tenant_id == tenant_id)
        if module_id:
            query = query.filter(TenantModule.module_id == module_id)
        if is_active is not None:
            query = query.filter(TenantModule.is_active == is_active)

        col = getattr(TenantModule, sort_by, TenantModule.assigned_at)
        query = query.order_by(desc(col) if sort_order.lower() == "desc" else asc(col))

        total = query.count()
        return query.offset(skip).limit(limit).all(), total

    @staticmethod
    def get_modules_for_tenant(db: Session, tenant_id: str, is_active: Optional[bool] = None) -> List[TenantModule]:
        query = db.query(TenantModule).filter(TenantModule.tenant_id == tenant_id)
        if is_active is not None:
            query = query.filter(TenantModule.is_active == is_active)
        return query.all()

    @staticmethod
    def get_tenants_for_module(db: Session, module_id: str, is_active: Optional[bool] = None) -> List[TenantModule]:
        query = db.query(TenantModule).filter(TenantModule.module_id == module_id)
        if is_active is not None:
            query = query.filter(TenantModule.is_active == is_active)
        return query.all()

    @staticmethod
    def update_assignment(
        db: Session, assignment_id: str, data: TenantModuleUpdate, updated_by: Optional[uuid.UUID] = None
    ) -> Optional[TenantModule]:
        db_tm = TenantModuleService.get_assignment(db, assignment_id)
        if not db_tm:
            return None
        update_data = data.model_dump(exclude_unset=True)
        if updated_by:
            update_data["updated_by"] = updated_by
        for field, value in update_data.items():
            setattr(db_tm, field, value)
        db.commit()
        db.refresh(db_tm)
        fire_audit_log(action="UPDATE", object_type="TenantModule", object_id=str(assignment_id), new_values=update_data)
        return db_tm

    @staticmethod
    def remove_assignment(db: Session, assignment_id: str) -> bool:
        db_tm = TenantModuleService.get_assignment(db, assignment_id)
        if not db_tm:
            return False
        fire_audit_log(
            action="DELETE", object_type="TenantModule", object_id=str(assignment_id),
            old_values={"tenant_id": str(db_tm.tenant_id), "module_id": str(db_tm.module_id)},
        )
        db.delete(db_tm)
        db.commit()
        return True
