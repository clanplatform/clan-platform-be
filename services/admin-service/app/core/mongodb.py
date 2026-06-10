"""
MongoDB connection and configuration for Admin Service
Provides async MongoDB client using Motor
"""
import os
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)

class MongoDB:
    """MongoDB connection manager"""

    def __init__(self, enabled: bool = None, url: str = None, database_name: str = None):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        # Allow initialization with parameters or fall back to environment variables
        self.url: str = url if url is not None else os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        self.database_name: str = database_name if database_name is not None else os.getenv("MONGODB_DATABASE", "admin_service")
        
        # Enable MongoDB by default (can be disabled via MONGODB_ENABLED=false)
        if enabled is not None:
            self.enabled = enabled
        else:
            self.enabled = os.getenv("MONGODB_ENABLED", "true").lower() == "true"
        
    async def connect(self) -> bool:
        """Connect to MongoDB"""
        if not self.enabled:
            logger.info("MongoDB is disabled")
            return False

        try:
            print(f"[MongoDB] Connecting to {self.url}, database: {self.database_name}")
            logger.info(f"Connecting to MongoDB at {self.url}")
            self.client = AsyncIOMotorClient(
                self.url,
                serverSelectionTimeoutMS=10000,  # 10 second timeout
                connectTimeoutMS=10000,
                socketTimeoutMS=10000
            )

            print("[MongoDB] Client created, testing connection...")
            # Test connection
            await self.client.admin.command('ping')
            print("[MongoDB] Ping successful")

            # Get database
            self.db = self.client[self.database_name]

            # List collections to verify database access
            collections = await self.db.list_collection_names()
            print(f"[MongoDB] Connected successfully. Collections: {collections}")
            logger.info(f"Connected to MongoDB database: {self.database_name}")
            return True

        except Exception as e:
            print(f"[MongoDB] Connection failed: {e}")
            logger.error(f"Failed to connect to MongoDB: {e}")
            import traceback
            traceback.print_exc()
            self.client = None
            self.db = None
            return False
    
    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            logger.info("Disconnected from MongoDB")
    
    def get_database(self) -> Optional[AsyncIOMotorDatabase]:
        """Get MongoDB database instance"""
        return self.db
    
    def is_connected(self) -> bool:
        """Check if MongoDB is connected"""
        return self.db is not None

# Global MongoDB instance
mongodb = MongoDB()

async def get_mongodb() -> Optional[AsyncIOMotorDatabase]:
    """Dependency for getting MongoDB database"""
    if not mongodb.is_connected():
        await mongodb.connect()
    return mongodb.get_database()

