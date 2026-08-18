"""
Single source of truth for syncing an application's menu tree to MongoDB.

Menu creation and menu reordering previously had their own sync
implementations (working_sync_to_mongodb in the navigation routes and
MenuReorderService.sync_to_mongodb) that produced slightly different
document shapes. Both now delegate here so the menu_details application
document always has one canonical shape:

    Application (level 1)
      └── children: Modules (level 2, all non-deleted modules, ordered)
            └── children: Menus (level 3, parent_menu_id IS NULL, ordered)
                  └── children: Nested menus (level 4+, recursive, ordered)

Menus without a module are grouped under a synthetic "Default Module".
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from bson import ObjectId
from sqlalchemy.orm import Session

from app.menus.models.menu import Menu

logger = logging.getLogger(__name__)

# Master navigation document holding the mainNavigation array of app doc ids
MASTER_NAV_DOC_ID = "69074724f217ab8fcb2e3b24"


def _build_menu_item(menu: Menu, menus_by_parent: Dict[Any, List[Menu]], application_id: UUID) -> Dict[str, Any]:
    """Build one menu node with nested children attached recursively."""
    item = {
        "key": menu.key or menu.name or str(menu.id),
        "name": menu.name,
        "label": menu.label,
        "route": menu.route,
        "icon": menu.icon,
        "component": menu.component,
        "menu_id": str(menu.id),
        "application_id": str(application_id),
        "module_id": str(menu.module_id) if menu.module_id else None,
        "order_index": menu.order_index,
        "level": menu.level,
        "is_active": menu.is_active,
        "showtopbar": True if menu.showtopbar is None else menu.showtopbar,
        "showsidebar": True if menu.showsidebar is None else menu.showsidebar,
        "children": [
            _build_menu_item(child, menus_by_parent, application_id)
            for child in sorted(
                menus_by_parent.get(menu.id, []),
                key=lambda c: (c.order_index or 0)
            )
        ],
    }

    # Optional fields
    if menu.badge:
        item["badge"] = menu.badge
    if menu.section_title:
        item["sectionTitle"] = menu.section_title
    if menu.menus_description:
        item["description"] = menu.menus_description
    if menu.access:
        item["access"] = menu.access

    return item


def _build_module_item(module, root_menus: List[Menu], menus_by_parent: Dict[Any, List[Menu]], application_id: UUID) -> Dict[str, Any]:
    """Build one module node (level 2) with its root menus as children."""
    item = {
        "key": module.key or (module.name.lower().replace(" ", "-") if module.name else f"module-{module.id}"),
        "name": module.name,
        "label": module.label or module.name,
        "route": module.route or "",
        "icon": module.icon or "ri-folder-line",
        "module_id": str(module.id),
        "application_id": str(application_id),
        "order_index": module.order_index,
        "level": 2,
        "is_active": module.is_active,
        "access": module.access or [],
        "children": [
            _build_menu_item(menu, menus_by_parent, application_id)
            for menu in sorted(root_menus, key=lambda m: (m.order_index or 0))
        ],
    }

    if module.badge:
        item["badge"] = module.badge
    if module.section_title:
        item["sectionTitle"] = module.section_title
    if module.description:
        item["description"] = module.description

    return item


async def sync_application_menus_to_mongodb(
    db: Session, application_id: UUID, nav_doc_id: Optional[str] = None
) -> bool:
    """
    Rebuild the application's menu_details document from PostgreSQL and
    upsert it into MongoDB. Also ensures the document is referenced from the
    master mainNavigation array (nav_doc_id, defaulting to MASTER_NAV_DOC_ID)
    and backfills mongo_id on the menus rows.

    Returns True on success, False otherwise (never raises — menu writes to
    PostgreSQL must not fail because of a Mongo outage).
    """
    try:
        from app.core.mongodb import get_mongodb
        from app.applications.models.application import Application
        from app.modules.models.module import Module

        db_mongo = await get_mongodb()
        if db_mongo is None:
            logger.warning("[Menu Sync] MongoDB not available, skipping sync")
            return False

        app = db.query(Application).filter(
            Application.id == application_id,
            Application.is_active == True,
            Application.is_deleted == False
        ).first()
        if not app:
            logger.warning(f"[Menu Sync] Application not found: {application_id}")
            return False

        menus = db.query(Menu).filter(
            Menu.application_id == application_id,
            Menu.deleted_at.is_(None)
        ).order_by(Menu.level, Menu.order_index).all()

        modules = db.query(Module).filter(
            Module.application_id == application_id,
            Module.is_deleted == False
        ).order_by(Module.order_index).all()

        logger.info(f"[Menu Sync] Application {application_id}: {len(modules)} modules, {len(menus)} menus")

        # Group menus by parent for recursive children lookup
        menus_by_parent: Dict[Any, List[Menu]] = {}
        for m in menus:
            if m.parent_menu_id is not None:
                menus_by_parent.setdefault(m.parent_menu_id, []).append(m)

        root_menus = [m for m in menus if m.parent_menu_id is None]

        # All non-deleted modules are included (even empty ones) so the doc
        # shape is stable no matter which operation triggered the sync
        navigation_structure = [
            _build_module_item(
                module,
                [m for m in root_menus if m.module_id == module.id],
                menus_by_parent,
                application_id,
            )
            for module in modules
        ]

        # Menus without a module go under a synthetic default module
        orphaned_menus = [m for m in root_menus if m.module_id is None]
        if orphaned_menus:
            navigation_structure.append({
                "key": "default-module",
                "name": "default-module",
                "label": "Default Module",
                "route": "",
                "icon": "ri-folder-line",
                "module_id": "default",
                "application_id": str(application_id),
                "order_index": 999000,
                "level": 2,
                "is_active": True,
                "access": [],
                "children": [
                    _build_menu_item(menu, menus_by_parent, application_id)
                    for menu in sorted(orphaned_menus, key=lambda m: (m.order_index or 0))
                ],
            })

        collection = db_mongo["menu_details"]
        master_doc_id = ObjectId(nav_doc_id or MASTER_NAV_DOC_ID)
        now = datetime.now(timezone.utc).isoformat()

        app_doc = await collection.find_one({
            "application_id": str(application_id),
            "_id": {"$ne": master_doc_id}
        })

        # Application-level fields are refreshed from PostgreSQL on every sync
        # so PUT /applications changes (label, icon, route, ...) reach MongoDB
        app_fields = {
            "key": app.key or app.name.lower().replace(" ", "-"),
            "name": app.name,
            "label": app.label or app.name,
            "icon": app.icon or "ri-apps-line",
            "description": app.description or f"Manage {app.name}",
            "badge": app.badge,
            "sectionTitle": app.section_title or app.name,
            "nav_group": app.nav_group or "apps",
            "route": app.route or f"/{app.name.lower().replace(' ', '-')}",
            "order_index": app.order_index or 1000,
            "access": app.access or [],
            "children": navigation_structure,
            "updated_at": now,
        }

        if app_doc:
            app_object_id = app_doc["_id"]
            await collection.update_one(
                {"_id": app_object_id},
                {"$set": app_fields}
            )
            logger.info(f"[Menu Sync] Updated application document {app_object_id}")
        else:
            new_doc = {
                **app_fields,
                "application_id": str(application_id),
                "level": 1,
                "is_active": True,
                "created_at": now,
            }
            result = await collection.insert_one(new_doc)
            app_object_id = result.inserted_id
            logger.info(f"[Menu Sync] Created application document {app_object_id}")

        # Ensure the document is referenced from the master navigation
        await collection.update_one(
            {"_id": master_doc_id},
            {"$addToSet": {"mainNavigation": app_object_id},
             "$set": {"updated_at": now}}
        )

        # Backfill/refresh mongo_id on PostgreSQL menu rows
        changed = 0
        for m in menus:
            if m.mongo_id != str(app_object_id):
                m.mongo_id = str(app_object_id)
                changed += 1
        if changed:
            db.commit()
            logger.info(f"[Menu Sync] Updated mongo_id on {changed} menus")

        return True

    except Exception as e:
        logger.error(f"[Menu Sync] Sync failed for application {application_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


# Postgres Application column -> Mongo application-doc field. Only these are
# ever touched by a field-level sync; "children" is deliberately absent so an
# application PUT can never affect the modules/menus tree.
_APPLICATION_FIELD_MAP: Dict[str, str] = {
    "name": "name",
    "key": "key",
    "label": "label",
    "icon": "icon",
    "description": "description",
    "badge": "badge",
    "section_title": "sectionTitle",
    "nav_group": "nav_group",
    "route": "route",
    "order_index": "order_index",
    "access": "access",
}


async def sync_application_fields_to_mongodb(
    db: Session, application_id: UUID, changed_fields: Dict[str, Any], nav_doc_id: Optional[str] = None
) -> bool:
    """
    Update only the application-level fields that actually changed on this
    PUT, leaving `children` (the modules/menus tree) completely untouched.

    sync_application_menus_to_mongodb() is a full tree rebuild - correct for
    module/menu writes, since those *are* the tree. But an application PUT
    (e.g. just editing the description) has no business touching modules or
    menus, and a full rebuild was silently wiping the tree whenever Postgres
    didn't happen to have every module/menu the Mongo doc previously showed.

    nav_doc_id selects which master navigation document this application's
    doc is excluded against / would be registered into on a fallback full
    build; defaults to MASTER_NAV_DOC_ID.

    Falls back to the full rebuild only if no MongoDB document exists yet for
    this application (first sync - nothing to preserve).

    Returns True on success, False otherwise (never raises).
    """
    try:
        from app.core.mongodb import get_mongodb
        from app.applications.models.application import Application

        db_mongo = await get_mongodb()
        if db_mongo is None:
            logger.warning("[Menu Sync] MongoDB not available, skipping field sync")
            return False

        app = db.query(Application).filter(Application.id == application_id).first()
        if not app:
            logger.warning(f"[Menu Sync] Application not found: {application_id}")
            return False

        collection = db_mongo["menu_details"]
        master_doc_id = ObjectId(nav_doc_id or MASTER_NAV_DOC_ID)

        app_doc = await collection.find_one({
            "application_id": str(application_id),
            "_id": {"$ne": master_doc_id}
        })

        if not app_doc:
            # No document to preserve yet - do the normal first-time build.
            logger.info(f"[Menu Sync] No existing document for {application_id}, doing full build")
            return await sync_application_menus_to_mongodb(db, application_id, nav_doc_id)

        updates = {
            mongo_field: getattr(app, pg_field)
            for pg_field, mongo_field in _APPLICATION_FIELD_MAP.items()
            if pg_field in changed_fields
        }

        if not updates:
            logger.info(f"[Menu Sync] No mongo-relevant fields changed for {application_id}, skipping")
            return True

        updates["updated_at"] = datetime.now(timezone.utc).isoformat()

        await collection.update_one(
            {"_id": app_doc["_id"]},
            {"$set": updates}
        )
        logger.info(f"[Menu Sync] Field-synced application {application_id}: {list(updates.keys())} (children untouched)")
        return True

    except Exception as e:
        logger.error(f"[Menu Sync] Field sync failed for application {application_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


# Postgres Module column -> Mongo module-node field, for the targeted $set
# below. "children" (the module's own nested menus) is deliberately absent.
_MODULE_FIELD_MAP: Dict[str, str] = {
    "name": "name",
    "key": "key",
    "label": "label",
    "icon": "icon",
    "route": "route",
    "order_index": "order_index",
    "is_active": "is_active",
    "access": "access",
    "badge": "badge",
    "section_title": "sectionTitle",
    "description": "description",
}


async def sync_module_fields_to_mongodb(
    db: Session, module_id: UUID, application_id: UUID, changed_fields: Dict[str, Any],
    nav_doc_id: Optional[str] = None,
) -> bool:
    """
    Update only the fields that changed on one module's own node inside its
    application's `children` array (via a positional array filter), leaving
    every other module and all menus - including this module's own nested
    menus - completely untouched.

    nav_doc_id selects which master navigation document this module's
    application doc is excluded against / would be registered into on a
    fallback full build; defaults to MASTER_NAV_DOC_ID.

    Falls back to the full rebuild when there's nothing to target: no app
    document yet, this module's node isn't in the tree yet, or the module is
    being moved to a different application (a structural change, not a field
    edit - rebuilds so it lands correctly in the new application's tree).

    Returns True on success, False otherwise (never raises).
    """
    try:
        from app.core.mongodb import get_mongodb
        from app.modules.models.module import Module

        if "application_id" in changed_fields:
            logger.info(f"[Menu Sync] Module {module_id} changed application, doing full rebuild")
            return await sync_application_menus_to_mongodb(db, application_id, nav_doc_id)

        db_mongo = await get_mongodb()
        if db_mongo is None:
            logger.warning("[Menu Sync] MongoDB not available, skipping module field sync")
            return False

        module = db.query(Module).filter(Module.id == module_id).first()
        if not module:
            logger.warning(f"[Menu Sync] Module not found: {module_id}")
            return False

        collection = db_mongo["menu_details"]
        master_doc_id = ObjectId(nav_doc_id or MASTER_NAV_DOC_ID)

        app_doc = await collection.find_one({
            "application_id": str(application_id),
            "_id": {"$ne": master_doc_id},
            "children.module_id": str(module_id),
        })

        if not app_doc:
            # No doc yet, or this module's node isn't in the tree yet.
            logger.info(f"[Menu Sync] Module {module_id} not found in existing tree, doing full rebuild")
            return await sync_application_menus_to_mongodb(db, application_id, nav_doc_id)

        updates = {
            f"children.$[mod].{mongo_field}": getattr(module, pg_field)
            for pg_field, mongo_field in _MODULE_FIELD_MAP.items()
            if pg_field in changed_fields
        }

        if not updates:
            logger.info(f"[Menu Sync] No mongo-relevant fields changed for module {module_id}, skipping")
            return True

        updates["updated_at"] = datetime.now(timezone.utc).isoformat()

        await collection.update_one(
            {"_id": app_doc["_id"]},
            {"$set": updates},
            array_filters=[{"mod.module_id": str(module_id)}],
        )
        logger.info(f"[Menu Sync] Field-synced module {module_id}: {list(updates.keys())} (menus untouched)")
        return True

    except Exception as e:
        logger.error(f"[Menu Sync] Module field sync failed for {module_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def add_module_to_mongodb(db: Session, module_id: UUID, nav_doc_id: Optional[str] = None) -> bool:
    """
    Append a newly-created module as a fresh node (no menus yet) onto its
    application's `children` array, without touching any other module or
    menu already in the tree.

    nav_doc_id selects which master navigation document this application's
    doc is excluded against / would be registered into on a fallback full
    build; defaults to MASTER_NAV_DOC_ID.

    Falls back to the full rebuild only if the application has no MongoDB
    document yet (first-ever sync for that application - nothing to append
    to).

    Returns True on success, False otherwise (never raises).
    """
    try:
        from app.core.mongodb import get_mongodb
        from app.modules.models.module import Module

        db_mongo = await get_mongodb()
        if db_mongo is None:
            logger.warning("[Menu Sync] MongoDB not available, skipping module add")
            return False

        module = db.query(Module).filter(Module.id == module_id).first()
        if not module:
            logger.warning(f"[Menu Sync] Module not found: {module_id}")
            return False

        collection = db_mongo["menu_details"]
        master_doc_id = ObjectId(nav_doc_id or MASTER_NAV_DOC_ID)

        app_doc = await collection.find_one({
            "application_id": str(module.application_id),
            "_id": {"$ne": master_doc_id}
        })

        if not app_doc:
            logger.info(f"[Menu Sync] No existing document for application {module.application_id}, doing full build")
            return await sync_application_menus_to_mongodb(db, module.application_id, nav_doc_id)

        # Avoid duplicating the node on a retry/race where it's already there
        already_present = any(
            isinstance(c, dict) and c.get("module_id") == str(module.id)
            for c in app_doc.get("children", [])
        )
        if already_present:
            logger.info(f"[Menu Sync] Module {module_id} node already present, skipping add")
            return True

        module_item = _build_module_item(module, [], {}, module.application_id)

        await collection.update_one(
            {"_id": app_doc["_id"]},
            {
                "$push": {"children": module_item},
                "$set": {"updated_at": datetime.now(timezone.utc).isoformat()},
            }
        )
        logger.info(f"[Menu Sync] Added new module {module_id} node (other modules/menus untouched)")
        return True

    except Exception as e:
        logger.error(f"[Menu Sync] Add module failed for {module_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def remove_module_from_mongodb(
    application_id: UUID, module_id: UUID, nav_doc_id: Optional[str] = None
) -> bool:
    """
    Remove one module's node (and its nested menus) from its application's
    `children` array via a targeted $pull, without rebuilding anything else.

    nav_doc_id selects which master navigation document to exclude the
    application's own doc against; defaults to MASTER_NAV_DOC_ID.

    Returns True on success, False otherwise (never raises).
    """
    try:
        from app.core.mongodb import get_mongodb

        db_mongo = await get_mongodb()
        if db_mongo is None:
            logger.warning("[Menu Sync] MongoDB not available, skipping module removal")
            return False

        collection = db_mongo["menu_details"]
        master_doc_id = ObjectId(nav_doc_id or MASTER_NAV_DOC_ID)
        now = datetime.now(timezone.utc).isoformat()

        result = await collection.update_one(
            {"application_id": str(application_id), "_id": {"$ne": master_doc_id}},
            {
                "$pull": {"children": {"module_id": str(module_id)}},
                "$set": {"updated_at": now},
            }
        )
        if result.modified_count:
            logger.info(f"[Menu Sync] Removed module {module_id} node from application {application_id}")
        else:
            logger.info(f"[Menu Sync] Module {module_id} not found in application {application_id} tree (already absent)")
        return True

    except Exception as e:
        logger.error(f"[Menu Sync] Remove module failed for {module_id}: {e}")
        return False


def _find_node_by_id(items: List[Dict[str, Any]], id_field: str, target_id: str) -> Optional[Dict[str, Any]]:
    """Recursively find a node in a Mongo children tree by menu_id or module_id."""
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get(id_field) == target_id:
            return item
        nested = item.get("children")
        if isinstance(nested, list):
            found = _find_node_by_id(nested, id_field, target_id)
            if found is not None:
                return found
    return None


async def add_menu_to_mongodb(db: Session, menu_id: UUID, nav_doc_id: Optional[str] = None) -> bool:
    """
    Insert a newly-created menu (with any children created alongside it,
    already nested in) as a single new node at the correct position in its
    application's tree - inside its parent menu's children, its module's
    children, or the synthetic default-module - without rebuilding or
    touching any sibling module or menu already in the tree.

    nav_doc_id selects which master navigation document this application's
    doc is excluded against / would be registered into on a fallback full
    build; defaults to MASTER_NAV_DOC_ID.

    Falls back to the full rebuild only when there's nowhere targeted to
    insert: no application document yet, or the intended parent (module or
    parent menu) isn't in the tree yet.

    Returns True on success, False otherwise (never raises).
    """
    try:
        from app.core.mongodb import get_mongodb

        db_mongo = await get_mongodb()
        if db_mongo is None:
            logger.warning("[Menu Sync] MongoDB not available, skipping menu add")
            return False

        menu = db.query(Menu).filter(Menu.id == menu_id).first()
        if not menu:
            logger.warning(f"[Menu Sync] Menu not found: {menu_id}")
            return False

        collection = db_mongo["menu_details"]
        master_doc_id = ObjectId(nav_doc_id or MASTER_NAV_DOC_ID)

        app_doc = await collection.find_one({
            "application_id": str(menu.application_id),
            "_id": {"$ne": master_doc_id}
        })
        if not app_doc:
            logger.info(f"[Menu Sync] No existing document for application {menu.application_id}, doing full build")
            return await sync_application_menus_to_mongodb(db, menu.application_id, nav_doc_id)

        # Build the new node - descendants created alongside it are already
        # committed in Postgres, so this nests them in via the normal recursion.
        all_menus = db.query(Menu).filter(
            Menu.application_id == menu.application_id,
            Menu.deleted_at.is_(None)
        ).all()
        menus_by_parent: Dict[Any, List[Menu]] = {}
        for m in all_menus:
            if m.parent_menu_id is not None:
                menus_by_parent.setdefault(m.parent_menu_id, []).append(m)
        menu_item = _build_menu_item(menu, menus_by_parent, menu.application_id)

        children = app_doc.get("children", [])

        if menu.parent_menu_id:
            parent_node = _find_node_by_id(children, "menu_id", str(menu.parent_menu_id))
            if parent_node is None:
                logger.info(f"[Menu Sync] Parent menu {menu.parent_menu_id} not found in tree, doing full rebuild")
                return await sync_application_menus_to_mongodb(db, menu.application_id, nav_doc_id)
            parent_node.setdefault("children", []).append(menu_item)
        else:
            target_module_id = str(menu.module_id) if menu.module_id else "default"
            module_node = _find_node_by_id(children, "module_id", target_module_id)
            if module_node is None:
                if menu.module_id:
                    logger.info(f"[Menu Sync] Module {menu.module_id} not found in tree, doing full rebuild")
                    return await sync_application_menus_to_mongodb(db, menu.application_id, nav_doc_id)
                # No module - create the synthetic default module holding just this menu.
                children.append({
                    "key": "default-module",
                    "name": "default-module",
                    "label": "Default Module",
                    "route": "",
                    "icon": "ri-folder-line",
                    "module_id": "default",
                    "application_id": str(menu.application_id),
                    "order_index": 999000,
                    "level": 2,
                    "is_active": True,
                    "access": [],
                    "children": [menu_item],
                })
            else:
                module_node.setdefault("children", []).append(menu_item)

        await collection.update_one(
            {"_id": app_doc["_id"]},
            {"$set": {"children": children, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        logger.info(f"[Menu Sync] Added new menu {menu_id} node (other modules/menus untouched)")
        return True

    except Exception as e:
        logger.error(f"[Menu Sync] Add menu failed for {menu_id}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def remove_application_from_mongodb(application_id: UUID, nav_doc_id: Optional[str] = None) -> bool:
    """
    Remove a deleted application's navigation document(s) from MongoDB and
    pull their references out of the master mainNavigation array (nav_doc_id,
    defaulting to MASTER_NAV_DOC_ID).

    Used by DELETE /applications - the rebuild sync can't handle this case
    because it skips applications that are deleted in PostgreSQL.
    Returns True on success, False otherwise (never raises).
    """
    try:
        from app.core.mongodb import get_mongodb

        db_mongo = await get_mongodb()
        if db_mongo is None:
            logger.warning("[Menu Sync] MongoDB not available, skipping application removal")
            return False

        collection = db_mongo["menu_details"]
        master_doc_id = ObjectId(nav_doc_id or MASTER_NAV_DOC_ID)
        now = datetime.now(timezone.utc).isoformat()

        doc_ids = []
        cursor = collection.find(
            {"application_id": str(application_id), "_id": {"$ne": master_doc_id}},
            {"_id": 1}
        )
        async for doc in cursor:
            doc_ids.append(doc["_id"])

        if doc_ids:
            await collection.update_one(
                {"_id": master_doc_id},
                {"$pull": {"mainNavigation": {"$in": doc_ids}},
                 "$set": {"updated_at": now}}
            )
            await collection.delete_many({"_id": {"$in": doc_ids}})
            logger.info(f"[Menu Sync] Removed {len(doc_ids)} navigation document(s) for application {application_id}")
        else:
            logger.info(f"[Menu Sync] No navigation documents found for application {application_id}")

        return True

    except Exception as e:
        logger.error(f"[Menu Sync] Failed to remove application {application_id} from MongoDB: {e}")
        return False
