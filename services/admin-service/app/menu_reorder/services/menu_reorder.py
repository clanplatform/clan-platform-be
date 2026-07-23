"""
Menu Reordering Services
Handles drag-and-drop reordering logic for menus and nested children
Automatically syncs changes to both PostgreSQL and MongoDB
"""
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List, Dict, Optional
from uuid import UUID
import logging

from app.menus.models.menu import Menu
from app.menu_reorder.schemas.menu_reorder import (
    MenuReorderItem, 
    MenuReorderRequest, 
    MenuReorderResponse,
    MenuBatchUpdateItem,
    MenuBatchUpdateRequest,
    MenuBatchUpdateResponse
)

logger = logging.getLogger(__name__)


class MenuReorderService:
    """Service for handling menu reordering operations"""

    @staticmethod
    async def sync_to_mongodb(db: Session, application_id: UUID, affected_module_ids: set = None):
        """
        Sync menu order changes to MongoDB for a specific application document.
        Thin wrapper - the actual implementation lives in
        app.menus.services.menu_sync (shared with the menu create routes).

        affected_module_ids is accepted for backward compatibility; the shared
        sync always rebuilds the full application document so no module can
        disappear from the navigation.
        """
        if affected_module_ids:
            logger.info(f"[MongoDB Sync] Affected modules: {affected_module_ids}")
        from app.menus.services.menu_sync import sync_application_menus_to_mongodb
        return await sync_application_menus_to_mongodb(db, application_id)

    @staticmethod
    def _cascade_to_descendants(db: Session, parent: Menu):
        """
        Keep descendants consistent with a moved menu: children always live in
        their parent's module and sit one level below it.
        """
        children = db.query(Menu).filter(
            Menu.parent_menu_id == parent.id,
            Menu.deleted_at.is_(None)
        ).all()
        for child in children:
            child.module_id = parent.module_id
            child.level = parent.level + 1
            MenuReorderService._cascade_to_descendants(db, child)

    @staticmethod
    async def reorder_menus(db: Session, reorder_data: MenuReorderRequest) -> MenuReorderResponse:
        """
        Reorder menus based on drag-and-drop action with automatic sibling reordering
        
        When a menu is moved, all sibling menus are automatically shifted to maintain
        sequential order_index values (1000, 2000, 3000, 4000...).
        
        Example:
        - Initial: [A:1000, B:2000, C:3000, D:4000] at indices [0,1,2,3]
        - Drag A from index 0 to index 3
        - Result: [B:1000, C:2000, D:3000, A:4000] at indices [0,1,2,3]
        
        Args:
            db: Database session
            reorder_data: Reorder request with menu items and new positions
            
        Returns:
            MenuReorderResponse with updated count and items
            
        Raises:
            HTTPException 404: If any menu not found
            HTTPException 400: If validation fails
        """
        try:
            # ✅ DETECT MODE: Module reordering vs Menu reordering
            is_module_reorder = all(
                item.menu_id is None and item.module_id is not None 
                for item in reorder_data.items
            )
            
            if is_module_reorder:
                logger.info(f"[Reorder] ========== MODULE REORDERING MODE ==========")
                logger.info(f"[Reorder] Application: {reorder_data.application_id}")
                logger.info(f"[Reorder] Modules to reorder: {len(reorder_data.items)}")
                
                # Import Module model
                from app.modules.models.module import Module as ModuleModel
                
                # ✅ AUTO-SHIFT LOGIC for single module reorder
                if len(reorder_data.items) == 1:
                    item = reorder_data.items[0]
                    
                    # Validate the module exists
                    module = db.query(ModuleModel).filter(
                        ModuleModel.id == item.module_id,
                        ModuleModel.application_id == reorder_data.application_id,
                        ModuleModel.is_deleted == False
                    ).first()
                    
                    if not module:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Module not found: {item.module_id}"
                        )
                    
                    logger.info(f"[Module Reorder] Single module reorder: '{module.label}'")
                    logger.info(f"[Module Reorder] Current order_index: {module.order_index}")
                    logger.info(f"[Module Reorder] New order_index: {item.order_index}")
                    
                    # Get all sibling modules (same application)
                    all_modules = db.query(ModuleModel).filter(
                        ModuleModel.application_id == reorder_data.application_id,
                        ModuleModel.is_deleted == False
                    ).order_by(ModuleModel.order_index).all()
                    
                    logger.info(f"[Module Reorder] Found {len(all_modules)} total modules")
                    
                    # Calculate old and new positions
                    old_index = (module.order_index // 1000) - 1
                    new_index = (item.order_index // 1000) - 1
                    
                    logger.info(f"[Module Reorder] Moving from array index {old_index} to {new_index}")
                    
                    # Remove the dragged module from list
                    modules_list = [m for m in all_modules if m.id != module.id]

                    # Insert the dragged module at the new position
                    # Clamp so non-1000-based order_index values can't land at a negative index
                    new_index = max(0, min(new_index, len(modules_list)))
                    modules_list.insert(new_index, module)
                    
                    # Reassign order_index to all modules sequentially
                    updated_count = 0
                    response_items = []
                    
                    for idx, mod in enumerate(modules_list):
                        new_order_index = (idx + 1) * 1000
                        old_order_index = mod.order_index
                        
                        if mod.order_index != new_order_index:
                            mod.order_index = new_order_index
                            updated_count += 1
                            logger.info(f"[Module Reorder] '{mod.label}': {old_order_index} → {new_order_index} (array index {idx})")
                        
                        # Add to response
                        response_items.append(MenuReorderItem(
                            menu_id=None,
                            module_id=mod.id,
                            order_index=mod.order_index,
                            parent_menu_id=None,
                            level=2
                        ))
                    
                    # Commit PostgreSQL changes
                    db.commit()
                    logger.info(f"[Module Reorder] ✅ Updated {updated_count} modules in PostgreSQL")
                    
                    # Sync to MongoDB (all modules affected)
                    affected_module_ids = {mod.id for mod in modules_list}
                    mongo_synced = await MenuReorderService.sync_to_mongodb(
                        db, 
                        reorder_data.application_id, 
                        affected_module_ids
                    )
                    
                    message = f"Successfully reordered {updated_count} modules (auto-shifted siblings)"
                    if mongo_synced:
                        message += " and synced to MongoDB"
                    
                    return MenuReorderResponse(
                        message=message,
                        updated_count=updated_count,
                        items=response_items
                    )
                
                # ✅ MULTI-MODULE REORDER: Update each module as specified
                else:
                    # Validate all modules exist and belong to the application
                    module_ids = [item.module_id for item in reorder_data.items]
                    modules = db.query(ModuleModel).filter(
                        ModuleModel.id.in_(module_ids),
                        ModuleModel.application_id == reorder_data.application_id,
                        ModuleModel.is_deleted == False
                    ).all()
                    
                    if len(modules) != len(module_ids):
                        found_ids = {module.id for module in modules}
                        missing_ids = set(module_ids) - found_ids
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Modules not found: {missing_ids}"
                        )
                    
                    # Create a map of module_id to module object
                    module_map: Dict[UUID, ModuleModel] = {module.id: module for module in modules}
                    
                    # Update each module's order_index
                    updated_count = 0
                    response_items = []
                    
                    for item in reorder_data.items:
                        module = module_map[item.module_id]
                        old_order = module.order_index
                        module.order_index = item.order_index
                        
                        updated_count += 1
                        logger.info(f"[Module Reorder] '{module.label}': {old_order} → {item.order_index}")
                        
                        # Add to response
                        response_items.append(MenuReorderItem(
                            menu_id=None,
                            module_id=module.id,
                            order_index=module.order_index,
                            parent_menu_id=None,
                            level=2  # Modules are always level 2
                        ))
                    
                    # Commit PostgreSQL changes
                    db.commit()
                    logger.info(f"[Module Reorder] ✅ Updated {updated_count} modules in PostgreSQL")
                    
                    # Sync to MongoDB (all modules affected)
                    affected_module_ids = set(module_ids)
                    mongo_synced = await MenuReorderService.sync_to_mongodb(
                        db, 
                        reorder_data.application_id, 
                        affected_module_ids
                    )
                    
                    message = f"Successfully reordered {updated_count} modules"
                    if mongo_synced:
                        message += " and synced to MongoDB"
                    
                    return MenuReorderResponse(
                        message=message,
                        updated_count=updated_count,
                        items=response_items
                    )
            
            # ✅ MENU REORDERING MODE (original logic)
            logger.info(f"[Reorder] ========== Starting reorder operation ==========")
            logger.info(f"[Reorder] Application: {reorder_data.application_id}")
            logger.info(f"[Reorder] Items to reorder: {len(reorder_data.items)}")
            
            # Validate all menus exist and belong to the application
            menu_ids = [item.menu_id for item in reorder_data.items]
            menus = db.query(Menu).filter(
                Menu.id.in_(menu_ids),
                Menu.application_id == reorder_data.application_id,
                Menu.deleted_at.is_(None)
            ).all()
            
            if len(menus) != len(menu_ids):
                found_ids = {menu.id for menu in menus}
                missing_ids = set(menu_ids) - found_ids
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Menus not found: {missing_ids}"
                )
            
            # Create a map of menu_id to menu object for quick lookup
            menu_map: Dict[UUID, Menu] = {menu.id: menu for menu in menus}
            
            # ✅ VALIDATION: Check if any parent_menu_id belongs to a different application
            parent_ids = [item.parent_menu_id for item in reorder_data.items if item.parent_menu_id is not None]
            
            if parent_ids:
                parent_menus = db.query(Menu).filter(
                    Menu.id.in_(parent_ids),
                    Menu.deleted_at.is_(None)
                ).all()
                
                # Check if all provided parent_menu_ids actually exist as menus
                found_parent_ids = {menu.id for menu in parent_menus}
                missing_parent_ids = set(parent_ids) - found_parent_ids
                
                if missing_parent_ids:
                    # Check if any of the missing IDs is actually the application ID
                    if reorder_data.application_id in missing_parent_ids:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Cannot set application ID as parent_menu_id. Use null for top-level menus."
                        )
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Parent menu(s) not found: {missing_parent_ids}"
                        )
                
                # Check if parent menus belong to the same application
                for parent_menu in parent_menus:
                    if parent_menu.application_id != reorder_data.application_id:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Could not move to another application"
                        )
            
            # ✅ VALIDATION: Check module_id constraints
            module_ids = [item.module_id for item in reorder_data.items if item.module_id is not None]
            
            if module_ids:
                # Verify all module_ids exist and belong to the same application
                from app.modules.models.module import Module
                modules = db.query(Module).filter(
                    Module.id.in_(module_ids),
                    Module.application_id == reorder_data.application_id,
                    Module.is_deleted == False  # ✅ Use is_deleted instead of deleted_at
                ).all()
                
                found_module_ids = {module.id for module in modules}
                missing_module_ids = set(module_ids) - found_module_ids
                
                if missing_module_ids:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Module(s) not found in application: {missing_module_ids}"
                    )
            
            # ✅ AUTO-SHIFT LOGIC: When one menu is moved, shift all siblings
            if len(reorder_data.items) == 1:
                item = reorder_data.items[0]
                menu = menu_map[item.menu_id]
                
                # ✅ Track original module_id before any changes
                original_module_id = menu.module_id
                
                logger.info(f"[Reorder] Single menu reorder detected: '{menu.label}'")
                logger.info(f"[Reorder] Current: parent={menu.parent_menu_id}, order_index={menu.order_index}, level={menu.level}, module_id={menu.module_id}")
                logger.info(f"[Reorder] New: parent={item.parent_menu_id}, order_index={item.order_index}, level={item.level}, module_id={item.module_id}")
                
                # Check if parent changed (moving between parents)
                parent_changed = menu.parent_menu_id != item.parent_menu_id
                
                if parent_changed:
                    logger.info(f"[Reorder] 🔄 Moving to different parent")
                    
                    # Step 1: Remove from old parent's children and reorder them
                    old_siblings = db.query(Menu).filter(
                        Menu.application_id == reorder_data.application_id,
                        Menu.parent_menu_id == menu.parent_menu_id,
                        Menu.module_id == menu.module_id,  # ✅ Include module_id in sibling filtering
                        Menu.id != menu.id,  # Exclude the dragged menu
                        Menu.deleted_at.is_(None)
                    ).order_by(Menu.order_index).all()
                    
                    logger.info(f"[Reorder] Reordering {len(old_siblings)} siblings in old parent (module: {menu.module_id})")
                    for idx, sibling in enumerate(old_siblings):
                        new_order_index = (idx + 1) * 1000
                        if sibling.order_index != new_order_index:
                            old_order = sibling.order_index
                            sibling.order_index = new_order_index
                            logger.info(f"[Reorder]   Old parent sibling '{sibling.label}': {old_order} → {new_order_index}")
                    
                    # Step 2: Update the dragged menu's parent, module, and level
                    menu.parent_menu_id = item.parent_menu_id

                    # ✅ Destination module: a menu always lives in its parent's module.
                    # Moving under a parent menu inherits that parent's module;
                    # only root-level moves use the client-supplied module_id.
                    new_parent = None
                    if item.parent_menu_id is not None:
                        new_parent = db.query(Menu).filter(Menu.id == item.parent_menu_id).first()
                        if new_parent and new_parent.module_id != menu.module_id:
                            if item.module_id is not None and item.module_id != new_parent.module_id:
                                logger.warning(
                                    f"[Reorder] Ignoring module_id {item.module_id}: "
                                    f"parent '{new_parent.label}' belongs to module {new_parent.module_id}"
                                )
                            logger.info(f"[Reorder] Moving from module {menu.module_id} to parent's module {new_parent.module_id}")
                            menu.module_id = new_parent.module_id
                    elif item.module_id is not None and item.module_id != menu.module_id:
                        logger.info(f"[Reorder] Moving from module {menu.module_id} to module {item.module_id}")
                        menu.module_id = item.module_id

                    # Auto-calculate level based on new parent
                    if item.level is not None:
                        menu.level = item.level
                        logger.info(f"[Reorder] Using provided level: {item.level}")
                    elif item.parent_menu_id is None:
                        # Root menus: level 3 under a module, level 2 directly under application
                        menu.level = 3 if menu.module_id else 2
                        logger.info(f"[Reorder] Moving to root level: {menu.level} (module: {menu.module_id})")
                    else:
                        if new_parent:
                            menu.level = new_parent.level + 1
                            logger.info(f"[Reorder] Auto-calculated level: {menu.level} (parent level: {new_parent.level})")

                    # ✅ Descendants follow the moved menu: same module, levels shifted
                    MenuReorderService._cascade_to_descendants(db, menu)
                    
                    # Step 3: Get all siblings in new parent (including the dragged menu)
                    # ✅ Filter by module_id to ensure reordering within the correct module
                    new_siblings = db.query(Menu).filter(
                        Menu.application_id == reorder_data.application_id,
                        Menu.parent_menu_id == item.parent_menu_id,
                        Menu.module_id == menu.module_id,  # ✅ Use updated module_id
                        Menu.id != menu.id,  # Exclude dragged menu for now
                        Menu.deleted_at.is_(None)
                    ).order_by(Menu.order_index).all()
                    
                    logger.info(f"[Reorder] Found {len(new_siblings)} siblings in new parent (module: {menu.module_id})")
                    
                    # Calculate new position
                    new_index = (item.order_index // 1000) - 1
                    # Clamp so non-1000-based order_index values can't land at a negative index
                    new_index = max(0, min(new_index, len(new_siblings)))
                    logger.info(f"[Reorder] Inserting at index {new_index} in new parent")

                    # Insert the dragged menu at the new position
                    new_siblings.insert(new_index, menu)
                    
                    # Reassign order_index to all siblings in new parent
                    updated_count = len(old_siblings) + len(new_siblings)
                    response_items = []
                    
                    logger.info(f"[Reorder] Reordering {len(new_siblings)} menus in new parent")
                    for idx, sibling in enumerate(new_siblings):
                        new_order_index = (idx + 1) * 1000
                        old_order_index = sibling.order_index
                        
                        if sibling.order_index != new_order_index:
                            sibling.order_index = new_order_index
                            logger.info(f"[Reorder]   New parent sibling '{sibling.label}': {old_order_index} → {new_order_index} (index {idx})")
                        
                        # Add to response items
                        response_items.append(MenuReorderItem(
                            menu_id=sibling.id,
                            order_index=sibling.order_index,
                            parent_menu_id=sibling.parent_menu_id,
                            level=sibling.level,
                            module_id=sibling.module_id
                        ))
                    
                else:
                    # Same parent - just reorder within siblings
                    logger.info(f"[Reorder] Reordering within same parent")
                    
                    # ✅ Module changes only apply to root menus: a nested menu always
                    # lives in its parent's module, so a different module_id with an
                    # unchanged parent would corrupt the hierarchy
                    if item.module_id is not None and item.module_id != menu.module_id:
                        if item.parent_menu_id is None:
                            old_module_id = menu.module_id
                            menu.module_id = item.module_id
                            logger.info(f"[Reorder] Moving from module {old_module_id} to module {item.module_id}")
                        else:
                            logger.warning(
                                f"[Reorder] Ignoring module_id {item.module_id} for '{menu.label}': "
                                f"nested menus inherit their parent's module"
                            )
                    
                    # ✅ ALWAYS auto-calculate level based on parent, even if parent doesn't change
                    # This ensures level is always correct based on hierarchy
                    if item.parent_menu_id is None:
                        # Root menus: level 3 under a module, level 2 directly under application
                        menu.level = 3 if menu.module_id else 2
                        logger.info(f"[Reorder] Auto-calculated level: {menu.level} (module: {menu.module_id})")
                    else:
                        # Get parent's level to calculate child level
                        parent = db.query(Menu).filter(Menu.id == item.parent_menu_id).first()
                        if parent:
                            menu.level = parent.level + 1
                            logger.info(f"[Reorder] Auto-calculated level: {menu.level} (parent level: {parent.level})")
                        elif item.level is not None:
                            # Fallback to provided level if parent not found
                            menu.level = item.level
                            logger.info(f"[Reorder] Using provided level: {item.level}")

                    # ✅ Descendants follow the menu: same module, levels shifted
                    MenuReorderService._cascade_to_descendants(db, menu)

                    # Get all sibling menus (same parent, same module, same application)
                    # ✅ Include module_id in sibling filtering
                    siblings = db.query(Menu).filter(
                        Menu.application_id == reorder_data.application_id,
                        Menu.parent_menu_id == item.parent_menu_id,
                        Menu.module_id == menu.module_id,  # ✅ Use updated module_id
                        Menu.deleted_at.is_(None)
                    ).order_by(Menu.order_index).all()
                    
                    logger.info(f"[Reorder] Found {len(siblings)} total siblings (including dragged menu) in module {menu.module_id}")
                    
                    # Calculate old and new positions
                    old_index = (menu.order_index // 1000) - 1
                    new_index = (item.order_index // 1000) - 1
                    
                    logger.info(f"[Reorder] Moving from MongoDB index {old_index} to {new_index}")
                    
                    # Remove the dragged menu from siblings list
                    siblings = [s for s in siblings if s.id != menu.id]

                    # Insert the dragged menu at the new position
                    # Clamp so non-1000-based order_index values can't land at a negative index
                    new_index = max(0, min(new_index, len(siblings)))
                    siblings.insert(new_index, menu)
                    
                    # Reassign order_index to all siblings sequentially
                    updated_count = 0
                    response_items = []
                    
                    for idx, sibling in enumerate(siblings):
                        new_order_index = (idx + 1) * 1000
                        old_order_index = sibling.order_index
                        
                        if sibling.order_index != new_order_index:
                            sibling.order_index = new_order_index
                            updated_count += 1
                            logger.info(f"[Reorder] '{sibling.label}': {old_order_index} → {new_order_index} (index {idx})")
                        
                        # Add to response items
                        response_items.append(MenuReorderItem(
                            menu_id=sibling.id,
                            order_index=sibling.order_index,
                            parent_menu_id=sibling.parent_menu_id,
                            level=sibling.level,
                            module_id=sibling.module_id
                        ))
                
                # Commit PostgreSQL changes
                db.commit()
                logger.info(f"[Reorder] ✅ Updated {updated_count} menus in PostgreSQL")
                
                # Sync to MongoDB with affected modules only
                affected_module_ids = set()
                
                # ✅ Always include the original module (source) if it's different from final module
                if original_module_id:
                    affected_module_ids.add(original_module_id)
                
                # ✅ Use the correct sibling list based on whether parent changed
                if parent_changed:
                    # Parent changed: use new_siblings (already defined above)
                    for sibling in new_siblings:
                        if sibling.module_id:
                            affected_module_ids.add(sibling.module_id)
                else:
                    # Same parent: use siblings (defined in the else block)
                    for sibling in siblings:
                        if sibling.module_id:
                            affected_module_ids.add(sibling.module_id)
                
                # ✅ Include destination module if menu moved between modules
                if item.module_id is not None and item.module_id != original_module_id:
                    affected_module_ids.add(item.module_id)
                    logger.info(f"[Reorder] Menu moved between modules: {original_module_id} → {item.module_id}")
                
                logger.info(f"[Reorder] Affected modules for sync: {sorted(affected_module_ids)}")
                
                mongo_synced = await MenuReorderService.sync_to_mongodb(db, reorder_data.application_id, affected_module_ids)
                
                message = f"Successfully reordered {updated_count} menus (auto-shifted siblings)"
                if mongo_synced:
                    message += " and synced to MongoDB"
                
                return MenuReorderResponse(
                    message=message,
                    updated_count=updated_count,
                    items=response_items
                )
            
            # ✅ MULTI-MENU REORDER: Update each menu as specified
            else:
                logger.info(f"[Reorder] Multi-menu reorder: {len(reorder_data.items)} menus")
                
                # ✅ Track original module IDs before any changes
                original_module_ids = {}
                for item in reorder_data.items:
                    menu = menu_map[item.menu_id]
                    original_module_ids[item.menu_id] = menu.module_id
                
                updated_count = 0
                for item in reorder_data.items:
                    menu = menu_map[item.menu_id]
                    
                    old_order = menu.order_index
                    menu.order_index = item.order_index
                    
                    # Update level if provided
                    if item.level is not None:
                        menu.level = item.level
                    
                    # Update parent if changed
                    if menu.parent_menu_id != item.parent_menu_id:
                        menu.parent_menu_id = item.parent_menu_id

                        # Auto-calculate level when the client didn't send one
                        if item.level is None:
                            if item.parent_menu_id is None:
                                # Root menus: level 3 under a module, level 2 directly under application
                                effective_module_id = item.module_id if item.module_id is not None else menu.module_id
                                menu.level = 3 if effective_module_id else 2
                            else:
                                parent = menu_map.get(item.parent_menu_id) or db.query(Menu).filter(
                                    Menu.id == item.parent_menu_id
                                ).first()
                                if parent:
                                    menu.level = parent.level + 1

                    # ✅ Update module_id if provided (allows moving between modules)
                    if item.module_id is not None and menu.module_id != item.module_id:
                        old_module_id = menu.module_id
                        menu.module_id = item.module_id
                        logger.info(f"[Reorder] Menu '{menu.label}': moved from module {old_module_id} to module {item.module_id}")

                    # ✅ Descendants follow the menu: same module, levels shifted
                    MenuReorderService._cascade_to_descendants(db, menu)

                    updated_count += 1
                    logger.info(f"[Reorder] '{menu.label}': {old_order} → {item.order_index} (module: {menu.module_id})")
                
                # Commit PostgreSQL changes
                db.commit()
                logger.info(f"[Reorder] ✅ Updated {updated_count} menus in PostgreSQL")
                
                # Sync to MongoDB with affected modules only
                affected_module_ids = set()
                
                # ✅ Include all original modules (source modules)
                for original_module_id in original_module_ids.values():
                    if original_module_id:
                        affected_module_ids.add(original_module_id)
                
                # ✅ Include all current modules (destination modules)
                for item in reorder_data.items:
                    menu = menu_map[item.menu_id]
                    if menu.module_id:
                        affected_module_ids.add(menu.module_id)
                
                logger.info(f"[Reorder] Affected modules for sync: {sorted(affected_module_ids)}")
                
                mongo_synced = await MenuReorderService.sync_to_mongodb(db, reorder_data.application_id, affected_module_ids)
                
                message = f"Successfully reordered {updated_count} menus"
                if mongo_synced:
                    message += " and synced to MongoDB"
                
                return MenuReorderResponse(
                    message=message,
                    updated_count=updated_count,
                    items=reorder_data.items
                )
            
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"[Reorder] ❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to reorder menus: {str(e)}"
            )

    @staticmethod
    async def reorder_children(
        db: Session,
        parent_menu_id: UUID,
        application_id: UUID,
        children_order: List[UUID]
    ) -> MenuReorderResponse:
        """
        Reorder children of a specific parent menu
        
        Args:
            db: Database session
            parent_menu_id: Parent menu ID
            application_id: Application ID
            children_order: List of child menu IDs in desired order
            
        Returns:
            MenuReorderResponse with updated count
        """
        try:
            # Get all children of the parent
            children = db.query(Menu).filter(
                Menu.parent_menu_id == parent_menu_id,
                Menu.application_id == application_id,
                Menu.deleted_at.is_(None)
            ).all()
            
            # Create map of menu_id to menu
            children_map = {child.id: child for child in children}
            
            # ✅ Track original module IDs before any changes
            original_module_ids = set()
            for child in children:
                if child.module_id:
                    original_module_ids.add(child.module_id)
            
            # Validate all provided IDs exist
            for child_id in children_order:
                if child_id not in children_map:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Child menu {child_id} not found under parent {parent_menu_id}"
                    )
            
            # Update order_index for each child (1000-based, matching the reorder convention)
            updated_count = 0
            for index, child_id in enumerate(children_order):
                child = children_map[child_id]
                child.order_index = (index + 1) * 1000
                updated_count += 1
            
            db.commit()
            
            # Sync to MongoDB with affected modules only
            affected_module_ids = set()
            
            # ✅ Include all original modules (source modules)
            affected_module_ids.update(original_module_ids)
            
            # ✅ Include current modules (destination modules)
            for child_id in children_order:
                child = children_map[child_id]
                if child.module_id:
                    affected_module_ids.add(child.module_id)
            
            logger.info(f"[Reorder Children] Affected modules for sync: {sorted(affected_module_ids)}")
            
            await MenuReorderService.sync_to_mongodb(db, application_id, affected_module_ids)
            
            # Create response items
            items = [
                MenuReorderItem(
                    menu_id=child_id,
                    order_index=(index + 1) * 1000,
                    parent_menu_id=parent_menu_id,
                    module_id=children_map[child_id].module_id
                )
                for index, child_id in enumerate(children_order)
            ]
            
            return MenuReorderResponse(
                message=f"Successfully reordered {updated_count} children and synced to MongoDB",
                updated_count=updated_count,
                items=items
            )
            
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error reordering children: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to reorder children: {str(e)}"
            )

    @staticmethod
    async def batch_update_menus(db: Session, update_data: MenuBatchUpdateRequest) -> MenuBatchUpdateResponse:
        """
        Batch update menus with both reordering and field updates
        
        This method handles:
        1. Reordering (order_index, parent_menu_id)
        2. Field updates (name, label, icon, route, etc.)
        3. Access permissions updates
        4. Navigation/UI field updates (key, badge, section_title, etc.)
        5. Auto-sync to MongoDB
        
        Args:
            db: Database session
            update_data: Batch update request with menu items and updates
            
        Returns:
            MenuBatchUpdateResponse with updated count and items
            
        Raises:
            HTTPException 404: If any menu not found
            HTTPException 400: If validation fails
        """
        try:
            # Validate all menus exist and belong to the application
            menu_ids = [item.menu_id for item in update_data.items]
            menus = db.query(Menu).filter(
                Menu.id.in_(menu_ids),
                Menu.application_id == update_data.application_id,
                Menu.deleted_at.is_(None)
            ).all()
            
            if len(menus) != len(menu_ids):
                found_ids = {menu.id for menu in menus}
                missing_ids = set(menu_ids) - found_ids
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Menus not found: {missing_ids}"
                )
            
            # Create a map of menu_id to menu object for quick lookup
            menu_map: Dict[UUID, Menu] = {menu.id: menu for menu in menus}
            
            # ✅ VALIDATION: Check module_id constraints for batch updates
            module_ids = []
            for item in update_data.items:
                if hasattr(item, 'module_id') and item.module_id is not None:
                    module_ids.append(item.module_id)
            
            if module_ids:
                # Verify all module_ids exist and belong to the same application
                from app.modules.models.module import Module
                modules = db.query(Module).filter(
                    Module.id.in_(module_ids),
                    Module.application_id == update_data.application_id,
                    Module.is_deleted == False  # ✅ Use is_deleted instead of deleted_at
                ).all()
                
                found_module_ids = {module.id for module in modules}
                missing_module_ids = set(module_ids) - found_module_ids
                
                if missing_module_ids:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Module(s) not found in application: {missing_module_ids}"
                    )
            
            # ✅ Track original module IDs before any changes
            original_module_ids = {}
            for item in update_data.items:
                menu = menu_map[item.menu_id]
                original_module_ids[item.menu_id] = menu.module_id
            
            # Update each menu
            updated_count = 0
            for item in update_data.items:
                menu = menu_map[item.menu_id]
                
                # Get update data excluding None values and menu_id
                update_dict = item.model_dump(exclude_unset=True, exclude={'menu_id'})
                
                # Track if order changed for MongoDB sync
                order_changed = False
                
                # Update each field
                for field, value in update_dict.items():
                    if field == 'children':
                        # Children are stored in MongoDB, skip for PostgreSQL
                        continue
                    
                    if field in ['order_index', 'parent_menu_id']:
                        order_changed = True
                    
                    # Handle parent_menu_id change - update level
                    if field == 'parent_menu_id' and value != menu.parent_menu_id:
                        if value is None:
                            # Root menus: level 3 under a module, level 2 directly under application
                            effective_module_id = update_dict.get('module_id', menu.module_id)
                            menu.level = 3 if effective_module_id else 2
                        else:
                            parent_menu = menu_map.get(value)
                            if parent_menu:
                                menu.level = parent_menu.level + 1
                            else:
                                # Parent not in current batch, query it
                                parent_menu = db.query(Menu).filter(
                                    Menu.id == value
                                ).first()
                                if parent_menu:
                                    menu.level = parent_menu.level + 1
                    
                    # Handle access field (ensure it's a list)
                    if field == 'access' and value is not None:
                        if isinstance(value, str):
                            value = [value.lower()]
                        elif isinstance(value, list):
                            value = [item.lower() if isinstance(item, str) else item for item in value]
                    
                    # Set the attribute if it exists on the model
                    if hasattr(menu, field):
                        setattr(menu, field, value)
                    else:
                        logger.warning(f"Menu model has no attribute '{field}', skipping")

                # ✅ Descendants follow when the menu's module or parent changed
                if menu.module_id != original_module_ids[item.menu_id] or 'parent_menu_id' in update_dict:
                    MenuReorderService._cascade_to_descendants(db, menu)

                updated_count += 1
            
            # Commit PostgreSQL changes
            db.commit()
            
            logger.info(f"✅ Batch updated {updated_count} menus in PostgreSQL for application {update_data.application_id}")
            
            # Sync to MongoDB with affected modules only
            affected_module_ids = set()
            
            # ✅ Include all original modules (source modules)
            for original_module_id in original_module_ids.values():
                if original_module_id:
                    affected_module_ids.add(original_module_id)
            
            # ✅ Include all current modules (destination modules)
            for item in update_data.items:
                menu = menu_map[item.menu_id]
                if menu.module_id:
                    affected_module_ids.add(menu.module_id)
            
            logger.info(f"[Batch Update] Affected modules for sync: {sorted(affected_module_ids)}")
            
            mongo_synced = await MenuReorderService.sync_to_mongodb(db, update_data.application_id, affected_module_ids)
            
            message = f"Successfully updated {updated_count} menus in PostgreSQL"
            if mongo_synced:
                message += " and synced to MongoDB"
            else:
                message += " (MongoDB sync skipped)"
            
            return MenuBatchUpdateResponse(
                message=message,
                updated_count=updated_count,
                items=update_data.items
            )
            
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Error batch updating menus: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to batch update menus: {str(e)}"
            )
