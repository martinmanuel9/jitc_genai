"""
Response Schemas

Pydantic models for API responses across all endpoints.
Provides consistent response structure and automatic API documentation.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum


# ============================================================================
# Status Enums
# ============================================================================

class JobStatus(str, Enum):
    """Status of background jobs"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class HealthStatus(str, Enum):
    """Health check status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


# ============================================================================
# Base Response Models
# ============================================================================

class BaseResponse(BaseModel):
    """Base response model with common fields"""
    success: bool = Field(..., description="Whether operation succeeded")
    message: Optional[str] = Field(None, description="Human-readable message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")

    model_config = ConfigDict(from_attributes=True)


class DataResponse(BaseResponse):
    """Response model that includes a data payload"""
    data: Any = Field(..., description="Response data payload")

    model_config = ConfigDict(from_attributes=True)


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Machine-readable error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "error": "Invalid collection name",
            "error_code": "VALIDATION_ERROR",
            "details": {"field": "collection_name", "issue": "too short"},
            "timestamp": "2025-01-15T10:30:00Z"
        }
    })


# ============================================================================
# Chat & Query Responses
# ============================================================================

class ChatResponse(BaseResponse):
    """Response from chat/query operations"""
    response: str = Field(..., description="LLM response text")
    model_used: str = Field(..., description="Model that generated response")
    query_type: str = Field(..., description="Type of query performed")
    response_time_ms: int = Field(..., description="Response time in milliseconds")
    session_id: Optional[str] = Field(None, description="Session identifier")
    formatted_citations: Optional[str] = Field(None, description="Formatted citation text")
    source_documents: Optional[List[str]] = Field(None, description="Source document names")
    documents_found: int = Field(0, description="Number of documents retrieved")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "success": True,
            "response": "The compliance requirements include...",
            "model_used": "gpt-4",
            "query_type": "rag",
            "response_time_ms": 1234,
            "documents_found": 5
        }
    })


# ============================================================================
# Document Responses
# ============================================================================

class DocumentMetadata(BaseModel):
    """Document metadata"""
    document_id: str = Field(..., description="Unique document identifier")
    document_name: str = Field(..., description="Document name")
    file_type: str = Field(..., description="File type/extension")
    total_chunks: int = Field(..., description="Total number of chunks")
    has_images: bool = Field(False, description="Whether document contains images")
    image_count: int = Field(0, description="Number of images")
    upload_date: Optional[datetime] = Field(None, description="Upload timestamp")


class DocumentUploadResponse(BaseResponse):
    """Response from document upload"""
    job_id: Optional[str] = Field(None, description="Job ID for async processing")
    documents_processed: int = Field(0, description="Number of documents processed")
    total_chunks: int = Field(0, description="Total chunks created")
    collection_name: str = Field(..., description="Target collection")
    processing_time_ms: Optional[int] = Field(None, description="Processing time")


class JobStatusResponse(BaseModel):
    """Response for job status check"""
    job_id: str = Field(..., description="Job identifier")
    status: JobStatus = Field(..., description="Current job status")
    progress: Optional[float] = Field(None, ge=0.0, le=100.0, description="Progress percentage")
    result: Optional[Dict[str, Any]] = Field(None, description="Job result if completed")
    error: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime = Field(..., description="Job creation time")
    updated_at: datetime = Field(..., description="Last update time")


# ============================================================================
# Collection Responses
# ============================================================================

class CollectionInfo(BaseModel):
    """Collection information"""
    name: str = Field(..., description="Collection name")
    count: int = Field(0, description="Number of documents")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Collection metadata")


class CollectionListResponse(BaseResponse):
    """Response with list of collections"""
    collections: List[str] = Field(..., description="Collection names")
    count: int = Field(..., description="Total number of collections")


class CollectionDetailResponse(BaseResponse):
    """Response with collection details"""
    collection: CollectionInfo = Field(..., description="Collection information")
    documents: Optional[List[DocumentMetadata]] = Field(None, description="Document list")


# ============================================================================
# Agent Responses
# ============================================================================

class AgentInfo(BaseModel):
    """Agent information"""
    id: int = Field(..., description="Agent ID")
    name: str = Field(..., description="Agent name")
    model_name: str = Field(..., description="Model used")
    system_prompt: str = Field(..., description="System prompt")
    user_prompt_template: str = Field(..., description="User prompt template")
    temperature: float = Field(..., description="Temperature setting")
    max_tokens: Optional[int] = Field(None, description="Max tokens")
    tools_enabled: Optional[Union[bool, Dict[str, Any]]] = Field(None, description="Tools enabled (boolean or tool configuration)")
    is_active: bool = Field(True, description="Active status")
    total_queries: int = Field(0, description="Total queries processed")
    avg_response_time_ms: Optional[float] = Field(None, description="Average response time")
    success_rate: Optional[float] = Field(None, description="Success rate percentage")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class AgentListResponse(BaseResponse):
    """Response with list of agents"""
    agents: List[AgentInfo] = Field(..., description="List of agents")
    count: int = Field(..., description="Total number of agents")


class AgentDetailResponse(BaseResponse):
    """Response with agent details"""
    agent: AgentInfo = Field(..., description="Agent information")


# ============================================================================
# Analytics Responses
# ============================================================================

class AnalyticsData(BaseModel):
    """Analytics metrics"""
    total_responses: int = Field(0, description="Total responses")
    avg_response_time_ms: float = Field(0.0, description="Average response time")
    rag_usage_rate: float = Field(0.0, description="RAG usage percentage")
    avg_documents_found: float = Field(0.0, description="Average documents retrieved")
    avg_confidence_score: Optional[float] = Field(None, description="Average confidence score")
    total_queries: int = Field(0, description="Total queries")
    success_rate: float = Field(0.0, description="Success rate percentage")
    unique_sessions: int = Field(0, description="Unique sessions")


class AnalyticsResponse(BaseResponse):
    """Response with analytics data"""
    analytics: AnalyticsData = Field(..., description="Analytics metrics")
    period_start: Optional[datetime] = Field(None, description="Period start")
    period_end: Optional[datetime] = Field(None, description="Period end")


# ============================================================================
# Health Check Responses
# ============================================================================

class ServiceHealth(BaseModel):
    """Health status of a service"""
    status: HealthStatus = Field(..., description="Service health status")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class HealthCheckResponse(BaseModel):
    """Response from health check"""
    status: HealthStatus = Field(..., description="Overall health status")
    timestamp: datetime = Field(..., description="Check timestamp")
    services: Dict[str, ServiceHealth] = Field(..., description="Individual service statuses")
    version: Optional[str] = Field(None, description="API version")


# ============================================================================
# Citation Responses
# ============================================================================

class Citation(BaseModel):
    """Citation information"""
    document_name: str = Field(..., description="Document name")
    document_id: Optional[str] = Field(None, description="Document ID")
    page_number: Optional[int] = Field(None, description="Page number")
    chunk_index: Optional[int] = Field(None, description="Chunk index")
    excerpt: str = Field(..., description="Text excerpt")
    relevance_score: Optional[float] = Field(None, description="Relevance/distance score")
    quality_tier: Optional[str] = Field(None, description="Quality indicator")
    collection_name: Optional[str] = Field(None, description="Source collection")


class CitationResponse(BaseResponse):
    """Response with citations"""
    citations: List[Citation] = Field(..., description="List of citations")
    formatted_citations: Optional[str] = Field(None, description="Pre-formatted citation text")


# ============================================================================
# Export Responses
# ============================================================================

class ExportResponse(BaseResponse):
    """Response from export operations"""
    filename: str = Field(..., description="Generated filename")
    content_b64: str = Field(..., description="Base64-encoded content")
    content_type: str = Field(..., description="MIME type")
    size_bytes: int = Field(..., description="File size in bytes")


# ============================================================================
# Session Responses
# ============================================================================

class SessionInfo(BaseModel):
    """Session information"""
    session_id: str = Field(..., description="Session identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    query_count: int = Field(0, description="Number of queries in session")
    last_activity: Optional[datetime] = Field(None, description="Last activity timestamp")


class SessionHistoryResponse(BaseResponse):
    """Response with session history"""
    session: SessionInfo = Field(..., description="Session information")
    queries: List[Dict[str, Any]] = Field(..., description="Query history")


# ============================================================================
# Batch Operation Responses
# ============================================================================

class BatchResult(BaseModel):
    """Result from a single batch item"""
    index: int = Field(..., description="Item index")
    success: bool = Field(..., description="Whether operation succeeded")
    result: Optional[Any] = Field(None, description="Operation result")
    error: Optional[str] = Field(None, description="Error message if failed")


class BatchResponse(BaseResponse):
    """Response from batch operations"""
    total: int = Field(..., description="Total items processed")
    successful: int = Field(..., description="Number of successful operations")
    failed: int = Field(..., description="Number of failed operations")
    results: List[BatchResult] = Field(..., description="Individual results")
    processing_time_ms: int = Field(..., description="Total processing time")


# ============================================================================
# Pagination Support
# ============================================================================

class PaginationMeta(BaseModel):
    """Pagination metadata"""
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, le=100, description="Items per page")
    total_items: int = Field(..., description="Total number of items")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether next page exists")
    has_prev: bool = Field(..., description="Whether previous page exists")


class PaginatedResponse(BaseResponse):
    """Response with pagination"""
    data: List[Any] = Field(..., description="Page data")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")
