from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from app.modules.models.module import Module
from app.client_modules.models.client_module import ClientModule
from app.modules.schemas.module import ModuleCreate, ModuleUpdate
from app.infrastructure.audit_client import fire_audit_log
from datetime import datetime

class ModuleService:
    """Service for managing modules"""

    @staticmethod
    def create_module(db: Session, module_data: ModuleCreate, created_by: Optional[int] = None) -> Module:
        """Create a new module"""
        db_module = Module(
            **module_data.model_dump(),
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
        is_public: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        client_id: Optional[str] = None,
    ) -> tuple[List[Module], int]:
        """Get modules with filtering and pagination.
        When client_id is provided, only returns modules licensed to that client."""

        query = db.query(Module).filter(Module.is_deleted == False)

        # Tenant isolation: restrict to modules the client has licensed
        if client_id:
            query = query.join(
                ClientModule,
                and_(
                    ClientModule.module_id == Module.id,
                    ClientModule.client_id == client_id,
                    ClientModule.is_active == True,
                )
            )

        # Apply filters
        if application_id:
            query = query.filter(Module.application_id == application_id)
        
        if is_active is not None:
            query = query.filter(Module.is_active == is_active)
            
        if is_public is not None:
            query = query.filter(Module.is_public == is_public)
        
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
        updated_by: Optional[int] = None
    ) -> Optional[Module]:
        """Update a module"""
        db_module = ModuleService.get_module(db, module_id)
        if not db_module:
            return None
        
        update_data = module_data.model_dump(exclude_unset=True)
        if updated_by:
            update_data["updated_by"] = updated_by
        
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

    @staticmethod
    def reorder_modules(
        db: Session,
        application_id: str,
        module_orders: List[Dict[str, Any]],
        updated_by: Optional[int] = None
    ) -> bool:
        """Reorder modules within an application"""
        try:
            for order_data in module_orders:
                module_id = order_data.get("module_id")
                new_order = order_data.get("order_index")
                
                if module_id and new_order is not None:
                    db_module = db.query(Module).filter(
                        and_(
                            Module.id == module_id,
                            Module.application_id == application_id,
                            Module.is_deleted == False
                        )
                    ).first()
                    
                    if db_module:
                        db_module.order_index = new_order
                        if updated_by:
                            db_module.updated_by = updated_by
            
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False