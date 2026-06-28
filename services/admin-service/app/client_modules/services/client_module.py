from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, asc
from app.client_modules.models.client_module import ClientModule
from app.client_modules.schemas.client_module import ClientModuleCreate, ClientModuleUpdate
from app.infrastructure.audit_client import fire_audit_log
import uuid


class ClientModuleService:

    @staticmethod
    def assign_module(db: Session, data: ClientModuleCreate, assigned_by: Optional[uuid.UUID] = None) -> ClientModule:
        db_cm = ClientModule(**data.model_dump(), assigned_by=assigned_by)
        db.add(db_cm)
        db.commit()
        db.refresh(db_cm)
        fire_audit_log(
            action="CREATE", object_type="ClientModule", object_id=str(db_cm.id),
            new_values={"client_id": str(db_cm.client_id), "module_id": str(db_cm.module_id), "is_active": db_cm.is_active},
        )
        return db_cm

    @staticmethod
    def get_assignment(db: Session, assignment_id: str) -> Optional[ClientModule]:
        return db.query(ClientModule).filter(ClientModule.id == assignment_id).first()

    @staticmethod
    def get_assignment_by_client_module(db: Session, client_id: str, module_id: str) -> Optional[ClientModule]:
        return db.query(ClientModule).filter(
            and_(ClientModule.client_id == client_id, ClientModule.module_id == module_id)
        ).first()

    @staticmethod
    def get_assignments(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        client_id: Optional[str] = None,
        module_id: Optional[str] = None,
        is_active: Optional[bool] = None,
        sort_by: str = "assigned_at",
        sort_order: str = "desc",
    ) -> tuple[List[ClientModule], int]:
        query = db.query(ClientModule)
        if client_id:
            query = query.filter(ClientModule.client_id == client_id)
        if module_id:
            query = query.filter(ClientModule.module_id == module_id)
        if is_active is not None:
            query = query.filter(ClientModule.is_active == is_active)

        col = getattr(ClientModule, sort_by, ClientModule.assigned_at)
        query = query.order_by(desc(col) if sort_order.lower() == "desc" else asc(col))

        total = query.count()
        return query.offset(skip).limit(limit).all(), total

    @staticmethod
    def get_modules_for_client(db: Session, client_id: str, is_active: Optional[bool] = None) -> List[ClientModule]:
        query = db.query(ClientModule).filter(ClientModule.client_id == client_id)
        if is_active is not None:
            query = query.filter(ClientModule.is_active == is_active)
        return query.all()

    @staticmethod
    def get_clients_for_module(db: Session, module_id: str, is_active: Optional[bool] = None) -> List[ClientModule]:
        query = db.query(ClientModule).filter(ClientModule.module_id == module_id)
        if is_active is not None:
            query = query.filter(ClientModule.is_active == is_active)
        return query.all()

    @staticmethod
    def update_assignment(
        db: Session, assignment_id: str, data: ClientModuleUpdate, updated_by: Optional[uuid.UUID] = None
    ) -> Optional[ClientModule]:
        db_cm = ClientModuleService.get_assignment(db, assignment_id)
        if not db_cm:
            return None
        update_data = data.model_dump(exclude_unset=True)
        if updated_by:
            update_data["updated_by"] = updated_by
        for field, value in update_data.items():
            setattr(db_cm, field, value)
        db.commit()
        db.refresh(db_cm)
        fire_audit_log(action="UPDATE", object_type="ClientModule", object_id=str(assignment_id), new_values=update_data)
        return db_cm

    @staticmethod
    def remove_assignment(db: Session, assignment_id: str) -> bool:
        db_cm = ClientModuleService.get_assignment(db, assignment_id)
        if not db_cm:
            return False
        fire_audit_log(
            action="DELETE", object_type="ClientModule", object_id=str(assignment_id),
            old_values={"client_id": str(db_cm.client_id), "module_id": str(db_cm.module_id)},
        )
        db.delete(db_cm)
        db.commit()
        return True
