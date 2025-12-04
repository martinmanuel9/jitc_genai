"""
Redis client wrapper and utilities.

This module provides a centralized Redis client with:
- Connection management
- Health checking
- Common operations (get, set, hset, etc.)
- Job tracking utilities
"""

import redis
from typing import Optional, Dict, Any, List
from functools import lru_cache

from core.config import get_settings
from core.exceptions import RedisException


class RedisClient:
    """
    Wrapper class for Redis client.

    Provides a clean interface for Redis operations with
    proper error handling and connection management.
    """

    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize Redis client.

        Args:
            redis_url: Redis connection URL (defaults to settings)
        """
        settings = get_settings()
        self.redis_url = redis_url or settings.redis_url

        try:
            self._client = redis.from_url(self.redis_url, decode_responses=True)
            # Test connection
            self._client.ping()
            print(f" Redis connected at {self.redis_url}")
        except Exception as e:
            print(f" Redis connection failed: {e}")
            raise RedisException(f"Failed to connect to Redis at {self.redis_url}") from e

    @property
    def client(self) -> redis.Redis:
        """
        Get the underlying Redis client.

        Returns:
            redis.Redis: The Redis client instance
        """
        return self._client

    def ping(self) -> bool:
        """
        Check Redis connection health.

        Returns:
            bool: True if connection is healthy

        Raises:
            RedisException: If ping fails
        """
        try:
            return self._client.ping()
        except Exception as e:
            raise RedisException("Ping check failed") from e

    # Basic Operations

    def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        try:
            return self._client.get(key)
        except Exception as e:
            raise RedisException(f"Failed to get key '{key}'") from e

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """
        Set key-value pair.

        Args:
            key: Redis key
            value: Value to store
            ex: Expiration time in seconds

        Returns:
            bool: True if successful
        """
        try:
            return self._client.set(key, value, ex=ex)
        except Exception as e:
            raise RedisException(f"Failed to set key '{key}'") from e

    def delete(self, *keys: str) -> int:
        """Delete one or more keys."""
        try:
            return self._client.delete(*keys)
        except Exception as e:
            raise RedisException(f"Failed to delete keys") from e

    def exists(self, *keys: str) -> int:
        """Check if keys exist."""
        try:
            return self._client.exists(*keys)
        except Exception as e:
            raise RedisException(f"Failed to check key existence") from e

    # Hash Operations

    def hset(self, name: str, mapping: Dict[str, Any]) -> int:
        """Set hash fields."""
        try:
            return self._client.hset(name, mapping=mapping)
        except Exception as e:
            raise RedisException(f"Failed to hset '{name}'") from e

    def hget(self, name: str, key: str) -> Optional[str]:
        """Get hash field value."""
        try:
            return self._client.hget(name, key)
        except Exception as e:
            raise RedisException(f"Failed to hget '{name}':'{key}'") from e

    def hgetall(self, name: str) -> Dict[str, str]:
        """Get all hash fields."""
        try:
            return self._client.hgetall(name)
        except Exception as e:
            raise RedisException(f"Failed to hgetall '{name}'") from e

    def hincrby(self, name: str, key: str, amount: int = 1) -> int:
        """Increment hash field by amount."""
        try:
            return self._client.hincrby(name, key, amount)
        except Exception as e:
            raise RedisException(f"Failed to hincrby '{name}':'{key}'") from e

    # List Operations

    def lpush(self, name: str, *values: str) -> int:
        """Push values to list head."""
        try:
            return self._client.lpush(name, *values)
        except Exception as e:
            raise RedisException(f"Failed to lpush to '{name}'") from e

    def rpush(self, name: str, *values: str) -> int:
        """Push values to list tail."""
        try:
            return self._client.rpush(name, *values)
        except Exception as e:
            raise RedisException(f"Failed to rpush to '{name}'") from e

    def lrange(self, name: str, start: int, end: int) -> List[str]:
        """Get list range."""
        try:
            return self._client.lrange(name, start, end)
        except Exception as e:
            raise RedisException(f"Failed to lrange '{name}'") from e

    # Job Tracking Utilities

    def set_job_status(self, job_id: str, status: str, ex: int = 3600) -> bool:
        """
        Set job status.

        Args:
            job_id: Job identifier
            status: Job status (running, completed, failed)
            ex: Expiration time in seconds (default 1 hour)

        Returns:
            bool: True if successful
        """
        return self.set(job_id, status, ex=ex)

    def get_job_status(self, job_id: str) -> Optional[str]:
        """Get job status."""
        return self.get(job_id)

    def set_job_progress(self, job_id: str, progress_data: Dict[str, Any]) -> int:
        """
        Set job progress data.

        Args:
            job_id: Job identifier
            progress_data: Progress metrics

        Returns:
            int: Number of fields set
        """
        key = f"job:{job_id}:progress"
        return self.hset(key, mapping=progress_data)

    def get_job_progress(self, job_id: str) -> Dict[str, str]:
        """Get job progress data."""
        key = f"job:{job_id}:progress"
        return self.hgetall(key)

    def increment_job_counter(self, job_id: str, counter_name: str, amount: int = 1) -> int:
        """
        Increment a job counter.

        Args:
            job_id: Job identifier
            counter_name: Counter field name
            amount: Increment amount

        Returns:
            int: New counter value
        """
        key = f"job:{job_id}:progress"
        return self.hincrby(key, counter_name, amount)

    # Health Status

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get comprehensive health status.

        Returns:
            dict: Health status information
        """
        try:
            info = self._client.info()
            return {
                "status": "healthy",
                "redis_url": self.redis_url.split('@')[-1] if '@' in self.redis_url else self.redis_url,
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "redis_url": self.redis_url.split('@')[-1] if '@' in self.redis_url else self.redis_url,
                "error": str(e),
            }


# Singleton instance
_redis_client: Optional[RedisClient] = None


@lru_cache()
def get_redis_client() -> RedisClient:
    """
    Get singleton Redis client instance.

    Returns:
        RedisClient: Shared Redis client instance
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client


def reset_redis_client() -> None:
    """
    Reset the singleton instance (useful for testing).
    """
    global _redis_client
    _redis_client = None
