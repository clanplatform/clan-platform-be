"""
Menu Cleanup Service

Handles permanent deletion of soft-deleted menus after a retention period.
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.menus.models.menu import Menu
from app.infrastructure.mongodb.mongodb_admin import get_mongodb
from app.core.config import settings
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)


class MenuCleanupService:
    """Service for cleaning up soft-deleted menus after retention period"""
    
    def __init__(self, retention_days: int = None):
        """
        Initialize cleanup service
        
        Args:
            retention_days: Number of days to keep soft-deleted records before permanent deletion
                          If None, uses default of 30 days
        """
        self.retention_days = retention_days or 30  # Default to 30 days
        logger.info(f"[Menu Cleanup] Initialized with {self.retention_days} days retention period")
    
    async def cleanup_old_deleted_menus(self, db: Session) -> dict:
        """
        Permanently delete menus that have been soft-deleted for longer than retention period
        
        Args:
            db: Database session
            
        Returns:
            Dictionary with cleanup statistics
        """
        try:
            # Calculate cutoff date
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
            
            logger.info(f"[Menu Cleanup] Starting cleanup for menus deleted before {cutoff_date}")
            
            # Find menus that are soft-deleted and past retention period
            menus_to_delete = db.query(Menu).filter(
                and_(
                    Menu.is_active == False,
                    Menu.deleted_at.isnot(None),
                    Menu.deleted_at < cutoff_date
                )
            ).all()
            
            if not menus_to_delete:
                logger.info("[Menu Cleanup] No menus found for cleanup")
                return {
                    "success": True,
                    "deleted_count": 0,
                    "cutoff_date": cutoff_date.isoformat(),
                    "message": "No menus to clean up"
                }
            
            logger.info(f"[Menu Cleanup] Found {len(menus_to_delete)} menus to permanently delete")
            
            # Collect menu IDs and mongo_ids for cleanup
            menu_ids = []
            mongo_ids = []
            
            for menu in menus_to_delete:
                menu_ids.append(str(menu.id))
                if menu.mongo_id:
                    mongo_ids.append(menu.mongo_id)
                logger.info(f"[Menu Cleanup]   - {menu.name} (ID: {menu.id}, deleted: {menu.deleted_at})")
            
            # Delete from MongoDB if mongo_ids exist
            mongo_deleted_count = 0
            if mongo_ids:
                try:
                    db_mongo = await get_mongodb()
                    if db_mongo is not None:
                        # Delete menu detail documents
                        result = await db_mongo.menu_details.delete_many({
                            "_id": {"$in": [ObjectId(mid) for mid in mongo_ids if len(mid) == 24]}
                        })
                        mongo_deleted_count = result.deleted_count
                        logger.info(f"[Menu Cleanup] Deleted {mongo_deleted_count} documents from MongoDB")
                except Exception as e:
                    logger.error(f"[Menu Cleanup] Error deleting from MongoDB: {e}")
            
            # Permanently delete from PostgreSQL
            deleted_count = 0
            for menu in menus_to_delete:
                db.delete(menu)
                deleted_count += 1
            
            db.commit()
            
            logger.info(f"[Menu Cleanup] ✅ Successfully deleted {deleted_count} menus from PostgreSQL")
            
            return {
                "success": True,
                "deleted_count": deleted_count,
                "mongo_deleted_count": mongo_deleted_count,
                "cutoff_date": cutoff_date.isoformat(),
                "retention_days": self.retention_days,
                "menu_ids": menu_ids,
                "message": f"Permanently deleted {deleted_count} menus older than {self.retention_days} days"
            }
            
        except Exception as e:
            logger.error(f"[Menu Cleanup] Error during cleanup: {e}")
            import traceback
            traceback.print_exc()
            db.rollback()
            return {
                "success": False,
                "error": str(e),
                "message": "Cleanup failed"
            }
    
    async def get_cleanup_preview(self, db: Session) -> dict:
        """
        Preview menus that will be deleted in next cleanup without actually deleting them
        
        Args:
            db: Database session
            
        Returns:
            Dictionary with preview information
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
            
            menus_to_delete = db.query(Menu).filter(
                and_(
                    Menu.is_active == False,
                    Menu.deleted_at.isnot(None),
                    Menu.deleted_at < cutoff_date
                )
            ).all()
            
            preview_list = []
            for menu in menus_to_delete:
                preview_list.append({
                    "id": str(menu.id),
                    "name": menu.name,
                    "label": menu.label,
                    "deleted_at": menu.deleted_at.isoformat(),
                    "days_since_deletion": (datetime.now(timezone.utc) - menu.deleted_at).days
                })
            
            return {
                "count": len(menus_to_delete),
                "cutoff_date": cutoff_date.isoformat(),
                "retention_days": self.retention_days,
                "menus": preview_list
            }
            
        except Exception as e:
            logger.error(f"[Menu Cleanup] Error getting preview: {e}")
            return {
                "count": 0,
                "error": str(e)
            }


# Global instance - uses MENU_RETENTION_DAYS from settings
menu_cleanup_service = MenuCleanupService()
