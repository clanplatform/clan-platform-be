from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc

from app.master_datas.models.master_countries import MasterCountry
from app.master_datas.models.master_states import MasterState
from app.master_datas.models.master_locales import MasterLocale
from app.master_datas.schemas.master_countries import MasterCountryCreate, MasterCountryUpdate
from app.master_datas.exceptions import (
    CountryNotFoundError,
    DuplicateCountryError,
    ReferencedByChildrenError,
)

SORTABLE_FIELDS = {
    "display_order", "country_name", "iso2_code", "iso3_code",
    "numeric_code", "currency_code", "created_at", "updated_at",
}


class MasterCountryService:

    @staticmethod
    def _assert_unique(db: Session, data: dict, exclude_id: Optional[UUID] = None) -> None:
        """Reject values already taken by another row, naming the field that clashed."""
        for field in ("country_name", "iso2_code", "iso3_code", "numeric_code"):
            value = data.get(field)
            if value is None:
                continue
            query = db.query(MasterCountry.id).filter(getattr(MasterCountry, field) == value)
            if exclude_id is not None:
                query = query.filter(MasterCountry.id != exclude_id)
            if query.first():
                raise DuplicateCountryError(field, str(value))

    @staticmethod
    def _clear_default(db: Session, keep_id: Optional[UUID] = None) -> None:
        """Unset is_default everywhere except keep_id, so at most one default survives."""
        query = db.query(MasterCountry).filter(MasterCountry.is_default == True)
        if keep_id is not None:
            query = query.filter(MasterCountry.id != keep_id)
        query.update({MasterCountry.is_default: False}, synchronize_session=False)

    @staticmethod
    def create_country(db: Session, country_data: MasterCountryCreate) -> MasterCountry:
        data = country_data.model_dump()
        MasterCountryService._assert_unique(db, data)

        db_country = MasterCountry(**data)
        if db_country.is_default:
            MasterCountryService._clear_default(db)

        db.add(db_country)
        db.commit()
        db.refresh(db_country)
        return db_country

    @staticmethod
    def get_country(db: Session, country_id: UUID) -> Optional[MasterCountry]:
        return db.query(MasterCountry).filter(MasterCountry.id == country_id).first()

    @staticmethod
    def get_country_by_iso2(db: Session, iso2_code: str) -> Optional[MasterCountry]:
        return db.query(MasterCountry).filter(
            MasterCountry.iso2_code == iso2_code.strip().upper()
        ).first()

    @staticmethod
    def get_default_country(db: Session) -> Optional[MasterCountry]:
        return db.query(MasterCountry).filter(MasterCountry.is_default == True).first()

    @staticmethod
    def get_countries(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
        currency_code: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "display_order",
        sort_order: str = "asc",
    ) -> Tuple[List[MasterCountry], int]:
        query = db.query(MasterCountry)

        if is_active is not None:
            query = query.filter(MasterCountry.is_active == is_active)
        if currency_code:
            query = query.filter(MasterCountry.currency_code == currency_code.strip().upper())
        if search:
            term = f"%{search}%"
            query = query.filter(
                or_(
                    MasterCountry.country_name.ilike(term),
                    MasterCountry.iso2_code.ilike(term),
                    MasterCountry.iso3_code.ilike(term),
                    MasterCountry.nationality.ilike(term),
                )
            )

        total = query.count()

        if sort_by in SORTABLE_FIELDS:
            col = getattr(MasterCountry, sort_by)
            query = query.order_by(desc(col) if sort_order.lower() == "desc" else asc(col))
        # Tie-break on id so pages don't overlap when the sort column repeats.
        query = query.order_by(asc(MasterCountry.id))

        countries = query.offset(skip).limit(limit).all()
        return countries, total

    @staticmethod
    def update_country(db: Session, country_id: UUID, country_data: MasterCountryUpdate) -> MasterCountry:
        db_country = MasterCountryService.get_country(db, country_id)
        if not db_country:
            raise CountryNotFoundError(str(country_id))

        update_data = country_data.model_dump(exclude_unset=True)
        MasterCountryService._assert_unique(db, update_data, exclude_id=country_id)

        if update_data.get("is_default") is True:
            MasterCountryService._clear_default(db, keep_id=country_id)

        for field, value in update_data.items():
            setattr(db_country, field, value)

        db.commit()
        db.refresh(db_country)
        return db_country

    @staticmethod
    def set_default_country(db: Session, country_id: UUID) -> MasterCountry:
        db_country = MasterCountryService.get_country(db, country_id)
        if not db_country:
            raise CountryNotFoundError(str(country_id))

        MasterCountryService._clear_default(db, keep_id=country_id)
        db_country.is_default = True
        db.commit()
        db.refresh(db_country)
        return db_country

    @staticmethod
    def delete_country(db: Session, country_id: UUID) -> MasterCountry:
        db_country = MasterCountryService.get_country(db, country_id)
        if not db_country:
            raise CountryNotFoundError(str(country_id))

        state_count = db.query(MasterState.id).filter(MasterState.country_id == country_id).count()
        if state_count:
            raise ReferencedByChildrenError("country", "state(s)", state_count)

        locale_count = db.query(MasterLocale.id).filter(MasterLocale.country_id == country_id).count()
        if locale_count:
            raise ReferencedByChildrenError("country", "locale(s)", locale_count)

        db.delete(db_country)
        db.commit()
        return db_country
