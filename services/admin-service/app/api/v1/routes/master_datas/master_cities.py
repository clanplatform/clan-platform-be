from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status, Request
from sqlalchemy.orm import Session
import math
import uuid

from app.infrastructure.database.session import get_db
from app.core.security import get_current_user
from app.master_datas.services.master_cities import MasterCityService
from app.master_datas.exceptions import CityNotFoundError
from app.master_datas.schemas.master_cities import (
    MasterCityCreate,
    MasterCityUpdate,
    MasterCityResponse,
    MasterCityListResponse,
)
from app.infrastructure.audit_helpers import (
    RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id,
)
from app.infrastructure.audit_tenant import fire_audit_log

router = APIRouter()


def _audit(request: Request, db: Session, current_user, action: str, **kwargs) -> None:
    """Fire an audit log enriched with the acting user's org context. Never fatal."""
    try:
        tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action=action,
            object_type="MasterCity",
            user_id=get_user_id(current_user),
            tenant_id=tenant_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            **kwargs,
        )
    except Exception:
        pass


@router.post(
    "/",
    response_model=MasterCityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a city",
    description="Add a city under a state. `city_name` must be unique within that state, "
                "but may repeat across different states.",
    responses={
        404: {"description": "The referenced state does not exist"},
        409: {"description": "This state already has a city with that name"},
    },
)
async def create_city(
    request: Request,
    city_data: MasterCityCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    city = MasterCityService.create_city(db, city_data)
    _audit(
        request, db, current_user, "CREATE",
        object_id=str(city.id),
        risk_score=RISK_SCORE["CREATE"],
        new_values={"city_name": city.city_name, "state_id": str(city.state_id)},
    )
    return city


@router.get(
    "/",
    response_model=MasterCityListResponse,
    summary="List cities",
    description="Paginated city list. Filter by state, or by country to get every city "
                "across that country's states.",
)
async def get_cities(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1, description="1-based page number"),
    size: int = Query(50, ge=1, le=250, description="Rows per page"),
    state_id: Optional[uuid.UUID] = Query(None, description="Filter by state"),
    country_id: Optional[uuid.UUID] = Query(None, description="Filter by country (joins through states)"),
    is_active: Optional[bool] = Query(None, description="Filter by active flag"),
    search: Optional[str] = Query(None, description="Match city name or postal code"),
    sort_by: str = Query("display_order", description="Sort column"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Sort direction"),
):
    cities, total = MasterCityService.get_cities(
        db=db,
        skip=(page - 1) * size,
        limit=size,
        state_id=state_id,
        country_id=country_id,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return MasterCityListResponse(
        cities=cities,
        total=total,
        page=page,
        size=size,
        total_pages=math.ceil(total / size) if total > 0 else 0,
    )


# Registered before /{city_id} so this literal path wins the match.
@router.get(
    "/by-state/{state_id}",
    response_model=List[MasterCityResponse],
    summary="Get all cities for a state",
    description="Unpaginated list ordered by display_order — intended for cascading state/city pickers.",
    responses={404: {"description": "The referenced state does not exist"}},
)
async def get_cities_by_state(
    request: Request,
    state_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    is_active: Optional[bool] = Query(None, description="Filter by active flag"),
):
    return MasterCityService.get_cities_by_state(db, state_id, is_active=is_active)


@router.get(
    "/{city_id}",
    response_model=MasterCityResponse,
    summary="Get a city by ID",
    responses={404: {"description": "City not found"}},
)
async def get_city(
    request: Request,
    city_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    city = MasterCityService.get_city(db, city_id)
    if not city:
        raise CityNotFoundError(str(city_id))
    return city


@router.put(
    "/{city_id}",
    response_model=MasterCityResponse,
    summary="Update a city",
    description="Partial update — only the fields present in the body are changed. "
                "Supplying `state_id` moves the city to another state.",
    responses={
        404: {"description": "City (or the target state) not found"},
        409: {"description": "The target state already has a city with that name"},
    },
)
async def update_city(
    request: Request,
    city_id: uuid.UUID,
    city_data: MasterCityUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    city = MasterCityService.update_city(db, city_id, city_data)
    _audit(
        request, db, current_user, "UPDATE",
        object_id=str(city_id),
        risk_score=RISK_SCORE["UPDATE"],
        new_values=city_data.model_dump(exclude_unset=True, mode="json"),
    )
    return city


@router.delete(
    "/{city_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a city",
    description="Permanently removes the city. Use `is_active=false` via PUT to retire one instead.",
    responses={404: {"description": "City not found"}},
)
async def delete_city(
    request: Request,
    city_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    city = MasterCityService.delete_city(db, city_id)
    _audit(
        request, db, current_user, "DELETE",
        object_id=str(city_id),
        risk_score=RISK_SCORE["DELETE"],
        old_values={"city_name": city.city_name, "state_id": str(city.state_id)},
    )
