import json
import redis
from typing import Any, Dict, List, Optional, Union
from datetime import timedelta
from app.core.config import settings

class RedisCache:
    """
    Redis caching service for hierarchical data caching.
    Implements caching for Client -> Domain -> Application hierarchy.
    """
    
    def __init__(self):
        self.redis_client = None
        self._connect()
    
    def _connect(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.Redis(
                host=getattr(settings, 'REDIS_HOST', 'localhost'),
                port=getattr(settings, 'REDIS_PORT', 6379),
                db=getattr(settings, 'REDIS_DB', 0),
                password=getattr(settings, 'REDIS_PASSWORD', None),
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True
            )
            # Test connection
            self.redis_client.ping()
            print("Redis connection established successfully")
        except Exception as e:
            print(f"Warning: Redis connection failed: {str(e)}")
            self.redis_client = None
    
    def is_available(self) -> bool:
        """Check if Redis is available."""
        if not self.redis_client:
            return False
        try:
            self.redis_client.ping()
            return True
        except:
            return False
    
    def _serialize_data(self, data: Any) -> str:
        """Serialize data for Redis storage."""
        if isinstance(data, (dict, list)):
            return json.dumps(data, default=str)
        return str(data)
    
    def _deserialize_data(self, data: str) -> Any:
        """Deserialize data from Redis."""
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return data
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in Redis with optional TTL."""
        if not self.is_available():
            return False
        
        try:
            serialized_value = self._serialize_data(value)
            if ttl:
                return self.redis_client.setex(key, ttl, serialized_value)
            else:
                return self.redis_client.set(key, serialized_value)
        except Exception as e:
            print(f"Redis SET error: {str(e)}")
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from Redis."""
        if not self.is_available():
            return None
        
        try:
            value = self.redis_client.get(key)
            if value is None:
                return None
            return self._deserialize_data(value)
        except Exception as e:
            print(f"Redis GET error: {str(e)}")
            return None
    
    def delete(self, key: str) -> bool:
        """Delete a key from Redis."""
        if not self.is_available():
            return False
        
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            print(f"Redis DELETE error: {str(e)}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern."""
        if not self.is_available():
            return 0
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            print(f"Redis DELETE_PATTERN error: {str(e)}")
            return 0
    
    def exists(self, key: str) -> bool:
        """Check if a key exists in Redis."""
        if not self.is_available():
            return False
        
        try:
            return bool(self.redis_client.exists(key))
        except Exception as e:
            print(f"Redis EXISTS error: {str(e)}")
            return False
    
    # Hierarchical caching methods
    
    def cache_client(self, client_id: int, client_data: Dict, ttl: int = 3600) -> bool:
        """Cache client data."""
        key = f"client:{client_id}"
        return self.set(key, client_data, ttl)
    
    def get_cached_client(self, client_id: int) -> Optional[Dict]:
        """Get cached client data."""
        key = f"client:{client_id}"
        return self.get(key)
    
    def cache_client_domains(self, client_id: int, domains_data: List[Dict], ttl: int = 1800) -> bool:
        """Cache domains for a specific client."""
        key = f"client:{client_id}:domains"
        return self.set(key, domains_data, ttl)
    
    def get_cached_client_domains(self, client_id: int) -> Optional[List[Dict]]:
        """Get cached domains for a client."""
        key = f"client:{client_id}:domains"
        return self.get(key)
    
    def cache_domain(self, domain_id: int, domain_data: Dict, ttl: int = 3600) -> bool:
        """Cache domain data."""
        key = f"domain:{domain_id}"
        return self.set(key, domain_data, ttl)
    
    def get_cached_domain(self, domain_id: int) -> Optional[Dict]:
        """Get cached domain data."""
        key = f"domain:{domain_id}"
        return self.get(key)
    
    def cache_domain_applications(self, domain_id: int, applications_data: List[Dict], ttl: int = 1800) -> bool:
        """Cache applications for a specific domain."""
        key = f"domain:{domain_id}:applications"
        return self.set(key, applications_data, ttl)
    
    def get_cached_domain_applications(self, domain_id: int) -> Optional[List[Dict]]:
        """Get cached applications for a domain."""
        key = f"domain:{domain_id}:applications"
        return self.get(key)
    
    def cache_application(self, app_id: int, app_data: Dict, ttl: int = 3600) -> bool:
        """Cache application data."""
        key = f"application:{app_id}"
        return self.set(key, app_data, ttl)
    
    def get_cached_application(self, app_id: int) -> Optional[Dict]:
        """Get cached application data."""
        key = f"application:{app_id}"
        return self.get(key)
    
    def cache_tenant_applications(self, tenant_id: int, applications_data: List[Dict], ttl: int = 1800) -> bool:
        """Cache applications for a specific tenant."""
        key = f"tenant:{tenant_id}:applications"
        return self.set(key, applications_data, ttl)

    def get_cached_tenant_applications(self, tenant_id: int) -> Optional[List[Dict]]:
        """Get cached applications for a tenant."""
        key = f"client:{client_id}:applications"
        return self.get(key)
    
    def cache_client_hierarchy(self, client_id: int, hierarchy_data: Dict, ttl: int = 1800) -> bool:
        """Cache complete client hierarchy (Client -> Domains -> Applications)."""
        key = f"client:{client_id}:hierarchy"
        return self.set(key, hierarchy_data, ttl)
    
    def get_cached_client_hierarchy(self, client_id: int) -> Optional[Dict]:
        """Get cached client hierarchy."""
        key = f"client:{client_id}:hierarchy"
        return self.get(key)
    
    def cache_domain_hierarchy(self, domain_id: int, hierarchy_data: Dict, ttl: int = 1800) -> bool:
        """Cache complete domain hierarchy (Domain -> Applications -> Clients)."""
        key = f"domain:{domain_id}:hierarchy"
        return self.set(key, hierarchy_data, ttl)
    
    def get_cached_domain_hierarchy(self, domain_id: int) -> Optional[Dict]:
        """Get cached domain hierarchy."""
        key = f"domain:{domain_id}:hierarchy"
        return self.get(key)
    
    # Cache invalidation methods
    
    def invalidate_client_cache(self, client_id: int) -> int:
        """Invalidate all cache entries related to a client."""
        pattern = f"client:{client_id}*"
        return self.delete_pattern(pattern)
    
    def invalidate_domain_cache(self, domain_id: int) -> int:
        """Invalidate all cache entries related to a domain."""
        pattern = f"domain:{domain_id}*"
        return self.delete_pattern(pattern)
    
    def invalidate_application_cache(self, app_id: int) -> int:
        """Invalidate all cache entries related to an application."""
        pattern = f"application:{app_id}*"
        return self.delete_pattern(pattern)
    
    def invalidate_client_domain_cache(self, client_id: int, domain_id: int) -> bool:
        """Invalidate cache when client-domain relationship changes."""
        keys_to_delete = [
            f"client:{client_id}:domains",
            f"client:{client_id}:hierarchy",
            f"domain:{domain_id}:hierarchy"
        ]
        
        deleted_count = 0
        for key in keys_to_delete:
            if self.delete(key):
                deleted_count += 1
        
        return deleted_count > 0
    
    def invalidate_domain_application_cache(self, domain_id: int, app_id: int) -> bool:
        """Invalidate cache when domain-application relationship changes."""
        keys_to_delete = [
            f"domain:{domain_id}:applications",
            f"domain:{domain_id}:hierarchy",
            f"application:{app_id}"
        ]
        
        deleted_count = 0
        for key in keys_to_delete:
            if self.delete(key):
                deleted_count += 1
        
        return deleted_count > 0
    
    def invalidate_client_application_cache(self, client_id: int, app_id: int) -> bool:
        """Invalidate cache when client-application relationship changes."""
        keys_to_delete = [
            f"client:{client_id}:applications",
            f"client:{client_id}:hierarchy",
            f"application:{app_id}"
        ]
        
        deleted_count = 0
        for key in keys_to_delete:
            if self.delete(key):
                deleted_count += 1
        
        return deleted_count > 0
    
    def clear_all_cache(self) -> bool:
        """Clear all cache entries (use with caution)."""
        if not self.is_available():
            return False
        
        try:
            self.redis_client.flushdb()
            return True
        except Exception as e:
            print(f"Redis FLUSHDB error: {str(e)}")
            return False

# Global Redis cache instance
redis_cache = RedisCache()