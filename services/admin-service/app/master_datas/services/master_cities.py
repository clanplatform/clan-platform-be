from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc

from app.master_datas.models.master_cities import MasterCity
from app.master_datas.models.master_states import MasterState
from app.master_datas.schemas.master_cities import MasterCityCreate, MasterCityUpdate
from app.master_datas.exceptions import (
    CityNotFoundError,
    DuplicateCityError,
    StateNotFoundError,
)

SORTABLE_FIELDS = {
    "display_order", "city_name", "postal_code",
    "created_at", "updated_at",
}


class MasterCityService:

    @staticmethod
    def _assert_state_exists(db: Session, state_id: UUID) -> None:
        if not db.query(MasterState.id).filter(MasterState.id == state_id).first():
            raise StateNotFoundError(str(state_id))

    @staticmethod
    def _assert_unique(db: Session, state_id: UUID, data: dict, exclude_id: Optional[UUID] = None) -> None:
        """Reject a city name already used by another city of the same state."""
        value = data.get("city_name")
        if value is None:
            return
        query = db.query(MasterCity.id).filter(
            MasterCity.state_id == state_id,
            MasterCity.city_name == value,
        )
        if exclude_id is not None:
            query = query.filter(MasterCity.id != exclude_id)
        if query.first():
            raise DuplicateCityError("city_name", str(value))

    @staticmethod
    def create_city(db: Session, city_data: MasterCityCreate) -> MasterCity:
        data = city_data.model_dump()
        MasterCityService._assert_state_exists(db, data["state_id"])
        MasterCityService._assert_unique(db, data["state_id"], data)

        db_city = MasterCity(**data)
        db.add(db_city)
        db.commit()
        db.refresh(db_city)
        return db_city

    @staticmethod
    def get_city(db: Session, city_id: UUID) -> Optional[MasterCity]:
        return db.query(MasterCity).filter(MasterCity.id == city_id).first()

    @staticmethod
    def get_cities_by_state(
        db: Session, state_id: UUID, is_active: Optional[bool] = None
    ) -> List[MasterCity]:
        MasterCityService._assert_state_exists(db, state_id)
        query = db.query(MasterCity).filter(MasterCity.state_id == state_id)
        if is_active is not None:
            query = query.filter(MasterCity.is_active == is_active)
        return query.order_by(asc(MasterCity.display_order), asc(MasterCity.city_name)).all()

    @staticmethod
    def get_cities(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        state_id: Optional[UUID] = None,
        country_id: Optional[UUID] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "display_order",
        sort_order: str = "asc",
    ) -> Tuple[List[MasterCity], int]:
        query = db.query(MasterCity)

        if state_id is not None:
            query = query.filter(MasterCity.state_id == state_id)
        if country_id is not None:
            # Cities reach a country only through their state.
            query = query.join(MasterState, MasterCity.state_id == MasterState.id).filter(
                MasterState.country_id == country_id
            )
        if is_active is not None:
            query = query.filter(MasterCity.is_active == is_active)
        if search:
            term = f"%{search}%"
            query = query.filter(
                or_(
                    MasterCity.city_name.ilike(term),
                    MasterCity.postal_code.ilike(term),
                )
            )

        total = query.count()

        if sort_by in SORTABLE_FIELDS:
            col = getattr(MasterCity, sort_by)
            query = query.order_by(desc(col) if sort_order.lower() == "desc" else asc(col))
        # Tie-break on id so pages don't overlap when the sort column repeats.
        query = query.order_by(asc(MasterCity.id))

        cities = query.offset(skip).limit(limit).all()
        return cities, total

    @staticmethod
    def update_city(db: Session, city_id: UUID, city_data: MasterCityUpdate) -> MasterCity:
        db_city = MasterCityService.get_city(db, city_id)
        if not db_city:
            raise CityNotFoundError(str(city_id))

        update_data = city_data.model_dump(exclude_unset=True)

        # A city can be moved between states, so uniqueness is checked against the
        # state it will end up in, using the name it will end up with.
        target_state_id = update_data.get("state_id", db_city.state_id)
        if "state_id" in update_data:
            MasterCityService._assert_state_exists(db, target_state_id)

        MasterCityService._assert_unique(
            db,
            target_state_id,
            {"city_name": update_data.get("city_name", db_city.city_name)},
            exclude_id=city_id,
        )

        for field, value in update_data.items():
            setattr(db_city, field, value)

        db.commit()
        db.refresh(db_city)
        return db_city

    @staticmethod
    def delete_city(db: Session, city_id: UUID) -> MasterCity:
        db_city = MasterCityService.get_city(db, city_id)
        if not db_city:
            raise CityNotFoundError(str(city_id))

        db.delete(db_city)
        db.commit()
        return db_city
