from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status, Request
from sqlalchemy.orm import Session
import math
import uuid

from app.infrastructure.database.session import get_db
from app.core.security import get_current_user
from app.master_datas.services.master_languages import MasterLanguageService
from app.master_datas.exceptions import LanguageNotFoundError
from app.master_datas.schemas.master_languages import (
    MasterLanguageCreate,
    MasterLanguageUpdate,
    MasterLanguageResponse,
    MasterLanguageListResponse,
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
            object_type="MasterLanguage",
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
    response_model=MasterLanguageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a language",
    description="Add a language to the master list. `language_name`, `iso639_1`, `iso639_2` and "
                "`locale` must each be unique. Setting `is_default` clears the flag on every other language.",
    responses={
        409: {"description": "A language with one of these unique values already exists"},
    },
)
async def create_language(
    request: Request,
    language_data: MasterLanguageCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    language = MasterLanguageService.create_language(db, language_data)
    _audit(
        request, db, current_user, "CREATE",
        object_id=str(language.id),
        risk_score=RISK_SCORE["CREATE"],
        new_values={"language_name": language.language_name, "iso639_1": language.iso639_1},
    )
    return language


@router.get(
    "/",
    response_model=MasterLanguageListResponse,
    summary="List languages",
    description="Paginated language list with optional search, direction/active filters and sorting.",
)
async def get_languages(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1, description="1-based page number"),
    size: int = Query(50, ge=1, le=250, description="Rows per page"),
    is_active: Optional[bool] = Query(None, description="Filter by active flag"),
    text_direction: Optional[str] = Query(None, regex="^(ltr|rtl)$", description="Filter by script direction"),
    search: Optional[str] = Query(None, description="Match name, native name, ISO code or locale"),
    sort_by: str = Query("display_order", description="Sort column"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Sort direction"),
):
    languages, total = MasterLanguageService.get_languages(
        db=db,
        skip=(page - 1) * size,
        limit=size,
        is_active=is_active,
        text_direction=text_direction,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return MasterLanguageListResponse(
        languages=languages,
        total=total,
        page=page,
        size=size,
        total_pages=math.ceil(total / size) if total > 0 else 0,
    )


# Registered before /{language_id} so these literal paths win the match.
@router.get(
    "/default",
    response_model=MasterLanguageResponse,
    summary="Get the default language",
    responses={404: {"description": "No default language is configured"}},
)
async def get_default_language(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    language = MasterLanguageService.get_default_language(db)
    if not language:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No default language is configured",
        )
    return language


@router.get(
    "/iso/{iso639_1}",
    response_model=MasterLanguageResponse,
    summary="Get a language by ISO 639-1 code",
    responses={404: {"description": "Language not found"}},
)
async def get_language_by_iso(
    request: Request,
    iso639_1: str = Path(..., min_length=2, max_length=2, description="ISO 639-1 two-letter code, e.g. hi"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    language = MasterLanguageService.get_language_by_iso639_1(db, iso639_1)
    if not language:
        raise LanguageNotFoundError(iso639_1.lower())
    return language


@router.get(
    "/{language_id}",
    response_model=MasterLanguageResponse,
    summary="Get a language by ID",
    responses={404: {"description": "Language not found"}},
)
async def get_language(
    request: Request,
    language_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    language = MasterLanguageService.get_language(db, language_id)
    if not language:
        raise LanguageNotFoundError(str(language_id))
    return language


@router.put(
    "/{language_id}",
    response_model=MasterLanguageResponse,
    summary="Update a language",
    description="Partial update — only the fields present in the body are changed.",
    responses={
        404: {"description": "Language not found"},
        409: {"description": "A language with one of these unique values already exists"},
    },
)
async def update_language(
    request: Request,
    language_id: uuid.UUID,
    language_data: MasterLanguageUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    language = MasterLanguageService.update_language(db, language_id, language_data)
    _audit(
        request, db, current_user, "UPDATE",
        object_id=str(language_id),
        risk_score=RISK_SCORE["UPDATE"],
        new_values=language_data.model_dump(exclude_unset=True, mode="json"),
    )
    return language


@router.patch(
    "/{language_id}/set-default",
    response_model=MasterLanguageResponse,
    summary="Make this language the default",
    description="Sets `is_default` on this language and clears it on every other row.",
    responses={404: {"description": "Language not found"}},
)
async def set_default_language(
    request: Request,
    language_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    language = MasterLanguageService.set_default_language(db, language_id)
    _audit(
        request, db, current_user, "UPDATE",
        object_id=str(language_id),
        risk_score=RISK_SCORE["UPDATE"],
        new_values={"is_default": True},
    )
    return language


@router.delete(
    "/{language_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a language",
    description="Permanently removes the language. Use `is_active=false` via PUT to retire one instead.",
    responses={404: {"description": "Language not found"}},
)
async def delete_language(
    request: Request,
    language_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    language = MasterLanguageService.delete_language(db, language_id)
    _audit(
        request, db, current_user, "DELETE",
        object_id=str(language_id),
        risk_score=RISK_SCORE["DELETE"],
        old_values={"language_name": language.language_name, "iso639_1": language.iso639_1},
    )
