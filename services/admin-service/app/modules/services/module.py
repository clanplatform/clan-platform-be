from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from app.modules.models.module import Module
from app.tenant_modules.models.tenant_module import TenantModule
from app.modules.schemas.module import ModuleCreate, ModuleUpdate
from app.applications.services.application import ensure_application_writable
from app.core.access import is_active_from_access, is_write_locked
from app.infrastructure.audit_tenant import fire_audit_log
from datetime import datetime


def ensure_module_writable(db: Session, module_id, resource: str = "this resource") -> None:
    """
    Raise 403 when the given module is read-only (access has no "write").

    No-op when module_id is None (e.g. a menu not attached to a module) or the
    module does not exist. Used to gate writes to a module's child resources
    (menus).
    """
    if not module_id:
        return
    module = db.query(Module).filter(Module.id == module_id).first()
    if module and is_write_locked(module.access):
        raise HTTPException(
            status_code=403,
            detail=f"Module is read-only; cannot create, modify, or delete {resource}.",
        )


class ModuleService:
    """Service for managing modules"""

    @staticmethod
    def create_module(db: Session, module_data: ModuleCreate, created_by: Optional[int] = None) -> Module:
        """Create a new module"""
        # Block writes when the parent application is read-only
        ensure_application_writable(db, module_data.application_id, "modules")
        data = module_data.model_dump()
        # Access drives the active state: "disable" -> False, "write"/"read" -> True
        derived_active = is_active_from_access(data.get("access"))
        if derived_active is not None:
            data["is_active"] = derived_active
        db_module = Module(
            **data,
            created_by=created_by
        )
        db.add(db_module)
        db.commit()
        db.refresh(db_module)
        fire_audit_log(
            action="CREATE", object_type="Module",
            object_id=str(db_module.id),
            new_values={"name": db_module.name, "code": db_module.code},
        )
        return db_module

    @staticmethod
    def get_module(db: Session, module_id: str) -> Optional[Module]:
        """Get a module by ID"""
        return db.query(Module).filter(
            and_(
                Module.id == module_id,
                Module.is_deleted == False
            )
        ).first()

    @staticmethod
    def get_module_by_code(db: Session, code: str) -> Optional[Module]:
        """Get a module by code"""
        return db.query(Module).filter(
            and_(
                Module.code == code,
                Module.is_deleted == False
            )
        ).first()

    @staticmethod
    def get_module_by_key(db: Session, key: str) -> Optional[Module]:
        """Get a module by key"""
        return db.query(Module).filter(
            and_(
                Module.key == key,
                Module.is_deleted == False
            )
        ).first()

    @staticmethod
    def get_modules(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        application_id: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        tenant_id: Optional[str] = None,
    ) -> tuple[List[Module], int]:
        """Get modules with filtering and pagination.
        When tenant_id is provided, only returns modules licensed to that tenant."""

        query = db.query(Module).filter(Module.is_deleted == False)

        # Tenant isolation: restrict to modules the tenant has licensed
        if tenant_id:
            query = query.join(
                TenantModule,
                and_(
                    TenantModule.module_id == Module.id,
                    TenantModule.tenant_id == tenant_id,
                    TenantModule.is_active == True,
                )
            )

        # Apply filters
        if application_id:
            query = query.filter(Module.application_id == application_id)
        
        if is_active is not None:
            query = query.filter(Module.is_active == is_active)

        if search:
            search_filter = or_(
                Module.name.ilike(f"%{search}%"),
                Module.label.ilike(f"%{search}%"),
                Module.description.ilike(f"%{search}%"),
                Module.code.ilike(f"%{search}%"),
                Module.key.ilike(f"%{search}%")
            )
            query = query.filter(search_filter)
        
        # Apply sorting
        if hasattr(Module, sort_by):
            if sort_order.lower() == "desc":
                query = query.order_by(desc(getattr(Module, sort_by)))
            else:
                query = query.order_by(asc(getattr(Module, sort_by)))
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        modules = query.offset(skip).limit(limit).all()
        
        return modules, total

    @staticmethod
    def get_modules_by_application(
        db: Session,
        application_id: str,
        is_active: Optional[bool] = None
    ) -> List[Module]:
        """Get all modules for a specific application"""
        query = db.query(Module).filter(
            and_(
                Module.application_id == application_id,
                Module.is_deleted == False
            )
        )
        
        if is_active is not None:
            query = query.filter(Module.is_active == is_active)
            
        return query.order_by(Module.order_index, Module.name).all()

    @staticmethod
    def update_module(
        db: Session,
        module_id: str,
        module_data: ModuleUpdate,
    ) -> Optional[Module]:
        """Update a module"""
        db_module = ModuleService.get_module(db, module_id)
        if not db_module:
            return None

        # Block writes when the parent application is read-only
        ensure_application_writable(db, db_module.application_id, "modules")

        update_data = module_data.model_dump(exclude_unset=True)

        # Self read-only lock: a write-locked module can only be edited by a
        # payload that changes "access" itself (the way to unlock it).
        if is_write_locked(db_module.access) and "access" not in update_data:
            raise HTTPException(
                status_code=403,
                detail="Module is read-only; include an 'access' change to modify it.",
            )

        # Keep is_active in sync when access changes (disable -> False, write/read -> True)
        if "access" in update_data:
            derived_active = is_active_from_access(update_data.get("access"))
            if derived_active is not None:
                update_data["is_active"] = derived_active
        
        for field, value in update_data.items():
            setattr(db_module, field, value)
        
        db.commit()
        db.refresh(db_module)
        fire_audit_log(
            action="UPDATE", object_type="Module",
            object_id=str(module_id),
            new_values=update_data,
        )
        return db_module

    @staticmethod
    def delete_module(db: Session, module_id: str, deleted_by: Optional[int] = None) -> bool:
        """Soft delete a module"""
        db_module = ModuleService.get_module(db, module_id)
        if not db_module:
            return False

        # Block writes when the parent application is read-only
        ensure_application_writable(db, db_module.application_id, "modules")

        # Self read-only lock: a write-locked module (access has no "write")
        # cannot be deleted even when its parent application is writable.
        if is_write_locked(db_module.access):
            raise HTTPException(
                status_code=403,
                detail="Module is read-only and cannot be deleted.",
            )

        db_module.is_deleted = True
        db_module.is_active = False
        if deleted_by:
            db_module.updated_by = deleted_by

        db.commit()
        fire_audit_log(
            action="DELETE", object_type="Module",
            object_id=str(module_id),
            old_values={"is_deleted": False}, new_values={"is_deleted": True},
        )
        return True

    @staticmethod
    def activate_module(db: Session, module_id: str, activated_by: Optional[int] = None) -> Optional[Module]:
        """Activate a module"""
        db_module = ModuleService.get_module(db, module_id)
        if not db_module:
            return None
        
        db_module.is_active = True
        if activated_by:
            db_module.updated_by = activated_by
        
        db.commit()
        db.refresh(db_module)
        return db_module

    @staticmethod
    def deactivate_module(db: Session, module_id: str, deactivated_by: Optional[int] = None) -> Optional[Module]:
        """Deactivate a module"""
        db_module = ModuleService.get_module(db, module_id)
        if not db_module:
            return None
        
        db_module.is_active = False
        if deactivated_by:
            db_module.updated_by = deactivated_by
        
        db.commit()
        db.refresh(db_module)
        return db_module