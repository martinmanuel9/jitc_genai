"""
Request Validation Schemas

Pydantic models for API request validation across all endpoints.
Provides type safety, automatic validation, and API documentation.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from enum import Enum


# ============================================================================
# Enums for validation
# ============================================================================

class QueryType(str, Enum):
    """Type of query being performed"""
    DIRECT = "direct"
    RAG = "rag"
    RAG_ENHANCED = "rag_enhanced"


class ExportFormat(str, Enum):
    """Document export formats"""
    DOCX = "docx"
    PDF = "pdf"
    JSON = "json"
    CSV = "csv"


class ModelProvider(str, Enum):
    """LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


# ============================================================================
# Chat & Query Requests
# ============================================================================

class ChatRequest(BaseModel):
    """Request for chat/query operations"""
    query: str = Field(..., min_length=1, max_length=10000, description="User query text")
    model_name: str = Field(..., description="LLM model to use")
    collection_name: Optional[str] = Field(None, description="Collection for RAG queries")
    query_type: QueryType = Field(QueryType.DIRECT, description="Type of query")
    session_id: Optional[str] = Field(None, description="Session identifier")
    agent_id: Optional[int] = Field(None, description="Agent ID if using agent")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Model temperature")
    max_tokens: Optional[int] = Field(None, ge=1, le=32000, description="Maximum tokens")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "query": "What are the compliance requirements?",
            "model_name": "gpt-4",
            "collection_name": "policies",
            "query_type": "rag",
            "session_id": "session-123"
        }
    })

    @field_validator('query')
    @classmethod
    def query_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Query cannot be empty or whitespace only')
        return v.strip()


# ============================================================================
# Document Upload & Processing Requests
# ============================================================================

class DocumentUploadRequest(BaseModel):
    """Request for document upload and processing"""
    collection_name: str = Field(..., min_length=3, max_length=63, description="Target collection")
    chunk_size: int = Field(1000, ge=100, le=5000, description="Chunk size in characters")
    chunk_overlap: int = Field(200, ge=0, le=1000, description="Overlap between chunks")
    store_images: bool = Field(True, description="Whether to store and process images")
    model_name: str = Field("enhanced", description="Processing model")
    vision_models: List[str] = Field(default_factory=list, description="Vision models to use")

    @field_validator('collection_name')
    @classmethod
    def validate_collection_name(cls, v):
        """Validate collection name follows ChromaDB rules"""
        if not v:
            raise ValueError('Collection name cannot be empty')

        # ChromaDB requirements
        v = v.strip().lower()
        v = v.replace(' ', '_')

        # Must be 3-63 characters, start/end with alphanumeric
        if len(v) < 3:
            raise ValueError('Collection name must be at least 3 characters')
        if len(v) > 63:
            raise ValueError('Collection name must be at most 63 characters')
        if not v[0].isalnum() or not v[-1].isalnum():
            raise ValueError('Collection name must start and end with alphanumeric character')

        return v

    @field_validator('chunk_overlap')
    @classmethod
    def overlap_not_larger_than_chunk(cls, v, info):
        """Ensure overlap is not larger than chunk size"""
        chunk_size = info.data.get('chunk_size', 1000)
        if v >= chunk_size:
            raise ValueError(f'Chunk overlap ({v}) must be less than chunk size ({chunk_size})')
        return v


class URLIngestRequest(BaseModel):
    """Request for URL ingestion"""
    url: str = Field(..., description="URL to ingest")
    collection_name: str = Field(..., min_length=3, max_length=63, description="Target collection")

    @field_validator('url')
    @classmethod
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v


# ============================================================================
# Collection Management Requests
# ============================================================================

class CollectionCreateRequest(BaseModel):
    """Request to create a collection"""
    name: str = Field(..., min_length=3, max_length=63, description="Collection name")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        """Validate collection name follows ChromaDB rules"""
        if not v:
            raise ValueError('Collection name cannot be empty')

        v = v.strip().lower().replace(' ', '_')

        if len(v) < 3 or len(v) > 63:
            raise ValueError('Collection name must be 3-63 characters')
        if not v[0].isalnum() or not v[-1].isalnum():
            raise ValueError('Collection name must start and end with alphanumeric character')

        return v


class CollectionDeleteRequest(BaseModel):
    """Request to delete a collection"""
    name: str = Field(..., description="Collection name to delete")


# ============================================================================
# Agent Management Requests
# ============================================================================

class AgentCreateRequest(BaseModel):
    """Request to create an agent"""
    name: str = Field(..., min_length=1, max_length=200, description="Agent name")
    model_name: str = Field(..., description="LLM model")
    system_prompt: str = Field(..., min_length=1, description="System prompt")
    user_prompt_template: str = Field(..., min_length=1, description="User prompt template")
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="Temperature")
    max_tokens: Optional[int] = Field(None, ge=1, le=32000, description="Max tokens")
    tools_enabled: Optional[Union[bool, Dict[str, Any]]] = Field(False, description="Enable tools (boolean or tool configuration)")
    is_active: bool = Field(True, description="Active status")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "Compliance Agent",
            "model_name": "gpt-4",
            "system_prompt": "You are a compliance expert.",
            "user_prompt_template": "Analyze: {data_sample}",
            "temperature": 0.7
        }
    })


class AgentUpdateRequest(BaseModel):
    """Request to update an agent"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    model_name: Optional[str] = None
    system_prompt: Optional[str] = Field(None, min_length=1)
    user_prompt_template: Optional[str] = Field(None, min_length=1)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=32000)
    tools_enabled: Optional[Union[bool, Dict[str, Any]]] = None
    is_active: Optional[bool] = None


# ============================================================================
# RAG Assessment Requests
# ============================================================================

class RAGAssessmentRequest(BaseModel):
    """Request for RAG quality assessment"""
    query: str = Field(..., min_length=1, description="Query text")
    collection_name: str = Field(..., description="Collection to assess")
    agent_ids: Optional[List[int]] = Field(None, description="Specific agents to use")
    model_name: str = Field("gpt-4", description="Assessment model")
    include_citations: bool = Field(True, description="Include citations")

    @field_validator('query')
    @classmethod
    def query_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Query cannot be empty')
        return v.strip()


# ============================================================================
# Analytics Requests
# ============================================================================

class AnalyticsRequest(BaseModel):
    """Request for analytics data"""
    start_date: Optional[datetime] = Field(None, description="Start date for filtering")
    end_date: Optional[datetime] = Field(None, description="End date for filtering")
    agent_id: Optional[int] = Field(None, description="Filter by agent")
    model_name: Optional[str] = Field(None, description="Filter by model")
    collection_name: Optional[str] = Field(None, description="Filter by collection")

    @field_validator('end_date')
    @classmethod
    def end_after_start(cls, v, info):
        """Ensure end date is after start date"""
        start_date = info.data.get('start_date')
        if start_date and v and v < start_date:
            raise ValueError('End date must be after start date')
        return v


# ============================================================================
# Export Requests
# ============================================================================

class ExportRequest(BaseModel):
    """Request for document export"""
    format: ExportFormat = Field(ExportFormat.DOCX, description="Export format")
    data: Dict[str, Any] = Field(..., description="Data to export")
    filename: Optional[str] = Field(None, description="Custom filename")


class WordExportRequest(BaseModel):
    """Request for Word document export"""
    content: str = Field(..., description="Content to export")
    title: Optional[str] = Field(None, description="Document title")
    author: Optional[str] = Field(None, description="Document author")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


# ============================================================================
# Legal Research Requests
# ============================================================================

class LegalResearchRequest(BaseModel):
    """Request for legal research"""
    query: str = Field(..., min_length=1, description="Research query")
    collection_name: Optional[str] = Field(None, description="Internal collection")
    include_external: bool = Field(True, description="Include external sources")
    agent_ids: Optional[List[int]] = Field(None, description="Agents to use")
    jurisdiction: Optional[str] = Field(None, description="Legal jurisdiction")
    date_range_start: Optional[datetime] = Field(None, description="Start date for cases")
    date_range_end: Optional[datetime] = Field(None, description="End date for cases")


# ============================================================================
# Batch Operations
# ============================================================================

class BatchQueryRequest(BaseModel):
    """Request for batch query operations"""
    queries: List[str] = Field(..., min_items=1, max_items=100, description="List of queries")
    model_name: str = Field(..., description="Model to use")
    collection_name: Optional[str] = Field(None, description="Collection for RAG")
    query_type: QueryType = Field(QueryType.DIRECT, description="Query type")

    @field_validator('queries')
    @classmethod
    def validate_queries(cls, v):
        """Ensure all queries are non-empty"""
        cleaned = [q.strip() for q in v if q and q.strip()]
        if not cleaned:
            raise ValueError('At least one non-empty query required')
        return cleaned


# ============================================================================
# Helper Functions
# ============================================================================

def validate_model_name(model_name: str) -> str:
    """
    Validate model name against supported models.

    Args:
        model_name: Model identifier

    Returns:
        Validated model name

    Raises:
        ValueError: If model is not supported
    """
    from llm_config.llm_config import validate_model

    is_valid, error = validate_model(model_name)
    if not is_valid:
        raise ValueError(error)
    return model_name
