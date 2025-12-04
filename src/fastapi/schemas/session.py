"""
Session-related Pydantic schemas.

This module contains schemas for:
- Session tracking requests and responses
- Session history and details
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class SessionHistoryRequest(BaseModel):
    """
    Request schema for fetching session history.

    Attributes:
        limit: Maximum number of sessions to return
        session_type: Filter by session type (optional)
        from_date: Filter sessions from this date (optional)
        to_date: Filter sessions to this date (optional)
    """
    limit: int = Field(default=50, ge=1, le=500, description="Maximum number of sessions")
    session_type: Optional[str] = Field(None, description="Filter by session type")
    from_date: Optional[datetime] = Field(None, description="Filter from date")
    to_date: Optional[datetime] = Field(None, description="Filter to date")


class SessionSummary(BaseModel):
    """
    Summary information for a session.

    Attributes:
        session_id: Session identifier
        session_type: Type of session
        analysis_type: Type of analysis
        user_query: User query (truncated)
        collection_name: Collection used (if RAG)
        created_at: Creation timestamp
        completed_at: Completion timestamp
        status: Session status
        agent_count: Number of agents involved
        total_response_time_ms: Total response time
    """
    session_id: str
    session_type: str
    analysis_type: str
    user_query: str
    collection_name: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    agent_count: int
    total_response_time_ms: Optional[int] = None


class SessionHistoryResponse(BaseModel):
    """
    Response schema for session history.

    Attributes:
        sessions: List of session summaries
        total_count: Total number of sessions
    """
    sessions: List[SessionSummary]
    total_count: int


class AgentResponseDetail(BaseModel):
    """
    Detailed agent response within a session.

    Attributes:
        agent_id: Agent identifier
        agent_name: Agent name
        response_text: Response text
        processing_method: Processing method used
        response_time_ms: Response time
        sequence_order: Order in debate sequence
        rag_used: Whether RAG was used
        documents_found: Number of documents found
        confidence_score: Confidence score
        model_used: Model used
        created_at: Creation timestamp
    """
    agent_id: int
    agent_name: str
    response_text: str
    processing_method: str
    response_time_ms: Optional[int] = None
    sequence_order: Optional[int] = None
    rag_used: bool = False
    documents_found: int = 0
    confidence_score: Optional[float] = None
    model_used: str
    created_at: datetime


class SessionDetailsResponse(BaseModel):
    """
    Detailed information about a specific session.

    Attributes:
        session_info: Session metadata
        agent_responses: List of agent responses
    """
    session_info: Dict[str, Any]
    agent_responses: List[AgentResponseDetail]


class CreateSessionRequest(BaseModel):
    """
    Request schema for creating a new session.

    Attributes:
        session_type: Type of session
        analysis_type: Type of analysis
        user_query: User query
        collection_name: Collection name (for RAG)
    """
    session_type: str = Field(..., description="Session type")
    analysis_type: str = Field(..., description="Analysis type")
    user_query: str = Field(..., min_length=1, description="User query")
    collection_name: Optional[str] = Field(None, description="Collection name for RAG")


class CreateSessionResponse(BaseModel):
    """
    Response schema for session creation.

    Attributes:
        session_id: Created session identifier
        message: Success message
    """
    session_id: str
    message: str
