"""
Redis Client Infrastructure

Session state management, caching, and real-time coordination.
"""

from typing import Optional, Any
import json
from redis.asyncio import Redis, ConnectionPool
from app.config import settings


class RedisClient:
    """
    Async Redis client wrapper.
    
    Provides session state management and caching (NFR-6, DR-3).
    """
    
    def __init__(self):
        self.pool: Optional[ConnectionPool] = None
        self.client: Optional[Redis] = None
    
    async def connect(self):
        """Initialize Redis connection pool"""
        self.pool = ConnectionPool.from_url(
            str(settings.redis_dsn),
            decode_responses=True,
            max_connections=50,
        )
        self.client = Redis(connection_pool=self.pool)
    
    async def disconnect(self):
        """Close Redis connections"""
        if self.client:
            await self.client.close()
        if self.pool:
            await self.pool.disconnect()
    
    async def get(self, key: str) -> Optional[str]:
        """Get value by key"""
        if not self.client:
            raise RuntimeError("Redis client not connected")
        return await self.client.get(key)
    
    async def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None
    ) -> bool:
        """Set key-value pair with optional TTL (seconds)"""
        if not self.client:
            raise RuntimeError("Redis client not connected")
        return await self.client.set(key, value, ex=ttl)
    
    async def delete(self, key: str) -> int:
        """Delete key"""
        if not self.client:
            raise RuntimeError("Redis client not connected")
        return await self.client.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self.client:
            raise RuntimeError("Redis client not connected")
        return await self.client.exists(key) > 0
    
    async def get_json(self, key: str) -> Optional[Any]:
        """Get JSON value"""
        value = await self.get(key)
        return json.loads(value) if value else None
    
    async def set_json(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Set JSON value"""
        return await self.set(key, json.dumps(value), ttl=ttl)
    
    # Session state helpers (NFR-6.1, DR-3)
    
    async def get_session_state(self, submission_id: int) -> Optional[dict]:
        """Get interview session state"""
        key = f"session:{submission_id}"
        return await self.get_json(key)
    
    async def set_session_state(
        self,
        submission_id: int,
        state: dict,
        ttl: Optional[int] = None
    ) -> bool:
        """Set interview session state"""
        key = f"session:{submission_id}"
        ttl = ttl or settings.redis_session_ttl
        return await self.set_json(key, state, ttl=ttl)
    
    async def delete_session_state(self, submission_id: int) -> int:
        """Delete interview session state"""
        key = f"session:{submission_id}"
        return await self.delete(key)


# Global Redis client instance
redis_client = RedisClient()


async def get_redis() -> RedisClient:
    """
    Dependency for FastAPI routes.
    
    Usage:
        @router.get("/session")
        async def get_session(redis: RedisClient = Depends(get_redis)):
            ...
    """
    return redis_client
