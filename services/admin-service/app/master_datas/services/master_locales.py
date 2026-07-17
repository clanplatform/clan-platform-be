from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc

from app.master_datas.models.master_locales import MasterLocale
from app.master_datas.models.master_languages import MasterLanguage
from app.master_datas.models.master_countries import MasterCountry
from app.master_datas.schemas.master_locales import MasterLocaleCreate, MasterLocaleUpdate
from app.master_datas.schemas.master_languages import normalize_locale_tag
from app.master_datas.exceptions import (
    LocaleNotFoundError,
    DuplicateLocaleError,
    LanguageNotFoundError,
    CountryNotFoundError,
)

# No display_order column on this table, so locale_code is the natural default sort.
SORTABLE_FIELDS = {"locale_code", "locale_name", "created_at", "updated_at"}


class MasterLocaleService:

    @staticmethod
    def _assert_language_exists(db: Session, language_id: UUID) -> None:
        if not db.query(MasterLanguage.id).filter(MasterLanguage.id == language_id).first():
            raise LanguageNotFoundError(str(language_id))

    @staticmethod
    def _assert_country_exists(db: Session, country_id: UUID) -> None:
        if not db.query(MasterCountry.id).filter(MasterCountry.id == country_id).first():
            raise CountryNotFoundError(str(country_id))

    @staticmethod
    def _assert_unique(db: Session, data: dict, exclude_id: Optional[UUID] = None) -> None:
        for field in ("locale_code", "locale_name"):
            value = data.get(field)
            if value is None:
                continue
            query = db.query(MasterLocale.id).filter(getattr(MasterLocale, field) == value)
            if exclude_id is not None:
                query = query.filter(MasterLocale.id != exclude_id)
            if query.first():
                raise DuplicateLocaleError(field, str(value))

    @staticmethod
    def _assert_pair_unique(
        db: Session, language_id: UUID, country_id: Optional[UUID], exclude_id: Optional[UUID] = None
    ) -> None:
        """
        One locale per language/country pairing. Checked here rather than relying
        solely on the DB constraint: Postgres treats NULL country_id values as
        distinct, so two language-only locales would otherwise both be allowed.
        """
        query = db.query(MasterLocale.id).filter(MasterLocale.language_id == language_id)
        query = query.filter(
            MasterLocale.country_id.is_(None) if country_id is None
            else MasterLocale.country_id == country_id
        )
        if exclude_id is not None:
            query = query.filter(MasterLocale.id != exclude_id)
        if query.first():
            raise DuplicateLocaleError(
                "language/country combination", f"{language_id} / {country_id or 'none'}"
            )

    @staticmethod
    def _clear_default(db: Session, keep_id: Optional[UUID] = None) -> None:
        """Unset is_default everywhere except keep_id, so at most one default survives."""
        query = db.query(MasterLocale).filter(MasterLocale.is_default == True)
        if keep_id is not None:
            query = query.filter(MasterLocale.id != keep_id)
        query.update({MasterLocale.is_default: False}, synchronize_session=False)

    @staticmethod
    def create_locale(db: Session, locale_data: MasterLocaleCreate) -> MasterLocale:
        data = locale_data.model_dump()

        MasterLocaleService._assert_language_exists(db, data["language_id"])
        if data.get("country_id") is not None:
            MasterLocaleService._assert_country_exists(db, data["country_id"])
        MasterLocaleService._assert_unique(db, data)
        MasterLocaleService._assert_pair_unique(db, data["language_id"], data.get("country_id"))

        db_locale = MasterLocale(**data)
        if db_locale.is_default:
            MasterLocaleService._clear_default(db)

        db.add(db_locale)
        db.commit()
        db.refresh(db_locale)
        return db_locale

    @staticmethod
    def get_locale(db: Session, locale_id: UUID) -> Optional[MasterLocale]:
        return db.query(MasterLocale).filter(MasterLocale.id == locale_id).first()

    @staticmethod
    def get_locale_by_code(db: Session, locale_code: str) -> Optional[MasterLocale]:
        return db.query(MasterLocale).filter(
            MasterLocale.locale_code == normalize_locale_tag(locale_code)
        ).first()

    @staticmethod
    def get_default_locale(db: Session) -> Optional[MasterLocale]:
        return db.query(MasterLocale).filter(MasterLocale.is_default == True).first()

    @staticmethod
    def get_locales(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        language_id: Optional[UUID] = None,
        country_id: Optional[UUID] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "locale_code",
        sort_order: str = "asc",
    ) -> Tuple[List[MasterLocale], int]:
        query = db.query(MasterLocale)

        if language_id is not None:
            query = query.filter(MasterLocale.language_id == language_id)
        if country_id is not None:
            query = query.filter(MasterLocale.country_id == country_id)
        if is_active is not None:
            query = query.filter(MasterLocale.is_active == is_active)
        if search:
            term = f"%{search}%"
            query = query.filter(
                or_(
                    MasterLocale.locale_code.ilike(term),
                    MasterLocale.locale_name.ilike(term),
                )
            )

        total = query.count()

        if sort_by in SORTABLE_FIELDS:
            col = getattr(MasterLocale, sort_by)
            query = query.order_by(desc(col) if sort_order.lower() == "desc" else asc(col))
        # Tie-break on id so pages don't overlap when the sort column repeats.
        query = query.order_by(asc(MasterLocale.id))

        locales = query.offset(skip).limit(limit).all()
        return locales, total

    @staticmethod
    def update_locale(db: Session, locale_id: UUID, locale_data: MasterLocaleUpdate) -> MasterLocale:
        db_locale = MasterLocaleService.get_locale(db, locale_id)
        if not db_locale:
            raise LocaleNotFoundError(str(locale_id))

        update_data = locale_data.model_dump(exclude_unset=True)

        # Re-point checks run against the language/country the row will end up on.
        target_language_id = update_data.get("language_id", db_locale.language_id)
        target_country_id = update_data.get("country_id", db_locale.country_id)

        if "language_id" in update_data:
            MasterLocaleService._assert_language_exists(db, target_language_id)
        if "country_id" in update_data and target_country_id is not None:
            MasterLocaleService._assert_country_exists(db, target_country_id)

        MasterLocaleService._assert_unique(db, update_data, exclude_id=locale_id)
        if "language_id" in update_data or "country_id" in update_data:
            MasterLocaleService._assert_pair_unique(
                db, target_language_id, target_country_id, exclude_id=locale_id
            )

        if update_data.get("is_default") is True:
            MasterLocaleService._clear_default(db, keep_id=locale_id)

        for field, value in update_data.items():
            setattr(db_locale, field, value)

        db.commit()
        db.refresh(db_locale)
        return db_locale

    @staticmethod
    def set_default_locale(db: Session, locale_id: UUID) -> MasterLocale:
        db_locale = MasterLocaleService.get_locale(db, locale_id)
        if not db_locale:
            raise LocaleNotFoundError(str(locale_id))

        MasterLocaleService._clear_default(db, keep_id=locale_id)
        db_locale.is_default = True
        db.commit()
        db.refresh(db_locale)
        return db_locale

    @staticmethod
    def delete_locale(db: Session, locale_id: UUID) -> MasterLocale:
        db_locale = MasterLocaleService.get_locale(db, locale_id)
        if not db_locale:
            raise LocaleNotFoundError(str(locale_id))

        db.delete(db_locale)
        db.commit()
        return db_locale
