"""
Common/shared Pydantic schemas.

This module contains reusable schemas used across the application:
- Base response types
- Pagination schemas
- Error responses
- Common field types
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict, Generic, TypeVar
from datetime import datetime


# Generic type for pagination
T = TypeVar('T')


class BaseResponse(BaseModel):
    """Base response model with standard fields."""
    message: str
    success: bool = True
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    detail: Optional[str] = None
    error_code: Optional[str] = None
    success: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""
    skip: int = Field(default=0, ge=0, description="Number of records to skip")
    limit: int = Field(default=100, ge=1, le=1000, description="Maximum number of records to return")
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: Optional[str] = Field(default="desc", description="Sort order: asc or desc")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response."""
    items: List[T]
    total: int
    skip: int
    limit: int
    has_more: bool = Field(description="Whether more items are available")

    class Config:
        arbitrary_types_allowed = True


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str
    database: Dict[str, Any]
    chromadb: Optional[Dict[str, Any]] = None
    redis: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BulkOperationResponse(BaseModel):
    """Response for bulk operations."""
    successful: int
    failed: int
    total: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    message: str
