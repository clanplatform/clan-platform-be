from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from uuid import UUID

from app.infrastructure.database.session import get_db
from app.menu_language.services.menu_language import menu_language_service
from app.menu_language.schemas.menu_language import (
    MenuLanguageCreate,
    MenuLanguageUpdate,
    MenuLanguageResponse,
    TranslationsWithEntitiesResponse,
    TranslationMapResponse
)
from app.core.security import get_current_user
from app.infrastructure.audit_helpers import RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id
from app.infrastructure.audit_client import fire_audit_log

router = APIRouter()


@router.post(
    "/",
    response_model=MenuLanguageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new menu language entry"
)
def create_menu_language(
    request: Request,
    menu_language_data: MenuLanguageCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create a new menu language translation entry.
    
    - **lang_code**: Language code (e.g., 'en', 'es', 'fr')
    - **language**: Language name (e.g., 'English', 'Spanish', 'Tamil')
    - **translated_name**: The translated text
    - **app_menu_entity_type**: Entity type ('application', 'module', or 'menu')
    - **app_menu_entity_id**: UUID of the application, module, or menu entity
    """
    try:
        menu_language = menu_language_service.create_menu_language(
            db=db,
            menu_language_data=menu_language_data
        )

        # Audit log: menu language created
        try:
            client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="CREATE",
                object_type="MenuLanguage",
                object_id=str(menu_language.id),
                user_id=get_user_id(current_user),
                client_id=client_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["CREATE"],
                new_values={
                    "lang_code": menu_language.lang_code,
                    "language": menu_language.language,
                    "translated_name": menu_language.translated_name,
                },
            )
        except Exception:
            pass

        return menu_language
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating menu language: {str(e)}"
        )


@router.get(
    "/{menu_language_id}",
    response_model=MenuLanguageResponse,
    summary="Get a menu language entry by ID"
)
def get_menu_language(
    menu_language_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get a specific menu language entry by its ID.
    """
    menu_language = menu_language_service.get_menu_language_by_id(
        db=db,
        menu_language_id=menu_language_id
    )
    
    if not menu_language:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu language entry not found"
        )
    
    return menu_language


@router.get(
    "/",
    response_model=List[MenuLanguageResponse],
    summary="Get all menu language entries"
)
def get_all_menu_languages(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get all menu language entries with pagination.
    
    - **skip**: Number of records to skip (default: 0)
    - **limit**: Maximum number of records to return (default: 100, max: 1000)
    """
    menu_languages = menu_language_service.get_all_menu_languages(
        db=db,
        skip=skip,
        limit=limit
    )
    return menu_languages


@router.get(
    "/by-lang/{lang_code}",
    response_model=List[MenuLanguageResponse],
    summary="Get menu language entries by language code"
)
def get_menu_languages_by_lang_code(
    lang_code: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get all menu language entries for a specific language code.
    
    - **lang_code**: Language code (e.g., 'en', 'es', 'fr')
    """
    menu_languages = menu_language_service.get_menu_languages_by_lang_code(
        db=db,
        lang_code=lang_code
    )
    return menu_languages




@router.put(
    "/{menu_language_id}",
    response_model=MenuLanguageResponse,
    summary="Update a menu language entry"
)
def update_menu_language(
    request: Request,
    menu_language_id: UUID,
    menu_language_data: MenuLanguageUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Update an existing menu language entry.
    
    - **menu_language_id**: ID of the menu language entry to update
    - All fields are optional; only provided fields will be updated
    """
    menu_language = menu_language_service.update_menu_language(
        db=db,
        menu_language_id=menu_language_id,
        menu_language_data=menu_language_data
    )

    if not menu_language:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu language entry not found"
        )

    # Audit log: menu language updated
    try:
        client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="UPDATE",
            object_type="MenuLanguage",
            object_id=str(menu_language_id),
            user_id=get_user_id(current_user),
            client_id=client_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["UPDATE"],
            new_values={
                "lang_code": menu_language.lang_code,
                "language": menu_language.language,
                "translated_name": menu_language.translated_name,
            },
        )
    except Exception:
        pass

    return menu_language


@router.delete(
    "/{menu_language_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete a menu language entry"
)
def delete_menu_language(
    request: Request,
    menu_language_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Soft delete a menu language entry (sets deleted_at timestamp).

    - **menu_language_id**: ID of the menu language entry to delete
    """
    success = menu_language_service.delete_menu_language(
        db=db,
        menu_language_id=menu_language_id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu language entry not found"
        )

    # Audit log: menu language deleted
    try:
        client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="DELETE",
            object_type="MenuLanguage",
            object_id=str(menu_language_id),
            user_id=get_user_id(current_user),
            client_id=client_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["DELETE"],
            old_values={"id": str(menu_language_id)},
        )
    except Exception:
        pass

    return None


