from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID

from app.db.database import get_db
from app.menu_language.services.menu_language import menu_language_service
from app.menu_language.schemas.menu_language import (
    MenuLanguageCreate,
    MenuLanguageUpdate,
    MenuLanguageResponse,
    TranslationsWithEntitiesResponse,
    TranslationMapResponse
)
from app.core.security import get_current_user

router = APIRouter()


@router.post(
    "/",
    response_model=MenuLanguageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new menu language entry"
)
def create_menu_language(
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


@router.get(
    "/by-entity-type/{entity_type}",
    response_model=List[MenuLanguageResponse],
    summary="Get menu language entries by entity type"
)
def get_menu_languages_by_entity_type(
    entity_type: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get all menu language entries for a specific entity type.
    
    - **entity_type**: Entity type ('application', 'module', or 'menu')
    """
    menu_languages = menu_language_service.get_menu_languages_by_entity_type(
        db=db,
        entity_type=entity_type
    )
    return menu_languages


@router.get(
    "/by-entity/{entity_type}/{entity_id}",
    response_model=List[MenuLanguageResponse],
    summary="Get menu language entries by entity"
)
def get_menu_languages_by_entity(
    entity_type: str,
    entity_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get all menu language entries for a specific entity.
    
    - **entity_type**: Entity type ('application', 'module', or 'menu')
    - **entity_id**: UUID of the entity
    """
    menu_languages = menu_language_service.get_menu_languages_by_entity(
        db=db,
        entity_type=entity_type,
        entity_id=entity_id
    )
    return menu_languages


@router.get(
    "/search/",
    response_model=List[MenuLanguageResponse],
    summary="Search menu language entries by filters"
)
def search_menu_languages(
    lang_code: Optional[str] = Query(None, description="Filter by language code"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type ('application', 'module', or 'menu')"),
    entity_id: Optional[UUID] = Query(None, description="Filter by entity ID"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Search menu language entries using multiple optional filters.
    
    - **lang_code**: Language code (optional)
    - **entity_type**: Entity type ('application', 'module', or 'menu') (optional)
    - **entity_id**: Entity UUID (optional)
    """
    menu_languages = menu_language_service.get_menu_language_by_filters(
        db=db,
        lang_code=lang_code,
        entity_type=entity_type,
        entity_id=entity_id
    )
    return menu_languages


@router.put(
    "/{menu_language_id}",
    response_model=MenuLanguageResponse,
    summary="Update a menu language entry"
)
def update_menu_language(
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
    
    return menu_language


@router.delete(
    "/{menu_language_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete a menu language entry"
)
def delete_menu_language(
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
    
    return None


@router.delete(
    "/{menu_language_id}/hard",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a menu language entry"
)
def hard_delete_menu_language(
    menu_language_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Permanently delete a menu language entry from the database.
    
    **Warning**: This action cannot be undone.
    
    - **menu_language_id**: ID of the menu language entry to permanently delete
    """
    success = menu_language_service.hard_delete_menu_language(
        db=db,
        menu_language_id=menu_language_id
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu language entry not found"
        )
    
    return None
