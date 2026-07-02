from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func
from app.forms.models.forms import Form
from app.forms.schemas.forms import FormCreate, FormUpdate, FormImport
from app.infrastructure.audit_tenant import fire_audit_log
from datetime import datetime

class FormsService:
    """Service for managing forms"""

    @staticmethod
    def create_form(db: Session, form_data: FormCreate, created_by: Optional[str] = None) -> Form:
        """Create a new form"""
        # Convert form to dict for JSON storage
        form_dict = form_data.model_dump()
        form_dict['created_by'] = created_by
        
        db_form = Form(**form_dict)
        db.add(db_form)
        db.commit()
        db.refresh(db_form)
        fire_audit_log(
            action="CREATE", object_type="Form",
            object_id=str(db_form.id),
            user_id=created_by,
            new_values={"name": db_form.name, "menu_id": str(db_form.menu_id) if db_form.menu_id else None},
        )
        return db_form

    @staticmethod
    def create_form_from_import(
        db: Session, 
        menu_id: str, 
        import_data: FormImport, 
        created_by: Optional[str] = None
    ) -> Form:
        """Create a form from imported JSON data"""
        
        # Convert import data to form creation data
        form_data = {
            'menu_id': menu_id,
            'name': import_data.name,
            'version': import_data.version,
            'trigger_when': import_data.trigger_when,
            'forms': [item.model_dump() if hasattr(item, 'model_dump') else item for item in import_data.forms],
            'actions': import_data.actions or {},
            'modal_type': import_data.modal_type or "AntModalAdapter",
            'tooltip_type': import_data.tooltip_type or "AntTooltip", 
            'error_type': import_data.error_type or "AntErrorMessage",
            'localization': import_data.localization or {},
            'languages': [lang.model_dump() if hasattr(lang, 'model_dump') else lang for lang in (import_data.languages or [])],
            'default_language': import_data.default_language or "en-US",
            'created_by': created_by
        }
        
        db_form = Form(**form_data)
        db.add(db_form)
        db.commit()
        db.refresh(db_form)
        return db_form

    @staticmethod
    def get_form(db: Session, form_id: str) -> Optional[Form]:
        """Get a form by ID"""
        return db.query(Form).filter(
            and_(
                Form.id == form_id,
                Form.is_deleted == False
            )
        ).first()

    @staticmethod
    def get_form_by_name(db: Session, name: str, menu_id: Optional[str] = None) -> Optional[Form]:
        """Get a form by name, optionally filtered by menu"""
        query = db.query(Form).filter(
            and_(
                Form.name == name,
                Form.is_deleted == False
            )
        )
        
        if menu_id:
            query = query.filter(Form.menu_id == menu_id)
            
        return query.first()

    @staticmethod
    def get_forms(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        menu_id: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> tuple[List[Form], int]:
        """Get forms with filtering and pagination"""
        
        query = db.query(Form).filter(Form.is_deleted == False)
        
        # Apply filters
        if menu_id:
            query = query.filter(Form.menu_id == menu_id)
        
        if is_active is not None:
            query = query.filter(Form.is_active == is_active)
        
        if search:
            search_filter = or_(
                Form.name.ilike(f"%{search}%"),
                Form.version.ilike(f"%{search}%"),
                Form.trigger_when.ilike(f"%{search}%")
            )
            query = query.filter(search_filter)
        
        # Apply sorting
        if hasattr(Form, sort_by):
            if sort_order.lower() == "desc":
                query = query.order_by(desc(getattr(Form, sort_by)))
            else:
                query = query.order_by(asc(getattr(Form, sort_by)))
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        forms = query.offset(skip).limit(limit).all()
        
        return forms, total

    @staticmethod
    def get_forms_by_menu(db: Session, menu_id: str, is_active: Optional[bool] = None) -> List[Form]:
        """Get all forms for a specific menu"""
        query = db.query(Form).filter(
            and_(
                Form.menu_id == menu_id,
                Form.is_deleted == False
            )
        )
        
        if is_active is not None:
            query = query.filter(Form.is_active == is_active)
            
        return query.order_by(Form.name, Form.version).all()

    @staticmethod
    def update_form(
        db: Session,
        form_id: str,
        form_data: FormUpdate,
        updated_by: Optional[str] = None
    ) -> Optional[Form]:
        """Update a form"""
        db_form = FormsService.get_form(db, form_id)
        if not db_form:
            return None
        
        update_data = form_data.model_dump(exclude_unset=True)
        if updated_by:
            update_data["updated_by"] = updated_by
        
        for field, value in update_data.items():
            setattr(db_form, field, value)
        
        db.commit()
        db.refresh(db_form)
        fire_audit_log(
            action="UPDATE", object_type="Form",
            object_id=str(form_id),
            user_id=updated_by,
            new_values=update_data,
        )
        return db_form

    @staticmethod
    def delete_form(db: Session, form_id: str, deleted_by: Optional[str] = None) -> bool:
        """Soft delete a form"""
        db_form = FormsService.get_form(db, form_id)
        if not db_form:
            return False
        
        db_form.is_deleted = True
        db_form.is_active = False
        if deleted_by:
            db_form.updated_by = deleted_by

        db.commit()
        fire_audit_log(
            action="DELETE", object_type="Form",
            object_id=str(form_id),
            user_id=deleted_by,
            old_values={"is_deleted": False}, new_values={"is_deleted": True},
        )
        return True

    @staticmethod
    def activate_form(db: Session, form_id: str, activated_by: Optional[str] = None) -> Optional[Form]:
        """Activate a form"""
        db_form = FormsService.get_form(db, form_id)
        if not db_form:
            return None
        
        db_form.is_active = True
        if activated_by:
            db_form.updated_by = activated_by
        
        db.commit()
        db.refresh(db_form)
        return db_form

    @staticmethod
    def deactivate_form(db: Session, form_id: str, deactivated_by: Optional[str] = None) -> Optional[Form]:
        """Deactivate a form"""
        db_form = FormsService.get_form(db, form_id)
        if not db_form:
            return None
        
        db_form.is_active = False
        if deactivated_by:
            db_form.updated_by = deactivated_by
        
        db.commit()
        db.refresh(db_form)
        return db_form

    @staticmethod
    def duplicate_form(
        db: Session, 
        form_id: str, 
        new_name: str, 
        new_version: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> Optional[Form]:
        """Duplicate an existing form"""
        original_form = FormsService.get_form(db, form_id)
        if not original_form:
            return None
        
        # Create new form data
        new_form_data = {
            'menu_id': original_form.menu_id,
            'name': new_name,
            'version': new_version or f"{original_form.version}-copy",
            'trigger_when': original_form.trigger_when,
            'forms': original_form.forms,
            'actions': original_form.actions,
            'modal_type': original_form.modal_type,
            'tooltip_type': original_form.tooltip_type,
            'error_type': original_form.error_type,
            'localization': original_form.localization,
            'languages': original_form.languages,
            'default_language': original_form.default_language,
            'is_active': True,
            'created_by': created_by
        }
        
        new_form = Form(**new_form_data)
        db.add(new_form)
        db.commit()
        db.refresh(new_form)
        return new_form

    @staticmethod
    def get_form_statistics(db: Session, menu_id: Optional[str] = None) -> Dict[str, Any]:
        """Get form statistics"""
        query = db.query(Form).filter(Form.is_deleted == False)
        
        if menu_id:
            query = query.filter(Form.menu_id == menu_id)
        
        total_forms = query.count()
        active_forms = query.filter(Form.is_active == True).count()
        inactive_forms = query.filter(Form.is_active == False).count()
        
        # Get forms by type (based on forms[0].form.type)
        forms_by_type = {}
        all_forms = query.all()
        for form in all_forms:
            if form.forms and len(form.forms) > 0:
                first_form = form.forms[0]
                if isinstance(first_form, dict) and 'form' in first_form:
                    form_type = first_form['form'].get('type', 'Unknown')
                    forms_by_type[form_type] = forms_by_type.get(form_type, 0) + 1
        
        return {
            'total_forms': total_forms,
            'active_forms': active_forms,
            'inactive_forms': inactive_forms,
            'forms_by_type': forms_by_type,
            'menu_id': menu_id
        }

    @staticmethod
    def search_forms_by_component(
        db: Session, 
        component_type: str, 
        menu_id: Optional[str] = None
    ) -> List[Form]:
        """Search forms that contain a specific component type"""
        query = db.query(Form).filter(Form.is_deleted == False)
        
        if menu_id:
            query = query.filter(Form.menu_id == menu_id)
        
        # Search in forms JSON for component type
        # This uses PostgreSQL JSON operators
        query = query.filter(
            func.jsonb_path_exists(
                Form.forms,
                f'$[*].form.children[*] ? (@.type == "{component_type}")'
            )
        )
        
        return query.all()

    @staticmethod
    def get_forms_with_access_level(
        db: Session, 
        access_level: str, 
        menu_id: Optional[str] = None
    ) -> List[Form]:
        """Get forms that have components with specific access level"""
        query = db.query(Form).filter(Form.is_deleted == False)
        
        if menu_id:
            query = query.filter(Form.menu_id == menu_id)
        
        # Search for forms with components having specific access level
        query = query.filter(
            func.jsonb_path_exists(
                Form.forms,
                f'$[*].form.children[*] ? (@.access[*] == "{access_level}")'
            )
        )
        
        return query.all()