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
from typing import Any, Dict, List
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


async def sync_application_menus_to_mongodb(db: Session, application_id: UUID) -> bool:
    """
    Rebuild the application's menu_details document from PostgreSQL and
    upsert it into MongoDB. Also ensures the document is referenced from the
    master mainNavigation array and backfills mongo_id on the menus rows.

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
        master_doc_id = ObjectId(MASTER_NAV_DOC_ID)
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
