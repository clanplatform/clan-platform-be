from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Request
from sqlalchemy.orm import Session
import math
import uuid

from app.infrastructure.database.session import get_db
from app.core.security import get_current_user
from app.master_datas.services.master_locales import MasterLocaleService
from app.master_datas.exceptions import LocaleNotFoundError
from app.master_datas.schemas.master_locales import (
    MasterLocaleCreate,
    MasterLocaleUpdate,
    MasterLocaleResponse,
    MasterLocaleListResponse,
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
            object_type="MasterLocale",
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
    response_model=MasterLocaleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a locale",
    description="Add a locale binding a language to an optional country. `locale_code` and "
                "`locale_name` must be unique, and a language/country pairing may only appear once. "
                "Setting `is_default` clears the flag on every other locale.",
    responses={
        404: {"description": "The referenced language or country does not exist"},
        409: {"description": "A locale with this code, name or language/country pairing already exists"},
    },
)
async def create_locale(
    request: Request,
    locale_data: MasterLocaleCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    locale = MasterLocaleService.create_locale(db, locale_data)
    _audit(
        request, db, current_user, "CREATE",
        object_id=str(locale.id),
        risk_score=RISK_SCORE["CREATE"],
        new_values={"locale_code": locale.locale_code, "language_id": str(locale.language_id)},
    )
    return locale


@router.get(
    "/",
    response_model=MasterLocaleListResponse,
    summary="List locales",
    description="Paginated locale list with optional language/country/active filters, search and sorting.",
)
async def get_locales(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1, description="1-based page number"),
    size: int = Query(50, ge=1, le=250, description="Rows per page"),
    language_id: Optional[uuid.UUID] = Query(None, description="Filter by language"),
    country_id: Optional[uuid.UUID] = Query(None, description="Filter by country"),
    is_active: Optional[bool] = Query(None, description="Filter by active flag"),
    search: Optional[str] = Query(None, description="Match locale code or name"),
    sort_by: str = Query("locale_code", description="Sort column"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Sort direction"),
):
    locales, total = MasterLocaleService.get_locales(
        db=db,
        skip=(page - 1) * size,
        limit=size,
        language_id=language_id,
        country_id=country_id,
        is_active=is_active,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return MasterLocaleListResponse(
        locales=locales,
        total=total,
        page=page,
        size=size,
        total_pages=math.ceil(total / size) if total > 0 else 0,
    )


# Registered before /{locale_id} so these literal paths win the match.
@router.get(
    "/default",
    response_model=MasterLocaleResponse,
    summary="Get the default locale",
    responses={404: {"description": "No default locale is configured"}},
)
async def get_default_locale(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    locale = MasterLocaleService.get_default_locale(db)
    if not locale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No default locale is configured",
        )
    return locale


@router.get(
    "/code/{locale_code}",
    response_model=MasterLocaleResponse,
    summary="Get a locale by its code",
    description="Lookup is normalisation-insensitive: `en_us`, `EN-us` and `en-US` all resolve.",
    responses={404: {"description": "Locale not found"}},
)
async def get_locale_by_code(
    request: Request,
    locale_code: str = Path(..., min_length=2, max_length=20, description="BCP 47 locale tag, e.g. en-US"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    locale = MasterLocaleService.get_locale_by_code(db, locale_code)
    if not locale:
        raise LocaleNotFoundError(locale_code)
    return locale


@router.get(
    "/{locale_id}",
    response_model=MasterLocaleResponse,
    summary="Get a locale by ID",
    responses={404: {"description": "Locale not found"}},
)
async def get_locale(
    request: Request,
    locale_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    locale = MasterLocaleService.get_locale(db, locale_id)
    if not locale:
        raise LocaleNotFoundError(str(locale_id))
    return locale


@router.put(
    "/{locale_id}",
    response_model=MasterLocaleResponse,
    summary="Update a locale",
    description="Partial update — only the fields present in the body are changed. "
                "Supplying `language_id` or `country_id` re-points the locale.",
    responses={
        404: {"description": "Locale (or the target language/country) not found"},
        409: {"description": "A locale with this code, name or language/country pairing already exists"},
    },
)
async def update_locale(
    request: Request,
    locale_id: uuid.UUID,
    locale_data: MasterLocaleUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    locale = MasterLocaleService.update_locale(db, locale_id, locale_data)
    _audit(
        request, db, current_user, "UPDATE",
        object_id=str(locale_id),
        risk_score=RISK_SCORE["UPDATE"],
        new_values=locale_data.model_dump(exclude_unset=True, mode="json"),
    )
    return locale


@router.patch(
    "/{locale_id}/set-default",
    response_model=MasterLocaleResponse,
    summary="Make this locale the default",
    description="Sets `is_default` on this locale and clears it on every other row.",
    responses={404: {"description": "Locale not found"}},
)
async def set_default_locale(
    request: Request,
    locale_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    locale = MasterLocaleService.set_default_locale(db, locale_id)
    _audit(
        request, db, current_user, "UPDATE",
        object_id=str(locale_id),
        risk_score=RISK_SCORE["UPDATE"],
        new_values={"is_default": True},
    )
    return locale


@router.delete(
    "/{locale_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a locale",
    description="Permanently removes the locale. Use `is_active=false` via PUT to retire one instead.",
    responses={404: {"description": "Locale not found"}},
)
async def delete_locale(
    request: Request,
    locale_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    locale = MasterLocaleService.delete_locale(db, locale_id)
    _audit(
        request, db, current_user, "DELETE",
        object_id=str(locale_id),
        risk_score=RISK_SCORE["DELETE"],
        old_values={"locale_code": locale.locale_code, "locale_name": locale.locale_name},
    )
