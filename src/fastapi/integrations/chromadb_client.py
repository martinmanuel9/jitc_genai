"""
ChromaDB client wrapper and utilities.

This module provides a centralized ChromaDB client with:
- Connection management
- Health checking
- Error handling
- Retry logic
"""

import chromadb
from typing import Optional, Dict, Any
from functools import lru_cache

from core.config import get_settings
from core.exceptions import ChromaDBException


class ChromaDBClient:
    """
    Wrapper class for ChromaDB HTTP client.

    Provides a clean interface for ChromaDB operations with
    proper error handling and connection management.
    """

    def __init__(self, host: Optional[str] = None, port: Optional[int] = None):
        """
        Initialize ChromaDB client.

        Args:
            host: ChromaDB host (defaults to settings)
            port: ChromaDB port (defaults to settings)
        """
        settings = get_settings()
        self.host = host or settings.chroma_host
        self.port = port or settings.chroma_port

        try:
            self._client = chromadb.HttpClient(
                host=self.host,
                port=self.port
            )
            # Test connection
            self._client.heartbeat()
            print(f" ChromaDB connected at {self.host}:{self.port}")
        except Exception as e:
            print(f" ChromaDB connection failed: {e}")
            raise ChromaDBException(f"Failed to connect to ChromaDB at {self.host}:{self.port}") from e

    @property
    def client(self) -> chromadb.HttpClient:
        """
        Get the underlying ChromaDB client.

        Returns:
            chromadb.HttpClient: The ChromaDB client instance
        """
        return self._client

    def heartbeat(self) -> int:
        """
        Check ChromaDB connection health.

        Returns:
            int: Heartbeat timestamp

        Raises:
            ChromaDBException: If heartbeat fails
        """
        try:
            return self._client.heartbeat()
        except Exception as e:
            raise ChromaDBException("Heartbeat check failed") from e

    def get_collection(self, name: str):
        """
        Get a collection by name.

        Args:
            name: Collection name

        Returns:
            Collection: ChromaDB collection instance

        Raises:
            ChromaDBException: If collection retrieval fails
        """
        try:
            return self._client.get_collection(name=name)
        except Exception as e:
            raise ChromaDBException(f"Failed to get collection '{name}'") from e

    def create_collection(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Create a new collection.

        Args:
            name: Collection name
            metadata: Optional collection metadata

        Returns:
            Collection: Created collection instance

        Raises:
            ChromaDBException: If collection creation fails
        """
        try:
            return self._client.create_collection(name=name, metadata=metadata)
        except Exception as e:
            raise ChromaDBException(f"Failed to create collection '{name}'") from e

    def get_or_create_collection(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Get existing collection or create if it doesn't exist.

        Args:
            name: Collection name
            metadata: Optional collection metadata

        Returns:
            Collection: Collection instance

        Raises:
            ChromaDBException: If operation fails
        """
        try:
            return self._client.get_or_create_collection(name=name, metadata=metadata)
        except Exception as e:
            raise ChromaDBException(f"Failed to get or create collection '{name}'") from e

    def delete_collection(self, name: str) -> None:
        """
        Delete a collection.

        Args:
            name: Collection name

        Raises:
            ChromaDBException: If deletion fails
        """
        try:
            self._client.delete_collection(name=name)
        except Exception as e:
            raise ChromaDBException(f"Failed to delete collection '{name}'") from e

    def list_collections(self):
        """
        List all collections.

        Returns:
            List: List of collection objects

        Raises:
            ChromaDBException: If listing fails
        """
        try:
            return self._client.list_collections()
        except Exception as e:
            raise ChromaDBException("Failed to list collections") from e

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get comprehensive health status.

        Returns:
            dict: Health status information
        """
        try:
            heartbeat = self.heartbeat()
            collections = self.list_collections()
            return {
                "status": "healthy",
                "host": self.host,
                "port": self.port,
                "heartbeat": heartbeat,
                "collections_count": len(collections),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "host": self.host,
                "port": self.port,
                "error": str(e),
            }


# Singleton instance
_chroma_client: Optional[ChromaDBClient] = None


@lru_cache()
def get_chroma_client() -> ChromaDBClient:
    """
    Get singleton ChromaDB client instance.

    Returns:
        ChromaDBClient: Shared ChromaDB client instance
    """
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = ChromaDBClient()
    return _chroma_client


def reset_chroma_client() -> None:
    """
    Reset the singleton instance (useful for testing).
    """
    global _chroma_client
    _chroma_client = None
