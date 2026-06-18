from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body, Request
from sqlalchemy.orm import Session
from uuid import UUID

from app.infrastructure.database.session import get_db
from app.form_language.schemas.form_language import (
    FormLanguageCreate,
    FormLanguageUpdate,
    FormLanguageResponse,
    FormLanguageBulkCreate,
    FormLanguageBulkResponse
)
from app.form_language.services.form_language import FormLanguageService
from app.core.security import get_current_user
from app.infrastructure.audit_helpers import RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id
from app.infrastructure.audit_client import fire_audit_log

router = APIRouter()


@router.post(
    "/",
    response_model=FormLanguageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Form Language Translation",
    description="""
    Create a new form language translation entry.
    
    This endpoint allows you to add translations for form fields, labels, placeholders, 
    help text, and error messages in different languages.
    
    **Use Cases:**
    - Translate form field labels
    - Translate placeholder text
    - Translate error messages
    - Translate help text
    
    **Required Fields:**
    - lang_code: Language code (ISO 639-1, e.g., 'en', 'fr', 'es')
    - language: Full language name (e.g., 'English', 'French', 'Spanish')
    - app_form_entity_type: Type of entity ('form', 'field', 'section')
    - app_form_entity_id: UUID of the form entity
    """,
    response_description="Successfully created form language translation",
    responses={
        201: {
            "description": "Translation created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "987fcdeb-51a2-43d1-b123-456789abcdef",
                        "sino": 1,
                        "lang_code": "fr",
                        "language": "French",
                        "app_form_entity_type": "field",
                        "app_form_entity_id": "123e4567-e89b-12d3-a456-426614174000",
                        "translated_name": "Nom d'utilisateur",
                        "type": "label",
                        "value": "Entrez votre nom d'utilisateur",
                        "key": "username_label",
                        "error_message": "Le nom d'utilisateur est requis",
                        "created_at": "2026-05-25T12:33:43.123456Z",
                        "updated_at": "2026-05-25T12:33:43.123456Z",
                        "deleted_at": None
                    }
                }
            }
        },
        400: {"description": "Bad Request - Invalid data provided"},
        401: {"description": "Unauthorized - Authentication required"}
    }
)
def create_form_language(
    request: Request,
    form_language: FormLanguageCreate = Body(
        ...,
        example={
            "lang_code": "fr",
            "language": "French",
            "app_form_entity_type": "field",
            "app_form_entity_id": "123e4567-e89b-12d3-a456-426614174000",
            "translated_name": "Nom d'utilisateur",
            "type": "label",
            "value": "Entrez votre nom d'utilisateur",
            "key": "username_label",
            "error_message": "Le nom d'utilisateur est requis"
        }
    ),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create a new form language translation.
    
    - **lang_code**: Language code (e.g., 'en', 'es', 'fr')
    - **language**: Language name (e.g., 'English', 'Spanish', 'French')
    - **app_form_entity_type**: Entity type (e.g., 'form', 'field', 'section')
    - **app_form_entity_id**: Form entity ID (foreign key to forms table)
    - **translated_name**: Translated name
    - **type**: Translation type (e.g., 'label', 'placeholder', 'help_text', 'error_message')
    - **value**: Translation value
    - **key**: Translation key
    - **error_message**: Error message translation
    """
    try:
        db_form_language = FormLanguageService.create(db, form_language)

        # Audit log: form language created
        try:
            client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="CREATE",
                object_type="FormLanguage",
                object_id=str(db_form_language.id),
                user_id=get_user_id(current_user),
                client_id=client_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["CREATE"],
                new_values={
                    "lang_code": db_form_language.lang_code,
                    "language": db_form_language.language,
                    "translated_name": db_form_language.translated_name,
                },
            )
        except Exception:
            pass

        return db_form_language
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create form language translation: {str(e)}"
        )




@router.get(
    "/",
    response_model=List[FormLanguageResponse],
    summary="Get All Form Language Translations",
    description="""
    Retrieve all form language translations with optional filters.
    
    **Filters Available:**
    - `lang_code`: Filter by specific language (e.g., 'fr', 'es')
    - `entity_type`: Filter by entity type ('form', 'field', 'section')
    - `entity_id`: Filter by specific form entity UUID
    - `skip`: Pagination offset
    - `limit`: Maximum results per page (max: 1000)
    
    **Example Queries:**
    - Get all French translations: `?lang_code=fr`
    - Get field translations: `?entity_type=field`
    - Get translations for specific form: `?entity_id=123e4567-e89b-12d3-a456-426614174000`
    - Combine filters: `?lang_code=fr&entity_type=field&limit=50`
    """,
    response_description="List of form language translations",
    responses={
        200: {
            "description": "Successfully retrieved translations",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "987fcdeb-51a2-43d1-b123-456789abcdef",
                            "sino": 1,
                            "lang_code": "fr",
                            "language": "French",
                            "app_form_entity_type": "field",
                            "app_form_entity_id": "123e4567-e89b-12d3-a456-426614174000",
                            "translated_name": "Nom d'utilisateur",
                            "type": "label",
                            "key": "username_label",
                            "created_at": "2026-05-25T12:33:43.123456Z",
                            "updated_at": "2026-05-25T12:33:43.123456Z",
                            "deleted_at": None
                        }
                    ]
                }
            }
        }
    }
)
def get_all_form_languages(
    skip: int = Query(0, ge=0, description="Number of records to skip for pagination"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return (max: 1000)"),
    lang_code: Optional[str] = Query(None, description="Filter by language code (e.g., 'en', 'fr', 'es')", example="fr"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type", example="field"),
    entity_id: Optional[UUID] = Query(None, description="Filter by form entity UUID"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get all form language translations with optional filters.
    
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    - **lang_code**: Filter by language code (e.g., 'en', 'fr')
    - **entity_type**: Filter by entity type (e.g., 'form', 'field')
    - **entity_id**: Filter by specific form entity ID
    """
    form_languages = FormLanguageService.get_all(
        db,
        skip=skip,
        limit=limit,
        lang_code=lang_code,
        entity_type=entity_type,
        entity_id=entity_id
    )
    return form_languages


@router.get(
    "/{form_language_id}",
    response_model=FormLanguageResponse,
    summary="Get Form Language Translation by ID",
    description="""
    Retrieve a specific form language translation by its UUID.
    
    Returns detailed information about a single translation including:
    - Translation content
    - Language information
    - Entity association
    - Timestamps
    """,
    response_description="Form language translation details",
    responses={
        200: {"description": "Translation found and returned successfully"},
        404: {
            "description": "Translation not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Form language translation with ID 987fcdeb-51a2-43d1-b123-456789abcdef not found"}
                }
            }
        }
    }
)
def get_form_language(
    form_language_id: UUID = Path(..., description="UUID of the form language translation"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get a specific form language translation by ID.
    """
    db_form_language = FormLanguageService.get_by_id(db, form_language_id)
    if not db_form_language:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Form language translation with ID {form_language_id} not found"
        )
    return db_form_language




@router.get(
    "/language/{lang_code}",
    response_model=List[FormLanguageResponse],
    summary="Get Translations by Language Code",
    description="Get all translations for a specific language"
)
def get_form_languages_by_lang_code(
    lang_code: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get all translations for a specific language.
    
    - **lang_code**: Language code (e.g., 'en', 'fr', 'es')
    """
    form_languages = FormLanguageService.get_by_lang_code(db, lang_code)
    return form_languages



@router.put(
    "/{form_language_id}",
    response_model=FormLanguageResponse,
    summary="Update Form Language Translation",
    description="Update an existing form language translation"
)
def update_form_language(
    request: Request,
    form_language_id: UUID,
    form_language_update: FormLanguageUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Update a form language translation.
    
    Only provided fields will be updated.
    """
    db_form_language = FormLanguageService.update(db, form_language_id, form_language_update)
    if not db_form_language:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Form language translation with ID {form_language_id} not found"
        )

    # Audit log: form language updated
    try:
        client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="UPDATE",
            object_type="FormLanguage",
            object_id=str(form_language_id),
            user_id=get_user_id(current_user),
            client_id=client_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["UPDATE"],
            new_values={"id": str(form_language_id)},
        )
    except Exception:
        pass

    return db_form_language


@router.delete(
    "/{form_language_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Form Language Translation",
    description="Soft delete a form language translation"
)
def delete_form_language(
    request: Request,
    form_language_id: UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Soft delete a form language translation.

    The record will be marked as deleted but not removed from the database.
    """
    success = FormLanguageService.delete(db, form_language_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Form language translation with ID {form_language_id} not found"
        )

    # Audit log: form language deleted
    try:
        client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="DELETE",
            object_type="FormLanguage",
            object_id=str(form_language_id),
            user_id=get_user_id(current_user),
            client_id=client_id_audit,
            entity_id=entity_id_audit,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["DELETE"],
            old_values={"id": str(form_language_id)},
        )
    except Exception:
        pass

    return None

