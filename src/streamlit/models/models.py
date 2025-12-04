from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# Enums
class MessageRole(str, Enum):
    """Chat message roles"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ModelProvider(str, Enum):
    """AI model providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class DocumentStatus(str, Enum):
    """Document processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# Collection Models
class Collection(BaseModel):
    """ChromaDB collection model"""
    name: str
    created_at: Optional[datetime] = None
    document_count: int = 0
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "name": "legal_documents",
                "document_count": 42,
                "created_at": "2024-01-15T10:30:00Z"
            }
        }


# Document Models
class Document(BaseModel):
    """Document model"""
    document_id: str
    document_name: str
    file_type: str
    total_chunks: int
    has_images: bool = False
    image_count: int = 0
    created_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "doc_123abc",
                "document_name": "contract.pdf",
                "file_type": "pdf",
                "total_chunks": 15,
                "has_images": True,
                "image_count": 3
            }
        }


class DocumentChunk(BaseModel):
    """Individual document chunk"""
    chunk_id: str
    document_id: str
    chunk_index: int
    content: str
    embedding: Optional[List[float]] = None
    metadata: Optional[Dict[str, Any]] = None


# Chat Models
class ChatMessage(BaseModel):
    """Chat message model"""
    id: str
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    model: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "msg_123",
                "role": "assistant",
                "content": "Here is the analysis...",
                "timestamp": "2024-01-15T10:30:00Z",
                "model": "gpt-4"
            }
        }


class ChatRequest(BaseModel):
    """Chat request payload"""
    query: str = Field(..., min_length=1, description="User query")
    model: str = Field(..., description="Model identifier")
    use_rag: bool = Field(default=False, description="Use RAG enhancement")
    collection_name: Optional[str] = Field(None, description="Collection for RAG")
    temperature: float = Field(default=0.7, ge=0, le=2, description="Model temperature")
    max_tokens: Optional[int] = Field(None, gt=0, description="Max tokens to generate")
    top_k: int = Field(default=5, ge=1, le=20, description="Top K results for RAG")

    @field_validator('collection_name')
    @classmethod
    def validate_collection_for_rag(cls, v, info):
        """Validate collection is provided when RAG is enabled"""
        if info.data.get('use_rag') and not v:
            raise ValueError("collection_name is required when use_rag is True")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "query": "Summarize the main points",
                "model": "gpt-4",
                "use_rag": True,
                "collection_name": "legal_docs",
                "temperature": 0.7,
                "top_k": 5
            }
        }


class ChatResponse(BaseModel):
    """Chat response payload"""
    response: str
    session_id: str
    response_time_ms: Optional[int] = None
    model_used: Optional[str] = None
    sources: Optional[List[Dict[str, Any]]] = None
    formatted_citations: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "response": "Based on the documents...",
                "session_id": "session_abc123",
                "response_time_ms": 1250,
                "model_used": "gpt-4",
                "sources": [{"document_id": "doc_123", "relevance": 0.95}]
            }
        }


# Agent Models
class Agent(BaseModel):
    """AI Agent configuration"""
    id: str
    name: str
    model_name: str
    system_prompt: str
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: Optional[int] = Field(None, gt=0)
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "id": "agent_123",
                "name": "Legal Analyst",
                "model_name": "gpt-4",
                "system_prompt": "You are a legal analyst...",
                "temperature": 0.7,
                "description": "Analyzes legal documents"
            }
        }


class AgentResponse(BaseModel):
    """Agent analysis response"""
    agent_id: str
    agent_name: str
    response: str
    confidence: Optional[float] = Field(None, ge=0, le=1)
    processing_time_ms: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


# Upload Models
class UploadOptions(BaseModel):
    """Document upload configuration"""
    collection_name: str = Field(..., min_length=3, max_length=63)
    chunk_size: int = Field(default=1000, ge=100, le=5000)
    chunk_overlap: int = Field(default=200, ge=0, le=1000)
    store_images: bool = Field(default=True)
    vision_models: List[str] = Field(default_factory=list)
    model_name: str = Field(default="enhanced")
    debug_mode: bool = Field(default=False)

    @field_validator('chunk_overlap')
    @classmethod
    def validate_overlap(cls, v, info):
        """Validate overlap is less than chunk size"""
        chunk_size = info.data.get('chunk_size', 1000)
        if v >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "collection_name": "contracts",
                "chunk_size": 1000,
                "chunk_overlap": 200,
                "store_images": True,
                "vision_models": ["openai", "enhanced_local"]
            }
        }


class UploadJob(BaseModel):
    """Document upload job status"""
    job_id: str
    status: DocumentStatus
    total_documents: int
    processed_documents: int
    total_chunks: int
    processed_chunks: int
    documents: List[Dict[str, Any]] = Field(default_factory=list)
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# Legal Research Models
class LegalSearchRequest(BaseModel):
    """Legal research search request"""
    query: str = Field(..., min_length=1)
    sources: List[str] = Field(default_factory=list)
    limit_per_source: int = Field(default=5, ge=1, le=20)
    analyze_relevance: bool = Field(default=True)
    model_name: str = Field(default="gpt-4")


class LegalCase(BaseModel):
    """Legal case result"""
    title: str
    court: str
    date: str
    citation: str
    snippet: str
    url: Optional[str] = None
    relevance_score: float = Field(default=0.0, ge=0, le=1)
    source: str
    metadata: Optional[Dict[str, Any]] = None


# Health Check Models
class HealthStatus(BaseModel):
    """System health status"""
    status: str
    timestamp: datetime = Field(default_factory=datetime.now)
    services: Dict[str, str] = Field(default_factory=dict)
    models: Dict[str, str] = Field(default_factory=dict)
    version: Optional[str] = None
