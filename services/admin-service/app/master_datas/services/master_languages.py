from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc

from app.master_datas.models.master_languages import MasterLanguage
from app.master_datas.models.master_locales import MasterLocale
from app.master_datas.schemas.master_languages import MasterLanguageCreate, MasterLanguageUpdate
from app.master_datas.exceptions import (
    LanguageNotFoundError,
    DuplicateLanguageError,
    ReferencedByChildrenError,
)

SORTABLE_FIELDS = {
    "display_order", "language_name", "native_name", "iso639_1",
    "iso639_2", "locale", "created_at", "updated_at",
}


class MasterLanguageService:

    @staticmethod
    def _assert_unique(db: Session, data: dict, exclude_id: Optional[UUID] = None) -> None:
        """Reject values already taken by another row, naming the field that clashed."""
        for field in ("language_name", "iso639_1", "iso639_2", "locale"):
            value = data.get(field)
            if value is None:
                continue
            query = db.query(MasterLanguage.id).filter(getattr(MasterLanguage, field) == value)
            if exclude_id is not None:
                query = query.filter(MasterLanguage.id != exclude_id)
            if query.first():
                raise DuplicateLanguageError(field, str(value))

    @staticmethod
    def _clear_default(db: Session, keep_id: Optional[UUID] = None) -> None:
        """Unset is_default everywhere except keep_id, so at most one default survives."""
        query = db.query(MasterLanguage).filter(MasterLanguage.is_default == True)
        if keep_id is not None:
            query = query.filter(MasterLanguage.id != keep_id)
        query.update({MasterLanguage.is_default: False}, synchronize_session=False)

    @staticmethod
    def create_language(db: Session, language_data: MasterLanguageCreate) -> MasterLanguage:
        data = language_data.model_dump()
        MasterLanguageService._assert_unique(db, data)

        db_language = MasterLanguage(**data)
        if db_language.is_default:
            MasterLanguageService._clear_default(db)

        db.add(db_language)
        db.commit()
        db.refresh(db_language)
        return db_language

    @staticmethod
    def get_language(db: Session, language_id: UUID) -> Optional[MasterLanguage]:
        return db.query(MasterLanguage).filter(MasterLanguage.id == language_id).first()

    @staticmethod
    def get_language_by_iso639_1(db: Session, iso639_1: str) -> Optional[MasterLanguage]:
        return db.query(MasterLanguage).filter(
            MasterLanguage.iso639_1 == iso639_1.strip().lower()
        ).first()

    @staticmethod
    def get_default_language(db: Session) -> Optional[MasterLanguage]:
        return db.query(MasterLanguage).filter(MasterLanguage.is_default == True).first()

    @staticmethod
    def get_languages(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        text_direction: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "display_order",
        sort_order: str = "asc",
    ) -> Tuple[List[MasterLanguage], int]:
        query = db.query(MasterLanguage)

        if is_active is not None:
            query = query.filter(MasterLanguage.is_active == is_active)
        if text_direction:
            query = query.filter(MasterLanguage.text_direction == text_direction.strip().lower())
        if search:
            term = f"%{search}%"
            query = query.filter(
                or_(
                    MasterLanguage.language_name.ilike(term),
                    MasterLanguage.native_name.ilike(term),
                    MasterLanguage.iso639_1.ilike(term),
                    MasterLanguage.iso639_2.ilike(term),
                    MasterLanguage.locale.ilike(term),
                )
            )

        total = query.count()

        if sort_by in SORTABLE_FIELDS:
            col = getattr(MasterLanguage, sort_by)
            query = query.order_by(desc(col) if sort_order.lower() == "desc" else asc(col))
        # Tie-break on id so pages don't overlap when the sort column repeats.
        query = query.order_by(asc(MasterLanguage.id))

        languages = query.offset(skip).limit(limit).all()
        return languages, total

    @staticmethod
    def update_language(db: Session, language_id: UUID, language_data: MasterLanguageUpdate) -> MasterLanguage:
        db_language = MasterLanguageService.get_language(db, language_id)
        if not db_language:
            raise LanguageNotFoundError(str(language_id))

        update_data = language_data.model_dump(exclude_unset=True)
        MasterLanguageService._assert_unique(db, update_data, exclude_id=language_id)

        if update_data.get("is_default") is True:
            MasterLanguageService._clear_default(db, keep_id=language_id)

        for field, value in update_data.items():
            setattr(db_language, field, value)

        db.commit()
        db.refresh(db_language)
        return db_language

    @staticmethod
    def set_default_language(db: Session, language_id: UUID) -> MasterLanguage:
        db_language = MasterLanguageService.get_language(db, language_id)
        if not db_language:
            raise LanguageNotFoundError(str(language_id))

        MasterLanguageService._clear_default(db, keep_id=language_id)
        db_language.is_default = True
        db.commit()
        db.refresh(db_language)
        return db_language

    @staticmethod
    def delete_language(db: Session, language_id: UUID) -> MasterLanguage:
        db_language = MasterLanguageService.get_language(db, language_id)
        if not db_language:
            raise LanguageNotFoundError(str(language_id))

        locale_count = db.query(MasterLocale.id).filter(MasterLocale.language_id == language_id).count()
        if locale_count:
            raise ReferencedByChildrenError("language", "locale(s)", locale_count)

        db.delete(db_language)
        db.commit()
        return db_language
