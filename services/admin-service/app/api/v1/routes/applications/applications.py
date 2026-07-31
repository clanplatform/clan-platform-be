from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session
from app.infrastructure.database.session import get_tenant_db as get_db
from app.applications.models.application import Application
from app.menus.models.menu import Menu
from app.applications.schemas.application import ApplicationCreate, ApplicationUpdate, ApplicationResponse
from app.applications.exceptions import ApplicationNotFoundError, DuplicateApplicationNameError, ApplicationReadOnlyError
from app.core.access import is_active_from_access, is_write_locked
from app.menus.schemas.menu import MenuResponse
from app.core.security import get_current_user
from app.core.config import settings
from app.infrastructure.redis_cache.redis_cache import redis_cache
from app.infrastructure.mongodb.mongodb_admin import get_mongodb
from app.infrastructure.audit_helpers import RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id
from app.infrastructure.audit_tenant import fire_audit_log
from bson import ObjectId
import uuid

router = APIRouter()

@router.get("/", response_model=List[ApplicationResponse])
def get_applications(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    domain_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get all applications with pagination and optional domain filtering, sorted by newest first (FILO)"""
    try:
        # Create cache key
        cache_key = f"applications:list:skip={skip}:limit={limit}:domain_id={domain_id}"

        # Try to get from cache (with error handling)
        try:
            cached_apps = redis_cache.get(cache_key)
            if cached_apps:
                return cached_apps
        except Exception as cache_error:
            print(f"Redis cache error (continuing without cache): {str(cache_error)}")

        # Query database if not in cache
        query = db.query(Application).filter(Application.is_active == True)

        # Check if is_deleted column exists before filtering
        try:
            query = query.filter(Application.is_deleted == False)
        except Exception:
            # Column might not exist in older schemas
            pass

        if domain_id:
            query = query.filter(Application.domain_id == domain_id)

        # Sort by created_at in descending order (newest first - FILO)
        # Fallback to id if created_at doesn't exist
        try:
            query = query.order_by(Application.created_at.desc())
        except Exception:
            print("Warning: created_at column not found, sorting by id instead")
            query = query.order_by(Application.id.desc())

        applications = query.offset(skip).limit(limit).all()

        # Convert to dict for caching
        apps_list = []
        for a in applications:
            app_dict = {
                "id": str(a.id),
                "name": a.name,
                "description": a.description,
                "domain_id": str(a.domain_id),
                "version": a.version,
                "status": a.status,
                "is_active": a.is_active,
                "key": getattr(a, 'key', None),
                "label": getattr(a, 'label', None),
                "route": getattr(a, 'route', None),
                "icon": getattr(a, 'icon', None),
                "badge": getattr(a, 'badge', None),
                "section_title": getattr(a, 'section_title', None),
                "access": getattr(a, 'access', None),
                "order_index": getattr(a, 'order_index', 0),
                "created_at": str(getattr(a, 'created_at', '')),
                "updated_at": str(getattr(a, 'updated_at', ''))
            }
            apps_list.append(app_dict)

        # Cache the result for 30 minutes (with error handling)
        try:
            redis_cache.set(cache_key, apps_list, ttl=settings.CACHE_DEFAULT_TTL)
        except Exception as cache_error:
            print(f"Redis cache set error (continuing without cache): {str(cache_error)}")

        try:
            tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="READ",
                object_type="Application",
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
        return applications
        
    except Exception as e:
        # Log the full error for debugging
        print(f"Error getting applications: {str(e)}")
        import traceback
        traceback.print_exc()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get applications: {str(e)}"
        )

    """Get a specific application by ID"""
    application = db.query(Application).filter(
        Application.id == application_id, 
        Application.is_active == True,
        Application.is_deleted == False
    ).first()
    if not application:
        raise ApplicationNotFoundError()
    return application

@router.get("/{application_id}/menus")
async def get_menus_by_application(
    application_id: uuid.UUID,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    include_children: bool = Query(True, description="Include child menus in the response"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get complete mainNavigation structure for a specific application
    
    Returns the full navigation structure including:
    - _id: Master document ID
    - config: Navigation configuration
    - mainNavigation: Array with the specific application and its menu hierarchy
    - profileSection: User profile menu items
    
    Structure matches the MongoDB mainNavigation document format.
    
    - **application_id**: UUID of the application
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    - **include_children**: Whether to include child menus (default: True)
    """
    # Verify application exists
    application = db.query(Application).filter(
        Application.id == application_id,
        Application.is_active == True,
        Application.is_deleted == False
    ).first()
    
    if not application:
        raise ApplicationNotFoundError(str(application_id))
    
    # Create cache key
    cache_key = f"menus:application:{application_id}:navigation:skip={skip}:limit={limit}:children={include_children}"
    
    # Try to get from cache
    cached_response = redis_cache.get(cache_key)
    if cached_response:
        return cached_response
    
    # Connect to MongoDB to get the master navigation document
    db_mongo = await get_mongodb()
    if db_mongo is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB not available"
        )
    
    # Fetch the master navigation document
    master_doc_id = ObjectId("69074724f217ab8fcb2e3b24")
    master_doc = await db_mongo.menu_details.find_one({"_id": master_doc_id})
    
    if not master_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Master navigation document not found"
        )
    
    # Get mainNavigation array references
    main_nav_refs = master_doc.get("mainNavigation", [])
    
    # Find the application document in MongoDB
    application_doc = None
    for app_ref in main_nav_refs:
        if isinstance(app_ref, ObjectId) or isinstance(app_ref, str):
            try:
                # Convert to ObjectId if it's a string
                if isinstance(app_ref, str):
                    app_doc_id = ObjectId(app_ref)
                else:
                    app_doc_id = app_ref
                
                # Fetch the application document
                app_doc = await db_mongo.menu_details.find_one({"_id": app_doc_id})
                
                if app_doc and app_doc.get("application_id") == str(application_id):
                    application_doc = app_doc
                    break
            except Exception as e:
                print(f"[Get Menus By Application] Error fetching app doc: {str(e)}")
                continue
        elif isinstance(app_ref, dict) and app_ref.get("application_id") == str(application_id):
            application_doc = app_ref
            break
    
    if not application_doc:
        # If not found in MongoDB, build from PostgreSQL
        print(f"[Get Menus By Application] Application document not found in MongoDB, building from PostgreSQL")
        
        # Query only parent menus (those without parent_menu_id)
        query = db.query(Menu).filter(
            Menu.application_id == application_id,
            Menu.is_active == True,
            Menu.deleted_at.is_(None),
            Menu.parent_menu_id.is_(None)
        )
        
        # Sort by order_index and created_at
        query = query.order_by(Menu.order_index.asc(), Menu.created_at.asc())
        
        # Apply pagination
        parent_menus = query.offset(skip).limit(limit).all()
        
        # Helper function to recursively build children
        def build_children_recursive(parent_menu):
            """Recursively fetch and build children for a menu"""
            children = db.query(Menu).filter(
                Menu.parent_menu_id == parent_menu.id,
                Menu.is_active == True,
                Menu.deleted_at.is_(None)
            ).order_by(Menu.order_index.asc(), Menu.created_at.asc()).all()
            
            if not children:
                return []
            
            children_list = []
            for child in children:
                child_dict = {
                    "key": child.key or child.name,
                    "label": child.label,
                    "icon": child.icon,
                    "description": child.menus_description,
                    "badge": child.badge,
                    "section_title": child.section_title or "",
                    "sectionTitle": child.section_title or "",
                    "route": child.route,
                    "component": child.component,
                    "menu_id": str(child.id),
                    "level": child.level,
                    "order_index": child.order_index,
                }
                
                # Recursively get grandchildren
                grandchildren = build_children_recursive(child)
                if grandchildren:
                    child_dict["children"] = grandchildren
                
                children_list.append(child_dict)
            
            return children_list
        
        # Build children array
        children_array = []
        for menu in parent_menus:
            menu_item = {
                "key": menu.key or menu.name,
                "label": menu.label,
                "icon": menu.icon,
                "description": menu.menus_description,
                "badge": menu.badge,
                "section_title": menu.section_title or "",
                "sectionTitle": menu.section_title or "",
                "route": menu.route,
                "component": menu.component,
                "menu_id": str(menu.id),
                "level": menu.level,
                "order_index": menu.order_index,
            }
            
            # Add children recursively if requested
            if include_children:
                children = build_children_recursive(menu)
                if children:
                    menu_item["children"] = children
            
            children_array.append(menu_item)
        
        # Build application document structure
        application_doc = {
            "key": application.key or application.name.lower().replace(" ", "-"),
            "label": application.label or application.name,
            "icon": application.icon or "ri-apps-line",
            "description": application.description or f"Manage {application.name}",
            "badge": application.badge,
            "sectionTitle": application.section_title or application.name,
            "route": application.route or f"/{application.name.lower().replace(' ', '-')}",
            "application_id": str(application.id),
            "level": 1,
            "order_index": 1000,
            "children": children_array
        }
    else:
        # Remove MongoDB internal fields
        application_doc.pop("_id", None)
        application_doc.pop("created_at", None)
        application_doc.pop("updated_at", None)
        application_doc.pop("is_active", None)
    
    # Get profileSection and config from master document
    profile_section = master_doc.get("profileSection", {})
    config = master_doc.get("config", {})
    
    # Populate profileSection with logged-in user's data dynamically
    try:
        from app.menu_details.services.menu_details import menu_details_service
        from app.user_setup.models.user_setup import UserSetupBasic
        from uuid import UUID
        
        # Get the user from database
        user_id = current_user.get("user_id") or current_user.get("id")
        if user_id:
            try:
                user_uuid = UUID(user_id)
                user = db.query(UserSetupBasic).filter(UserSetupBasic.id == user_uuid).first()
                
                if user:
                    profile_section = menu_details_service.populate_profile_section_with_user_data(
                        profile_section, user, db
                    )
            except Exception as e:
                print(f"[Get Application Menus] ⚠️ Error fetching user: {str(e)}")
    except Exception as e:
        print(f"[Get Application Menus] ⚠️ Error populating profile section: {str(e)}")
    
    # Clean userData fields (ensure simple strings, not {value, color} objects)
    if profile_section and "userData" in profile_section:
        user_data = profile_section["userData"]
        cleaned_user_data = {}
        
        for key, value in user_data.items():
            if isinstance(value, dict) and 'value' in value:
                cleaned_user_data[key] = value['value']
            else:
                cleaned_user_data[key] = value
        
        profile_section["userData"] = cleaned_user_data
    
    # Build response matching mainNavigation structure
    response = {
        "_id": str(master_doc_id),
        "config": config,
        "mainNavigation": [application_doc],  # Array with single application
        "profileSection": profile_section
    }
    
    # Cache the result for 30 minutes
    redis_cache.set(cache_key, response, ttl=settings.CACHE_DEFAULT_TTL)
    
    return response
    
    # Cache the result for 30 minutes
    redis_cache.set(cache_key, response, ttl=settings.CACHE_DEFAULT_TTL)
    
    return response

@router.get("/domain/{domain_id}", response_model=List[ApplicationResponse])
def get_applications_by_domain(
    request: Request,
    domain_id: uuid.UUID,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    include_inactive: bool = Query(False, description="Include inactive applications"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all applications for a specific domain
    
    - **domain_id**: UUID of the domain
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    - **include_inactive**: Whether to include inactive applications (default: False)
    
    Returns a list of applications sorted by created_at (newest first - FILO)
    """
    # Create cache key
    cache_key = f"applications:domain:{domain_id}:skip={skip}:limit={limit}:inactive={include_inactive}"
    
    # Try to get from cache
    cached_apps = redis_cache.get(cache_key)
    if cached_apps:
        return cached_apps
    
    # Query applications for this domain
    query = db.query(Application).filter(
        Application.domain_id == domain_id,
        Application.is_deleted == False
    )
    
    # Filter by active status unless include_inactive is True
    if not include_inactive:
        query = query.filter(Application.is_active == True)
    
    # Sort by created_at in descending order (newest first - FILO)
    query = query.order_by(Application.created_at.desc())
    
    # Apply pagination
    applications = query.offset(skip).limit(limit).all()
    
    # If no applications found, return empty list (not an error - domain might be new)
    if not applications:
        return []
    
    # Convert to dict for caching
    apps_list = [
        {
            "id": str(app.id),
            "domain_id": str(app.domain_id),
            "name": app.name,
            "description": app.description,
            "version": app.version,
            "status": app.status,
            "is_active": app.is_active,
            "key": app.key,
            "label": app.label,
            "route": app.route,
            "icon": app.icon,
            "badge": app.badge,
            "section_title": app.section_title,
            "access": app.access,
            "order_index": app.order_index,
            "created_at": str(app.created_at),
            "updated_at": str(app.updated_at)
        }
        for app in applications
    ]
    
    # Cache the result for 30 minutes
    redis_cache.set(cache_key, apps_list, ttl=settings.CACHE_DEFAULT_TTL)

    try:
        tenant_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="READ",
            object_type="Application",
            object_id=str(domain_id),
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
    return applications

@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
def create_application(
    request: Request,
    application_data: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new application"""
    try:
        # Check if application name already exists in the same domain
        existing_application = db.query(Application).filter(
            Application.name == application_data.name,
            Application.domain_id == application_data.domain_id
        ).first()
        if existing_application:
            raise DuplicateApplicationNameError()

        # Create application using dict() method
        application_dict = application_data.dict()

        # Access drives the active state: "disable" forces it off, "write"/"read"
        # keep it on; otherwise fall back to the value supplied on the request.
        derived_active = is_active_from_access(application_dict.get("access"))
        if derived_active is not None:
            application_dict["is_active"] = derived_active

        application = Application(**application_dict)
        
        db.add(application)
        db.commit()
        db.refresh(application)

        # Cache the created application
        app_dict = {
            "id": str(application.id),
            "name": application.name,
            "description": application.description,
            "domain_id": str(application.domain_id),
            "version": application.version,
            "status": application.status,
            "is_active": application.is_active,
            "key": application.key,
            "label": application.label,
            "route": application.route,
            "icon": application.icon,
            "badge": application.badge,
            "section_title": application.section_title,
            "access": application.access,
            "order_index": application.order_index,
            "created_at": str(application.created_at),
            "updated_at": str(application.updated_at)
        }
        redis_cache.set(f"application:{application.id}", app_dict, ttl=settings.CACHE_DEFAULT_TTL)

        # Invalidate applications list cache
        redis_cache.delete_pattern("applications:list:*")

        # Audit log: application created
        try:
            tenant_id, entity_id = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="CREATE",
                object_type="Application",
                object_id=str(application.id),
                user_id=get_user_id(current_user),
                tenant_id=tenant_id,
                entity_id=entity_id,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["CREATE"],
                new_values={
                    "name": application.name,
                    "domain_id": str(application.domain_id),
                    "status": application.status,
                    "is_active": application.is_active,
                },
            )
        except Exception:
            pass

        return application
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log the full error for debugging
        print(f"Error creating application: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Rollback the transaction
        db.rollback()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create application: {str(e)}"
        )

@router.put("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    request: Request,
    application_id: uuid.UUID,
    application_data: ApplicationUpdate,
    nav_doc_id: str = Query("69074724f217ab8fcb2e3b24", description="Navigation document ID"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Update an application in PostgreSQL and sync to MongoDB navigation

    This endpoint:
    1. Updates the application in PostgreSQL
    2. Syncs the changes to MongoDB mainNavigation structure
    3. Invalidates relevant caches
    """
    print(f"[Application Update] Updating application_id: {application_id}")

    application = db.query(Application).filter(
        Application.id == application_id,
        Application.is_active == True,
        Application.is_deleted == False
    ).first()
    if not application:
        raise ApplicationNotFoundError()

    # Read-only lock: a write-locked app (access grants no "write") can only be
    # edited by a payload that also changes "access" (the way to unlock it).
    if is_write_locked(application.access) and "access" not in application_data.model_fields_set:
        raise ApplicationReadOnlyError()

    # Check if new name conflicts with existing application in the target domain
    target_domain_id = application_data.domain_id or application.domain_id
    if application_data.name and application_data.name != application.name or (
        application_data.domain_id and application_data.domain_id != application.domain_id
    ):
        existing_application = db.query(Application).filter(
            Application.name == (application_data.name or application.name),
            Application.domain_id == target_domain_id,
            Application.id != application.id
        ).first()
        if existing_application:
            raise DuplicateApplicationNameError()

    # Capture old values before update for audit
    old_values = {
        "name": application.name,
        "domain_id": str(application.domain_id),
        "status": application.status,
        "is_active": application.is_active,
    }

    # Update PostgreSQL
    update_data = application_data.dict(exclude_unset=True)

    # Keep is_active in sync when access changes: "disable" forces it off,
    # "write"/"read" keep it on (access wins over any is_active in the payload).
    # Without this, an app left is_active=False stays that way even after the
    # access change, and the MongoDB sync below silently no-ops since it
    # requires is_active=True - modules then appear to "disappear".
    if "access" in update_data:
        derived_active = is_active_from_access(update_data.get("access"))
        if derived_active is not None:
            update_data["is_active"] = derived_active

    for field, value in update_data.items():
        setattr(application, field, value)

    db.commit()
    db.refresh(application)

    print(f"[Application Update] ✅ PostgreSQL updated")

    # Audit log: application updated
    try:
        tenant_id, entity_id = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="UPDATE",
            object_type="Application",
            object_id=str(application.id),
            user_id=get_user_id(current_user),
            tenant_id=tenant_id,
            entity_id=entity_id,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["UPDATE"],
            old_values=old_values,
            new_values=update_data,
        )
    except Exception:
        pass

    # Sync to MongoDB: full rebuild of this application's navigation document.
    # mainNavigation holds ObjectId references to per-application documents, so
    # the app doc itself must be updated - the shared sync refreshes its
    # application-level fields (key, label, icon, route, ...) from PostgreSQL.
    try:
        from app.menus.services.menu_sync import sync_application_menus_to_mongodb
        synced = await sync_application_menus_to_mongodb(db, application.id)
        if synced:
            print(f"[Application Update] ✅ MongoDB navigation synced")
        else:
            print(f"[Application Update] ⚠️ MongoDB sync skipped (not available)")
    except Exception as e:
        print(f"[Application Update] ⚠️ MongoDB sync failed: {e}")
        import traceback
        traceback.print_exc()

    # Invalidate caches
    redis_cache.delete(f"application:{application.id}")
    redis_cache.delete_pattern("applications:list:*")
    redis_cache.delete("menus:mongo:main_navigation_full")

    print(f"[Application Update] ✅ Complete!")

    return application

@router.delete("/{application_id}", status_code=status.HTTP_200_OK)
def delete_application(
    request: Request,
    application_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Soft delete an application"""
    application = db.query(Application).filter(
        Application.id == application_id,
        Application.is_active == True,
        Application.is_deleted == False
    ).first()
    if not application:
        raise ApplicationNotFoundError()

    # Read-only lock: a write-locked app (access grants no "write") cannot be deleted.
    if is_write_locked(application.access):
        raise ApplicationReadOnlyError()

    try:
        # Import datetime for soft delete
        from datetime import datetime

        # Snapshot name before soft delete for audit
        old_name = application.name

        # Soft delete - set flags and timestamp
        application.is_active = False
        application.is_deleted = True
        application.deleted_at = datetime.utcnow()

        db.commit()

        # Audit log: application deleted
        try:
            tenant_id, entity_id = get_audit_org_context(db, get_user_id(current_user))
            fire_audit_log(
                action="DELETE",
                object_type="Application",
                object_id=str(application_id),
                user_id=get_user_id(current_user),
                tenant_id=tenant_id,
                entity_id=entity_id,
                session_id=get_session_id(current_user),
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                risk_score=RISK_SCORE["DELETE"],
                old_values={"name": old_name, "id": str(application_id)},
            )
        except Exception:
            pass

        return {"message": "Application deleted successfully", "application_id": str(application_id)}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete application: {str(e)}"
        )
