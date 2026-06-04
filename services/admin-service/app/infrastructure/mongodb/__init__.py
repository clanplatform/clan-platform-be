"""MongoDB infrastructure package"""
from .mongodb_admin import mongodb_client, get_mongodb, MongoDBadmin

__all__ = ["mongodb_client", "get_mongodb", "MongoDBadmin"]
