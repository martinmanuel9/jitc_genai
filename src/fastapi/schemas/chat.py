"""
Chat-related Pydantic schemas.

This module contains schemas for:
- Chat history requests and responses
- Chat message structures
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class ChatMessage(BaseModel):
    """
    Individual chat message.

    Attributes:
        role: Message role ('user' or 'assistant')
        content: Message content
        timestamp: Message timestamp
    """
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., min_length=1, description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    """
    Request schema for chat operations.

    Attributes:
        query: User query
        session_id: Session identifier for conversation continuity
        model_name: Model to use (optional)
        collection_name: Collection name for RAG (optional)
        use_rag: Whether to use RAG enhancement
    """
    query: str = Field(..., min_length=1, description="User query")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    model_name: Optional[str] = Field(None, description="Model to use")
    collection_name: Optional[str] = Field(None, description="Collection name for RAG")
    use_rag: bool = Field(default=False, description="Use RAG enhancement")


class ChatResponse(BaseModel):
    """
    Response schema for chat operations.

    Attributes:
        response: Assistant's response
        session_id: Session identifier
        model_used: Model used for generation
        response_time_ms: Response time in milliseconds
        source_documents: Source documents (if RAG was used)
    """
    response: str
    session_id: str
    model_used: str
    response_time_ms: int
    source_documents: Optional[List[Dict[str, Any]]] = None


class ChatHistoryRequest(BaseModel):
    """
    Request schema for fetching chat history.

    Attributes:
        session_id: Session identifier to fetch history for
        limit: Maximum number of messages to return
        offset: Offset for pagination
    """
    session_id: str = Field(..., description="Session ID")
    limit: int = Field(default=100, ge=1, le=500, description="Maximum messages")
    offset: int = Field(default=0, ge=0, description="Offset for pagination")


class ChatHistoryResponse(BaseModel):
    """
    Response schema for chat history.

    Attributes:
        session_id: Session identifier
        messages: List of chat messages
        total_count: Total number of messages in session
    """
    session_id: str
    messages: List[Dict[str, Any]]
    total_count: int


class ChatSessionSummary(BaseModel):
    """
    Summary of a chat session.

    Attributes:
        session_id: Session identifier
        first_message_timestamp: Timestamp of first message
        last_message_timestamp: Timestamp of last message
        message_count: Number of messages
        model_used: Primary model used
        collection_name: Collection used (if RAG)
    """
    session_id: str
    first_message_timestamp: datetime
    last_message_timestamp: datetime
    message_count: int
    model_used: str
    collection_name: Optional[str] = None


class ChatSessionListResponse(BaseModel):
    """
    Response schema for listing chat sessions.

    Attributes:
        sessions: List of session summaries
        total_count: Total number of sessions
    """
    sessions: List[ChatSessionSummary]
    total_count: int
