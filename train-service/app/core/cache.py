"""
Redis cache management for Train service.
Used for caching user context and other frequently accessed data.
"""

import redis.asyncio as redis
import json
import logging
from typing import Optional, Any

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class RedisCache:
    """
    Singleton Redis cache manager.
    Handles connection, get, set, and delete operations.
    """
    _instance = None
    
    def __new__(cls):
        """Singleton pattern to ensure single Redis connection pool."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = None
        return cls._instance
    
    async def connect(self) -> None:
        """Establish connection to Redis server. Called during app startup."""
        try:
            self._client = await redis.from_url(
                f"redis://{settings.redis_host}:{settings.redis_port}",
                decode_responses=True
            )
            logger.info(f"Redis connected at {settings.redis_host}:{settings.redis_port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self) -> None:
        """Close Redis connection. Called during app shutdown."""
        if self._client:
            await self._client.close()
            logger.info("Redis disconnected")
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache by key.
        
        Args:
            key: Cache key (e.g., "user_context:123")
        
        Returns:
            Parsed JSON value or None if key doesn't exist
        """
        if not self._client:
            await self.connect()
        
        value = await self._client.get(key)
        if value:
            return json.loads(value)
        return None
    
    async def set(self, key: str, value: Any, ttl: int = 1800) -> bool:
        """
        Set value in cache with TTL.
        
        Args:
            key: Cache key
            value: Value to store (will be JSON serialized)
            ttl: Time to live in seconds (default: 30 minutes)
        
        Returns:
            True if successful
        """
        if not self._client:
            await self.connect()
        
        await self._client.setex(key, ttl, json.dumps(value))
        logger.debug(f"Cache set: {key} (TTL: {ttl}s)")
        return True
    
    async def delete(self, key: str) -> bool:
        """
        Delete a key from cache.
        
        Args:
            key: Cache key to delete
        
        Returns:
            True if key was deleted
        """
        if not self._client:
            await self.connect()
        
        result = await self._client.delete(key)
        return result > 0
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key to check
        
        Returns:
            True if key exists
        """
        if not self._client:
            await self.connect()
        
        result = await self._client.exists(key)
        return result > 0
    
    async def clear_prefix(self, prefix: str) -> int:
        """
        Delete all keys with a given prefix.
        
        Args:
            prefix: Key prefix (e.g., "user_context:")
        
        Returns:
            Number of keys deleted
        """
        if not self._client:
            await self.connect()
        
        pattern = f"{prefix}*"
        keys = await self._client.keys(pattern)
        if keys:
            return await self._client.delete(*keys)
        return 0


# Singleton instance
cache = RedisCache()