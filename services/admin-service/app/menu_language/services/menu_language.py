from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_
from uuid import UUID
from app.models.menu_language import MenuLanguage
from app.models.application import Application
from app.models.modules import Module
from app.models.menu import Menu
from app.schemas.menu_language import MenuLanguageCreate, MenuLanguageUpdate


class MenuLanguageService:
    """Service for managing menu language translations"""

    def create_menu_language(
        self,
        db: Session,
        menu_language_data: MenuLanguageCreate
    ) -> MenuLanguage:
        """Create a new menu language entry"""
        db_menu_language = MenuLanguage(
            lang_code=menu_language_data.lang_code,
            language=menu_language_data.language,
            translated_name=menu_language_data.translated_name,
            app_menu_entity_type=menu_language_data.app_menu_entity_type,
            app_menu_entity_id=menu_language_data.app_menu_entity_id
        )
        db.add(db_menu_language)
        db.commit()
        db.refresh(db_menu_language)
        return db_menu_language

    def get_menu_language_by_id(
        self,
        db: Session,
        menu_language_id: UUID
    ) -> Optional[MenuLanguage]:
        """Get a menu language entry by ID"""
        return db.query(MenuLanguage).filter(
            and_(
                MenuLanguage.id == menu_language_id,
                MenuLanguage.deleted_at.is_(None)
            )
        ).first()

    def get_all_menu_languages(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100
    ) -> List[MenuLanguage]:
        """Get all menu language entries (not deleted)"""
        return db.query(MenuLanguage).filter(
            MenuLanguage.deleted_at.is_(None)
        ).offset(skip).limit(limit).all()

    def get_menu_languages_by_lang_code(
        self,
        db: Session,
        lang_code: str
    ) -> List[MenuLanguage]:
        """Get all menu language entries for a specific language code"""
        return db.query(MenuLanguage).filter(
            and_(
                MenuLanguage.lang_code == lang_code,
                MenuLanguage.deleted_at.is_(None)
            )
        ).all()

    def get_translations_with_entities(
        self,
        db: Session,
        lang_code: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all translations for a language code with full entity details.
        Returns a structured dictionary with applications, modules, and menus.
        """
        # Get all translations for the language
        translations = self.get_menu_languages_by_lang_code(db, lang_code)
        
        # Initialize result structure
        result = {
            "applications": [],
            "modules": [],
            "menus": []
        }
        
        # Group translations by entity type
        app_translations = {}
        module_translations = {}
        menu_translations = {}
        
        for trans in translations:
            entity_type = trans.app_menu_entity_type.lower()
            entity_id = trans.app_menu_entity_id
            
            if entity_type == "application":
                app_translations[entity_id] = trans.translated_name
            elif entity_type == "module":
                module_translations[entity_id] = trans.translated_name
            elif entity_type == "menu":
                menu_translations[entity_id] = trans.translated_name
        
        # Fetch and merge application data
        if app_translations:
            apps = db.query(Application).filter(
                Application.id.in_(app_translations.keys()),
                Application.is_deleted == False
            ).all()
            
            for app in apps:
                result["applications"].append({
                    "id": str(app.id),
                    "original_name": app.name,
                    "translated_name": app_translations.get(app.id),
                    "code": getattr(app, 'code', None),
                    "key": app.key,
                    "label": app.label,
                    "icon": app.icon,
                    "route": app.route,
                    "order_index": app.order_index
                })
        
        # Fetch and merge module data
        if module_translations:
            modules = db.query(Module).filter(
                Module.id.in_(module_translations.keys()),
                Module.is_deleted == False
            ).all()
            
            for module in modules:
                result["modules"].append({
                    "id": str(module.id),
                    "application_id": str(module.application_id),
                    "original_name": module.name,
                    "translated_name": module_translations.get(module.id),
                    "code": module.code,
                    "key": module.key,
                    "label": module.label,
                    "icon": module.icon,
                    "route": module.route,
                    "order_index": module.order_index
                })
        
        # Fetch and merge menu data
        if menu_translations:
            menus = db.query(Menu).filter(
                Menu.id.in_(menu_translations.keys()),
                Menu.deleted_at.is_(None)
            ).all()
            
            for menu in menus:
                result["menus"].append({
                    "id": str(menu.id),
                    "application_id": str(menu.application_id),
                    "module_id": str(menu.module_id) if menu.module_id else None,
                    "original_name": menu.name,
                    "translated_name": menu_translations.get(menu.id),
                    "label": menu.label,
                    "icon": menu.icon,
                    "route": menu.route,
                    "order_index": menu.order_index,
                    "parent_menu_id": str(menu.parent_menu_id) if menu.parent_menu_id else None
                })
        
        return result

    def get_translation_map(
        self,
        db: Session,
        lang_code: str
    ) -> Dict[str, str]:
        """
        Get a simple translation map for a language code.
        Returns a dictionary mapping entity_id to translated_name.
        """
        translations = self.get_menu_languages_by_lang_code(db, lang_code)
        
        translation_map = {}
        for trans in translations:
            translation_map[str(trans.app_menu_entity_id)] = trans.translated_name
        
        return translation_map

    def get_menu_languages_by_entity_type(
        self,
        db: Session,
        entity_type: str
    ) -> List[MenuLanguage]:
        """Get all menu language entries for a specific entity type"""
        return db.query(MenuLanguage).filter(
            and_(
                MenuLanguage.app_menu_entity_type == entity_type,
                MenuLanguage.deleted_at.is_(None)
            )
        ).all()

    def get_menu_languages_by_entity(
        self,
        db: Session,
        entity_type: str,
        entity_id: UUID
    ) -> List[MenuLanguage]:
        """Get all menu language entries for a specific entity"""
        return db.query(MenuLanguage).filter(
            and_(
                MenuLanguage.app_menu_entity_type == entity_type,
                MenuLanguage.app_menu_entity_id == entity_id,
                MenuLanguage.deleted_at.is_(None)
            )
        ).all()

    def get_menu_language_by_filters(
        self,
        db: Session,
        lang_code: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None
    ) -> List[MenuLanguage]:
        """Get menu language entries by multiple filters"""
        query = db.query(MenuLanguage).filter(MenuLanguage.deleted_at.is_(None))
        
        if lang_code:
            query = query.filter(MenuLanguage.lang_code == lang_code)
        if entity_type:
            query = query.filter(MenuLanguage.app_menu_entity_type == entity_type)
        if entity_id:
            query = query.filter(MenuLanguage.app_menu_entity_id == entity_id)
        
        return query.all()

    def update_menu_language(
        self,
        db: Session,
        menu_language_id: UUID,
        menu_language_data: MenuLanguageUpdate
    ) -> Optional[MenuLanguage]:
        """Update a menu language entry"""
        db_menu_language = self.get_menu_language_by_id(db, menu_language_id)
        
        if not db_menu_language:
            return None
        
        update_data = menu_language_data.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(db_menu_language, field, value)
        
        db.commit()
        db.refresh(db_menu_language)
        return db_menu_language

    def delete_menu_language(
        self,
        db: Session,
        menu_language_id: UUID
    ) -> bool:
        """Soft delete a menu language entry"""
        db_menu_language = self.get_menu_language_by_id(db, menu_language_id)
        
        if not db_menu_language:
            return False
        
        db_menu_language.deleted_at = datetime.utcnow()
        db.commit()
        return True

    def hard_delete_menu_language(
        self,
        db: Session,
        menu_language_id: UUID
    ) -> bool:
        """Permanently delete a menu language entry"""
        db_menu_language = self.get_menu_language_by_id(db, menu_language_id)
        
        if not db_menu_language:
            return False
        
        db.delete(db_menu_language)
        db.commit()
        return True


# Global instance
menu_language_service = MenuLanguageService()
