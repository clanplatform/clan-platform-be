from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone

from app.form_language.models.form_language import FormLanguage
from app.form_language.schemas.form_language import FormLanguageCreate, FormLanguageUpdate
from app.infrastructure.audit_client import fire_audit_log


class FormLanguageService:
    """Service for managing form language translations"""

    @staticmethod
    def create(db: Session, form_language: FormLanguageCreate) -> FormLanguage:
        """Create a new form language translation"""
        db_form_language = FormLanguage(**form_language.model_dump())
        db.add(db_form_language)
        db.commit()
        db.refresh(db_form_language)
        fire_audit_log(
            action="CREATE", object_type="FormLanguage",
            object_id=str(db_form_language.id),
            new_values={"lang_code": db_form_language.lang_code, "entity_id": str(db_form_language.app_form_entity_id)},
        )
        return db_form_language

    @staticmethod
    def bulk_create(db: Session, form_languages: List[FormLanguageCreate]) -> List[FormLanguage]:
        """Bulk create form language translations"""
        db_form_languages = [FormLanguage(**fl.model_dump()) for fl in form_languages]
        db.add_all(db_form_languages)
        db.commit()
        for db_fl in db_form_languages:
            db.refresh(db_fl)
        return db_form_languages

    @staticmethod
    def get_by_id(db: Session, form_language_id: UUID) -> Optional[FormLanguage]:
        """Get form language translation by ID"""
        return db.query(FormLanguage).filter(
            and_(
                FormLanguage.id == form_language_id,
                FormLanguage.deleted_at.is_(None)
            )
        ).first()

    @staticmethod
    def get_all(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        lang_code: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[UUID] = None
    ) -> List[FormLanguage]:
        """Get all form language translations with optional filters"""
        query = db.query(FormLanguage).filter(FormLanguage.deleted_at.is_(None))
        
        if lang_code:
            query = query.filter(FormLanguage.lang_code == lang_code)
        
        if entity_type:
            query = query.filter(FormLanguage.app_form_entity_type == entity_type)
        
        if entity_id:
            query = query.filter(FormLanguage.app_form_entity_id == entity_id)
        
        return query.order_by(FormLanguage.sino.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def get_by_entity(
        db: Session,
        entity_id: UUID,
        lang_code: Optional[str] = None
    ) -> List[FormLanguage]:
        """Get all translations for a specific form entity"""
        query = db.query(FormLanguage).filter(
            and_(
                FormLanguage.app_form_entity_id == entity_id,
                FormLanguage.deleted_at.is_(None)
            )
        )
        
        if lang_code:
            query = query.filter(FormLanguage.lang_code == lang_code)
        
        return query.order_by(FormLanguage.sino).all()

    @staticmethod
    def get_by_lang_code(db: Session, lang_code: str) -> List[FormLanguage]:
        """Get all translations for a specific language"""
        return db.query(FormLanguage).filter(
            and_(
                FormLanguage.lang_code == lang_code,
                FormLanguage.deleted_at.is_(None)
            )
        ).order_by(FormLanguage.sino).all()

    @staticmethod
    def update(
        db: Session,
        form_language_id: UUID,
        form_language_update: FormLanguageUpdate
    ) -> Optional[FormLanguage]:
        """Update a form language translation"""
        db_form_language = FormLanguageService.get_by_id(db, form_language_id)
        
        if not db_form_language:
            return None
        
        update_data = form_language_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_form_language, field, value)
        
        db_form_language.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(db_form_language)
        fire_audit_log(
            action="UPDATE", object_type="FormLanguage",
            object_id=str(form_language_id),
            new_values=update_data,
        )
        return db_form_language

    @staticmethod
    def delete(db: Session, form_language_id: UUID) -> bool:
        """Soft delete a form language translation"""
        db_form_language = FormLanguageService.get_by_id(db, form_language_id)
        
        if not db_form_language:
            return False
        
        db_form_language.deleted_at = datetime.now(timezone.utc)
        db.commit()
        fire_audit_log(
            action="DELETE", object_type="FormLanguage",
            object_id=str(form_language_id),
        )
        return True

    @staticmethod
    def hard_delete(db: Session, form_language_id: UUID) -> bool:
        """Permanently delete a form language translation"""
        db_form_language = db.query(FormLanguage).filter(
            FormLanguage.id == form_language_id
        ).first()
        
        if not db_form_language:
            return False
        
        db.delete(db_form_language)
        db.commit()
        return True

    @staticmethod
    def search(
        db: Session,
        search_term: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[FormLanguage]:
        """Search form language translations by translated_name, key, or value"""
        search_pattern = f"%{search_term}%"
        return db.query(FormLanguage).filter(
            and_(
                FormLanguage.deleted_at.is_(None),
                or_(
                    FormLanguage.translated_name.ilike(search_pattern),
                    FormLanguage.key.ilike(search_pattern),
                    FormLanguage.value.ilike(search_pattern)
                )
            )
        ).order_by(FormLanguage.sino.desc()).offset(skip).limit(limit).all()
