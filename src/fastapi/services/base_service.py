"""
Base Service Class

Provides common functionality and patterns for all FastAPI services.
Includes error handling, logging, metrics, and standardized method patterns.
"""

import logging
import time
from typing import Optional, Dict, Any, TypeVar, Generic
from abc import ABC, abstractmethod
from sqlalchemy.orm import Session
from services.error_handling import handle_service_errors, ServiceError

T = TypeVar('T')


class BaseService(ABC):
    """
    Base class for all service implementations.

    Provides:
    - Standardized logging
    - Performance metrics
    - Error handling patterns
    - Common utility methods
    - Database session management
    """

    def __init__(self, db: Optional[Session] = None, service_name: Optional[str] = None):
        """
        Initialize base service.

        Args:
            db: Optional database session
            service_name: Service name for logging (defaults to class name)
        """
        self.db = db
        self.service_name = service_name or self.__class__.__name__
        self.logger = logging.getLogger(self.service_name)
        self._metrics: Dict[str, Any] = {
            "total_calls": 0,
            "total_errors": 0,
            "total_time_ms": 0
        }

    # ========================================================================
    # Metrics & Monitoring
    # ========================================================================

    def _record_call(self, operation: str, duration_ms: int, success: bool = True):
        """
        Record metrics for a service call.

        Args:
            operation: Operation name
            duration_ms: Duration in milliseconds
            success: Whether operation succeeded
        """
        self._metrics["total_calls"] += 1
        self._metrics["total_time_ms"] += duration_ms

        if not success:
            self._metrics["total_errors"] += 1

        # Log slow operations (>5 seconds)
        if duration_ms > 5000:
            self.logger.warning(
                f"Slow operation detected: {operation} took {duration_ms}ms"
            )

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get service metrics.

        Returns:
            Dictionary of metric values
        """
        return {
            **self._metrics,
            "avg_time_ms": (
                self._metrics["total_time_ms"] / self._metrics["total_calls"]
                if self._metrics["total_calls"] > 0 else 0
            ),
            "success_rate": (
                (self._metrics["total_calls"] - self._metrics["total_errors"])
                / self._metrics["total_calls"] * 100
                if self._metrics["total_calls"] > 0 else 100
            )
        }

    def reset_metrics(self):
        """Reset service metrics"""
        self._metrics = {
            "total_calls": 0,
            "total_errors": 0,
            "total_time_ms": 0
        }

    # ========================================================================
    # Error Handling
    # ========================================================================

    def _handle_error(self, operation: str, error: Exception) -> ServiceError:
        """
        Handle and log service errors consistently.

        Args:
            operation: Operation that failed
            error: Exception that occurred

        Returns:
            ServiceError with context
        """
        self.logger.error(f"Error in {operation}: {str(error)}", exc_info=True)
        self._metrics["total_errors"] += 1

        return ServiceError(
            message=f"{operation} failed: {str(error)}",
            error_code="SERVICE_ERROR",
            details={"operation": operation, "service": self.service_name}
        )

    # ========================================================================
    # Database Helpers
    # ========================================================================

    def _ensure_db(self) -> Session:
        """
        Ensure database session is available.

        Returns:
            Database session

        Raises:
            ServiceError: If no database session available
        """
        if self.db is None:
            raise ServiceError(
                "Database session not available",
                error_code="NO_DB_SESSION"
            )
        return self.db

    def _commit_with_error_handling(self):
        """Commit database transaction with error handling"""
        try:
            if self.db:
                self.db.commit()
        except Exception as e:
            if self.db:
                self.db.rollback()
            raise ServiceError(
                f"Database commit failed: {str(e)}",
                error_code="DB_COMMIT_ERROR"
            )

    # ========================================================================
    # Timing Utilities
    # ========================================================================

    def _timed_operation(self, operation_name: str):
        """
        Context manager for timing operations.

        Usage:
            with self._timed_operation("my_operation"):
                # operation code
                pass
        """
        return TimedOperation(self, operation_name)

    # ========================================================================
    # Validation Helpers
    # ========================================================================

    def _validate_required(self, value: Any, field_name: str) -> Any:
        """
        Validate that a required field is not None or empty.

        Args:
            value: Value to validate
            field_name: Field name for error messages

        Returns:
            The value if valid

        Raises:
            ValueError: If value is None or empty
        """
        if value is None:
            raise ValueError(f"{field_name} is required")

        if isinstance(value, str) and not value.strip():
            raise ValueError(f"{field_name} cannot be empty")

        if isinstance(value, (list, dict)) and len(value) == 0:
            raise ValueError(f"{field_name} cannot be empty")

        return value

    def _validate_positive(self, value: int, field_name: str) -> int:
        """
        Validate that a numeric value is positive.

        Args:
            value: Value to validate
            field_name: Field name for error messages

        Returns:
            The value if valid

        Raises:
            ValueError: If value is not positive
        """
        if value <= 0:
            raise ValueError(f"{field_name} must be positive")
        return value

    def _validate_range(
        self,
        value: float,
        min_val: float,
        max_val: float,
        field_name: str
    ) -> float:
        """
        Validate that a value is within a range.

        Args:
            value: Value to validate
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            field_name: Field name for error messages

        Returns:
            The value if valid

        Raises:
            ValueError: If value is out of range
        """
        if value < min_val or value > max_val:
            raise ValueError(
                f"{field_name} must be between {min_val} and {max_val}"
            )
        return value

    # ========================================================================
    # Abstract Methods (to be implemented by subclasses)
    # ========================================================================

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check for this service.

        Returns:
            Dictionary with health status and details

        Example:
            {
                "status": "healthy",
                "details": {
                    "database": "connected",
                    "cache": "available"
                }
            }
        """
        pass


class TimedOperation:
    """Context manager for timing operations"""

    def __init__(self, service: BaseService, operation_name: str):
        self.service = service
        self.operation_name = operation_name
        self.start_time = None
        self.success = True

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((time.time() - self.start_time) * 1000)
        self.success = exc_type is None

        self.service._record_call(
            self.operation_name,
            duration_ms,
            success=self.success
        )

        return False  # Don't suppress exceptions


class CachedService(BaseService, Generic[T]):
    """
    Base service with caching support.

    Provides in-memory caching for expensive operations.
    """

    def __init__(self, db: Optional[Session] = None, service_name: Optional[str] = None):
        super().__init__(db, service_name)
        self._cache: Dict[str, T] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._cache_ttl: int = 300  # 5 minutes default

    def _get_from_cache(self, key: str) -> Optional[T]:
        """
        Get value from cache if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if key not in self._cache:
            return None

        # Check if expired
        timestamp = self._cache_timestamps.get(key, 0)
        if time.time() - timestamp > self._cache_ttl:
            self._invalidate_cache(key)
            return None

        return self._cache[key]

    def _set_in_cache(self, key: str, value: T):
        """
        Store value in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        self._cache[key] = value
        self._cache_timestamps[key] = time.time()

    def _invalidate_cache(self, key: Optional[str] = None):
        """
        Invalidate cache.

        Args:
            key: Specific key to invalidate, or None to clear all
        """
        if key is None:
            self._cache.clear()
            self._cache_timestamps.clear()
        else:
            self._cache.pop(key, None)
            self._cache_timestamps.pop(key, None)

    def _set_cache_ttl(self, ttl_seconds: int):
        """
        Set cache time-to-live.

        Args:
            ttl_seconds: TTL in seconds
        """
        self._cache_ttl = ttl_seconds
