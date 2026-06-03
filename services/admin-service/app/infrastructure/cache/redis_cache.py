"""
Redis caching layer
"""
import json
import redis
from typing import Any, Optional
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class RedisCache:
    """Redis cache client wrapper"""
    
    def __init__(self):
        self.client: Optional[redis.Redis] = None
        self._connect()
    
    def _connect(self):
        """Establish Redis connection"""
        try:
            self.client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.client.ping()
            logger.info("Redis connection established successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.client = None
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found or error
        """
        if not self.client:
            return None
        
        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Redis GET error for key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache with optional TTL.
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds (optional)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            return False
        
        try:
            serialized_value = json.dumps(value)
            if ttl:
                self.client.setex(key, ttl, serialized_value)
            else:
                self.client.set(key, serialized_value)
            return True
        except Exception as e:
            logger.error(f"Redis SET error for key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete a key from cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            return False
        
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis DELETE error for key {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> bool:
        """
        Delete all keys matching a pattern.
        
        Args:
            pattern: Key pattern (e.g., "domains:list:*")
            
        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            return False
        
        try:
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Redis DELETE_PATTERN error for pattern {pattern}: {e}")
            return False
    
    def cache_domain(self, domain_id: str, domain_data: dict, ttl: Optional[int] = None) -> bool:
        """
        Cache a domain object.
        
        Args:
            domain_id: Domain UUID
            domain_data: Domain data dictionary
            ttl: Time to live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        return self.set(f"domain:{domain_id}", domain_data, ttl)
    
    def get_cached_domain(self, domain_id: str) -> Optional[dict]:
        """
        Get a cached domain object.
        
        Args:
            domain_id: Domain UUID
            
        Returns:
            Domain data dictionary or None
        """
        return self.get(f"domain:{domain_id}")
    
    def close(self):
        """Close Redis connection"""
        if self.client:
            try:
                self.client.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")


# Global Redis cache instance
redis_cache = RedisCache()
