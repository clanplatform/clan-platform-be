"""
MongoDB client and connection management
"""
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from typing import Optional
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class MongoDBadmin:
    """MongoDB client wrapper"""
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.sync_client: Optional[MongoClient] = None
        self.db = None
    
    def connect(self):
        """Establish MongoDB connection"""
        try:
            # Async client for async operations
            self.client = AsyncIOMotorClient(
                settings.MONGODB_URL,
                serverSelectionTimeoutMS=5000
            )
            
            # Sync client for sync operations
            self.sync_client = MongoClient(
                settings.MONGODB_URL,
                serverSelectionTimeoutMS=5000
            )
            
            # Get database
            self.db = self.client[settings.MONGODB_DB_NAME]
            
            # Test connection
            self.sync_client.admin.command('ping')
            logger.info("MongoDB connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            self.client = None
            self.sync_client = None
            self.db = None
    
    def get_database(self):
        """Get the MongoDB database instance"""
        if not self.db:
            self.connect()
        return self.db
    
    def close(self):
        """Close MongoDB connection"""
        if self.client:
            try:
                self.client.close()
                logger.info("MongoDB async client closed")
            except Exception as e:
                logger.error(f"Error closing MongoDB async client: {e}")
        
        if self.sync_client:
            try:
                self.sync_client.close()
                logger.info("MongoDB sync client closed")
            except Exception as e:
                logger.error(f"Error closing MongoDB sync client: {e}")


# Global MongoDB client instance
mongodb_client = MongoDBadmin()


def get_mongodb():
    """
    Dependency to get MongoDB database instance.
    Used in FastAPI route handlers.
    """
    return mongodb_client.get_database()
