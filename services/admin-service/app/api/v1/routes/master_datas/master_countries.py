from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Request
from sqlalchemy.orm import Session
import math
import uuid

from app.infrastructure.database.session import get_db
from app.core.security import get_current_user
from app.master_datas.services.master_countries import MasterCountryService
from app.master_datas.exceptions import CountryNotFoundError
from app.master_datas.schemas.master_countries import (
    MasterCountryCreate,
    MasterCountryUpdate,
    MasterCountryResponse,
    MasterCountryListResponse,
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
            object_type="MasterCountry",
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
    response_model=MasterCountryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a country",
    description="Add a country to the master list. `country_name`, `iso2_code`, `iso3_code` and "
                "`numeric_code` must each be unique. Setting `is_default` clears the flag on every other country.",
    responses={
        409: {"description": "A country with one of these unique values already exists"},
    },
)
async def create_country(
    request: Request,
    country_data: MasterCountryCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    country = MasterCountryService.create_country(db, country_data)
    _audit(
        request, db, current_user, "CREATE",
        object_id=str(country.id),
        risk_score=RISK_SCORE["CREATE"],
        new_values={"country_name": country.country_name, "iso2_code": country.iso2_code},
    )
    return country


@router.get(
    "/",
    response_model=MasterCountryListResponse,
    summary="List countries",
    description="Paginated country list with optional search, currency/active filters and sorting.",
)
async def get_countries(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1, description="1-based page number"),
    size: int = Query(50, ge=1, le=250, description="Rows per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active flag"),
    currency_code: Optional[str] = Query(None, min_length=3, max_length=3, description="Filter by ISO 4217 currency"),
    search: Optional[str] = Query(None, description="Match name, ISO2, ISO3 or nationality"),
    sort_by: str = Query("display_order", description="Sort column"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Sort direction"),
):
    countries, total = MasterCountryService.get_countries(
        db=db,
        skip=(page - 1) * size,
        limit=size,
        is_active=is_active,
        currency_code=currency_code,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return MasterCountryListResponse(
        countries=countries,
        total=total,
        page=page,
        size=size,
        total_pages=math.ceil(total / size) if total > 0 else 0,
    )


# Registered before /{country_id} so these literal paths win the match.
@router.get(
    "/default",
    response_model=MasterCountryResponse,
    summary="Get the default country",
    responses={404: {"description": "No default country is configured"}},
)
async def get_default_country(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    country = MasterCountryService.get_default_country(db)
    if not country:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No default country is configured",
        )
    return country


@router.get(
    "/iso/{iso2_code}",
    response_model=MasterCountryResponse,
    summary="Get a country by ISO2 code",
    responses={404: {"description": "Country not found"}},
)
async def get_country_by_iso2(
    request: Request,
    iso2_code: str = Path(..., min_length=2, max_length=2, description="ISO 3166-1 alpha-2 code, e.g. IN"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    country = MasterCountryService.get_country_by_iso2(db, iso2_code)
    if not country:
        raise CountryNotFoundError(iso2_code.upper())
    return country


@router.get(
    "/{country_id}",
    response_model=MasterCountryResponse,
    summary="Get a country by ID",
    responses={404: {"description": "Country not found"}},
)
async def get_country(
    request: Request,
    country_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    country = MasterCountryService.get_country(db, country_id)
    if not country:
        raise CountryNotFoundError(str(country_id))
    return country


@router.put(
    "/{country_id}",
    response_model=MasterCountryResponse,
    summary="Update a country",
    description="Partial update — only the fields present in the body are changed.",
    responses={
        404: {"description": "Country not found"},
        409: {"description": "A country with one of these unique values already exists"},
    },
)
async def update_country(
    request: Request,
    country_id: uuid.UUID,
    country_data: MasterCountryUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    country = MasterCountryService.update_country(db, country_id, country_data)
    _audit(
        request, db, current_user, "UPDATE",
        object_id=str(country_id),
        risk_score=RISK_SCORE["UPDATE"],
        new_values=country_data.model_dump(exclude_unset=True),
    )
    return country


@router.patch(
    "/{country_id}/set-default",
    response_model=MasterCountryResponse,
    summary="Make this country the default",
    description="Sets `is_default` on this country and clears it on every other row.",
    responses={404: {"description": "Country not found"}},
)
async def set_default_country(
    request: Request,
    country_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    country = MasterCountryService.set_default_country(db, country_id)
    _audit(
        request, db, current_user, "UPDATE",
        object_id=str(country_id),
        risk_score=RISK_SCORE["UPDATE"],
        new_values={"is_default": True},
    )
    return country


@router.delete(
    "/{country_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a country",
    description="Permanently removes the country. Use `is_active=false` via PUT to retire one instead.",
    responses={404: {"description": "Country not found"}},
)
async def delete_country(
    request: Request,
    country_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    country = MasterCountryService.delete_country(db, country_id)
    _audit(
        request, db, current_user, "DELETE",
        object_id=str(country_id),
        risk_score=RISK_SCORE["DELETE"],
        old_values={"country_name": country.country_name, "iso2_code": country.iso2_code},
    )
