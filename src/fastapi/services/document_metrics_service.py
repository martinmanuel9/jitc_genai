"""
Document Metrics Service - Example Implementation of BaseService

This service demonstrates proper usage of the Phase 3 BaseService pattern.
It provides document statistics and metrics with built-in monitoring,
validation, and error handling.

Use this as a reference when creating new services.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from services.base_service import BaseService, CachedService
from services.error_handling import ServiceError
from models.document import Document  # Assuming this exists
import logging

logger = logging.getLogger("DocumentMetricsService")


class DocumentMetricsService(BaseService):
    """
    Example service implementing BaseService pattern.

    Demonstrates:
    - Metrics tracking with _timed_operation
    - Input validation with _validate_* methods
    - Error handling with _handle_error
    - Database operations with _ensure_db
    - Health check implementation
    """

    def __init__(self, db: Optional[Session] = None):
        """Initialize document metrics service."""
        super().__init__(db=db, service_name="DocumentMetricsService")

    # ========================================================================
    # Public API Methods (using BaseService features)
    # ========================================================================

    def get_collection_stats(
        self,
        collection_name: str,
        include_inactive: bool = False
    ) -> Dict[str, Any]:
        """
        Get statistics for a specific collection.

        Demonstrates:
        - Input validation
        - Timed operation tracking
        - Database access with error handling

        Args:
            collection_name: Collection to analyze
            include_inactive: Whether to include inactive documents

        Returns:
            Dictionary with collection statistics

        Raises:
            ServiceError: If operation fails
        """
        # Validate inputs using BaseService validation methods
        self._validate_required(collection_name, "collection_name")

        try:
            # Use timed operation context manager for automatic metrics
            with self._timed_operation("get_collection_stats"):
                db = self._ensure_db()

                # Build query
                query = db.query(
                    func.count(Document.id).label('total_documents'),
                    func.sum(Document.chunk_count).label('total_chunks'),
                    func.avg(Document.chunk_count).label('avg_chunks_per_doc')
                ).filter(Document.collection_name == collection_name)

                if not include_inactive:
                    query = query.filter(Document.is_active == True)

                result = query.first()

                return {
                    "collection_name": collection_name,
                    "total_documents": result.total_documents or 0,
                    "total_chunks": int(result.total_chunks or 0),
                    "avg_chunks_per_doc": float(result.avg_chunks_per_doc or 0),
                    "include_inactive": include_inactive,
                    "timestamp": datetime.utcnow().isoformat()
                }

        except Exception as e:
            # Use BaseService error handler
            raise self._handle_error("get_collection_stats", e)

    def get_recent_documents(
        self,
        collection_name: Optional[str] = None,
        days: int = 7,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recently added documents.

        Demonstrates:
        - Range validation
        - Positive number validation
        - Complex query with optional filtering

        Args:
            collection_name: Optional collection filter
            days: Number of days to look back (default: 7)
            limit: Maximum number of results (default: 10)

        Returns:
            List of recent document metadata

        Raises:
            ServiceError: If operation fails
        """
        # Validate inputs
        self._validate_range(days, 1, 365, "days")
        self._validate_positive(limit, "limit")

        try:
            with self._timed_operation("get_recent_documents"):
                db = self._ensure_db()

                # Calculate date range
                cutoff_date = datetime.utcnow() - timedelta(days=days)

                # Build query
                query = db.query(Document).filter(
                    Document.created_at >= cutoff_date
                )

                if collection_name:
                    query = query.filter(Document.collection_name == collection_name)

                # Execute with limit
                documents = query.order_by(
                    Document.created_at.desc()
                ).limit(limit).all()

                # Transform to dict
                return [
                    {
                        "id": doc.id,
                        "name": doc.document_name,
                        "collection": doc.collection_name,
                        "chunk_count": doc.chunk_count,
                        "created_at": doc.created_at.isoformat() if doc.created_at else None,
                        "file_type": doc.file_type
                    }
                    for doc in documents
                ]

        except Exception as e:
            raise self._handle_error("get_recent_documents", e)

    def calculate_storage_metrics(self) -> Dict[str, Any]:
        """
        Calculate overall storage and usage metrics.

        Demonstrates:
        - Complex aggregation queries
        - Service metrics exposure
        - Multiple database operations

        Returns:
            Storage metrics dictionary
        """
        try:
            with self._timed_operation("calculate_storage_metrics"):
                db = self._ensure_db()

                # Get total counts
                total_docs = db.query(func.count(Document.id)).scalar()
                total_chunks = db.query(func.sum(Document.chunk_count)).scalar()

                # Get collection breakdown
                collection_stats = db.query(
                    Document.collection_name,
                    func.count(Document.id).label('doc_count'),
                    func.sum(Document.chunk_count).label('chunk_count')
                ).group_by(Document.collection_name).all()

                collections = [
                    {
                        "name": stat.collection_name,
                        "documents": stat.doc_count,
                        "chunks": int(stat.chunk_count or 0)
                    }
                    for stat in collection_stats
                ]

                # Include service metrics
                service_metrics = self.get_metrics()

                return {
                    "storage": {
                        "total_documents": total_docs or 0,
                        "total_chunks": int(total_chunks or 0),
                        "collections": collections,
                        "collection_count": len(collections)
                    },
                    "service_performance": {
                        "total_calls": service_metrics["total_calls"],
                        "avg_time_ms": service_metrics["avg_time_ms"],
                        "success_rate": service_metrics["success_rate"]
                    },
                    "timestamp": datetime.utcnow().isoformat()
                }

        except Exception as e:
            raise self._handle_error("calculate_storage_metrics", e)

    # ========================================================================
    # Required Abstract Method Implementation
    # ========================================================================

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check for document metrics service.

        Demonstrates:
        - Health check implementation
        - Database connectivity test
        - Service metrics reporting

        Returns:
            Health status dictionary
        """
        try:
            # Test database connection
            if self.db:
                db = self._ensure_db()
                # Simple query to test connection
                db.query(func.count(Document.id)).scalar()
                db_status = "connected"
            else:
                db_status = "no_session"

            # Get service metrics
            metrics = self.get_metrics()

            return {
                "status": "healthy",
                "service": self.service_name,
                "details": {
                    "database": db_status,
                    "total_calls": metrics["total_calls"],
                    "success_rate": f"{metrics['success_rate']:.2f}%",
                    "avg_response_time_ms": f"{metrics['avg_time_ms']:.2f}"
                }
            }

        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "service": self.service_name,
                "details": {
                    "database": "error",
                    "error": str(e)
                }
            }


class CachedDocumentMetricsService(CachedService):
    """
    Example of CachedService usage for expensive operations.

    Demonstrates:
    - TTL-based caching
    - Cache key management
    - Cache invalidation patterns
    """

    def __init__(self, db: Optional[Session] = None, cache_ttl: int = 300):
        """
        Initialize cached document metrics service.

        Args:
            db: Database session
            cache_ttl: Cache time-to-live in seconds (default: 5 minutes)
        """
        super().__init__(db=db, service_name="CachedDocumentMetricsService")
        self._set_cache_ttl(cache_ttl)

    def get_expensive_analytics(
        self,
        collection_name: str,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        Get expensive analytics with caching.

        Demonstrates:
        - Cache usage for expensive operations
        - Cache key generation
        - Force refresh pattern

        Args:
            collection_name: Collection to analyze
            force_refresh: Skip cache and force recomputation

        Returns:
            Analytics dictionary
        """
        cache_key = f"analytics_{collection_name}"

        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_result = self._get_from_cache(cache_key)
            if cached_result is not None:
                self.logger.info(f"Returning cached analytics for {collection_name}")
                return cached_result

        try:
            with self._timed_operation("get_expensive_analytics"):
                # Expensive computation here
                db = self._ensure_db()

                # Simulate expensive aggregation
                result = {
                    "collection_name": collection_name,
                    "computed_at": datetime.utcnow().isoformat(),
                    "expensive_metric": "computed_value",
                    # ... more expensive computations
                }

                # Store in cache
                self._set_in_cache(cache_key, result)

                return result

        except Exception as e:
            raise self._handle_error("get_expensive_analytics", e)

    def invalidate_collection_cache(self, collection_name: str):
        """
        Invalidate cache for specific collection.

        Demonstrates:
        - Targeted cache invalidation
        - Cache management patterns

        Args:
            collection_name: Collection to invalidate
        """
        cache_key = f"analytics_{collection_name}"
        self._invalidate_cache(cache_key)
        self.logger.info(f"Invalidated cache for collection: {collection_name}")

    def health_check(self) -> Dict[str, Any]:
        """Health check for cached service."""
        base_health = {
            "status": "healthy",
            "service": self.service_name,
            "cache_size": len(self._cache),
            "cache_ttl_seconds": self._cache_ttl
        }

        try:
            if self.db:
                db = self._ensure_db()
                db.execute("SELECT 1")  # Test connection
                base_health["database"] = "connected"

            return base_health

        except Exception as e:
            return {
                **base_health,
                "status": "degraded",
                "database": "error",
                "error": str(e)
            }


# ============================================================================
# Usage Examples
# ============================================================================

"""
Example 1: Basic Service Usage
-------------------------------

from services.document_metrics_service import DocumentMetricsService
from core.dependencies import get_db

# Initialize service
db = next(get_db())
metrics_service = DocumentMetricsService(db=db)

# Get collection stats with automatic metrics tracking
stats = metrics_service.get_collection_stats("legal_docs")
print(stats)
# {
#     "collection_name": "legal_docs",
#     "total_documents": 150,
#     "total_chunks": 3420,
#     "avg_chunks_per_doc": 22.8,
#     ...
# }

# Check service health and performance
health = metrics_service.health_check()
print(health)
# {
#     "status": "healthy",
#     "details": {
#         "database": "connected",
#         "total_calls": 5,
#         "success_rate": "100.00%",
#         "avg_response_time_ms": "124.50"
#     }
# }

# Get service metrics
metrics = metrics_service.get_metrics()
print(metrics)
# {
#     "total_calls": 5,
#     "total_errors": 0,
#     "total_time_ms": 622,
#     "avg_time_ms": 124.4,
#     "success_rate": 100.0
# }


Example 2: Cached Service Usage
--------------------------------

from services.document_metrics_service import CachedDocumentMetricsService

# Initialize with custom cache TTL
cached_service = CachedDocumentMetricsService(db=db, cache_ttl=600)  # 10 minutes

# First call - computes and caches
analytics = cached_service.get_expensive_analytics("legal_docs")
# Takes 5000ms to compute

# Second call - returns cached
analytics = cached_service.get_expensive_analytics("legal_docs")
# Takes < 1ms (cached)

# Force refresh
analytics = cached_service.get_expensive_analytics("legal_docs", force_refresh=True)
# Recomputes and updates cache

# Invalidate specific collection
cached_service.invalidate_collection_cache("legal_docs")


Example 3: Error Handling
--------------------------

try:
    stats = metrics_service.get_collection_stats("")  # Invalid input
except ServiceError as e:
    print(f"Error: {e.message}")
    print(f"Code: {e.error_code}")
    print(f"Details: {e.details}")

# Validation errors are caught automatically:
# - Empty strings raise ValueError
# - Out of range values raise ValueError
# - Database errors wrapped in ServiceError


Example 4: Using in FastAPI Endpoint
-------------------------------------

from fastapi import APIRouter, Depends
from core.dependencies import get_db
from schemas.responses import BaseResponse

router = APIRouter()

def get_metrics_service(db: Session = Depends(get_db)) -> DocumentMetricsService:
    return DocumentMetricsService(db=db)

@router.get("/metrics/collection/{collection_name}", response_model=BaseResponse)
async def get_collection_metrics(
    collection_name: str,
    service: DocumentMetricsService = Depends(get_metrics_service)
):
    try:
        stats = service.get_collection_stats(collection_name)
        return BaseResponse(
            success=True,
            message=f"Retrieved metrics for {collection_name}",
            **stats
        )
    except ServiceError as e:
        raise HTTPException(status_code=400, detail=e.message)

@router.get("/health/metrics")
async def metrics_health_check(
    service: DocumentMetricsService = Depends(get_metrics_service)
):
    return service.health_check()
"""
