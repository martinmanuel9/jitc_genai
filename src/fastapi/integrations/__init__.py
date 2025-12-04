"""
External service integrations package.

This package contains client wrappers and utilities for external services:
- ChromaDB: Vector database client
- Redis: Cache and job queue client
- AWS S3: Object storage (if needed)
- Other third-party services

Each integration module provides a clean interface that can be:
- Easily mocked for testing
- Swapped out for alternative implementations
- Monitored and instrumented for observability

Usage:
    from integrations import get_chroma_client, get_redis_client

    # Get ChromaDB client (singleton)
    chroma = get_chroma_client()
    collection = chroma.get_or_create_collection("my_collection")

    # Get Redis client (singleton)
    redis = get_redis_client()
    redis.set_job_progress(job_id, {"status": "processing"})
"""

from integrations.chromadb_client import ChromaDBClient, get_chroma_client
from integrations.redis_client import RedisClient, get_redis_client

__all__ = [
    "ChromaDBClient",
    "RedisClient",
    "get_chroma_client",
    "get_redis_client",
]
