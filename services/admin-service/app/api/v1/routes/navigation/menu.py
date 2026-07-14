from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, text, and_
from datetime import datetime, timezone
from app.infrastructure.database.session import get_tenant_db as get_db
from app.menus.models.menu import Menu
from app.applications.models.application import Application
from app.modules.models.module import Module
from app.menus.schemas.menu import MenuCreate, MenuUpdate, MenuResponse, MenuBatchCreate
from app.menu_reorder.schemas.menu_reorder import (
    MenuReorderRequest,
    MenuReorderResponse,
    MenuReorderItem,
    MenuReorderExample,
    MenuBatchUpdateRequest,
    MenuBatchUpdateResponse,
    MenuBatchUpdateItem
)
from app.menu_navigation.schemas.menu_navigation import create_navigation_item, validate_navigation_item  # ✅ Import validation helpers
from app.core.security import get_current_user, get_current_user_id, decode_access_token
from app.core.config import settings
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.menu_details.services.menu_details import menu_details_service
from app.menu_reorder.services.menu_reorder import MenuReorderService
from app.menu_soft_delete.services.menu_soft_delete import menu_cleanup_service
from app.infrastructure.redis_cache.redis_cache import redis_cache
from app.infrastructure.audit_helpers import RISK_SCORE, get_client_ip, get_audit_org_context, get_user_id, get_session_id
from app.infrastructure.audit_tenant import fire_audit_log
from app.menu_language.models.menu_language import MenuLanguage
from bson import ObjectId
from app.infrastructure.mongodb import get_mongodb
from app.user_setup.models.user_setup import UserSetupBasic, UserSetupRolesEntity
from app.user_role.models.user_role import UserRolePermission
import uuid
from uuid import UUID
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def get_menu_translations(db: Session, lang_code: str) -> Dict[str, str]:
    """
    Fetch menu translations from menu_languages table for a specific language code.
def get_menu_translations(db: Session, lang_code: str) -> Dict[str, str]:
    
    Fetch menu translations from menu_languages table for a specific language code.
    
    Returns a dictionary mapping entity IDs to translated names.
    Key format: "entity_id" -> translated_name
    """
    if not lang_code:
        return {}
    
    try:
        translations = db.query(MenuLanguage).filter(
            and_(
                MenuLanguage.lang_code == lang_code,
                MenuLanguage.deleted_at.is_(None)
            )
        ).all()
        
        translation_map = {}
        for trans in translations:
            # Map entity_id to translated_name
            entity_id_str = str(trans.app_menu_entity_id)
            translation_map[entity_id_str] = trans.translated_name
            print(f"[Translation] Loaded: {trans.app_menu_entity_type} ID={entity_id_str} -> {trans.translated_name}")
        
        print(f"[Translation] Loaded {len(translation_map)} translations for lang_code: {lang_code}")
        return translation_map
    except Exception as e:
        print(f"[Translation] Error loading translations: {e}")
        import traceback
        traceback.print_exc()
        return {}


def apply_translations_to_navigation(
    navigation_data: List[Dict[str, Any]], 
    translation_map: Dict[str, str],
    app_name: str = None
) -> List[Dict[str, Any]]:
    """
    Recursively apply translations to navigation structure.
    Replaces 'name' and 'label' fields with translated values from menu_languages table.
    
    Args:
        navigation_data: List of navigation items (applications, modules, menus)
        translation_map: Dictionary mapping entity_id -> translated_name
        app_name: Current application name for context (unused, kept for compatibility)
    
    Returns:
        Modified navigation data with translated names
    """
    if not translation_map:
        return navigation_data
    
    for item in navigation_data:
        if not isinstance(item, dict):
            continue
        
        # Get the entity ID based on the item type
        entity_id = None
        
        # Level 1: Application - use application_id
        if item.get("level") == 1 and item.get("application_id"):
            entity_id = str(item.get("application_id"))
        
        # Level 2: Module - use module_id
        elif item.get("level") == 2 and item.get("module_id"):
            entity_id = str(item.get("module_id"))
        
        # Level 3+: Menu - use menu_id
        elif item.get("menu_id"):
            entity_id = str(item.get("menu_id"))
        
        # Apply translation if found
        if entity_id and entity_id in translation_map:
            translated_name = translation_map[entity_id]
            original_name = item.get("label") or item.get("name")
            print(f"[Translation] Applying: {original_name} -> {translated_name} (ID: {entity_id})")
            item["name"] = translated_name
            item["label"] = translated_name
        
        # Process children recursively
        if "children" in item and isinstance(item["children"], list):
            apply_translations_to_navigation(item["children"], translation_map, app_name)
    
    return navigation_data


async def working_sync_to_mongodb(db: Session, application_id: UUID) -> bool:
    """
    Sync the application's menus to MongoDB.
    Thin wrapper kept for backward compatibility - the actual implementation
    lives in app.menus.services.menu_sync (shared with MenuReorderService).
    """
    from app.menus.services.menu_sync import sync_application_menus_to_mongodb
    return await sync_application_menus_to_mongodb(db, application_id)

@router.get("/")
async def get_menus(
    request: Request,
    lang_code: Optional[str] = Query(None, description="Language code for menu translations (e.g., 'en', 'es', 'fr')"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Gets entire mainNavigation with all menu details from MongoDBs.
    Includes access field from PostgreSQL applications and modules tables.
    Supports language switching via lang_code parameter.

    Process:
    - Fetches master document with specific ID
    - Extracts menu_object_id references from mainNavigation array
    - Fetches each individual menu document by ObjectId
    - Enriches with access data from PostgreSQL applications and modules tables
    - If lang_code is provided, replaces name/label fields with translations from menu_languages table
    - Returns combined navigation structure with full menu details and access permissions

    Parameters:
    - lang_code: Optional language code (e.g., 'en', 'es', 'fr'). If not provided, returns default English names.
    """

    print(f"[GET Menus] Fetching entire mainNavigation from MongoDB with access data (lang_code: {lang_code})")

    # Create cache key for entire navigation (include lang_code for separate caching)
    cache_key = f"menus:mongo:main_navigation_full_with_access:{lang_code}" if lang_code else "menus:mongo:main_navigation_full_with_access"

    # ⚠️ TEMPORARILY BYPASS CACHE FOR DEBUGGING
    # Try to get from cache
    # cached_data = redis_cache.get(cache_key)
    # if cached_data:
    #     print(f"[GET Menus] ✅ Returning cached mainNavigation data")
    #     return cached_data
    print(f"[GET Menus] ⚠️ Cache bypassed for debugging")

    # Fetch from MongoDB
    db_mongo = get_mongodb()
    if db_mongo is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB not available"
        )

    # Permanent master document ID
    master_doc_id_str = "69074724f217ab8fcb2e3b24"
    try:
        master_doc_id = ObjectId(master_doc_id_str)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid MongoDB document ID"
        )

    # Fetch the master navigation document
    master_doc = await db_mongo.menu_details.find_one({"_id": master_doc_id})
    if not master_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Master navigation document not found"
        )

    # Get the mainNavigation array (should contain ObjectId strings)
    main_navigation = master_doc.get("mainNavigation", [])
    print(f"[GET Menus] ✅ Found {len(main_navigation)} application references in mainNavigation")

    # ✅ CHUNKED SEPARATION: Fetch each application document by ObjectId
    application_documents = []
    
    print(f"[GET Menus] 🔍 Processing {len(main_navigation)} references in mainNavigation")
    
    for idx, app_ref in enumerate(main_navigation):
        print(f"[GET Menus]   [{idx}] Type: {type(app_ref)}, Value: {app_ref}")
        
        # Handle both ObjectId objects and string representations
        if isinstance(app_ref, ObjectId) or isinstance(app_ref, str):
            # It's an ObjectId or ObjectId string - fetch the application document
            try:
                # Convert to ObjectId if it's a string
                if isinstance(app_ref, str):
                    app_doc_id = ObjectId(app_ref)
                else:
                    app_doc_id = app_ref
                
                print(f"[GET Menus]   [{idx}] Fetching document with ObjectId: {app_doc_id}")
                
                app_doc = await db_mongo.menu_details.find_one({"_id": app_doc_id})
                
                if app_doc:
                    print(f"[GET Menus]   [{idx}] ✅ Document found!")
                    print(f"[GET Menus]   [{idx}]    Keys: {list(app_doc.keys())}")
                    
                    # ✅ ENRICH WITH ACCESS DATA FROM POSTGRESQL
                    # Fetch access field from PostgreSQL applications table
                    app_access = []
                    if app_doc.get("application_id"):
                        try:
                            pg_app = db.query(Application).filter(
                                Application.id == app_doc.get("application_id"),
                                Application.is_active == True,
                                Application.is_deleted == False
                            ).first()
                            if pg_app and pg_app.access:
                                app_access = pg_app.access
                                print(f"[GET Menus]   [{idx}] ✅ Found application access: {app_access}")
                        except Exception as e:
                            print(f"[GET Menus]   [{idx}] ⚠️ Error fetching application access: {e}")
                    
                    # Add access field to application level (Level 1)
                    app_doc["access"] = app_access
                    
                    # ✅ ENRICH MODULES WITH ACCESS DATA (Level 2)
                    children = app_doc.get("children", [])
                    enriched_children = []
                    
                    # Group children by module_id to add module access data
                    modules_processed = set()
                    
                    for child in children:
                        if isinstance(child, dict):
                            module_id = child.get("module_id")
                            
                            # If this child belongs to a module and we haven't processed this module yet
                            if module_id and module_id not in modules_processed:
                                try:
                                    # Fetch access field from PostgreSQL modules table
                                    pg_module = db.query(Module).filter(
                                        Module.id == module_id,
                                        Module.is_active == True,
                                        Module.is_deleted == False
                                    ).first()
                                    
                                    if pg_module and pg_module.access:
                                        module_access = pg_module.access
                                        print(f"[GET Menus]   [{idx}] ✅ Found module access for {module_id}: {module_access}")
                                        
                                        # Add access to all children with this module_id
                                        for child_to_update in children:
                                            if isinstance(child_to_update, dict) and child_to_update.get("module_id") == module_id:
                                                # Check if this is a module-level item (level 2) or add access to module metadata
                                                if child_to_update.get("level") == 2:
                                                    child_to_update["access"] = module_access
                                                else:
                                                    # For level 3+ items, add module access to metadata
                                                    if "moduleAccess" not in child_to_update:
                                                        child_to_update["moduleAccess"] = module_access
                                    
                                    modules_processed.add(module_id)
                                    
                                except Exception as e:
                                    print(f"[GET Menus]   [{idx}] ⚠️ Error fetching module access for {module_id}: {e}")
                        
                        enriched_children.append(child)
                    
                    app_doc["children"] = enriched_children
                    
                    # Remove MongoDB-specific fields for clean response
                    app_doc.pop("_id", None)
                    app_doc.pop("created_at", None)
                    app_doc.pop("updated_at", None)
                    app_doc.pop("is_active", None)
                    
                    application_documents.append(app_doc)
                    app_name = app_doc.get("label", "Unknown")
                    children_count = len(app_doc.get("children", []))
                    print(f"[GET Menus]   [{idx}] {app_name} - {children_count} menus (with access data)")
                else:
                    print(f"[GET Menus]   [{idx}] ⚠️ Application document not found: {app_ref}")
            except Exception as e:
                print(f"[GET Menus]   [{idx}] ⚠️ Error fetching application {app_ref}: {str(e)}")
                import traceback
                traceback.print_exc()
        elif isinstance(app_ref, dict):
            # It's already an inline object (backward compatibility)
            print(f"[GET Menus]   [{idx}] ✅ Inline object found")
            
            # ✅ ENRICH INLINE OBJECTS WITH ACCESS DATA TOO
            # Fetch access field from PostgreSQL applications table
            app_access = []
            if app_ref.get("application_id"):
                try:
                    pg_app = db.query(Application).filter(
                        Application.id == app_ref.get("application_id"),
                        Application.is_active == True,
                        Application.is_deleted == False
                    ).first()
                    if pg_app and pg_app.access:
                        app_access = pg_app.access
                        print(f"[GET Menus]   [{idx}] ✅ Found inline application access: {app_access}")
                except Exception as e:
                    print(f"[GET Menus]   [{idx}] ⚠️ Error fetching inline application access: {e}")
            
            # Add access field to application level
            app_ref["access"] = app_access
            
            # ✅ ENRICH MODULES WITH ACCESS DATA (Level 2) for inline objects
            children = app_ref.get("children", [])
            modules_processed = set()
            
            for child in children:
                if isinstance(child, dict):
                    module_id = child.get("module_id")
                    
                    if module_id and module_id not in modules_processed:
                        try:
                            pg_module = db.query(Module).filter(
                                Module.id == module_id,
                                Module.is_active == True,
                                Module.is_deleted == False
                            ).first()
                            
                            if pg_module and pg_module.access:
                                module_access = pg_module.access
                                print(f"[GET Menus]   [{idx}] ✅ Found inline module access for {module_id}: {module_access}")
                                
                                # Add access to all children with this module_id
                                for child_to_update in children:
                                    if isinstance(child_to_update, dict) and child_to_update.get("module_id") == module_id:
                                        if child_to_update.get("level") == 2:
                                            child_to_update["access"] = module_access
                                        else:
                                            if "moduleAccess" not in child_to_update:
                                                child_to_update["moduleAccess"] = module_access
                            
                            modules_processed.add(module_id)
                            
                        except Exception as e:
                            print(f"[GET Menus]   [{idx}] ⚠️ Error fetching inline module access for {module_id}: {e}")
            
            application_documents.append(app_ref)
            app_name = app_ref.get("application_name") or app_ref.get("label", "Unknown")
            children_count = len(app_ref.get("children", []))
            print(f"[GET Menus]   [{idx}] {app_name} (inline) - {children_count} menus (with access data)")
        else:
            print(f"[GET Menus]   [{idx}] ⚠️ Invalid item in mainNavigation at index {idx}: {type(app_ref)}")
    
    print(f"[GET Menus] 📊 Total application_documents collected: {len(application_documents)}")

    # Get profileSection and config
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
                print(f"[GET Menus] ⚠️ Error fetching user: {str(e)}")
    except Exception as e:
        print(f"[GET Menus] ⚠️ Error populating profile section: {str(e)}")

    # Ensure userData fields are simple strings (not {value, color} objects)
    if profile_section and "userData" in profile_section:
        user_data = profile_section["userData"]
        cleaned_user_data = {}
        
        for key, value in user_data.items():
            # If value is a dict with 'value' key, extract the value
            if isinstance(value, dict) and 'value' in value:
                cleaned_user_data[key] = value['value']
                print(f"[GET Menus] 🔧 Cleaned userData.{key}: {value} → {value['value']}")
            else:
                # Keep as is if it's already a simple value
                cleaned_user_data[key] = value
        
        profile_section["userData"] = cleaned_user_data

    # Return the complete navigation structure with inline data and access permissions
    # ✅ Return application_documents (fetched data) instead of main_navigation (ObjectId strings)
    response_data = {
        "_id": str(master_doc_id),
        "mainNavigation": application_documents,  # ✅ Return fetched application documents with access data
        "profileSection": profile_section,
        "config": config
    }

    # ✅ Apply language translations if lang_code is provided
    if lang_code:
        print(f"[GET Menus] 🌐 Applying translations for language: {lang_code}")
        translation_map = get_menu_translations(db, lang_code)
        
        if translation_map:
            response_data["mainNavigation"] = apply_translations_to_navigation(
                response_data["mainNavigation"], 
                translation_map
            )
            print(f"[GET Menus] ✅ Translations applied successfully")
        else:
            print(f"[GET Menus] ⚠️ No translations found for lang_code: {lang_code}")

    # Cache the result for configured TTL (default 5 minutes)
    redis_cache.set(cache_key, response_data, ttl=settings.CACHE_DEFAULT_TTL)

    try:
        client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="READ",
            object_type="Menu",
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

    print(f"[GET Menus] ✅ Returning {len(application_documents)} application structures with inline menu data and access permissions")
    return response_data


security = HTTPBearer()

@router.get("/login-user-menus")
async def get_login_user_menus(
    lang_code: Optional[str] = Query(None, description="Language code for menu translations (e.g., 'en', 'es', 'fr')"),
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """
    Get complete navigation structure filtered by logged-in user's permissions.
    Supports language switching via lang_code parameter.

    This endpoint:
    1. Authenticates the user via JWT token
    2. Fetches user's role permissions from userrole_permission table
    3. Filters the mainNavigation structure to only show menus the user has access to
    4. If lang_code is provided, translates menu names from menu_languages table
    5. Includes profileSection and config from the master navigation document

    Parameters:
    - lang_code: Optional language code (e.g., 'en', 'es', 'fr'). If not provided, returns default names.

    Returns:
        {
            "_id": "document_id",
            "mainNavigation": [...],  // Filtered by user permissions and translated
            "profileSection": {       // User profile menu items
                "label": "Profile",
                "items": [...]
            },
            "config": {               // Navigation configuration
                "version": "1.0.0",
                "theme": {...},
                "navigation": {...},
                "features": {...},
                "permissions": {...}
            }
        }
    """

    try:
        print(f"[GET Login User Menus] 🚀 Starting request with lang_code: {lang_code}...")

        # Check if credentials are provided
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify and decode the JWT token
        token = credentials.credentials
        print(f"[GET Login User Menus] 🔍 Token received (length: {len(token)})")
        payload = decode_access_token(token)
        print(f"[GET Login User Menus] ✅ Token verified successfully")

        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Extract user information from token
        current_user_id = payload.get("user_id")
        user_email = payload.get("email")
        username = payload.get("username")

        print(f"[GET Login User Menus] 🔍 Token payload: user_id={current_user_id}, email={user_email}, username={username}")

        # Try to find user by ID first, then by email as fallback
        user = None

        if current_user_id:
            try:
                user_uuid = UUID(current_user_id)
                print(f"[GET Login User Menus] 🔍 Querying UserSetupBasic with ID: {user_uuid}")
                user = db.query(UserSetupBasic).filter(UserSetupBasic.id == user_uuid).first()
            except ValueError as e:
                print(f"[GET Login User Menus] ⚠️ Invalid UUID format for user_id: {e}")

        # Fallback to email lookup
        if not user and user_email:
            print(f"[GET Login User Menus] 🔍 Trying to find user by email: {user_email}")
            user = db.query(UserSetupBasic).filter(UserSetupBasic.email == user_email).first()

        # Fallback to username lookup
        if not user and username:
            print(f"[GET Login User Menus] 🔍 Trying to find user by username: {username}")
            user = db.query(UserSetupBasic).filter(UserSetupBasic.username == username).first()

        if not user:
            all_users_count = db.query(UserSetupBasic).count()
            print(f"[GET Login User Menus] ❌ User not found with ID: {current_user_id}, email: {user_email}, username: {username}")
            print(f"[GET Login User Menus] 📊 Total users in database: {all_users_count}")

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User not found. Tried ID: {current_user_id}, email: {user_email}, username: {username}. Total users in DB: {all_users_count}"
            )

        print(f"[GET Login User Menus] ✅ Found user: {user.username} ({user.email}) with ID: {user.id}")

        # Create cache key using the actual user ID from database and lang_code
        cache_key = f"menus:user:{user.id}:navigation:{lang_code}" if lang_code else f"menus:user:{user.id}:navigation"

        # Try to get from cache
        cached_data = redis_cache.get(cache_key)
        if cached_data:
            print(f"[GET Login User Menus] ✅ Returning cached navigation for user {user.id} (lang_code: {lang_code})")
            return cached_data

        # 2. Get user's assigned roles from usersetup_roles_entity
        roles_entity = db.query(UserSetupRolesEntity).filter(
            UserSetupRolesEntity.usersetup_basic_id == user.id
        ).first()

        # Initialize accessible menu IDs
        accessible_menu_ids = set()
        has_permissions = False
        is_admin_user = False

        if not roles_entity or not roles_entity.assigned_roles:
            print(f"[GET Login User Menus] ⚠️ User {user.id} has no assigned roles")
            print(f"[GET Login User Menus] 📊 Will return all menus (no role-based filtering)")
            # Don't return early - fetch all menus instead
        else:
            assigned_role_ids = roles_entity.assigned_roles
            print(f"[GET Login User Menus] ✅ User has {len(assigned_role_ids)} assigned roles: {assigned_role_ids}")

            # 2a. Check if user has any admin role (is_admin = True)
            from app.user_role.models.user_role import UserRoleBasic
            admin_roles = db.query(UserRoleBasic).filter(
                and_(
                    UserRoleBasic.id.in_(assigned_role_ids),
                    UserRoleBasic.is_admin == True,
                    UserRoleBasic.active == True
                )
            ).all()

            if admin_roles:
                is_admin_user = True
                admin_role_names = [role.role_name for role in admin_roles]
                print(f"[GET Login User Menus] 👑 User has ADMIN role(s): {admin_role_names}")
                print(f"[GET Login User Menus] 👑 Admin users see ALL menus without filtering")
                # Admin users bypass permission filtering - they see everything
            else:
                print(f"[GET Login User Menus] 👤 User is NOT an admin - will apply permission filtering")

            # 3. Get all permissions for these roles from userrole_permission
            permissions = db.query(UserRolePermission).filter(
                UserRolePermission.userrole_basic_id.in_(assigned_role_ids)
            ).all()

            if not permissions:
                print(f"[GET Login User Menus] ⚠️ No permissions found for user's roles: {assigned_role_ids}")
                if not is_admin_user:
                    print(f"[GET Login User Menus] 📊 Will return all menus (no permission-based filtering)")
                # Don't return early - fetch all menus instead
            else:
                print(f"[GET Login User Menus] ✅ Found {len(permissions)} permission records")
                
                # 4. Build a set of accessible menu IDs (excluding disabled menus)
                disabled_menu_ids = set()

                for idx, perm in enumerate(permissions):
                    print(f"[GET Login User Menus] 🔍 Processing permission {idx + 1}/{len(permissions)}")
                    print(f"[GET Login User Menus]   - Role ID: {perm.userrole_basic_id}")
                    print(f"[GET Login User Menus]   - menu_permissions type: {type(perm.menu_permissions)}")
                    print(f"[GET Login User Menus]   - menu_permissions value: {perm.menu_permissions}")

                    # Check menu_permissions (JSONB array)
                    if perm.menu_permissions:
                        for menu_idx, menu_perm in enumerate(perm.menu_permissions):
                            print(f"[GET Login User Menus]   - Menu permission {menu_idx + 1}: {menu_perm}")

                            if isinstance(menu_perm, dict):
                                menu_ids = menu_perm.get('id', [])
                                access_list = menu_perm.get('access', [])

                                print(f"[GET Login User Menus]     - Menu IDs (raw): {menu_ids}")
                                print(f"[GET Login User Menus]     - Menu IDs type: {type(menu_ids)}")
                                print(f"[GET Login User Menus]     - Access: {access_list}")

                                # Ensure menu_ids is a list and convert all to strings
                                if not isinstance(menu_ids, list):
                                    menu_ids = [menu_ids]

                                # Convert all menu IDs to strings (in case they're UUIDs)
                                menu_ids_str = [str(mid) for mid in menu_ids]
                                print(f"[GET Login User Menus]     - Menu IDs (converted to strings): {menu_ids_str}")

                                # If access contains 'disable', mark these menus as disabled
                                if 'disable' in access_list:
                                    disabled_menu_ids.update(menu_ids_str)
                                    print(f"[GET Login User Menus]     - ❌ Marked as disabled")
                                else:
                                    # Add to accessible menus if they have read or write access
                                    if 'read' in access_list or 'write' in access_list:
                                        accessible_menu_ids.update(menu_ids_str)
                                        print(f"[GET Login User Menus]     - ✅ Added to accessible menus")

                # Remove disabled menus from accessible set
                accessible_menu_ids -= disabled_menu_ids
                
                # Only set has_permissions to True if we actually found accessible menu IDs
                if accessible_menu_ids:
                    has_permissions = True
                    print(f"[GET Login User Menus] ✅ User has permissions for {len(accessible_menu_ids)} menus")
                else:
                    print(f"[GET Login User Menus] ⚠️ No accessible menu IDs found (all disabled or no valid permissions)")
                    print(f"[GET Login User Menus] 📊 Will return all menus (no valid permissions)")

                print(f"[GET Login User Menus] 📊 Total accessible menu IDs: {len(accessible_menu_ids)}")
                print(f"[GET Login User Menus] 📊 Accessible menu IDs: {accessible_menu_ids}")
                print(f"[GET Login User Menus] 📊 Disabled menu IDs: {disabled_menu_ids}")

                # ⚠️ DESCENDANT EXPANSION DISABLED
                # Previously, this code expanded accessible_menu_ids to include ALL descendants
                # This caused issues where if a parent menu was accessible, ALL its children were included
                # even if they didn't have explicit permissions.
                # 
                # For level 3 menu filtering, we only want to show menus that have explicit permissions
                # in the menu_permissions JSONB field, not auto-include all siblings.
                #
                # If you need to re-enable descendant expansion for nested menus (level 4+), 
                # uncomment the code below and adjust the logic to only expand for specific levels.
                
                # expanded_menu_ids = set(accessible_menu_ids)
                # def get_all_descendants(parent_ids: set) -> set:
                #     if not parent_ids:
                #         return set()
                #     children = db.query(Menu).filter(
                #         and_(
                #             Menu.parent_menu_id.in_(parent_ids),
                #             Menu.is_active == True,
                #             Menu.deleted_at.is_(None)
                #         )
                #     ).all()
                #     if not children:
                #         return set()
                #     child_ids = {str(child.id) for child in children}
                #     grandchild_ids = get_all_descendants(child_ids)
                #     return child_ids | grandchild_ids
                # descendant_ids = get_all_descendants(accessible_menu_ids)
                # expanded_menu_ids.update(descendant_ids)
                # expanded_menu_ids -= disabled_menu_ids
                # accessible_menu_ids = expanded_menu_ids
                
                print(f"[GET Login User Menus] ✅ Using explicit permissions only (no descendant expansion)")

        # 5. Fetch the full mainNavigation structure from MongoDB
        print(f"[GET Login User Menus] 🔍 Connecting to MongoDB...")
        db_mongo = get_mongodb()
        if db_mongo is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="MongoDB not available"
            )

        print(f"[GET Login User Menus] ✅ MongoDB connected")

        master_doc_id = ObjectId("69074724f217ab8fcb2e3b24")
        print(f"[GET Login User Menus] 🔍 Fetching master navigation document: {master_doc_id}")
        master_doc = await db_mongo.menu_details.find_one({"_id": master_doc_id})

        if not master_doc:
            print(f"[GET Login User Menus] ❌ Master navigation document not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Master navigation document not found"
            )

        print(f"[GET Login User Menus] ✅ Master document found")

        # 6. Get the mainNavigation array (contains ObjectId references)
        main_nav_refs = master_doc.get("mainNavigation", [])
        print(f"[GET Login User Menus] 📊 Master document has {len(main_nav_refs)} navigation references")
        print(f"[GET Login User Menus] 📊 Accessible menu IDs ({len(accessible_menu_ids)}): {sorted(list(accessible_menu_ids))[:20]}...")  # Show first 20

        # 6a. Fetch actual application documents from MongoDB by ObjectId
        main_nav_items = []
        
        for idx, app_ref in enumerate(main_nav_refs):
            print(f"[GET Login User Menus] 🔍 Fetching application document {idx + 1}/{len(main_nav_refs)}")
            print(f"[GET Login User Menus]   - Type: {type(app_ref)}, Value: {app_ref}")
            
            # Handle both ObjectId objects and string representations
            if isinstance(app_ref, ObjectId) or isinstance(app_ref, str):
                try:
                    # Convert to ObjectId if it's a string
                    if isinstance(app_ref, str):
                        app_doc_id = ObjectId(app_ref)
                    else:
                        app_doc_id = app_ref
                    
                    print(f"[GET Login User Menus]   - Fetching document with ObjectId: {app_doc_id}")
                    
                    app_doc = await db_mongo.menu_details.find_one({"_id": app_doc_id})
                    
                    if app_doc:
                        print(f"[GET Login User Menus]   - ✅ Document found!")
                        print(f"[GET Login User Menus]   - Keys: {list(app_doc.keys())}")
                        
                        # Don't remove _id yet, we might need it for filtering
                        main_nav_items.append(app_doc)
                        app_name = app_doc.get("label", "Unknown")
                        children_count = len(app_doc.get("children", []))
                        print(f"[GET Login User Menus]   - {app_name} - {children_count} menus")
                    else:
                        print(f"[GET Login User Menus]   - ⚠️ Application document not found: {app_ref}")
                except Exception as e:
                    print(f"[GET Login User Menus]   - ⚠️ Error fetching application {app_ref}: {str(e)}")
                    import traceback
                    traceback.print_exc()
            elif isinstance(app_ref, dict):
                # It's already an inline object (backward compatibility)
                print(f"[GET Login User Menus]   - ✅ Inline object found (backward compatibility)")
                main_nav_items.append(app_ref)
            else:
                print(f"[GET Login User Menus]   - ⚠️ Invalid item type: {type(app_ref)}")

        print(f"[GET Login User Menus] 📊 Fetched {len(main_nav_items)} application documents")

        # 7. Filter the navigation items by permissions
        filtered_navigation = []

        for idx, nav_item in enumerate(main_nav_items):
            print(f"[GET Login User Menus] 🔍 Processing navigation item {idx + 1}/{len(main_nav_items)}")

            if not isinstance(nav_item, dict):
                print(f"[GET Login User Menus]   - ⚠️ Not a dict, skipping")
                continue

            menu_label = nav_item.get("label", "Unknown")
            menu_id = nav_item.get("menu_id")

            print(f"[GET Login User Menus]   - Label: {menu_label}")
            print(f"[GET Login User Menus]   - menu_id: {menu_id}")
            print(f"[GET Login User Menus]   - Has {len(nav_item.get('children', []))} children")

            try:
                # If user is admin OR has no permissions, return all menus without filtering
                if is_admin_user or not has_permissions:
                    if is_admin_user:
                        print(f"[GET Login User Menus]   - 👑 Admin user - including all menus")
                    else:
                        print(f"[GET Login User Menus]   - ✅ No permissions - including all menus")
                    
                    # Convert ObjectId to string for JSON serialization if present
                    if "_id" in nav_item:
                        nav_item["_id"] = str(nav_item["_id"])
                    # Remove MongoDB-specific fields for clean response
                    nav_item.pop("created_at", None)
                    nav_item.pop("updated_at", None)
                    nav_item.pop("is_active", None)
                    
                    filtered_navigation.append(nav_item)
                    print(f"[GET Login User Menus]   - ✅ Included menu: {menu_label}")
                else:
                    # Filter the menu item based on user permissions
                    filtered_menu = await _filter_menu_by_permissions(
                        nav_item,
                        accessible_menu_ids,
                        db
                    )

                    if filtered_menu:
                        # Convert ObjectId to string for JSON serialization if present
                        if "_id" in filtered_menu:
                            filtered_menu["_id"] = str(filtered_menu["_id"])
                        # Remove MongoDB-specific fields for clean response
                        filtered_menu.pop("created_at", None)
                        filtered_menu.pop("updated_at", None)
                        filtered_menu.pop("is_active", None)
                        
                        filtered_navigation.append(filtered_menu)
                        print(f"[GET Login User Menus]   - ✅ Included menu: {menu_label}")
                    else:
                        print(f"[GET Login User Menus]   - ⚠️ Menu filtered out (no accessible children): {menu_label}")

            except Exception as e:
                print(f"[GET Login User Menus]   - ❌ Error processing menu: {str(e)}")
                import traceback
                traceback.print_exc()
                continue

        # 8. Get profileSection and config from master document
        profile_section = master_doc.get("profileSection", {})
        config = master_doc.get("config", {})
        
        # 8b. Populate profileSection with logged-in user's data dynamically
        try:
            from app.menu_details.services.menu_details import menu_details_service
            profile_section = menu_details_service.populate_profile_section_with_user_data(
                profile_section, user, db
            )
        except Exception as e:
            print(f"[GET Login User Menus] ⚠️ Error populating profile section with user data: {str(e)}")
            import traceback
            traceback.print_exc()

        # 8a. Ensure userData fields are simple strings (not {value, color} objects)
        if profile_section and "userData" in profile_section:
            user_data = profile_section["userData"]
            cleaned_user_data = {}
            
            for key, value in user_data.items():
                # If value is a dict with 'value' key, extract the value
                if isinstance(value, dict) and 'value' in value:
                    cleaned_user_data[key] = value['value']
                    print(f"[GET Login User Menus] 🔧 Cleaned userData.{key}: {value} → {value['value']}")
                else:
                    # Keep as is if it's already a simple value
                    cleaned_user_data[key] = value
            
            profile_section["userData"] = cleaned_user_data

        print(f"[GET Login User Menus] 📊 Profile section items: {len(profile_section.get('items', []))}")
        print(f"[GET Login User Menus] 📊 Config version: {config.get('version', 'N/A')}")

        # 9. Apply translations if lang_code is provided
        if lang_code:
            print(f"[GET Login User Menus] 🌐 Applying translations for lang_code: {lang_code}")
            translation_map = get_menu_translations(db, lang_code)
            if translation_map:
                print(f"[GET Login User Menus] 📚 Found {len(translation_map)} translations")
                filtered_navigation = apply_translations_to_navigation(filtered_navigation, translation_map)
                print(f"[GET Login User Menus] ✅ Translations applied")
            else:
                print(f"[GET Login User Menus] ⚠️ No translations found for lang_code: {lang_code}")

        # 10. Return the filtered navigation structure with profile and config
        response_data = {
            "_id": str(master_doc_id),
            "mainNavigation": filtered_navigation,
            "profileSection": profile_section,
            "config": config
        }

        # Cache the result for configured TTL (default 5 minutes)
        try:
            redis_cache.set(cache_key, response_data, ttl=settings.CACHE_DEFAULT_TTL)
        except Exception as e:
            print(f"[GET Login User Menus] ⚠️ Failed to cache response: {str(e)}")
            # Continue even if caching fails

        print(f"[GET Login User Menus] ✅ Returning {len(filtered_navigation)} filtered menu structures")
        print(f"[GET Login User Menus] ✅ Response includes profileSection and config")
        return response_data

    except HTTPException:
        # Re-raise HTTP exceptions (401, 404, etc.)
        raise
    except Exception as e:
        # Catch all other exceptions and return 500 with details
        print(f"[GET Login User Menus] ❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )


async def _filter_menu_by_permissions(
    menu_doc: Dict[str, Any],
    accessible_menu_ids: set,
    db: Session,
    depth: int = 0
) -> Optional[Dict[str, Any]]:
    """
    Recursively filter menu structure based on accessible menu IDs.

    Args:
        menu_doc: Menu document from MongoDB
        accessible_menu_ids: Set of menu IDs (as strings) the user can access
        db: Database session
        depth: Current recursion depth (for logging)

    Returns:
        Filtered menu document or None if no accessible children
    """
    import copy

    indent = "  " * depth
    menu_label = menu_doc.get("label", "Unknown")
    menu_id = menu_doc.get("menu_id")

    print(f"[Filter Menu] {indent}🔍 Filtering menu: {menu_label}")
    print(f"[Filter Menu] {indent}  - menu_id: {menu_id}")
    print(f"[Filter Menu] {indent}  - Is menu_id in accessible set? {menu_id in accessible_menu_ids if menu_id else 'N/A (no menu_id)'}")

    # Create a shallow copy to avoid mutating the original MongoDB document
    result = dict(menu_doc)

    # If this menu has children, filter them recursively
    children = menu_doc.get("children", [])
    print(f"[Filter Menu] {indent}  - Has {len(children)} children")
    filtered_children = []

    for idx, child in enumerate(children):
        if isinstance(child, dict):
            child_label = child.get("label", child.get("key", "Unknown"))
            child_menu_id = child.get("menu_id")
            child_key = child.get("key")

            print(f"[Filter Menu] {indent}  - Child {idx + 1}: {child_label}")
            print(f"[Filter Menu] {indent}    - child_menu_id: {child_menu_id}")
            print(f"[Filter Menu] {indent}    - child_key: {child_key}")

            # Try to find the menu in PostgreSQL by key or menu_id
            child_accessible = False

            if child_menu_id and child_menu_id in accessible_menu_ids:
                child_accessible = True
                print(f"[Filter Menu] {indent}    - ✅ Accessible (menu_id {child_menu_id} in set)")
            elif child_key:
                # Look up menu by name (key) in PostgreSQL
                menu = db.query(Menu).filter(
                    Menu.name == child_key,
                    Menu.is_active == True,
                    Menu.deleted_at.is_(None)
                ).first()

                if menu:
                    menu_id_str = str(menu.id)
                    print(f"[Filter Menu] {indent}    - Found in PostgreSQL: {menu_id_str}")
                    print(f"[Filter Menu] {indent}    - Checking if {menu_id_str} in accessible_menu_ids...")
                    if menu_id_str in accessible_menu_ids:
                        child_accessible = True
                        child["menu_id"] = menu_id_str
                        print(f"[Filter Menu] {indent}    - ✅ Accessible (found in PostgreSQL and in accessible set)")
                    else:
                        print(f"[Filter Menu] {indent}    - ❌ Not accessible (PostgreSQL ID {menu_id_str} NOT in accessible set)")
                else:
                    print(f"[Filter Menu] {indent}    - ⚠️ Not found in PostgreSQL with key '{child_key}'")

            # Recursively filter child's children if they exist
            child_has_children = child.get("children") is not None and len(child.get("children", [])) > 0

            if child_has_children:
                print(f"[Filter Menu] {indent}    - Has {len(child.get('children', []))} children, recursing...")
                filtered_child = await _filter_menu_by_permissions(child, accessible_menu_ids, db, depth + 2)
                if filtered_child:
                    # Child has accessible nested children, include it
                    filtered_children.append(filtered_child)
                    print(f"[Filter Menu] {indent}    - ✅ Included (has accessible nested children)")
                elif child_accessible:
                    # Child itself is accessible even though nested children were filtered out
                    # Include it with its original children preserved
                    filtered_children.append(child)
                    print(f"[Filter Menu] {indent}    - ✅ Included (accessible, preserving original children)")
                else:
                    print(f"[Filter Menu] {indent}    - ❌ Excluded (not accessible and no accessible nested children)")
            elif child_accessible:
                # Leaf node that is accessible (no children)
                filtered_children.append(child)
                print(f"[Filter Menu] {indent}    - ✅ Included (leaf node, accessible)")
            else:
                print(f"[Filter Menu] {indent}    - ❌ Excluded (leaf node, not accessible)")

    # If this menu or any of its children are accessible, include it
    if menu_id and menu_id in accessible_menu_ids:
        # This menu itself is accessible, but we still need to filter its children
        # based on permissions (don't include all children blindly)
        print(f"[Filter Menu] {indent}✅ Menu '{menu_label}' is accessible (menu_id in set)")
        
        # Use the already filtered children instead of including all children
        if filtered_children:
            result["children"] = filtered_children
            print(f"[Filter Menu] {indent}✅ Including menu '{menu_label}' with {len(filtered_children)} filtered children")
        else:
            # No accessible children, but the menu itself is accessible
            result["children"] = []
            print(f"[Filter Menu] {indent}✅ Including menu '{menu_label}' with no accessible children")
        
        return result
    elif filtered_children:
        # This menu is not directly accessible, but has accessible children
        result["children"] = filtered_children
        print(f"[Filter Menu] {indent}✅ Including menu '{menu_label}' (has {len(filtered_children)} accessible children)")
        return result
    else:
        # Neither this menu nor its children are accessible
        print(f"[Filter Menu] {indent}❌ Excluding menu '{menu_label}' (not accessible and no accessible children)")
        return None





@router.get("/by-module/{module_id}")
async def get_menus_by_module(
    request: Request,
    module_id: uuid.UUID,
    include_inactive: bool = Query(False, description="Include inactive menus in the response"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get all menus belonging to a specific module (Level 2 in hierarchy).

    Returns menus from PostgreSQL organized in parent → children hierarchy:
    - Level 3: Menus directly under the module
    - Level 4+: Nested child menus under their parent menu

    Parameters:
    - module_id: UUID of the module
    - include_inactive: Include inactive menus (default: False). Soft-deleted menus are always excluded.
    """
    print(f"[GET Menus By Module] 🚀 Fetching menus for module: {module_id}")

    # Validate module exists
    module = db.query(Module).filter(
        Module.id == module_id,
        Module.is_deleted == False
    ).first()

    if not module:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Module not found: {module_id}"
        )

    print(f"[GET Menus By Module] ✅ Module found: {module.name}")

    # Fetch all menus for this module (soft-deleted always excluded)
    filters = [
        Menu.module_id == module_id,
        Menu.deleted_at.is_(None)
    ]
    if not include_inactive:
        filters.append(Menu.is_active == True)

    menus = db.query(Menu).filter(and_(*filters)).order_by(Menu.level, Menu.order_index).all()
    print(f"[GET Menus By Module] ✅ Found {len(menus)} menus for module: {module.name}")

    def serialize_menu(menu: Menu) -> Dict[str, Any]:
        return {
            "id": str(menu.id),
            "application_id": str(menu.application_id) if menu.application_id else None,
            "module_id": str(menu.module_id) if menu.module_id else None,
            "parent_menu_id": str(menu.parent_menu_id) if menu.parent_menu_id else None,
            "name": menu.name,
            "label": menu.label,
            "key": menu.key,
            "icon": menu.icon,
            "route": menu.route,
            "component": menu.component,
            "badge": menu.badge,
            "section_title": menu.section_title,
            "description": menu.menus_description,
            "order_index": menu.order_index,
            "level": menu.level,
            "is_visible": menu.is_visible,
            "is_active": menu.is_active,
            "showtopbar": menu.showtopbar,
            "showsidebar": menu.showsidebar,
            "access": menu.access if menu.access else ["read"],
            "menu_metadata": menu.menu_metadata,
            "created_at": menu.created_at.isoformat() if menu.created_at else None,
            "updated_at": menu.updated_at.isoformat() if menu.updated_at else None,
            "children": []
        }

    # Build parent → children hierarchy (menus are already ordered by level, order_index)
    menu_map = {str(menu.id): serialize_menu(menu) for menu in menus}
    root_menus = []

    for menu_dict in menu_map.values():
        parent_id = menu_dict["parent_menu_id"]
        if parent_id and parent_id in menu_map:
            menu_map[parent_id]["children"].append(menu_dict)
        else:
            root_menus.append(menu_dict)

    try:
        client_id_audit, entity_id_audit = get_audit_org_context(db, get_user_id(current_user))
        fire_audit_log(
            action="READ",
            object_type="Menu",
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

    print(f"[GET Menus By Module] ✅ Returning {len(root_menus)} root menus ({len(menus)} total)")
    return {
        "module_id": str(module.id),
        "module_name": module.name,
        "module_label": module.label,
        "application_id": str(module.application_id) if module.application_id else None,
        "total_menus": len(menus),
        "menus": root_menus
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_menu(
    request: Request,
    menu_data: Union[MenuCreate, MenuBatchCreate],
    nav_doc_id: Optional[str] = Query("69074724f217ab8fcb2e3b24", description="Mongo navigation doc ObjectId (defaults to known id)"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Create menu(s) with structured hierarchy support: Applications -> Modules -> Menus -> Nested Menus
    
    **Single Menu with Module:**
    ```json
    {
      "application_id": "uuid",
      "module_id": "uuid",
      "name": "menu-key",
      "label": "Menu Label",
      "level": 3,
      "children": [...]
    }
    ```
    
    **Batch (Multiple Parents with Modules):**
    ```json
    {
      "application_id": "uuid",
      "module_id": "uuid", 
      "menus": [
        {"name": "menu1", "label": "Menu 1", "level": 3, "children": [...]},
        {"name": "menu2", "label": "Menu 2", "level": 3, "children": [...]}
      ]
    }
    ```
    
    **Hierarchy Levels:**
    - Level 1: Applications (root level)
    - Level 2: Modules (functional groupings)
    - Level 3: Menus (individual menu items)
    - Level 4: Nested Menus (sub-menus)
    """
    
    # Detect if this is batch or single
    if isinstance(menu_data, MenuBatchCreate):
        print(f"[Menu Create] 🚀 Batch creation: {len(menu_data.menus)} parent menus")
        return await create_menus_batch_structured(menu_data, nav_doc_id, db, current_user)
    else:
        print(f"[Menu Create] 🚀 Single menu creation")
        return await create_single_menu_structured(menu_data, nav_doc_id, db, current_user, request)


async def create_single_menu_structured(
    menu_data: MenuCreate,
    nav_doc_id: str,
    db: Session,
    current_user,
    request: Optional[Request] = None
) -> MenuResponse:
    """
    Create a single menu with structured hierarchy support
    """
    try:
        print(f"[Menu Create Structured] 🚀 Starting structured menu creation")
        print(f"[Menu Create Structured] Menu: {menu_data.name}, App: {menu_data.application_id}, Module: {menu_data.module_id}")
    except Exception as e:
        print(f"[Menu Create Structured] ❌ Error in initial validation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Menu creation failed during validation: {str(e)}"
        )
    
    # Convert to dict for processing
    create_data = menu_data.dict(by_alias=False, exclude_unset=False)
    
    # Handle access permissions
    if 'access' in create_data and create_data['access'] is not None:
        if isinstance(create_data['access'], str):
            create_data['access'] = [create_data['access'].lower()]
        elif isinstance(create_data['access'], list):
            create_data['access'] = [item.lower() if isinstance(item, str) else item for item in create_data['access']]

    children_payload = create_data.pop('children', [])
    if not create_data.get('label'):
        create_data['label'] = create_data['name']

    # Validate application exists
    if not create_data.get('application_id'):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="application_id is required")

    app_exists = db.execute(
        text("SELECT 1 FROM applications WHERE id = :id"),
        {"id": str(create_data['application_id'])}
    ).scalar()
    if not app_exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    # Validate module exists if module_id is provided
    if create_data.get('module_id'):
        module_exists = db.execute(
            text("SELECT 1 FROM modules WHERE id = :id"),
            {"id": str(create_data['module_id'])}
        ).scalar()
        if not module_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")

    # Set hierarchy level based on structure
    if create_data.get('module_id'):
        # Menu belongs to a module (Level 3: Menus)
        if not create_data.get('level'):
            create_data['level'] = 3
        print(f"[Menu Create Structured] 📊 Module-based menu, level: {create_data['level']}")
    else:
        # Direct application menu (Level 2: Module-level or legacy)
        if not create_data.get('level'):
            create_data['level'] = 2
        print(f"[Menu Create Structured] 📊 Direct application menu, level: {create_data['level']}")

    # Auto-calculate order_index based on siblings
    if create_data.get('parent_menu_id'):
        # Child menu - find siblings with same parent
        parent_menu = db.query(Menu).filter(Menu.id == create_data['parent_menu_id']).first()
        if not parent_menu:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent menu not found")
        
        create_data['level'] = parent_menu.level + 1
        
        max_order = db.query(func.max(Menu.order_index)).filter(
            Menu.parent_menu_id == create_data['parent_menu_id'],
            Menu.application_id == create_data['application_id'],
            Menu.deleted_at.is_(None)
        ).scalar() or 0
        
        create_data['order_index'] = max_order + 1000
        print(f"[Menu Create Structured] 📊 Child menu - Level: {create_data['level']}, Order: {create_data['order_index']}")
    else:
        # Root level menu - find siblings in same module/application
        if create_data.get('module_id'):
            # Find siblings in same module
            max_order = db.query(func.max(Menu.order_index)).filter(
                Menu.module_id == create_data['module_id'],
                Menu.parent_menu_id.is_(None),
                Menu.deleted_at.is_(None)
            ).scalar() or 0
        else:
            # Find siblings in same application (no module)
            max_order = db.query(func.max(Menu.order_index)).filter(
                Menu.application_id == create_data['application_id'],
                Menu.module_id.is_(None),
                Menu.parent_menu_id.is_(None),
                Menu.deleted_at.is_(None)
            ).scalar() or 0
        
        create_data['order_index'] = max_order + 1000
        print(f"[Menu Create Structured] 📊 Root menu - Level: {create_data['level']}, Order: {create_data['order_index']}")

    # Handle field mappings
    if 'description' in create_data:
        create_data['menus_description'] = create_data.pop('description')
    
    # Set defaults for optional fields
    if 'key' not in create_data or create_data['key'] is None:
        create_data['key'] = create_data['name']
    
    for field in ['badge', 'section_title', 'mongo_id', 'component', 'icon', 'menu_metadata']:
        if field not in create_data:
            create_data[field] = None if field != 'menu_metadata' else {}

    # Create menu in PostgreSQL
    menu = Menu(**create_data)
    db.add(menu)
    db.commit()
    db.refresh(menu)

    print(f"[Menu Create Structured] ✅ Created menu in PostgreSQL: {menu.id}")

    try:
        _uid = get_user_id(current_user)
        _cid, _eid = get_audit_org_context(db, _uid)
        fire_audit_log(
            action="CREATE", object_type="Menu",
            object_id=str(menu.id),
            user_id=_uid, client_id=_cid, entity_id=_eid,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request) if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
            risk_score=RISK_SCORE["CREATE"],
            new_values={"name": menu.name, "label": menu.label, "application_id": str(menu.application_id)},
        )
    except Exception:
        pass

    # Process children recursively
    processed_children = await process_children_recursive_structured(
        menu.id, children_payload, menu.level, menu.application_id, menu.module_id, db
    )
    
    if processed_children:
        db.commit()
        print(f"[Menu Create Structured] ✅ Processed {len(processed_children)} children")

    # ✅ USE WORKING SYNC: Use working_sync_to_mongodb instead of broken MenuReorderService
    print(f"[Menu Create Structured] 🔄 Syncing to MongoDB using working sync function...")
    print(f"[Menu Create Structured] Application ID: {menu.application_id}")
    
    # Check MongoDB connection first
    from app.core.mongodb import mongodb
    print(f"[Menu Create Structured] MongoDB enabled: {mongodb.enabled}")
    print(f"[Menu Create Structured] MongoDB connected: {mongodb.is_connected()}")
    
    if not mongodb.enabled:
        print(f"[Menu Create Structured] ⚠️ MongoDB is disabled - skipping sync")
    elif not mongodb.is_connected():
        print(f"[Menu Create Structured] ⚠️ MongoDB not connected - attempting to connect...")
        try:
            connect_result = await mongodb.connect()
            print(f"[Menu Create Structured] MongoDB connection result: {connect_result}")
        except Exception as conn_error:
            print(f"[Menu Create Structured] ❌ Failed to connect to MongoDB: {conn_error}")
    
    try:
        sync_success = await working_sync_to_mongodb(db, menu.application_id)
        
        if sync_success:
            print(f"[Menu Create Structured] ✅ MongoDB sync completed successfully")
            print(f"[Menu Create Structured] ✅ Menu synced to mainNavigation in MongoDB")
        else:
            print(f"[Menu Create Structured] ⚠️ MongoDB sync failed, but menu created in PostgreSQL")
            logger.warning(f"Menu {menu.id} created in PostgreSQL but MongoDB sync failed for application {menu.application_id}")
            # Don't fail the request if MongoDB sync fails - menu is still created in PostgreSQL
            
    except Exception as sync_error:
        print(f"[Menu Create Structured] ❌ MongoDB sync error: {sync_error}")
        print(f"[Menu Create Structured] ⚠️ Menu created in PostgreSQL but not synced to MongoDB")
        logger.error(f"MongoDB sync error for menu {menu.id}: {sync_error}")
        # Log the error but don't fail the request
        import traceback
        traceback.print_exc()

    # Build response
    response_dict = build_menu_response(menu, processed_children)
    
    print(f"[Menu Create Structured] ✅ Menu creation completed successfully!")
    
    return MenuResponse(**response_dict)


async def process_children_recursive_structured(
    parent_id: UUID,
    children_list: List[Dict[str, Any]],
    parent_level: int,
    application_id: UUID,
    module_id: Optional[UUID],
    db: Session
) -> List[Dict[str, Any]]:
    """
    Process children menus with structured hierarchy support
    """
    processed_children = []
    
    if not children_list or not isinstance(children_list, list):
        return processed_children
    
    for child_data in children_list:
        if not isinstance(child_data, dict):
            continue
        
        # Prepare child menu data
        child_menu_data = {
            'application_id': application_id,
            'module_id': module_id,  # Inherit module from parent
            'name': child_data.get('name') or child_data.get('key'),
            'key': child_data.get('key') or child_data.get('name'),
            'label': child_data.get('label') or child_data.get('name'),
            'route': child_data.get('route'),
            'icon': child_data.get('icon'),
            'component': child_data.get('component'),
            'order_index': child_data.get('order_index', 1000),
            'level': child_data.get('level', parent_level + 1),
            'is_visible': child_data.get('is_visible', True),
            'is_active': child_data.get('is_active', True),
            'parent_menu_id': parent_id,
            'menu_metadata': child_data.get('menu_metadata', {}),
            'badge': child_data.get('badge'),
            'section_title': child_data.get('section_title', ''),
            'menus_description': child_data.get('menus_description', ''),
            'access': child_data.get('access', ['read']),
            'showtopbar': child_data.get('showtopbar', True),
            'showsidebar': child_data.get('showsidebar', True)
        }
        
        # Create child menu
        child_menu = Menu(**child_menu_data)
        db.add(child_menu)
        db.flush()
        
        print(f"[Menu Create Structured]   - Created child: {child_menu.label} (Level: {child_menu.level})")
        
        # Process grandchildren
        grandchildren = child_data.get('children', [])
        processed_grandchildren = await process_children_recursive_structured(
            child_menu.id, grandchildren, child_menu.level, application_id, module_id, db
        )
        
        # Build child item structure
        child_item = {
            "key": child_menu.key or child_menu.name,
            "label": child_menu.label,
            "icon": child_menu.icon,
            "description": child_menu.menus_description,
            "badge": child_menu.badge,
            "section_title": child_menu.section_title or "",
            "sectionTitle": child_menu.section_title or "",
            "route": child_menu.route,
            "component": child_menu.component,
            "menu_id": str(child_menu.id),
            "module_id": str(child_menu.module_id) if child_menu.module_id else None,
            "level": child_menu.level,
            "order_index": child_menu.order_index,
            "showtopbar": child_menu.showtopbar,
            "showsidebar": child_menu.showsidebar,
            "children": processed_grandchildren
        }
        
        processed_children.append(child_item)
    
    return processed_children


async def update_mongodb_structured_hierarchy(
    menu: Menu,
    processed_children: List[Dict[str, Any]],
    nav_doc_id: str,
    db: Session
):
    """
    Update MongoDB with structured hierarchy: Applications -> Modules -> Menus -> Nested Menus
    Structure: Root Application -> children[Modules] -> children[Menus] -> children[Nested Menus]
    """
    try:
        db_mongo = get_mongodb()
        if db_mongo is None:
            raise RuntimeError("MongoDB database not initialized")

        nav_doc_object_id = ObjectId(nav_doc_id or "69074724f217ab8fcb2e3b24")
        
        # Get application details
        application = db.query(Application).filter(Application.id == menu.application_id).first()
        if not application:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

        # Get module details if module_id exists
        module = None
        if menu.module_id:
            module = db.query(Module).filter(Module.id == menu.module_id).first()

        # Create menu item structure (Level 3)
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
            "module_id": str(menu.module_id) if menu.module_id else None,
            "level": 3,
            "order_index": menu.order_index,
            "showtopbar": menu.showtopbar if hasattr(menu, 'showtopbar') else True,
            "showsidebar": menu.showsidebar if hasattr(menu, 'showsidebar') else True,
            "children": processed_children  # Level 4: Nested Menus
        }

        # Check if application document exists
        app_doc = await db_mongo.menu_details.find_one({
            "application_id": str(menu.application_id),
            "_id": {"$ne": nav_doc_object_id}
        })

        if not app_doc:
            # Create new application document with module structure
            print(f"[MongoDB Structured] Creating new application document for: {application.name}")
            
            # Create module structure if module exists
            if module:
                module_item = {
                    "_id": str(module.id) if hasattr(module, 'id') else None,
                    "key": module.name.lower().replace(" ", "-") if hasattr(module, 'name') else "default-module",
                    "label": module.name if hasattr(module, 'name') else "Default Module",
                    "icon": getattr(module, 'icon', 'ri-folder-line'),
                    "description": getattr(module, 'description', ''),
                    "badge": getattr(module, 'badge', None),
                    "sectionTitle": getattr(module, 'section_title', ''),
                    "route": getattr(module, 'route', ''),
                    "component": getattr(module, 'component', ''),
                    "module_id": str(menu.module_id),
                    "level": 2,
                    "order_index": getattr(module, 'order_index', 1000),
                    "showtopbar": getattr(module, 'showtopbar', True),
                    "showsidebar": getattr(module, 'showsidebar', True),
                    "children": [menu_item]  # Menus go in module's children array
                }
                app_children = [module_item]
            else:
                # Create default module for menus without module_id
                default_module = {
                    "_id": None,
                    "key": "default-module",
                    "label": "Default Module",
                    "icon": "ri-folder-line",
                    "description": "Default module for menus without specific module",
                    "badge": None,
                    "sectionTitle": "Default",
                    "route": "",
                    "component": "",
                    "module_id": "default",
                    "level": 2,
                    "order_index": 9999,
                    "showtopbar": True,
                    "showsidebar": True,
                    "children": [menu_item]  # Menus go in module's children array
                }
                app_children = [default_module]
            
            new_app_doc = {
                "key": application.name.lower().replace(" ", "-"),
                "label": application.name,
                "icon": menu.icon or "ri-apps-line",
                "description": application.description or f"Manage {application.name}",
                "badge": None,
                "sectionTitle": application.name,
                "route": f"/{application.name.lower().replace(' ', '-')}",
                "application_id": str(application.id),
                "level": 1,
                "order_index": 1000,
                "showtopbar": True,
                "showsidebar": True,
                "children": app_children,  # Modules go in application's children array
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }

            app_result = await db_mongo.menu_details.insert_one(new_app_doc)
            app_object_id = app_result.inserted_id
            
            # Store application document ObjectId in menu
            menu.mongo_id = str(app_object_id)
            db.commit()
            
            print(f"[MongoDB Structured] ✅ Created application document: {app_object_id}")

            # Add to mainNavigation array
            await db_mongo.menu_details.update_one(
                {"_id": nav_doc_object_id},
                {"$addToSet": {"mainNavigation": app_object_id}}
            )
            
            print(f"[MongoDB Structured] ✅ Added to mainNavigation array")
        else:
            # Application document exists - add menu to appropriate module
            app_object_id = app_doc["_id"]
            menu.mongo_id = str(app_object_id)
            db.commit()
            
            if menu.module_id:
                # Find or create module in application's children array
                module_found = False
                app_children = app_doc.get("children", [])
                
                for idx, child in enumerate(app_children):
                    if child.get("module_id") == str(menu.module_id):
                        # Module exists - add menu to its children array
                        module_found = True
                        await db_mongo.menu_details.update_one(
                            {"_id": app_object_id},
                            {
                                "$push": {f"children.{idx}.children": menu_item},
                                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                            }
                        )
                        print(f"[MongoDB Structured] ✅ Added menu to existing module")
                        break
                
                if not module_found:
                    # Module doesn't exist - create new module with this menu
                    if module:
                        module_item = {
                            "_id": str(module.id) if hasattr(module, 'id') else None,
                            "key": module.name.lower().replace(" ", "-") if hasattr(module, 'name') else "new-module",
                            "label": module.name if hasattr(module, 'name') else "New Module",
                            "icon": getattr(module, 'icon', 'ri-folder-line'),
                            "description": getattr(module, 'description', ''),
                            "badge": getattr(module, 'badge', None),
                            "sectionTitle": getattr(module, 'section_title', ''),
                            "route": getattr(module, 'route', ''),
                            "component": getattr(module, 'component', ''),
                            "module_id": str(menu.module_id),
                            "level": 2,
                            "order_index": getattr(module, 'order_index', 1000),
                            "showtopbar": getattr(module, 'showtopbar', True),
                            "showsidebar": getattr(module, 'showsidebar', True),
                            "children": [menu_item]
                        }
                    else:
                        # Create generic module structure
                        module_item = {
                            "_id": str(menu.module_id),
                            "key": f"module-{str(menu.module_id)[:8]}",
                            "label": "Module",
                            "icon": "ri-folder-line",
                            "description": "Module description",
                            "badge": None,
                            "sectionTitle": "Module",
                            "route": "",
                            "component": "",
                            "module_id": str(menu.module_id),
                            "level": 2,
                            "order_index": 1000,
                            "showtopbar": True,
                            "showsidebar": True,
                            "children": [menu_item]
                        }
                    
                    await db_mongo.menu_details.update_one(
                        {"_id": app_object_id},
                        {
                            "$push": {"children": module_item},
                            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                        }
                    )
                    print(f"[MongoDB Structured] ✅ Created new module and added menu")
            else:
                # No module_id - add to default module
                default_module_found = False
                app_children = app_doc.get("children", [])
                
                for idx, child in enumerate(app_children):
                    if child.get("module_id") == "default":
                        # Default module exists - add menu to it
                        default_module_found = True
                        await db_mongo.menu_details.update_one(
                            {"_id": app_object_id},
                            {
                                "$push": {f"children.{idx}.children": menu_item},
                                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                            }
                        )
                        print(f"[MongoDB Structured] ✅ Added menu to default module")
                        break
                
                if not default_module_found:
                    # Create default module
                    default_module = {
                        "_id": None,
                        "key": "default-module",
                        "label": "Default Module",
                        "icon": "ri-folder-line",
                        "description": "Default module for menus without specific module",
                        "badge": None,
                        "sectionTitle": "Default",
                        "route": "",
                        "component": "",
                        "module_id": "default",
                        "level": 2,
                        "order_index": 9999,
                        "showtopbar": True,
                        "showsidebar": True,
                        "children": [menu_item]
                    }
                    
                    await db_mongo.menu_details.update_one(
                        {"_id": app_object_id},
                        {
                            "$push": {"children": default_module},
                            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                        }
                    )
                    print(f"[MongoDB Structured] ✅ Created default module and added menu")
            
    except Exception as e:
        print(f"[MongoDB Structured] ⚠️ Failed to update MongoDB: {e}")
        import traceback
        traceback.print_exc()


def find_parent_path_in_doc(items: List[Dict[str, Any]], parent_menu_id: str, current_path: str = "children") -> Optional[str]:
    """Find the MongoDB path to parent menu's children array"""
    if not isinstance(items, list):
        return None
    
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        
        if item.get("menu_id") == parent_menu_id:
            return f"{current_path}.{idx}.children"
        
        if "children" in item and isinstance(item["children"], list):
            child_path = find_parent_path_in_doc(
                item["children"],
                parent_menu_id,
                f"{current_path}.{idx}.children"
            )
            if child_path:
                return child_path
    
    return None


def build_menu_response(menu: Menu, processed_children: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build menu response dictionary"""
    
    def build_children_response(children_items):
        result = []
        for child_item in children_items:
            child_dict = {
                "id": child_item['menu_id'],
                "application_id": child_item.get('application_id'),
                "module_id": child_item.get('module_id'),
                "name": child_item['key'],
                "key": child_item['key'],
                "label": child_item['label'],
                "icon": child_item.get('icon'),
                "menus_description": child_item.get('description'),
                "badge": child_item.get('badge'),
                "section_title": child_item.get('section_title', ''),
                "route": child_item.get('route'),
                "component": child_item.get('component'),
                "level": child_item.get('level'),
                "order_index": child_item.get('order_index'),
                "is_visible": True,
                "is_active": True,
                "parent_menu_id": None,
                "menu_metadata": {},
                "access": ["read"],
                "mongo_id": None,
                "object_id": None,
                "deleted_at": None,
                "created_at": None,
                "updated_at": None,
                "children": build_children_response(child_item.get('children', []))
            }
            result.append(child_dict)
        return result
    
    return {
        "id": str(menu.id),
        "application_id": str(menu.application_id) if menu.application_id else None,
        "module_id": str(menu.module_id) if menu.module_id else None,
        "name": menu.name,
        "key": menu.key,
        "label": menu.label,
        "route": menu.route,
        "icon": menu.icon,
        "component": menu.component,
        "badge": menu.badge,
        "section_title": menu.section_title,
        "menus_description": menu.menus_description,
        "order_index": menu.order_index,
        "level": menu.level,
        "is_visible": menu.is_visible,
        "is_active": menu.is_active,
        "parent_menu_id": str(menu.parent_menu_id) if menu.parent_menu_id else None,
        "menu_metadata": menu.menu_metadata or {},
        "access": menu.access or ["read"],
        "mongo_id": menu.mongo_id,
        "object_id": None,
        "deleted_at": menu.deleted_at.isoformat() if menu.deleted_at else None,
        "created_at": menu.created_at.isoformat() if menu.created_at else None,
        "updated_at": menu.updated_at.isoformat() if menu.updated_at else None,
        "children": build_children_response(processed_children) if processed_children else []
    }


async def create_menus_batch_structured(
    batch_data: MenuBatchCreate,
    nav_doc_id: str,
    db: Session,
    current_user
):
    """
    Create multiple menus in batch with structured hierarchy support
    """
    print(f"[Batch Create Structured] 🚀 Creating {len(batch_data.menus)} menus")
    print(f"[Batch Create Structured] Application: {batch_data.application_id}, Module: {batch_data.module_id}")
    
    created_menus = []
    
    for idx, menu_data in enumerate(batch_data.menus):
        print(f"[Batch Create Structured] Processing menu {idx + 1}/{len(batch_data.menus)}")
        
        # Create MenuCreate instance with batch data.
        # Batch-level application_id always wins; per-item module_id only wins
        # when actually provided — a per-item "module_id": null must NOT wipe
        # the batch module (that is what pushed menus into "Default Module").
        menu_create_data = {**menu_data}
        menu_create_data["application_id"] = batch_data.application_id
        if not menu_create_data.get("module_id"):
            menu_create_data["module_id"] = batch_data.module_id

        # Batch items are menus (level 3+). Drop app/module-shaped levels (1/2)
        # from nav-export payloads so level is recalculated correctly.
        if menu_create_data.get("level") is not None and menu_create_data["level"] < 3:
            print(f"[Batch Create Structured] ⚠️ Dropping invalid level {menu_create_data['level']} for '{menu_create_data.get('name')}' - will be recalculated")
            menu_create_data.pop("level")

        menu_create = MenuCreate(**menu_create_data)
        
        # Create individual menu
        created_menu = await create_single_menu_structured(menu_create, nav_doc_id, db, current_user)
        created_menus.append(created_menu)
    
    print(f"[Batch Create Structured] ✅ Created {len(created_menus)} menus successfully")
    
    return {
        "message": f"Successfully created {len(created_menus)} menus",
        "created_count": len(created_menus),
        "menus": created_menus
    }


async def create_single_menu(
    menu_data: MenuCreate,
    nav_doc_id: str,
    db: Session,
    current_user
) -> MenuResponse:
    try:
        print(f"[Menu Create] 🚀 Starting menu creation")
        print(f"[Menu Create] Menu name: {menu_data.name}, App ID: {menu_data.application_id}")
    except Exception as e:
        print(f"[Menu Create] ❌ Error in initial validation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Menu creation failed during validation: {str(e)}"
        )
    
    # ✅ Use dict() with proper enum handling - use enum values not names
    create_data = menu_data.dict(by_alias=False, exclude_unset=False)

    print(f"[DEBUG] create_data after dict(): {create_data.get('access')}, type: {type(create_data.get('access'))}")

    # ✅ Access is now a list of strings, no enum conversion needed
    # Just ensure it's a list if provided
    if 'access' in create_data and create_data['access'] is not None:
        if isinstance(create_data['access'], str):
            # If it's a single string, convert to list
            create_data['access'] = [create_data['access'].lower()]
            print(f"[DEBUG] Converted string to list: {create_data['access']}")
        elif isinstance(create_data['access'], list):
            # Ensure all items are lowercase strings
            create_data['access'] = [item.lower() if isinstance(item, str) else item for item in create_data['access']]
            print(f"[DEBUG] Lowercased list items: {create_data['access']}")

    print(f"[DEBUG] create_data before Menu(**create_data): {create_data.get('access')}, type: {type(create_data.get('access'))}")

    children_payload = create_data.pop('children', [])
    if not create_data.get('label'):
        create_data['label'] = create_data['name']

    # Store children payload for later processing
    # children_snapshot will be populated after recursive processing

    if not create_data.get('application_id'):
      raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="application_id is required")

    app_exists = db.execute(
      text("SELECT 1 FROM applications WHERE id = :id"),
      {"id": str(create_data['application_id'])}
    ).scalar()
    if not app_exists:
      raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    # ✅ AUTO-INCREMENT: Calculate level and order_index based on parent and siblings
    if create_data.get('parent_menu_id'):
      # Fetch parent menu to get its level
      parent_menu = db.query(Menu).filter(Menu.id == create_data['parent_menu_id']).first()
      if not parent_menu:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent menu not found")
      
      # Auto-increment level: parent.level + 1
      create_data['level'] = parent_menu.level + 1
      print(f"[Menu Create] 📊 Auto-calculated level: {create_data['level']} (parent level: {parent_menu.level})")
      
      # Auto-increment order_index: find max order_index of siblings and add 1000
      max_order = db.query(func.max(Menu.order_index)).filter(
        Menu.parent_menu_id == create_data['parent_menu_id'],
        Menu.application_id == create_data['application_id'],
        Menu.deleted_at.is_(None)
      ).scalar() or 0
      
      create_data['order_index'] = max_order + 1000
      print(f"[Menu Create] 📊 Auto-calculated order_index: {create_data['order_index']} (max sibling: {max_order})")
    else:
      # Root level menu (no parent) - Application level is 1, so parent menus start at level 2
      create_data['level'] = 2
      print(f"[Menu Create] 📊 Root level menu (parent menu), level set to: 2")
      
      # Find max order_index of root menus in this application
      max_order = db.query(func.max(Menu.order_index)).filter(
        Menu.parent_menu_id.is_(None),
        Menu.application_id == create_data['application_id'],
        Menu.deleted_at.is_(None)
      ).scalar() or 0
      
      create_data['order_index'] = max_order + 1000
      print(f"[Menu Create] 📊 Auto-calculated order_index: {create_data['order_index']} (max root: {max_order})")

    # ✅ Handle field name mapping for PostgreSQL
    # The schema uses 'description' but the model column is 'menus_description'
    if 'description' in create_data:
        create_data['menus_description'] = create_data.pop('description')
    
    # ✅ Ensure all optional fields have proper defaults if not provided
    # This prevents NULL values in PostgreSQL when data is provided
    if 'key' not in create_data or create_data['key'] is None:
        create_data['key'] = create_data['name']  # Default key to name
    
    if 'badge' not in create_data:
        create_data['badge'] = None
    
    if 'section_title' not in create_data:
        create_data['section_title'] = None
    
    if 'mongo_id' not in create_data:
        create_data['mongo_id'] = None
    
    if 'component' not in create_data:
        create_data['component'] = None
    
    if 'icon' not in create_data:
        create_data['icon'] = None
    
    if 'menu_metadata' not in create_data or create_data['menu_metadata'] is None:
        create_data['menu_metadata'] = {}
    
    menu = Menu(**create_data)
    
    db.add(menu)
    db.commit()
    db.refresh(menu)

    # ✅ PROCESS CHILDREN RECURSIVELY
    # Use children_payload that was extracted earlier (line 924)
    print(f"[Menu Create] Found {len(children_payload)} children to process")
    
    async def process_children_recursive(parent_id, children_list, parent_level):
        """
        Recursively process children menus:
        1. Save each child to PostgreSQL
        2. Build menu item structure for MongoDB
        3. Process grandchildren recursively
        """
        processed_children = []
        
        if not children_list or not isinstance(children_list, list):
            return processed_children
        
        for child_data in children_list:
            if not isinstance(child_data, dict):
                continue
            
            # Prepare child menu data for PostgreSQL
            child_menu_data = {
                'application_id': menu.application_id,
                'name': child_data.get('name') or child_data.get('key'),
                'key': child_data.get('key') or child_data.get('name'),
                'label': child_data.get('label') or child_data.get('name'),
                'route': child_data.get('route'),
                'icon': child_data.get('icon'),
                'component': child_data.get('component'),
                'order_index': child_data.get('order_index', 1000),
                'level': child_data.get('level', parent_level + 1),
                'is_visible': child_data.get('is_visible', True),
                'is_active': child_data.get('is_active', True),
                'parent_menu_id': parent_id,
                'menu_metadata': child_data.get('menu_metadata', {}),
                'badge': child_data.get('badge'),
                'section_title': child_data.get('section_title', ''),
                'menus_description': child_data.get('menus_description', ''),
                'access': child_data.get('access', []),
                'showtopbar': child_data.get('showtopbar', True),
                'showsidebar': child_data.get('showsidebar', True)
            }
            
            # Create child menu in PostgreSQL
            child_menu = Menu(**child_menu_data)
            db.add(child_menu)
            db.flush()  # Get ID without committing
            
            print(f"[Menu Create]   - Created child in PostgreSQL: {child_menu.label} (ID: {child_menu.id})")
            
            # Process grandchildren recursively
            grandchildren = child_data.get('children', [])
            processed_grandchildren = await process_children_recursive(
                child_menu.id,
                grandchildren,
                child_menu.level
            )
            
            # Build menu item structure for MongoDB
            child_item = {
                "key": child_menu.key or child_menu.name,
                "label": child_menu.label,
                "icon": child_menu.icon,
                "description": child_menu.menus_description,
                "badge": child_menu.badge,
                "section_title": child_menu.section_title or "",
                "sectionTitle": child_menu.section_title or "",
                "route": child_menu.route,
                "component": child_menu.component,
                "menu_id": str(child_menu.id),
                "level": child_menu.level,
                "order_index": child_menu.order_index,
                "showtopbar": child_menu.showtopbar,
                "showsidebar": child_menu.showsidebar,
                "children": processed_grandchildren
            }
            
            processed_children.append(child_item)
        
        return processed_children
    
    # Process all children
    processed_children = await process_children_recursive(menu.id, children_payload, menu.level)
    
    # Commit all children to PostgreSQL
    if processed_children:
        db.commit()
        print(f"[Menu Create] ✅ Saved {len(processed_children)} children (and nested) to PostgreSQL")

    # ✅ CREATE/UPDATE APPLICATION DOCUMENT IN MONGODB
    # Application documents contain the full menu hierarchy
    # mainNavigation array contains ObjectId references to application documents
    print(f"[Menu Create] Menu created in PostgreSQL with ID: {menu.id}")
    print(f"[Menu Create] Processing application document in MongoDB")

    try:
        db_mongo = get_mongodb()
        if db_mongo is None:
            raise RuntimeError("MongoDB database not initialized")

        nav_doc_id_str = nav_doc_id or "69074724f217ab8fcb2e3b24"
        nav_doc_object_id = ObjectId(nav_doc_id_str)
        
        # Fetch application details from PostgreSQL
        application = db.query(Application).filter(Application.id == menu.application_id).first()
        if not application:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

        # Create menu item structure for MongoDB (with processed children)
        menu_item = {
            "key": menu.key or menu.name,
            "label": menu.label,
            "icon": menu.icon,
            "description": menu.menus_description or create_data.get('menu_metadata', {}).get('description'),
            "badge": menu.badge,
            "section_title": menu.section_title or "",
            "sectionTitle": menu.section_title or "",
            "route": menu.route,
            "component": menu.component,
            "menu_id": str(menu.id),
            "level": menu.level,
            "order_index": menu.order_index,
            "showtopbar": menu.showtopbar if hasattr(menu, 'showtopbar') else True,
            "showsidebar": menu.showsidebar if hasattr(menu, 'showsidebar') else True,
            "children": processed_children  # Include processed children
        }

        # Check if application document already exists
        app_doc = await db_mongo.menu_details.find_one({
            "application_id": str(menu.application_id),
            "_id": {"$ne": nav_doc_object_id}  # Exclude master navigation document
        })

        if not app_doc:
            # ✅ CREATE NEW APPLICATION DOCUMENT
            print(f"[Menu Create] Creating new application document for: {application.name}")
            
            new_app_doc = {
                "key": application.name.lower().replace(" ", "-"),
                "label": application.name,
                "icon": menu.icon or "ri-apps-line",
                "description": application.description or f"Manage {application.name}",
                "badge": None,
                "sectionTitle": application.name,
                "route": f"/{application.name.lower().replace(' ', '-')}",
                "application_id": str(application.id),
                "level": 1,
                "order_index": 1000,
                "showtopbar": True,
                "showsidebar": True,
                "children": [menu_item],  # First menu becomes first child
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }

            # Insert the new application document
            app_result = await db_mongo.menu_details.insert_one(new_app_doc)
            app_object_id = app_result.inserted_id
            
            # Store the application document ObjectId in PostgreSQL menu.mongo_id
            menu.mongo_id = str(app_object_id)
            db.commit()
            db.refresh(menu)
            
            print(f"[Menu Create] ✅ Created application document with _id: {app_object_id}")

            # ✅ ADD APPLICATION OBJECTID TO MAINNAVIGATION ARRAY
            update_result = await db_mongo.menu_details.update_one(
                {"_id": nav_doc_object_id},
                {"$addToSet": {"mainNavigation": app_object_id}}  # Store as ObjectId
            )

            if update_result.modified_count > 0:
                print(f"[Menu Create] ✅ Added application ObjectId to mainNavigation array")
            else:
                print(f"[Menu Create] ℹ️  Application ObjectId already in mainNavigation")
                
        else:
            # ✅ APPLICATION DOCUMENT EXISTS - ADD MENU TO IT
            app_object_id = app_doc["_id"]
            print(f"[Menu Create] Application document exists with _id: {app_object_id}")
            
            # Store the application document ObjectId in PostgreSQL menu.mongo_id
            menu.mongo_id = str(app_object_id)
            db.commit()
            db.refresh(menu)
            
            if not menu.parent_menu_id:
                # Root-level menu - add to application's children array
                print(f"[Menu Create] Adding root-level menu to application children")
                
                update_result = await db_mongo.menu_details.update_one(
                    {"_id": app_object_id},
                    {
                        "$push": {"children": menu_item},
                        "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                    }
                )
                
                if update_result.modified_count > 0:
                    print(f"[Menu Create] ✅ Added menu to application document")
                else:
                    print(f"[Menu Create] ⚠️  Failed to add menu to application document")
            else:
                # Child menu - find parent and add to its children
                print(f"[Menu Create] Adding child menu to parent: {menu.parent_menu_id}")
                
                # Helper function to find parent path recursively
                def find_parent_path(items, parent_menu_id, current_path="children"):
                    """Find the MongoDB path to parent menu's children array"""
                    if not isinstance(items, list):
                        return None
                    
                    for idx, item in enumerate(items):
                        if not isinstance(item, dict):
                            continue
                        
                        if item.get("menu_id") == str(parent_menu_id):
                            # Found parent - return path to its children
                            return f"{current_path}.{idx}.children"
                        
                        # Search in children recursively
                        if "children" in item and isinstance(item["children"], list):
                            child_path = find_parent_path(
                                item["children"],
                                parent_menu_id,
                                f"{current_path}.{idx}.children"
                            )
                            if child_path:
                                return child_path
                    
                    return None
                
                # Find parent path in application document
                parent_path = find_parent_path(app_doc.get("children", []), menu.parent_menu_id)
                
                if parent_path:
                    print(f"[Menu Create] Found parent at path: {parent_path}")
                    
                    update_result = await db_mongo.menu_details.update_one(
                        {"_id": app_object_id},
                        {
                            "$push": {parent_path: menu_item},
                            "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                        }
                    )
                    
                    if update_result.modified_count > 0:
                        print(f"[Menu Create] ✅ Added child menu to parent")
                    else:
                        print(f"[Menu Create] ⚠️  Failed to add child menu")
                else:
                    print(f"[Menu Create] ⚠️  Parent menu not found in application document")
            
    except Exception as e:
        print(f"[Menu Create] ⚠️ Failed to update MongoDB: {e}")
        import traceback
        traceback.print_exc()
        # Continue without failing - menu is already in PostgreSQL

    # ✅ POPULATE RESPONSE WITH CHILDREN
    # Build response dictionary with children instead of modifying Menu object
    def build_children_response(children_items):
        """Recursively build children response from processed items"""
        result = []
        for child_item in children_items:
            child_dict = {
                "id": child_item['menu_id'],
                "application_id": child_item.get('application_id'),
                "name": child_item['key'],
                "key": child_item['key'],
                "label": child_item['label'],
                "icon": child_item.get('icon'),
                "menus_description": child_item.get('description'),
                "badge": child_item.get('badge'),
                "section_title": child_item.get('section_title', ''),
                "route": child_item.get('route'),
                "component": child_item.get('component'),
                "level": child_item.get('level'),
                "order_index": child_item.get('order_index'),
                "is_visible": True,
                "is_active": True,
                "parent_menu_id": None,
                "menu_metadata": {},
                "access": ["read"],
                "mongo_id": None,
                "object_id": None,
                "deleted_at": None,
                "created_at": None,
                "updated_at": None,
                "children": build_children_response(child_item.get('children', []))
            }
            result.append(child_dict)
        return result
    
    # Build complete response dictionary matching MenuResponse schema
    response_dict = {
        "id": str(menu.id),
        "application_id": str(menu.application_id) if menu.application_id else None,
        "name": menu.name,
        "key": menu.key,
        "label": menu.label,
        "route": menu.route,
        "icon": menu.icon,
        "component": menu.component,
        "badge": menu.badge,
        "section_title": menu.section_title,
        "menus_description": menu.menus_description,
        "order_index": menu.order_index,
        "level": menu.level,
        "is_visible": menu.is_visible,
        "is_active": menu.is_active,
        "parent_menu_id": str(menu.parent_menu_id) if menu.parent_menu_id else None,
        "menu_metadata": menu.menu_metadata or {},
        "access": menu.access or ["read"],
        "mongo_id": menu.mongo_id,
        "object_id": None,
        "deleted_at": menu.deleted_at.isoformat() if menu.deleted_at else None,
        "created_at": menu.created_at.isoformat() if menu.created_at else None,
        "updated_at": menu.updated_at.isoformat() if menu.updated_at else None,
        "children": build_children_response(processed_children) if processed_children else []
    }
    
    if processed_children:
        print(f"[Menu Create] ✅ Added {len(processed_children)} children to response")

    print(f"[Menu Create] ✅ Menu creation completed successfully!")
    
    return MenuResponse(**response_dict)


async def create_menus_batch(
    batch_data: MenuBatchCreate,
    nav_doc_id: str,
    db: Session,
    current_user
) -> Dict[str, Any]:
    """
    Create multiple parent menus with nested children in one request.
    All menus will be added to the same application document.
    """
    print(f"[Menu Batch Create] 🚀 Creating {len(batch_data.menus)} parent menus")
    print(f"[Menu Batch Create] Application ID: {batch_data.application_id}")
    
    created_menus = []
    all_menu_items = []
    
    try:
        # Verify application exists
        app_exists = db.execute(
            text("SELECT 1 FROM applications WHERE id = :id"),
            {"id": str(batch_data.application_id)}
        ).scalar()
        if not app_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
        
        # Process each parent menu
        for idx, menu_dict in enumerate(batch_data.menus):
            print(f"[Menu Batch Create] Processing parent {idx + 1}/{len(batch_data.menus)}: {menu_dict.get('name')}")
            
            # Add application_id to menu data
            menu_dict['application_id'] = str(batch_data.application_id)
            
            # Extract children before creating Menu object
            children_payload = menu_dict.pop('children', [])
            
            # Set defaults
            if 'menu_metadata' not in menu_dict:
                menu_dict['menu_metadata'] = {}
            if 'key' not in menu_dict:
                menu_dict['key'] = menu_dict['name']
            if 'label' not in menu_dict:
                menu_dict['label'] = menu_dict['name']
            if 'level' not in menu_dict:
                menu_dict['level'] = 1
            if 'order_index' not in menu_dict:
                # Auto-calculate order_index
                max_order = db.query(func.max(Menu.order_index)).filter(
                    Menu.parent_menu_id.is_(None),
                    Menu.application_id == batch_data.application_id,
                    Menu.deleted_at.is_(None)
                ).scalar() or 0
                menu_dict['order_index'] = max_order + 1000
            
            # Handle field mappings
            if 'description' in menu_dict:
                menu_dict['menus_description'] = menu_dict.pop('description')
            
            # Create parent menu in PostgreSQL
            parent_menu = Menu(**menu_dict)
            db.add(parent_menu)
            db.flush()
            
            print(f"[Menu Batch Create]   - Created parent in PostgreSQL: {parent_menu.name} (ID: {parent_menu.id})")
            
            # Process children recursively
            async def process_children_recursive(parent_id, children_list, parent_level):
                processed_children = []
                if not children_list or not isinstance(children_list, list):
                    return processed_children
                
                for child_data in children_list:
                    if not isinstance(child_data, dict):
                        continue
                    
                    child_menu_data = {
                        'application_id': batch_data.application_id,
                        'name': child_data.get('name') or child_data.get('key'),
                        'key': child_data.get('key') or child_data.get('name'),
                        'label': child_data.get('label') or child_data.get('name'),
                        'route': child_data.get('route'),
                        'icon': child_data.get('icon'),
                        'component': child_data.get('component'),
                        'order_index': child_data.get('order_index', 1000),
                        'level': child_data.get('level', parent_level + 1),
                        'is_visible': child_data.get('is_visible', True),
                        'is_active': child_data.get('is_active', True),
                        'parent_menu_id': parent_id,
                        'menu_metadata': child_data.get('menu_metadata', {}),
                        'badge': child_data.get('badge'),
                        'section_title': child_data.get('section_title', ''),
                        'menus_description': child_data.get('menus_description', ''),
                        'access': child_data.get('access', []),
                        'showtopbar': child_data.get('showtopbar', True),
                        'showsidebar': child_data.get('showsidebar', True)
                    }
                    
                    child_menu = Menu(**child_menu_data)
                    db.add(child_menu)
                    db.flush()
                    
                    grandchildren = child_data.get('children', [])
                    processed_grandchildren = await process_children_recursive(
                        child_menu.id,
                        grandchildren,
                        child_menu.level
                    )
                    
                    child_item = {
                        "key": child_menu.key or child_menu.name,
                        "label": child_menu.label,
                        "icon": child_menu.icon,
                        "description": child_menu.menus_description,
                        "badge": child_menu.badge,
                        "section_title": child_menu.section_title or "",
                        "sectionTitle": child_menu.section_title or "",
                        "route": child_menu.route,
                        "component": child_menu.component,
                        "menu_id": str(child_menu.id),
                        "level": child_menu.level,
                        "order_index": child_menu.order_index,
                        "showtopbar": child_menu.showtopbar,
                        "showsidebar": child_menu.showsidebar,
                        "children": processed_grandchildren
                    }
                    
                    processed_children.append(child_item)
                
                return processed_children
            
            # Process children for this parent
            processed_children = await process_children_recursive(parent_menu.id, children_payload, parent_menu.level)
            
            # Build menu item for MongoDB
            menu_item = {
                "key": parent_menu.key or parent_menu.name,
                "label": parent_menu.label,
                "icon": parent_menu.icon,
                "description": parent_menu.menus_description,
                "badge": parent_menu.badge,
                "section_title": parent_menu.section_title or "",
                "sectionTitle": parent_menu.section_title or "",
                "route": parent_menu.route,
                "component": parent_menu.component,
                "menu_id": str(parent_menu.id),
                "level": parent_menu.level,
                "order_index": parent_menu.order_index,
                "showtopbar": parent_menu.showtopbar,
                "showsidebar": parent_menu.showsidebar,
                "children": processed_children
            }
            
            all_menu_items.append(menu_item)
            created_menus.append(parent_menu)
        
        # Commit all menus to PostgreSQL
        db.commit()
        print(f"[Menu Batch Create] ✅ Committed {len(created_menus)} parent menus to PostgreSQL")
        
        # Update MongoDB application document
        db_mongo = get_mongodb()
        if db_mongo is None:
            raise RuntimeError("MongoDB database not initialized")
        
        nav_doc_id_str = nav_doc_id or "69074724f217ab8fcb2e3b24"
        nav_doc_object_id = ObjectId(nav_doc_id_str)
        
        # Fetch application details
        application = db.query(Application).filter(Application.id == batch_data.application_id).first()
        if not application:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
        
        # Check if application document exists
        app_doc = await db_mongo.menu_details.find_one({
            "application_id": str(batch_data.application_id),
            "_id": {"$ne": nav_doc_object_id}
        })
        
        if not app_doc:
            # Create new application document with all menus
            print(f"[Menu Batch Create] Creating new application document")
            
            new_app_doc = {
                "key": application.name.lower().replace(" ", "-"),
                "label": application.name,
                "icon": "ri-apps-line",
                "description": application.description or f"Manage {application.name}",
                "badge": None,
                "sectionTitle": application.name,
                "route": f"/{application.name.lower().replace(' ', '-')}",
                "application_id": str(application.id),
                "level": 1,
                "order_index": 1000,
                "showtopbar": True,
                "showsidebar": True,
                "children": all_menu_items,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
            
            app_result = await db_mongo.menu_details.insert_one(new_app_doc)
            app_object_id = app_result.inserted_id
            
            # Update all menus with mongo_id
            for menu in created_menus:
                menu.mongo_id = str(app_object_id)
            db.commit()
            
            # Add to mainNavigation
            await db_mongo.menu_details.update_one(
                {"_id": nav_doc_object_id},
                {"$addToSet": {"mainNavigation": app_object_id}}
            )
            
            print(f"[Menu Batch Create] ✅ Created application document and added to mainNavigation")
        else:
            # Add all menus to existing application document
            app_object_id = app_doc["_id"]
            print(f"[Menu Batch Create] Adding {len(all_menu_items)} menus to existing application document")
            
            await db_mongo.menu_details.update_one(
                {"_id": app_object_id},
                {
                    "$push": {"children": {"$each": all_menu_items}},
                    "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}
                }
            )
            
            # Update all menus with mongo_id
            for menu in created_menus:
                menu.mongo_id = str(app_object_id)
            db.commit()
            
            print(f"[Menu Batch Create] ✅ Added menus to application document")
        
        print(f"[Menu Batch Create] ✅ Batch creation completed successfully!")
        
        return {
            "message": f"Successfully created {len(created_menus)} parent menus with nested children",
            "created_count": len(created_menus),
            "application_id": str(batch_data.application_id),
            "menus": [{"id": str(m.id), "name": m.name, "label": m.label} for m in created_menus]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"[Menu Batch Create] ❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch menu creation failed: {str(e)}"
        )



    """
    Batch update menus - primarily for drag and drop reordering
    
    Updates multiple menus' order_index and parent_menu_id in a single transaction.
    Automatically syncs to MongoDB.
    
    **Use Cases:**
    - Drag and drop reordering
    - Moving menus between parents
    - Swapping menu positions
    - Bulk order updates
    
    **Example - Drag & Drop:**
    ```json
    {
      "application_id": "app-uuid",
      "items": [
        {
          "menu_id": "menu-1",
          "order_index": 0,
          "parent_menu_id": "parent-uuid"
        },
        {
          "menu_id": "menu-2",
          "order_index": 1,
          "parent_menu_id": "parent-uuid"
        }
      ]
    }
    ```
    
    **Frontend Integration:**
    ```javascript
    const handleDragEnd = async (result) => {
      const items = reorder(menuList, result.source.index, result.destination.index);
      
      await fetch('/api/v1/menus/', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          application_id: currentAppId,
          items: items.map((item, index) => ({
            menu_id: item.id,
            order_index: index,
            parent_menu_id: item.parent_menu_id
          }))
        })
      });
    };
    ```
    """
    return await MenuReorderService.reorder_menus(db, reorder_data)





@router.put("/{menu_id}", response_model=MenuResponse)
async def update_menu(
    request: Request,
    menu_id: uuid.UUID,
    menu_data: MenuUpdate,
    nav_doc_id: str = Query("69074724f217ab8fcb2e3b24", description="Navigation document ID"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    ✅ SIMPLIFIED: Update menu in PostgreSQL and MongoDB
    Required: menu_id, application_id (from menu), nav_doc_id
    - Updates PostgreSQL menus table
    - Updates MongoDB menu_details collection
    - Updates MongoDB mainNavigation tree (finds by menu_id)
    """
    # 1️⃣ Find menu in PostgreSQL
    menu = db.query(Menu).filter(
        Menu.id == menu_id,
        Menu.is_active == True,
        Menu.deleted_at.is_(None)
    ).first()
    if not menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu not found"
        )

    # 2️⃣ Prepare update data
    update_data = menu_data.dict(exclude_unset=True, by_alias=False)
    old_values = {f: getattr(menu, f, None) for f in update_data if f != "children"}

    # ✅ Access is now a list of strings, no enum conversion needed
    if 'access' in update_data and update_data['access'] is not None:
        if isinstance(update_data['access'], str):
            update_data['access'] = [update_data['access'].lower()]
        elif isinstance(update_data['access'], list):
            update_data['access'] = [item.lower() if isinstance(item, str) else item for item in update_data['access']]

    # 4️⃣ Update PostgreSQL

    # Only set attributes that belong to the SQLAlchemy model and skip
    # nested/navigation payloads (e.g., `children`) which are stored in MongoDB.
    for field, value in update_data.items():
        if field == 'children':
            # children are stored in MongoDB mainNavigation tree, not as SQLAlchemy relations
            print(f"[Menu Update] Skipping SQL update for field: {field}")
            continue
        try:
            if hasattr(menu, field):
                setattr(menu, field, value)
            else:
                print(f"[Menu Update] ⚠️ Menu model has no attribute '{field}', skipping")
        except Exception as e:
            # Log and skip fields that SQLAlchemy cannot accept (e.g., wrong types)
            print(f"[Menu Update] ⚠️ Skipping field {field} due to error when setting attribute: {e}")
    db.commit()
    db.refresh(menu)
    print(f"[Menu Update] ✅ Updated PostgreSQL for menu_id: {menu.id}")

    try:
        _uid = get_user_id(current_user)
        _cid, _eid = get_audit_org_context(db, _uid)
        fire_audit_log(
            action="UPDATE", object_type="Menu",
            object_id=str(menu_id),
            user_id=_uid, client_id=_cid, entity_id=_eid,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["UPDATE"],
            old_values={k: str(v) if v is not None else None for k, v in old_values.items()},
            new_values={k: str(v) if v is not None else None for k, v in update_data.items() if k != "children"},
        )
    except Exception:
        pass

    # 4.5️⃣ Sync the application's navigation document (full rebuild) so ANY
    # field change reaches MongoDB, not just order/parent moves
    if update_data:
        print(f"[Menu Update] 🔄 Syncing navigation to MongoDB...")
        await MenuReorderService.sync_to_mongodb(db, menu.application_id)
        print(f"[Menu Update] ✅ Navigation sync completed")

    # 5️⃣ Update MongoDB menu_details collection (individual document)
    try:
        details_update: dict = {}
        # ✅ Include all fields including new ones: key, badge, section_title, mongo_id, description
        for key in ['route', 'icon', 'order_index', 'parent_menu_id', 'level', 'is_visible', 'component', 'menu_metadata', 'is_active', 'key', 'badge', 'section_title', 'mongo_id', 'description']:
            if key in update_data:
                details_update[key] = update_data[key]
        if 'parent_menu_id' in details_update and details_update['parent_menu_id'] is not None:
            details_update['parent_menu_id'] = str(details_update['parent_menu_id'])
        if details_update:
            await menu_details_service.update_menu_details(str(menu.id), details_update)
            print(f"[Menu Update] ✅ Updated MongoDB menu_details for menu_id: {menu.id}")
    except Exception as e:
        print(f"[Menu Update] ⚠️ Failed to update menu_details: {e}")

    # 6️⃣ Update MongoDB mainNavigation tree
    # ✅ Find the application document and update the menu within it
    try:
        db_mongo = get_mongodb()
        if db_mongo is None:
            print("[Menu Update] MongoDB not initialized, skipping navigation update")
            return menu

        # Build the update object for navigation
        metadata = update_data.get('menu_metadata') or menu.menu_metadata or {}
        nav_update: dict = {}

        if 'name' in update_data:
            nav_update["name"] = update_data['name']
            nav_update["key"] = update_data['name']  # key is derived from name
        if 'label' in update_data:
            nav_update["label"] = update_data['label']
        if 'icon' in update_data:
            nav_update["icon"] = update_data['icon']
        if 'route' in update_data:
            nav_update["route"] = update_data['route']
        if 'component' in update_data:
            nav_update["component"] = update_data['component']
        if 'order_index' in update_data:
            nav_update["order_index"] = update_data['order_index']
        if 'level' in update_data:
            nav_update["level"] = update_data['level']

        # ✅ Sync new fields to MongoDB mainNavigation
        if 'badge' in update_data:
            nav_update["badge"] = update_data['badge']
        if 'section_title' in update_data:
            nav_update["sectionTitle"] = update_data['section_title']
        if 'description' in update_data:
            nav_update["description"] = update_data['description']

        # Handle menu_metadata fields
        if 'menu_metadata' in update_data:
            if metadata.get('description') is not None:
                nav_update["description"] = metadata.get('description')
            if metadata.get('badge') is not None:
                nav_update["badge"] = metadata.get('badge')
            if metadata.get('sectionTitle') is not None:
                nav_update["sectionTitle"] = metadata.get('sectionTitle')

        if not nav_update:
            print("[Menu Update] No navigation fields to update")
            return menu

        print(f"[Menu Update] ========================================")
        print(f"[Menu Update] menu_id: {menu.id}")
        print(f"[Menu Update] application_id: {menu.application_id}")
        print(f"[Menu Update] mongo_id: {menu.mongo_id}")
        print(f"[Menu Update] Fields to update: {nav_update}")
        print(f"[Menu Update] ========================================")

        # ✅ Find the application document that contains this menu
        if not menu.mongo_id:
            print(f"[Menu Update] ⚠️ Menu has no mongo_id, cannot update MongoDB")
            return menu

        try:
            app_doc_id = ObjectId(menu.mongo_id)
        except Exception as e:
            print(f"[Menu Update] ⚠️ Invalid mongo_id: {e}")
            return menu

        app_doc = await db_mongo.menu_details.find_one({
            "_id": app_doc_id,
            "application_id": str(menu.application_id)
        })

        if not app_doc:
            print(f"[Menu Update] ⚠️ Application document not found with _id: {menu.mongo_id}")
            return menu

        # ✅ Recursive function to find and update menu by menu_id
        def update_menu_in_tree(items, target_menu_id, updates, new_children=None):
            """Recursively find menu by menu_id and update it"""
            if not isinstance(items, list):
                return False
            
            for item in items:
                if not isinstance(item, dict):
                    continue
                
                if item.get("menu_id") == target_menu_id:
                    # Found it! Update the fields
                    for key, value in updates.items():
                        item[key] = value

                    # ✅ Update children ONLY if provided AND not empty
                    # If children is empty array [], ignore it (don't delete existing children)
                    if new_children is not None and len(new_children) > 0:
                        item["children"] = new_children
                        print(f"[Menu Update] ✅ Updated children for menu: {item.get('label')} ({len(new_children)} children)")
                    elif new_children is not None and len(new_children) == 0:
                        print(f"[Menu Update] ⚠️ Ignoring empty children array for menu: {item.get('label')} (preserving existing children)")

                    print(f"[Menu Update] ✅ Found and updated menu in tree: {item.get('label')} (menu_id: {target_menu_id})")
                    return True
                
                # Search in children
                if "children" in item and isinstance(item["children"], list):
                    if update_menu_in_tree(item["children"], target_menu_id, updates, new_children):
                        return True
            return False

        # ✅ Get children from update_data if provided
        # If children is empty array [], set to None to ignore it
        new_children = None
        if 'children' in update_data:
            children_value = update_data.get('children')
            if children_value and len(children_value) > 0:
                new_children = children_value
                print(f"[Menu Update] Will update children with {len(children_value)} items")
            else:
                print(f"[Menu Update] Ignoring empty children array (preserving existing children)")

        # Update the menu in the application document's children array
        updated = update_menu_in_tree(app_doc.get("children", []), str(menu.id), nav_update, new_children)

        if updated:
            # Save the updated document back to MongoDB
            result = await db_mongo.menu_details.update_one(
                {"_id": app_doc_id},
                {
                    "$set": {
                        "children": app_doc["children"],
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
            print(f"[Menu Update] ✅ Successfully updated MongoDB application document! (modified={result.modified_count})")
        else:
            print(f"[Menu Update] ⚠️ Menu with menu_id={menu.id} not found in application document")

    except Exception as e:
        print(f"[Menu Update] ⚠️ Failed to update navigation: {e}")
        import traceback
        traceback.print_exc()

    # 7️⃣ Clear cache to ensure GET endpoints return updated data
    redis_cache.delete("menus:mongo:main_navigation_full")
    print(f"[Menu Update] ✅ Cleared navigation cache")

    # 8️⃣ Fetch children from MongoDB to include in response
    try:
        db_mongo = get_mongodb()
        if db_mongo is not None and menu.mongo_id:
            # Find the application document to get the menu's children
            try:
                app_doc_id = ObjectId(menu.mongo_id)
                app_doc = await db_mongo.menu_details.find_one({
                    "_id": app_doc_id,
                    "application_id": str(menu.application_id)
                })

                if app_doc and "children" in app_doc:
                    # Recursive function to find menu and get its children
                    def find_menu_children(items, target_menu_id):
                        """Recursively find menu by menu_id and return its children"""
                        if not isinstance(items, list):
                            return None
                        
                        for item in items:
                            if not isinstance(item, dict):
                                continue
                            
                            if item.get("menu_id") == target_menu_id:
                                return item.get("children", [])
                            
                            # Search in children
                            if "children" in item and isinstance(item["children"], list):
                                result = find_menu_children(item["children"], target_menu_id)
                                if result is not None:
                                    return result
                        return None

                    children = find_menu_children(app_doc["children"], str(menu.id))
                    if children is not None:
                        # Add children to the menu object for the response
                        menu.children = children
                        print(f"[Menu Update] ✅ Added {len(children)} children to response")
            except Exception as e:
                print(f"[Menu Update] ⚠️ Failed to fetch children: {e}")
    except Exception as e:
        print(f"[Menu Update] ⚠️ Failed to get MongoDB connection for children: {e}")

    return menu

async def _remove_menus_from_nav_docs(application_id: UUID, deleted_menu_ids: set) -> int:
    """
    Surgically remove deleted menu entries (matched by menu_id) from the MongoDB
    navigation documents:
    - the application's own document(s) in menu_details (children tree)
    - any inline entries in the master navigation document (backward compatibility)

    Removing a parent entry also removes everything nested under it.
    Returns the number of MongoDB documents updated.
    """
    # Use app.core.mongodb (the client the create path uses) — the
    # infrastructure client is a separate instance and may not be connected.
    from app.core.mongodb import get_mongodb as get_core_mongodb
    db_mongo = await get_core_mongodb()
    if db_mongo is None:
        print(f"[Menu Delete] ⚠️ MongoDB not available - nav documents not pruned")
        return 0

    def prune_children(items):
        """Return (kept_items, changed) with deleted menu entries removed recursively."""
        changed = False
        kept = []
        for item in items:
            if isinstance(item, dict):
                if str(item.get("menu_id")) in deleted_menu_ids:
                    changed = True
                    continue  # drop this entry and everything nested under it
                nested = item.get("children")
                if isinstance(nested, list):
                    new_nested, nested_changed = prune_children(nested)
                    if nested_changed:
                        item["children"] = new_nested
                        changed = True
            kept.append(item)
        return kept, changed

    updated_docs = 0
    master_doc_id = ObjectId("69074724f217ab8fcb2e3b24")

    # 1) Prune the application's own document(s)
    cursor = db_mongo.menu_details.find({
        "application_id": str(application_id),
        "_id": {"$ne": master_doc_id}
    })
    async for app_doc in cursor:
        children = app_doc.get("children")
        if not isinstance(children, list):
            continue
        new_children, changed = prune_children(children)
        if changed:
            await db_mongo.menu_details.update_one(
                {"_id": app_doc["_id"]},
                {"$set": {
                    "children": new_children,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            updated_docs += 1
            print(f"[Menu Delete] ✅ Pruned deleted menu entries from app document {app_doc['_id']}")

    # 2) Prune inline dict entries in the master navigation document
    #    (ObjectId references are kept untouched by prune_children)
    master_doc = await db_mongo.menu_details.find_one(
        {"_id": master_doc_id}, {"mainNavigation": 1}
    )
    if master_doc and isinstance(master_doc.get("mainNavigation"), list):
        new_nav, changed = prune_children(master_doc["mainNavigation"])
        if changed:
            await db_mongo.menu_details.update_one(
                {"_id": master_doc_id},
                {"$set": {"mainNavigation": new_nav}}
            )
            updated_docs += 1
            print(f"[Menu Delete] ✅ Pruned deleted menu entries from master navigation document")

    return updated_docs


@router.delete("/{menu_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_menu(
    request: Request,
    menu_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Soft delete a menu and all its children recursively.
    
    When a parent menu is deleted, all its children and nested children 
    are also deleted automatically (cascading delete).
    """
    # Look up WITHOUT active/deleted filters: DELETE is idempotent, so retrying
    # after a half-failed delete (PostgreSQL row soft-deleted but MongoDB nav
    # entry left behind) still prunes the leftover nav-doc entries instead of 404ing.
    menu = db.query(Menu).filter(Menu.id == menu_id).first()
    if not menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu not found"
        )

    was_already_deleted = menu.deleted_at is not None or menu.is_active is False
    if was_already_deleted:
        print(f"[Menu Delete] ♻️ Menu {menu_id} already soft-deleted - re-running MongoDB nav cleanup")

    menu_snapshot = {"name": menu.name, "label": menu.label}

    # Recursive function to collect all descendant menu IDs
    def get_all_descendant_ids(parent_id):
        """Recursively get all descendant menu IDs"""
        descendant_ids = []
        
        # Get direct children (no active/deleted filters so previously
        # soft-deleted children also get their nav-doc entries pruned)
        children = db.query(Menu).filter(
            Menu.parent_menu_id == parent_id
        ).all()

        for child in children:
            descendant_ids.append(child.id)
            # Recursively get grandchildren
            descendant_ids.extend(get_all_descendant_ids(child.id))
        
        return descendant_ids
    
    # Get all descendant menu IDs (children, grandchildren, etc.)
    all_menu_ids = [menu_id] + get_all_descendant_ids(menu_id)
    
    print(f"[Menu Delete] Deleting menu {menu_id} and {len(all_menu_ids) - 1} descendants")
    print(f"[Menu Delete] Menu IDs to delete: {all_menu_ids}")
    
    # Soft delete all menus (parent and all descendants)
    deleted_count = db.query(Menu).filter(
        Menu.id.in_(all_menu_ids)
    ).update(
        {
            "is_active": False,
            "deleted_at": datetime.now(timezone.utc)
        },
        synchronize_session=False
    )
    
    db.commit()
    print(f"[Menu Delete] ✅ Soft deleted {deleted_count} menus in PostgreSQL")

    try:
        _uid = get_user_id(current_user)
        _cid, _eid = get_audit_org_context(db, _uid)
        fire_audit_log(
            action="DELETE", object_type="Menu",
            object_id=str(menu_id),
            user_id=_uid, client_id=_cid, entity_id=_eid,
            session_id=get_session_id(current_user),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            risk_score=RISK_SCORE["DELETE"],
            old_values=menu_snapshot,
        )
    except Exception:
        pass

    # ✅ Remove the deleted menu entries from the MongoDB navigation documents.
    # Wrapped in try/except so a MongoDB failure never 500s after the PostgreSQL
    # commit — DELETE is idempotent, retry it to prune any leftovers.
    print(f"[Menu Delete] 🔄 Pruning deleted menus from MongoDB navigation documents...")
    try:
        deleted_id_strs = {str(mid) for mid in all_menu_ids}
        updated_docs = await _remove_menus_from_nav_docs(menu.application_id, deleted_id_strs)
        print(f"[Menu Delete] ✅ MongoDB nav cleanup done ({updated_docs} document(s) updated)")
    except Exception as e:
        print(f"[Menu Delete] ⚠️ MongoDB nav cleanup failed (menus stay soft-deleted in PostgreSQL, retry DELETE to prune): {e}")
        import traceback
        traceback.print_exc()

    # Clear all navigation caches (full nav + per-user + per-language variants)
    redis_cache.delete_pattern("menus:*")
    print(f"[Menu Delete] ✅ Cleared navigation caches")

    return None


    """Create a new menu from modal (PostgreSQL + push into Mongo navigation structure).
    Appends the new item under mainNavigation → admin-app → app-management → children.
    """
    create_data = menu_data.dict()
    # Extract children to avoid invalid arg when constructing SQLAlchemy model
    modal_children = create_data.pop('children', [])
    if not create_data.get('label'):
        create_data['label'] = create_data['name']

    # Ensure application exists
    if not create_data.get('application_id'):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="application_id is required")
    app_exists = db.execute(
        text("SELECT 1 FROM applications WHERE id = :id"),
        {"id": str(create_data['application_id'])}
    ).scalar()
    if not app_exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    # 2) Derive parent_menu_id for 'app-management' if not provided
    if not create_data.get('parent_menu_id'):
        parent_menu = db.query(Menu).filter(
            Menu.application_id == create_data['application_id'],
            Menu.name == 'app-management',
            Menu.is_active == True,
            Menu.deleted_at.is_(None)
        ).first()
        if parent_menu:
            create_data['parent_menu_id'] = parent_menu.id
        else:
            # If parent not found, keep None (root) but still push into navigation under app-management
            create_data['parent_menu_id'] = None

    # Auto order_index: place after existing siblings under parent
    if create_data.get('parent_menu_id'):
        max_order = db.query(func.max(Menu.order_index)).filter(
            Menu.parent_menu_id == create_data['parent_menu_id'],
            Menu.application_id == create_data['application_id'],
            Menu.is_active == True,
            Menu.deleted_at.is_(None)
        ).scalar()
        create_data['order_index'] = (max_order or 0) + 1

    # 3) Create in PostgreSQL
    menu = Menu(**create_data)
    db.add(menu)
    db.commit()
    db.refresh(menu)

    # 3a) If modal submitted nested children, create them recursively in PostgreSQL
    async def _create_children_recursive(parent_id, items, base_level=2):
        children_snap = []
        if not items:
            return children_snap
        for idx, item in enumerate(items):
            # Normalize fields from navigation-style payload
            child_name = item.get("key") or item.get("name")
            if not child_name:
                continue
            child_label = item.get("label") or child_name
            child_icon = item.get("icon") or ""
            child_route = item.get("route")
            child_component = item.get("component")
            child_meta = item.get("menu_metadata") or {}
            # Derive next order_index under this parent
            max_order = db.query(func.max(Menu.order_index)).filter(
                Menu.parent_menu_id == parent_id,
                Menu.application_id == create_data['application_id'],
                Menu.is_active == True,
                Menu.deleted_at.is_(None)
            ).scalar()
            child_order = (max_order or 0) + 1
            child_data = {
                "application_id": create_data['application_id'],
                "parent_menu_id": parent_id,
                "name": child_name,
                "label": child_label,
                "route": child_route,
                "component": child_component,
                "icon": child_icon,
                "order_index": child_order,
                "level": base_level,
                "is_visible": True,
                "menu_metadata": child_meta,
                "is_active": True
            }
            child_menu = Menu(**child_data)
            db.add(child_menu)
            db.commit()
            db.refresh(child_menu)
            # Create separate menu detail document for child menu
            try:
                child_mongo_id = await menu_details_service.create_menu_details(
                    menu_id=str(child_menu.id),
                    application_id=str(create_data['application_id']),
                    module_id=str(create_data.get('module_id')) if create_data.get('module_id') else None,  # New: Module support
                    route=child_route,
                    icon=child_icon,
                    order_index=child_order,
                    parent_menu_id=str(parent_id),
                    level=base_level,
                    is_visible=True,
                    component=child_component,
                    menu_metadata=child_meta,
                    is_active=True,
                    description=item.get("description"),
                    badge=item.get("badge"),
                    sectionTitle=item.get("sectionTitle"),
                 
                    children=item.get("children") or []
                )
                child_menu.mongo_id = child_mongo_id
                db.commit()
                db.refresh(child_menu)
            except Exception as e:
                print(f"[Menu Modal] Failed to create child menu details in MongoDB: {e}")
                pass
            # Recurse for grandchildren
            grand_children = item.get("children") or []
            nested_snap = await _create_children_recursive(child_menu.id, grand_children, base_level + 1)
            # ✅ Use validation helper to build navigation snapshot for this child
            child_snapshot = create_navigation_item(
                key=child_name,
                label=child_label,
                icon=child_icon,
                description=item.get("description"),
                badge=item.get("badge"),
                children=nested_snap,
                # Optional fields
                route=child_route,
                sectionTitle=item.get("sectionTitle"),
                menu_id=str(child_menu.id),
                application_id=str(create_data['application_id']),
                mongo_id=str(child_mongo_id) if child_mongo_id else "",  # ✅ Use mongo_id
               
            )
            children_snap.append(child_snapshot)
        return children_snap

    children_snapshot = await _create_children_recursive(menu.id, modal_children, base_level=(create_data.get('level', 1) + 1))

    # ✅ NO LONGER CREATE SEPARATE MENU DETAIL DOCUMENTS
    # All menu data will be stored in the mainNavigation array structure
    mongo_id = None  # Set to None since we're not creating separate documents

    # 5) Push into navigation structure in MongoDB under admin-app → app-management → children
    try:
        db_mongo = get_mongodb()
        if db_mongo is None:
            raise RuntimeError("MongoDB database not initialized")

        # Target doc id from request parameter (default: 69074724f217ab8fcb2e3b24)
        doc_id_str = nav_doc_id or "69074724f217ab8fcb2e3b24"
        try:
            doc_id = ObjectId(doc_id_str)
        except Exception:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid nav_doc_id")

        # ✅ Use validation helper to build child object for navigation
        metadata = create_data.get('menu_metadata') or {}
        new_item = create_navigation_item(
            key=create_data['name'],
            label=create_data.get('label') or create_data['name'],
            icon=create_data.get('icon'),
            description=create_data.get('description') or metadata.get('description'),
            badge=metadata.get('badge'),
            children=children_snapshot or [],
            # Optional fields
            route=create_data.get('route'),
            sectionTitle=metadata.get('sectionTitle'),
            menu_id=str(menu.id),
            application_id=str(menu.application_id),
            mongo_id=str(mongo_id) if mongo_id else "",  # ✅ Use mongo_id
          
        )

        # Resolve path keys
        keys = parent_keys or ["admin-app", "app-management"]
        if not keys:
            keys = ["admin-app"]

        # Fetch current document from menu_details to find app index
        doc = await db_mongo.menu_details.find_one({"_id": doc_id}, {"mainNavigation": 1})
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Navigation document not found")

        # mainNavigation should be an array
        main_nav = doc.get("mainNavigation", [])

        # Ensure it's an array
        if not isinstance(main_nav, list):
            if isinstance(main_nav, dict):
                main_nav = [v for k, v in sorted(main_nav.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0) if v is not None]
            else:
                main_nav = []

        # Find which array index contains the first parent key (e.g., "admin-app")
        app_index = None
        for idx, app_data in enumerate(main_nav):
            if isinstance(app_data, dict) and app_data.get("key") == keys[0]:
                app_index = idx
                break

        if app_index is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Application '{keys[0]}' not found in navigation")

        # Helper to find children array and index of insert_after_key
        def _find_by_key(items, key):
            for item in items or []:
                if isinstance(item, dict) and item.get("key") == key:
                    return item
            return None

        def _find_target_children(doc_root, key_path, app_idx):
            nav = (doc_root or {}).get("mainNavigation") or []
            # Ensure nav is a list
            if not isinstance(nav, list):
                return None
            # Start from the app object
            if app_idx >= len(nav):
                return None
            cur_obj = nav[app_idx]
            if not cur_obj:
                return None
            # Navigate through remaining keys
            for k in key_path[1:]:  # Skip first key as it's the app
                cur_list = cur_obj.get("children", [])
                cur_obj = _find_by_key(cur_list, k)
                if not cur_obj:
                    return None
            return cur_obj.get("children") if cur_obj else None

        # Compute $position if insert_after_key is provided
        position: Optional[int] = None
        children_arr = _find_target_children(doc, keys, app_index)
        if isinstance(children_arr, list):
            idx = next((i for i, it in enumerate(children_arr) if isinstance(it, dict) and it.get("key") == insert_after_key), None)
            if idx is not None:
                position = idx + 1

        # Build dynamic update path for array-based mainNavigation
        placeholders = [f"lvl{i}" for i in range(len(keys) - 1)]  # -1 because first key is the app index
        path_parts = [f"mainNavigation.{app_index}"]  # Start with the array index

        # Add children path for remaining keys
        for i in range(1, len(keys)):
            path_parts.append(f"children.$[{placeholders[i-1]}]")
        update_path = ".".join(path_parts + ["children"])  # push into the target parent's children

        filter_doc = {"_id": doc_id}
        push_payload: dict = {"$each": [new_item]}
        if position is not None:
            push_payload["$position"] = position
        update_doc = {
            "$push": {
                update_path: push_payload
            }
        }
        # Array filters only for children navigation (skip the first key which is now an object property)
        array_filters = [{f"{placeholders[i]}.key": keys[i+1]} for i in range(len(keys) - 1)]

        # Try primary collection 'menu_details', fallback to 'menus' if needed
        result = await db_mongo.menu_details.update_one(filter_doc, update_doc, array_filters=array_filters)
    except Exception:
        # Swallow to keep endpoint resilient; in real system, log the error
        pass

    # Clear cache to ensure GET endpoints return updated data
    redis_cache.delete("menus:mongo:main_navigation_full")
    print(f"[Menu Create From Modal] ✅ Cleared navigation cache")

    # Fetch children from MongoDB to include in response
    try:
        db_mongo = get_mongodb()
        if db_mongo is not None:
            try:
                doc_id = ObjectId(nav_doc_id)
                nav_doc = await db_mongo.menu_details.find_one({"_id": doc_id})

                if nav_doc and "mainNavigation" in nav_doc:
                    # Recursive function to find menu and get its children
                    def find_menu_children(items, target_menu_id):
                        """Recursively find menu by menu_id and return its children"""
                        for item in items:
                            if item.get("menu_id") == target_menu_id:
                                return item.get("children", [])
                            # Search in children
                            if "children" in item and isinstance(item["children"], list):
                                result = find_menu_children(item["children"], target_menu_id)
                                if result is not None:
                                    return result
                        return None

                    children = find_menu_children(nav_doc["mainNavigation"], str(menu.id))
                    if children is not None:
                        menu.children = children
                        print(f"[Menu Create From Modal] ✅ Added {len(children)} children to response")
            except Exception as e:
                print(f"[Menu Create From Modal] ⚠️ Failed to fetch children: {e}")
    except Exception as e:
        print(f"[Menu Create From Modal] ⚠️ Failed to get MongoDB connection for children: {e}")

    return menu


# ============================================================================
# MENU REORDERING ENDPOINTS
# ============================================================================


@router.post(
    "/reorder",
    response_model=MenuReorderResponse,
    status_code=status.HTTP_200_OK,
    summary="Reorder Menus (Drag & Drop + Swap)",
    description="""
    Reorder menus using drag-and-drop functionality or swap two menus.
    
    **Supports:**
    - Parent menu reordering
    - Children menu reordering within same parent
    - Moving menus between parents
    - Nested children reordering (multi-level)
    - **Swap two menus** (automatically detected when exactly 2 items with same parent)
    
    **How it works:**
    1. Frontend sends all affected menus with new order_index
    2. Backend updates order_index for each menu
    3. If parent changed, updates parent_menu_id and level
    4. **Auto-detects swap**: When exactly 2 items with same parent, swaps their order_index
    5. Automatically syncs to both PostgreSQL and MongoDB
    6. Returns success with updated count
    
    **Example Use Cases:**
    
    **1. Reorder Parent Menus:**
    ```json
    {
      "application_id": "app-uuid",
      "items": [
        {"menu_id": "admin-app", "order_index": 0, "parent_menu_id": null},
        {"menu_id": "calendar-app", "order_index": 1, "parent_menu_id": null},
        {"menu_id": "client-directory", "order_index": 2, "parent_menu_id": null}
      ]
    }
    ```
    
    **2. Reorder Children Under Parent:**
    ```json
    {
      "application_id": "app-uuid",
      "items": [
        {"menu_id": "client-setup", "order_index": 0, "parent_menu_id": "admin-app"},
        {"menu_id": "app-setup", "order_index": 1, "parent_menu_id": "admin-app"},
        {"menu_id": "user-roles", "order_index": 2, "parent_menu_id": "admin-app"}
      ]
    }
    ```
    
    **3. Reorder Nested Children:**
    ```json
    {
      "application_id": "app-uuid",
      "items": [
        {"menu_id": "entities", "order_index": 0, "parent_menu_id": "client-setup"},
        {"menu_id": "date-time", "order_index": 1, "parent_menu_id": "client-setup"},
        {"menu_id": "divisions", "order_index": 2, "parent_menu_id": "client-setup"}
      ]
    }
    ```
    
    **4. Move Menu to Different Parent:**
    ```json
    {
      "application_id": "app-uuid",
      "items": [
        {"menu_id": "user-roles", "order_index": 0, "parent_menu_id": "calendar-app"}
      ]
    }
    ```
    
    **5. Swap Two Menus (Auto-detected):**
    ```json
    {
      "application_id": "app-uuid",
      "items": [
        {"menu_id": "menu-1", "order_index": 1, "parent_menu_id": "admin-app"},
        {"menu_id": "menu-2", "order_index": 0, "parent_menu_id": "admin-app"}
      ]
    }
    ```
    Note: When exactly 2 items with same parent are provided, the system automatically 
    detects this as a swap operation and swaps their order_index values efficiently.
    
    **Frontend Integration:**
    ```javascript
    // On drag end
    const reorderMenus = async (draggedItem, newIndex, newParent) => {
      const items = affectedMenus.map((menu, index) => ({
        menu_id: menu.id,
        order_index: index,
        parent_menu_id: menu.parent_id
      }));
      
      await fetch('/api/v1/menus/reorder', {
        method: 'POST',
        body: JSON.stringify({
          application_id: currentAppId,
          items: items
        })
      });
    };
    ```
    """,
    responses={
        200: {
            "description": "Menus reordered successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Successfully reordered 5 menus",
                        "updated_count": 5,
                        "items": [
                            {
                                "menu_id": "uuid1",
                                "order_index": 0,
                                "parent_menu_id": None
                            },
                            {
                                "menu_id": "uuid2",
                                "order_index": 1,
                                "parent_menu_id": None
                            }
                        ]
                    }
                }
            }
        },
        404: {
            "description": "One or more menus not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Menus not found: {uuid1, uuid2}"}
                }
            }
        },
        400: {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid menu order"}
                }
            }
        }
    }
)
async def reorder_menus(
    reorder_data: MenuReorderRequest,
    db: Session = Depends(get_db)
):
    """
    Reorder menus based on drag-and-drop action
    
    Handles parent menus, children, and nested children reordering.
    Automatically syncs to both PostgreSQL and MongoDB.
    """
    return await MenuReorderService.reorder_menus(db, reorder_data)









    """
    Permanently delete menus that have been soft-deleted for longer than retention period.
    
    This endpoint:
    1. Finds all menus with is_active=false and deleted_at older than retention period
    2. Permanently deletes them from PostgreSQL
    3. Removes associated documents from MongoDB
    4. Returns statistics about the cleanup
    
    Default retention period: 30 days
    
    Returns:
        - success: Whether cleanup was successful
        - deleted_count: Number of menus permanently deleted from PostgreSQL
        - mongo_deleted_count: Number of documents deleted from MongoDB
        - cutoff_date: Date used for filtering
        - retention_days: Configured retention period
        - menu_ids: List of deleted menu IDs
    """
    result = await menu_cleanup_service.cleanup_old_deleted_menus(db)
    
    if result["success"]:
        # Clear cache after cleanup
        redis_cache.delete("menus:mongo:main_navigation_full")
        logger.info("[Menu Cleanup] ✅ Cleared navigation cache after cleanup")
    
    return result

