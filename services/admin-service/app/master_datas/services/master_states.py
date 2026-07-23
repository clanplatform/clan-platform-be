from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc

from app.master_datas.models.master_states import MasterState
from app.master_datas.models.master_countries import MasterCountry
from app.master_datas.models.master_cities import MasterCity
from app.master_datas.schemas.master_states import MasterStateCreate, MasterStateUpdate
from app.master_datas.exceptions import (
    StateNotFoundError,
    DuplicateStateError,
    CountryNotFoundError,
    ReferencedByChildrenError,
)

SORTABLE_FIELDS = {
    "display_order", "state_name", "state_code", "capital",
    "created_at", "updated_at",
}


class MasterStateService:

    @staticmethod
    def _assert_country_exists(db: Session, country_id: UUID) -> None:
        if not db.query(MasterCountry.id).filter(MasterCountry.id == country_id).first():
            raise CountryNotFoundError(str(country_id))

    @staticmethod
    def _assert_unique(db: Session, country_id: UUID, data: dict, exclude_id: Optional[UUID] = None) -> None:
        """Reject names/codes already used by another state of the same country."""
        for field in ("state_name", "state_code"):
            value = data.get(field)
            if value is None:
                continue
            query = db.query(MasterState.id).filter(
                MasterState.country_id == country_id,
                getattr(MasterState, field) == value,
            )
            if exclude_id is not None:
                query = query.filter(MasterState.id != exclude_id)
            if query.first():
                raise DuplicateStateError(field, str(value))

    @staticmethod
    def create_state(db: Session, state_data: MasterStateCreate) -> MasterState:
        data = state_data.model_dump()
        MasterStateService._assert_country_exists(db, data["country_id"])
        MasterStateService._assert_unique(db, data["country_id"], data)

        db_state = MasterState(**data)
        db.add(db_state)
        db.commit()
        db.refresh(db_state)
        return db_state

    @staticmethod
    def get_state(db: Session, state_id: UUID) -> Optional[MasterState]:
        return db.query(MasterState).filter(MasterState.id == state_id).first()

    @staticmethod
    def get_states_by_country(
        db: Session, country_id: UUID, is_active: Optional[bool] = None
    ) -> List[MasterState]:
        MasterStateService._assert_country_exists(db, country_id)
        query = db.query(MasterState).filter(MasterState.country_id == country_id)
        if is_active is not None:
            query = query.filter(MasterState.is_active == is_active)
        return query.order_by(asc(MasterState.display_order), asc(MasterState.state_name)).all()

    @staticmethod
    def get_states(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        country_id: Optional[UUID] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        sort_by: str = "display_order",
        sort_order: str = "asc",
    ) -> Tuple[List[MasterState], int]:
        query = db.query(MasterState)

        if country_id is not None:
            query = query.filter(MasterState.country_id == country_id)
        if is_active is not None:
            query = query.filter(MasterState.is_active == is_active)
        if search:
            term = f"%{search}%"
            query = query.filter(
                or_(
                    MasterState.state_name.ilike(term),
                    MasterState.state_code.ilike(term),
                    MasterState.capital.ilike(term),
                )
            )

        total = query.count()

        if sort_by in SORTABLE_FIELDS:
            col = getattr(MasterState, sort_by)
            query = query.order_by(desc(col) if sort_order.lower() == "desc" else asc(col))
        # Tie-break on id so pages don't overlap when the sort column repeats.
        query = query.order_by(asc(MasterState.id))

        states = query.offset(skip).limit(limit).all()
        return states, total

    @staticmethod
    def update_state(db: Session, state_id: UUID, state_data: MasterStateUpdate) -> MasterState:
        db_state = MasterStateService.get_state(db, state_id)
        if not db_state:
            raise StateNotFoundError(str(state_id))

        update_data = state_data.model_dump(exclude_unset=True)

        # A state can be moved between countries, so uniqueness is checked against the
        # country it will end up in, using the values it will end up with.
        target_country_id = update_data.get("country_id", db_state.country_id)
        if "country_id" in update_data:
            MasterStateService._assert_country_exists(db, target_country_id)

        MasterStateService._assert_unique(
            db,
            target_country_id,
            {
                "state_name": update_data.get("state_name", db_state.state_name),
                "state_code": update_data.get("state_code", db_state.state_code),
            },
            exclude_id=state_id,
        )

        for field, value in update_data.items():
            setattr(db_state, field, value)

        db.commit()
        db.refresh(db_state)
        return db_state

    @staticmethod
    def delete_state(db: Session, state_id: UUID) -> MasterState:
        db_state = MasterStateService.get_state(db, state_id)
        if not db_state:
            raise StateNotFoundError(str(state_id))

        city_count = db.query(MasterCity.id).filter(MasterCity.state_id == state_id).count()
        if city_count:
            raise ReferencedByChildrenError("state", "city/cities", city_count)

        db.delete(db_state)
        db.commit()
        return db_state
