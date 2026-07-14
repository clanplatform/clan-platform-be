from typing import Dict, List, Optional, Any
from motor.motor_asyncio import AsyncIOMotorCollection
from app.core.mongodb import mongodb
from bson import ObjectId
from datetime import datetime

class BaseMongoService:
    """Base service class for MongoDB operations"""
    
    def __init__(self, collection_name: str):
        self.collection_name = collection_name
    
    async def get_collection(self) -> AsyncIOMotorCollection:
        """Get MongoDB collection"""
        try:
            if not mongodb.client:
                connected = await mongodb.connect()
                if not connected:
                    raise Exception("MongoDB connection failed")
            
            db = mongodb.client[mongodb.database_name]
            return db[self.collection_name]
        except Exception as e:
            print(f"MongoDB connection error: {str(e)}")
            raise Exception(f"MongoDB not available: {str(e)}")
    
    async def create(self, data: Dict[str, Any]) -> str:
        """Create a new document"""
        collection = await self.get_collection()
        result = await collection.insert_one(data)
        return str(result.inserted_id)
    
    async def get_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get document by ObjectId"""
        collection = await self.get_collection()
        doc = await collection.find_one({"_id": ObjectId(doc_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
    
    async def update_by_id(self, doc_id: str, update_data: Dict[str, Any]) -> bool:
        """Update document by ObjectId"""
        collection = await self.get_collection()
        update_data["updated_at"] = datetime.utcnow()
        result = await collection.update_one(
            {"_id": ObjectId(doc_id)},
            {"$set": update_data}
        )
        return result.modified_count > 0
    
    async def delete_by_id(self, doc_id: str) -> bool:
        """Delete document by ObjectId"""
        collection = await self.get_collection()
        result = await collection.delete_one({"_id": ObjectId(doc_id)})
        return result.deleted_count > 0
    
    async def soft_delete_by_id(self, doc_id: str) -> bool:
        """Soft delete document by ObjectId"""
        collection = await self.get_collection()
        result = await collection.update_one(
            {"_id": ObjectId(doc_id)},
            {"$set": {
                "is_active": False,
                "updated_at": datetime.utcnow()
            }}
        )
        return result.modified_count > 0
    
    async def find(self, query: Dict[str, Any], limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Find documents by query"""
        collection = await self.get_collection()
        cursor = collection.find(query)
        
        if limit:
            cursor = cursor.limit(limit)
        
        docs = await cursor.to_list(length=None)
        for doc in docs:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
        return docs
    
    async def count(self, query: Dict[str, Any]) -> int:
        """Count documents by query"""
        collection = await self.get_collection()
        return await collection.count_documents(query)
    
    async def aggregate(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute aggregation pipeline"""
        collection = await self.get_collection()
        cursor = collection.aggregate(pipeline)
        docs = await cursor.to_list(length=None)
        
        for doc in docs:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
        return docs