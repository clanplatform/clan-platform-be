from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Request
from sqlalchemy.orm import Session
from datetime import datetime
import math
from app.infrastructure.database.session import get_tenant_db as get_db
from app.core.security import get_current_user
from app.forms.services.forms import FormsService
from app.infrastructure.audit_helpers import RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id
from app.infrastructure.audit_tenant import fire_audit_log
from app.forms_details.services.forms_details import forms_details_service
from app.forms.schemas.forms import (
    FormCreate,
    FormCreateFromFrontend,
    FormUpdate,
    FormUpdateSimple,
    FormResponse,
    FormListResponse,
    FormImport,
    FormExport
)
import math
import json

router = APIRouter()


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new form",
    description="Create a new form from frontend payload structure"
)
async def create_form(
    request: Request,
    form_data: FormCreateFromFrontend,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new form from frontend payload.
    
    Expected structure:
    {
        "menu_id": "8a1ff357-c1d5-4858-8847-ed65843a9cf1",
        "access": ["read", "write"],
        "forms": [
            {
                "name": "clienttest",
                "defaultLanguage": "en-US",
                "form": {...},
                "languages": [...],
                "version": "1"
            }
        ]
    }
    """
    
    # Validate forms array
    if not form_data.forms or len(form_data.forms) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="forms array must contain at least one form item"
        )
    
    # Get name from the first form item
    form_name = form_data.forms[0].name
    
    # Check for duplicate form name in the same menu
    existing_form = FormsService.get_form_by_name(db, form_name, str(form_data.menu_id))
    if existing_form:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Form with name '{form_name}' already exists in this menu"
        )
    
    try:
        # Convert frontend format to backend format - store the entire forms array
        backend_form_data = FormCreate(
            menu_id=form_data.menu_id,
            name=form_name,  # Use name from first form item
            version=form_data.forms[0].version if form_data.forms else "1.0.0",
            trigger_when=json.dumps(form_data.forms[0].triggerWhen) if form_data.forms and form_data.forms[0].triggerWhen else None,
            forms=[item.model_dump() if hasattr(item, 'model_dump') else item for item in form_data.forms],
            actions={},
            modal_type=form_data.forms[0].modalType if form_data.forms else "AntModal",
            tooltip_type=form_data.forms[0].tooltipType if form_data.forms else "AntTooltip",
            error_type=form_data.forms[0].errorType if form_data.forms else "AntErrorMessage",
            localization=form_data.forms[0].localization if form_data.forms else {},
            languages=form_data.forms[0].languages if form_data.forms else [],
            default_language=form_data.forms[0].defaultLanguage if form_data.forms else "en-US",
            is_active=True,
            created_by=None
        )
        
        # Create form in PostgreSQL
        form = FormsService.create_form(db, backend_form_data, None)
        
        # Try to create form details in MongoDB
        try:
            print(f"[Forms Create] 🔄 Syncing form to MongoDB...")
            print(f"[Forms Create]    form_id: {form.id}")
            print(f"[Forms Create]    menu_id: {form.menu_id}")
            print(f"[Forms Create]    name: {form.name}")
            
            mongo_id = await forms_details_service.create_form_details(
                form_id=str(form.id),
                menu_id=str(form.menu_id),
                name=form.name,
                version=form.version,
                trigger_when=form.trigger_when,
                forms=form.forms,
                actions=form.actions,
                modal_type=form.modal_type,
                tooltip_type=form.tooltip_type,
                error_type=form.error_type,
                localization=form.localization,
                languages=form.languages,
                default_language=form.default_language,
                is_active=form.is_active,
                created_by=None
            )
            
            print(f"[Forms Create] ✅ MongoDB sync successful, mongo_id: {mongo_id}")
            
            # Update PostgreSQL with MongoDB ID
            form.mongo_id = mongo_id
            db.commit()
            db.refresh(form)
        except Exception as mongo_error:
            print(f"[Forms Create] ❌ MongoDB error: {str(mongo_error)}")
            import traceback
            traceback.print_exc()
            # Continue without MongoDB - form is still created in PostgreSQL

        # Audit log: form created
        try:
            client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="CREATE",
                object_type="Form",
                object_id=str(form.id),
                user_id=get_user_id(current_user),
                client_id=client_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["CREATE"],
                new_values={"name": form.name, "menu_id": str(form.menu_id)},
            )
        except Exception:
            pass

        return form
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create form: {str(e)}"
        )

@router.post(
    "/import/{menu_id}",
    response_model=FormResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import form from JSON",
    description="Import a form from the provided JSON structure"
)
async def import_form(
    request: Request,
    menu_id: str,
    import_data: FormImport,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    created_by: Optional[str] = Query(None, description="User who is importing the form")
):
    """
    Import a form from JSON structure.
    
    - **menu_id**: UUID of the menu this form belongs to
    - **import_data**: Complete form JSON structure to import
    """
    
    # Check for duplicate form name in the same menu
    existing_form = FormsService.get_form_by_name(db, import_data.name, menu_id)
    if existing_form:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Form with name '{import_data.name}' already exists in this menu"
        )
    
    try:
        # Create form from import data
        form = FormsService.create_form_from_import(db, menu_id, import_data, created_by)
        
        # Create form details in MongoDB
        mongo_id = await forms_details_service.create_form_details(
            form_id=str(form.id),
            menu_id=str(form.menu_id),
            name=form.name,
            version=form.version,
            trigger_when=form.trigger_when,
            forms=form.forms,
            actions=form.actions,
            modal_type=form.modal_type,
            tooltip_type=form.tooltip_type,
            error_type=form.error_type,
            localization=form.localization,
            languages=form.languages,
            default_language=form.default_language,
            is_active=form.is_active,
            created_by=created_by
        )
        
        # Update PostgreSQL with MongoDB ID
        form.mongo_id = mongo_id
        db.commit()
        db.refresh(form)

        # Audit log: form imported (CREATE action)
        try:
            client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="CREATE",
                object_type="Form",
                object_id=str(form.id),
                user_id=get_user_id(current_user),
                client_id=client_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["CREATE"],
                new_values={"name": form.name, "menu_id": str(form.menu_id)},
            )
        except Exception:
            pass

        return form
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import form: {str(e)}"
        )

@router.get(
    "/",
    summary="Get forms with filtering and pagination",
    description="Retrieve forms grouped by menu from MongoDB in the new structure"
)
async def get_forms(
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    size: int = Query(10, ge=1, le=100, description="Number of items per page"),
    menu_id: Optional[str] = Query(None, description="Filter by menu ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search in name, version, or trigger_when"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order (asc or desc)")
):
    """
    Get forms directly from MongoDB in the grouped structure.
    
    Returns forms exactly as stored in MongoDB:
    [
        {
            "_id": "mongodb_object_id",
            "menu_id": "uuid",
            "name": "form collection",
            "access": ["read", "write"],
            "forms": [
                {
                    "form_id": "uuid",
                    "defaultLanguage": "en-US",
                    "form": {...},
                    "languages": [...],
                    "modalType": "AntModal",
                    "version": "1"
                }
            ],
            "created_at": "2026-04-22T13:04:11.251+00:00",
            "updated_at": "2026-04-22T13:04:11.251+00:00"
        }
    ]
    """
    
    skip = (page - 1) * size
    
    try:
        # Get forms directly from MongoDB
        collection = await forms_details_service.get_collection()
        
        # Build query
        query = {}
        if menu_id:
            query["menu_id"] = menu_id
        
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"forms.version": {"$regex": search, "$options": "i"}},
                {"forms.form.key": {"$regex": search, "$options": "i"}}
            ]
        
        # Get total count
        total = await collection.count_documents(query)
        
        # Get paginated results
        cursor = collection.find(query).skip(skip).limit(size)
        
        # Apply sorting
        if sort_order.lower() == "desc":
            cursor = cursor.sort(sort_by, -1)
        else:
            cursor = cursor.sort(sort_by, 1)
        
        forms_data = await cursor.to_list(length=size)
        
        # Convert ObjectId to string for JSON serialization
        for doc in forms_data:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
        
        total_pages = math.ceil(total / size) if total > 0 else 0
        
        result = {
            "forms": forms_data,
            "total": total,
            "page": page,
            "size": size,
            "total_pages": total_pages
        }
        try:
            client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="READ",
                object_type="Form",
                user_id=get_user_id(current_user),
                client_id=client_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score="LOW",
            )
        except Exception:
            pass
        return result

    except Exception as e:
        print(f"ERROR: Failed to retrieve forms from MongoDB: {str(e)}")
        import traceback
        traceback.print_exc()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve forms: {str(e)}"
        )


@router.get(
    "/menu/{menu_id}",
    summary="Get forms by menu ID", 
    description="Retrieve forms collection for a specific menu from MongoDB"
)
async def get_forms_by_menu(
    request: Request,
    menu_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get forms collection for a specific menu from MongoDB.
    
    Returns the clean MongoDB structure with name inside each form:
    {
        "menu_id": "8a1ff357-c1d5-4858-8847-ed65843a9cf1",
        "access": ["read", "write"],
        "forms": [
            {
                "form_id": "76f9740a-85b4-460b-9fd0-a9070c9f4ac9",
                "name": "client arun",
                "defaultLanguage": "en-US", 
                "form": {
                    "key": "Screen",
                    "type": "Screen",
                    "props": {},
                    "access": [],
                    "children": [...]
                },
                "languages": [...],
                "localization": {...},
                "modalType": "AntModal",
                "tooltipType": "AntTooltip",
                "errorType": "AntErrorMessage", 
                "triggerWhen": {...},
                "version": "1"
            }
        ]
    }
    
    - **menu_id**: The UUID of the menu
    """
    
    try:
        # Get forms collection directly from MongoDB for this menu
        forms_collection = await forms_details_service.get_form_details_by_menu(menu_id)
        
        if not forms_collection:
            # Return empty structure instead of error
            return {
                "menu_id": menu_id,
                "access": [],
                "forms": []
            }
        
        # Return only the essential structure - name is now inside each form object
        response = {
            "menu_id": forms_collection.get("menu_id"),
            "access": forms_collection.get("access", []),
            "forms": forms_collection.get("forms", [])
        }
        try:
            client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="READ",
                object_type="Form",
                object_id=menu_id,
                user_id=get_user_id(current_user),
                client_id=client_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score="LOW",
            )
        except Exception:
            pass
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR: Failed to retrieve forms for menu {menu_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve forms for menu: {str(e)}"
        )

@router.put(
    "/{form_id}",
    summary="Update a form",
    description="Update an existing form with the provided details"
)
async def update_form(
    request: Request,
    form_id: str,
    form_data: FormUpdateSimple,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Update an existing form.
    
    Expected structure:
    {
        "menu_id": "8a1ff357-c1d5-4858-8847-ed65843a9cf1",
        "access": ["read", "write"],
        "forms": [
            {
                "form_id": "758ef3e6-de5b-4a5b-9256-d94e179d3848",
                "name": "clienttest",
                "defaultLanguage": "en-US",
                "form": {...},
                "languages": [...],
                "version": "1"
            }
        ]
    }
    """
    
    # Check if form exists
    existing_form = FormsService.get_form(db, form_id)
    if not existing_form:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Form with ID {form_id} not found"
        )

    # Get name from the first form item for duplicate check
    form_name = form_data.forms[0].name if form_data.forms and len(form_data.forms) > 0 else None
    
    # Check for duplicate name if being updated
    if form_name and form_name != existing_form.name:
        duplicate_form = FormsService.get_form_by_name(db, form_name, str(form_data.menu_id))
        if duplicate_form:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Form with name '{form_name}' already exists in this menu"
            )

    try:
        # Convert simplified format to full update format
        update_data = FormUpdate(
            menu_id=form_data.menu_id,
            name=form_name,
            forms=form_data.forms,
            updated_by=None
        )
        
        # Update form in PostgreSQL
        updated_form = FormsService.update_form(db, form_id, update_data, None)
        
        # Update form details in MongoDB - update only the specific form
        if form_data.forms:
            collection = await forms_details_service.get_collection()
            
            # Find the collection containing this form_id
            existing_doc = await collection.find_one({
                "menu_id": str(form_data.menu_id),
                "forms.form_id": form_id
            })
            
            if not existing_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Form with ID {form_id} not found in menu {form_data.menu_id}"
                )
            
            # Convert the updated form data to dict format
            updated_form_data = form_data.forms[0]  # Get the first (and should be only) form from request
            form_dict = updated_form_data.model_dump() if hasattr(updated_form_data, 'model_dump') else updated_form_data
            
            # Ensure form_id is preserved
            form_dict['form_id'] = form_id
            
            # Update only the specific form in the forms array using positional operator
            await collection.update_one(
                {
                    "menu_id": str(form_data.menu_id),
                    "forms.form_id": form_id
                },
                {
                    "$set": {
                        "forms.$": form_dict,  # Update only the matched form
                        "access": form_data.access if isinstance(form_data.access, list) else [form_data.access] if form_data.access else [],
                        "updated_at": datetime.utcnow(),
                        "updated_by": None
                    }
                }
            )
        
        # Audit log: form updated
        try:
            client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="UPDATE",
                object_type="Form",
                object_id=str(form_id),
                user_id=get_user_id(current_user),
                client_id=client_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["UPDATE"],
                new_values={"form_id": form_id, "menu_id": str(form_data.menu_id) if form_data.menu_id else None},
            )
        except Exception:
            pass

        return {"message": "Form updated successfully", "form_id": form_id}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update form: {str(e)}"
        )
@router.delete(
    "/{form_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a form",
    description="Soft delete a form (marks as deleted but keeps in database)"
)
async def delete_form(
    request: Request,
    form_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Soft delete a form.
    
    - **form_id**: The UUID of the form to delete
    
    This performs a soft delete - the form is marked as deleted but remains in the database.
    """
    
    try:
        # Get form to find menu_id
        db_form = FormsService.get_form(db, form_id)
        if not db_form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Form with ID {form_id} not found"
            )
        
        # Delete from PostgreSQL (soft delete)
        success = FormsService.delete_form(db, form_id, None)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Form with ID {form_id} not found"
            )
        
        # Delete from MongoDB (remove from collection)
        await forms_details_service.delete_form_details(form_id, str(db_form.menu_id))

        # Audit log: form deleted
        try:
            client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="DELETE",
                object_type="Form",
                object_id=str(form_id),
                user_id=get_user_id(current_user),
                client_id=client_id_audit,
                entity_id=entity_id_audit,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["DELETE"],
                old_values={"id": str(form_id)},
            )
        except Exception:
            pass

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete form: {str(e)}"
        )


    """
    Get forms statistics.
    
    - **menu_id**: Filter by menu ID (optional)
    
    Returns statistics including total forms, active/inactive counts, and component type distribution.
    """
    
    try:
        # Get PostgreSQL statistics
        pg_stats = FormsService.get_form_statistics(db, menu_id)
        
        # Get MongoDB statistics
        mongo_stats = await forms_details_service.get_forms_statistics(menu_id)
        
        return {
            "postgresql": pg_stats,
            "mongodb": mongo_stats,
            "menu_id": menu_id
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )