from typing import List, Optional, Dict, Any
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Request
from sqlalchemy.orm import Session
from datetime import datetime
import math
from app.infrastructure.database.session import get_tenant_db as get_db
from app.core.security import get_current_user
from app.core.access import cascade_access, coerce_access, apply_field_permissions, prune_hidden_fields
from app.infrastructure.scope_helpers import require_form_admin
from app.forms.services.forms import FormsService
from app.infrastructure.audit_helpers import RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id
from app.infrastructure.audit_tenant import fire_audit_log
from app.forms_details.services.forms_details import forms_details_service
from app.user_role.services.user_role import UserRoleService
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


def _user_permission_context(db: Session, current_user: dict) -> Dict[str, Any]:
    """Resolve the current user's role-based access context (see
    UserRoleService.get_user_permission_context) so forms can be scoped to
    the same menu/form/button permissions the dashboard nav is scoped to."""
    user_id_str = get_user_id(current_user)
    try:
        user_uuid = UUID(user_id_str) if user_id_str else None
    except ValueError:
        user_uuid = None
    return UserRoleService.get_user_permission_context(db, user_uuid)


def _filter_accessible_forms(forms: list, accessible_form_ids: set) -> list:
    """Keep only form entries whose form_id is in the role's accessible set —
    same JSONB shape as forms_details_service's grouped-by-menu documents."""
    return [
        f for f in (forms or [])
        if isinstance(f, dict) and str(f.get("form_id")) in accessible_form_ids
    ]


def _overlay_field_permissions(forms: list, context: Dict[str, Any]) -> None:
    """Overlay the role's per-field permission tree
    (form_permissions[].fields) onto each served form's component tree, in
    place — so a non-admin sees per-field read/write/hidden, not just which
    forms exist. No-op for admins / roles without a field tree."""
    trees_by_form = context.get("form_field_permissions") or {}
    if not trees_by_form:
        return
    for f in (forms or []):
        if not isinstance(f, dict):
            continue
        tree = trees_by_form.get(str(f.get("form_id")))
        if isinstance(tree, dict) and isinstance(f.get("form"), dict):
            apply_field_permissions(f["form"], tree)


def _prune_hidden_fields(forms: list) -> None:
    """Drop every hidden/disabled field (and its subtree) from each served
    form's component tree, in place — runs UNCONDITIONALLY (not gated by
    should_filter/role), since a field can be marked disable at the form's
    own definition level (baked in at save time by cascade_access,
    independent of any viewing role) as well as by a role's field-permission
    overlay (_overlay_field_permissions, above) — either way it must be
    genuinely absent from what GET returns, not merely marked, for every
    caller including admins. Must run AFTER _overlay_field_permissions so it
    sees the fully-resolved access."""
    for f in (forms or []):
        if isinstance(f, dict) and isinstance(f.get("form"), dict):
            prune_hidden_fields(f["form"])


def _subscription_granted_menu_ids(db: Session) -> Optional[set]:
    """Menu ids belonging to an application/module this caller's own
    Subscription actually grants (applications_to_grant / modules_to_grant).

    Returns None when there's no subscription signal at all — permissive,
    same convention as menu.py's _filter_navigation_by_subscription: an
    unconfigured tenant isn't blanked outright. A master-DB caller's `db`
    session has no tenant subscription row (subscriptions live only in each
    tenant's own DB, seeded at onboarding), so this is always None for them
    -> unrestricted, which is exactly "master sees all"."""
    from app.subscription.models.subscription import Subscription
    from app.menus.models.menu import Menu
    from sqlalchemy import or_

    subscription = db.query(Subscription).first()
    if not subscription:
        return None
    granted_apps = {str(a) for a in (subscription.applications_to_grant or [])}
    granted_modules = {str(m) for m in (subscription.modules_to_grant or [])}
    if not granted_apps and not granted_modules:
        return None

    conditions = []
    if granted_apps:
        conditions.append(Menu.application_id.in_(granted_apps))
    if granted_modules:
        conditions.append(Menu.module_id.in_(granted_modules))
    return {str(mid) for (mid,) in db.query(Menu.id).filter(or_(*conditions)).all()}


def _forms_payload_dicts(forms) -> list:
    """The incoming forms array as plain dicts (Pydantic FormItem or already-dict)."""
    return [item.model_dump() if hasattr(item, "model_dump") else item for item in (forms or [])]


def _cascade_forms_access(forms_payload: list, top_level_access=None) -> list:
    """Resolve the parent -> child access cascade on each incoming form item's
    component tree, in place, so the PostgreSQL forms JSON and the MongoDB
    forms_details copy store the same resolved access. Seed precedence: the
    item's own form['access'], then the request's top-level access, then the
    ['read', 'write'] default. See app.core.access.cascade_access."""
    fallback = coerce_access(top_level_access) or ["read", "write"]
    for item in (forms_payload or []):
        if not isinstance(item, dict):
            continue
        form_structure = item.get("form")
        if isinstance(form_structure, dict):
            seed = coerce_access(form_structure.get("access")) or fallback
            cascade_access(form_structure, seed)
    return forms_payload


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
    current_user: dict = Depends(require_form_admin)
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
    
    # Resolve the parent -> child access cascade before the payload is written
    # to either store (parent 'write' => nested children 'write' unless a child
    # overrides lower; a child never exceeds its parent).
    forms_payload = _cascade_forms_access(_forms_payload_dicts(form_data.forms), form_data.access)

    try:
        # Convert frontend format to backend format - store the entire forms array
        backend_form_data = FormCreate(
            menu_id=form_data.menu_id,
            name=form_name,  # Use name from first form item
            version=form_data.forms[0].version if form_data.forms else "1.0.0",
            trigger_when=json.dumps(form_data.forms[0].triggerWhen) if form_data.forms and form_data.forms[0].triggerWhen else None,
            forms=forms_payload,
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
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="CREATE",
                object_type="Form",
                object_id=str(form.id),
                user_id=get_user_id(current_user),
                tenant_id=tenant_id_audit,
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
    current_user: dict = Depends(require_form_admin),
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

    # Resolve the parent -> child access cascade on the imported tree before it
    # is persisted to PostgreSQL / MongoDB.
    import_data.forms = _cascade_forms_access(_forms_payload_dicts(import_data.forms))

    try:
        # Create form from import data
        form = FormsService.create_form_from_import(db, menu_id, import_data, created_by)
        
        # Create form details in MongoDB (non-fatal: form is already in PostgreSQL)
        try:
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
        except Exception as mongo_error:
            print(f"[Forms Import] ⚠️ MongoDB sync failed (form imported in PostgreSQL): {mongo_error}")

        # Audit log: form imported (CREATE action)
        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="CREATE",
                object_type="Form",
                object_id=str(form.id),
                user_id=get_user_id(current_user),
                tenant_id=tenant_id_audit,
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

        # Build query. forms_details is one shared Mongo collection across
        # every tenant (there's no tenant_id field, and menu_id is the same
        # catalog id in every tenant DB — see onboarding's catalog copy), so
        # an unscoped query here would hand a tenant caller every OTHER
        # tenant's forms too. Restrict to menu ids under this caller's own
        # subscription BEFORE pagination — a master caller has no tenant
        # subscription row, so this stays unrestricted for them (permissive
        # fallback for an unconfigured tenant as well).
        query = {}
        allowed_menu_ids = _subscription_granted_menu_ids(db)
        if menu_id:
            if allowed_menu_ids is not None and menu_id not in allowed_menu_ids:
                query["menu_id"] = "__not_subscribed__"  # deliberately matches nothing
            else:
                query["menu_id"] = menu_id
        elif allowed_menu_ids is not None:
            query["menu_id"] = {"$in": list(allowed_menu_ids)}

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

        # Scope each menu's forms down to what the user's role permissions
        # actually grant (dashboard should only ever show permissioned forms),
        # then overlay per-field read/write/hidden overrides.
        context = _user_permission_context(db, current_user)
        if UserRoleService.should_filter(context, "form"):
            for doc in forms_data:
                doc["forms"] = _filter_accessible_forms(doc.get("forms"), context["form_ids"])
                _overlay_field_permissions(doc["forms"], context)

        # Drop hidden/disabled fields entirely (not just marked) — runs for
        # every caller including admins, since a field can be disabled at
        # the form's own definition level independent of any role.
        for doc in forms_data:
            _prune_hidden_fields(doc.get("forms"))

        total_pages = math.ceil(total / size) if total > 0 else 0
        
        result = {
            "forms": forms_data,
            "total": total,
            "page": page,
            "size": size,
            "total_pages": total_pages
        }
        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="READ",
                object_type="Form",
                user_id=get_user_id(current_user),
                tenant_id=tenant_id_audit,
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
        forms_list = forms_collection.get("forms", [])

        # Scope down to what the user's role permissions actually grant
        # (dashboard should only ever show permissioned forms), then overlay
        # per-field read/write/hidden overrides.
        context = _user_permission_context(db, current_user)
        if UserRoleService.should_filter(context, "form"):
            forms_list = _filter_accessible_forms(forms_list, context["form_ids"])
            _overlay_field_permissions(forms_list, context)

        # Drop hidden/disabled fields entirely (not just marked) — runs for
        # every caller including admins, since a field can be disabled at
        # the form's own definition level independent of any role.
        _prune_hidden_fields(forms_list)

        response = {
            "menu_id": forms_collection.get("menu_id"),
            "access": forms_collection.get("access", []),
            "forms": forms_list
        }
        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="READ",
                object_type="Form",
                object_id=menu_id,
                user_id=get_user_id(current_user),
                tenant_id=tenant_id_audit,
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
    current_user: dict = Depends(require_form_admin)
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

    # Resolve the parent -> child access cascade once, so the PostgreSQL row and
    # the MongoDB forms_details copy are written with the same resolved access.
    forms_payload = _cascade_forms_access(_forms_payload_dicts(form_data.forms), form_data.access)

    try:
        # Convert simplified format to full update format
        update_data = FormUpdate(
            menu_id=form_data.menu_id,
            name=form_name,
            forms=forms_payload,
            updated_by=None
        )

        # Update form in PostgreSQL
        updated_form = FormsService.update_form(db, form_id, update_data, None)

        # Update form details in MongoDB - update only the specific form.
        # Non-fatal: PostgreSQL is already updated; a Mongo outage must not 500.
        if forms_payload:
            try:
                collection = await forms_details_service.get_collection()

                # Convert the updated form data to dict format
                form_dict = dict(forms_payload[0])  # first (and should be only) form from request

                # Ensure form_id is preserved
                form_dict['form_id'] = form_id

                access_list = form_data.access if isinstance(form_data.access, list) else [form_data.access] if form_data.access else []

                # Find the collection containing this form_id
                existing_doc = await collection.find_one({
                    "menu_id": str(form_data.menu_id),
                    "forms.form_id": form_id
                })

                if existing_doc:
                    # Update only the specific form in the forms array using positional operator
                    await collection.update_one(
                        {
                            "menu_id": str(form_data.menu_id),
                            "forms.form_id": form_id
                        },
                        {
                            "$set": {
                                "forms.$": form_dict,  # Update only the matched form
                                "access": access_list,
                                "updated_at": datetime.utcnow(),
                                "updated_by": None
                            }
                        }
                    )
                else:
                    # Self-heal: the form is missing from MongoDB (e.g., created
                    # while Mongo was down) - add it instead of 404ing after the
                    # PostgreSQL update already succeeded
                    print(f"[Forms Update] ♻️ Form {form_id} missing in MongoDB - recreating entry")
                    await forms_details_service.create_or_update_form_collection(
                        menu_id=str(form_data.menu_id),
                        collection_name="",
                        access=access_list or ["read", "write"],
                        form_item=form_dict,
                        created_by=None
                    )
            except Exception as mongo_error:
                print(f"[Forms Update] ⚠️ MongoDB sync failed (form updated in PostgreSQL): {mongo_error}")
        
        # Audit log: form updated
        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="UPDATE",
                object_type="Form",
                object_id=str(form_id),
                user_id=get_user_id(current_user),
                tenant_id=tenant_id_audit,
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
    except HTTPException:
        raise
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
    current_user: dict = Depends(require_form_admin)
):
    """
    Soft delete a form.
    
    - **form_id**: The UUID of the form to delete
    
    This performs a soft delete - the form is marked as deleted but remains in the database.
    """
    
    try:
        # Idempotent delete: look up WITHOUT the is_deleted filter so retrying a
        # half-failed delete (PostgreSQL soft-deleted but MongoDB pull failed)
        # still prunes the MongoDB entry instead of 404ing.
        from app.forms.models.forms import Form
        db_form = db.query(Form).filter(Form.id == form_id).first()
        if not db_form:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Form with ID {form_id} not found"
            )

        if not db_form.is_deleted:
            # Delete from PostgreSQL (soft delete)
            FormsService.delete_form(db, form_id, None)
        else:
            print(f"[Forms Delete] ♻️ Form {form_id} already soft-deleted - re-running MongoDB cleanup")

        # Delete from MongoDB (remove from collection). Non-fatal: retry the
        # DELETE to prune leftovers if MongoDB is unavailable right now.
        try:
            await forms_details_service.delete_form_details(form_id, str(db_form.menu_id))
        except Exception as mongo_error:
            print(f"[Forms Delete] ⚠️ MongoDB cleanup failed (form stays soft-deleted in PostgreSQL, retry DELETE to prune): {mongo_error}")

        # Audit log: form deleted
        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="DELETE",
                object_type="Form",
                object_id=str(form_id),
                user_id=get_user_id(current_user),
                tenant_id=tenant_id_audit,
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