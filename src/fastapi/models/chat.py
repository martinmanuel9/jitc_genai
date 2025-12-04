"""
Chat history ORM model.

This module contains the ChatHistory model for storing conversation history.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Index

from models.base import Base


class ChatHistory(Base):
    """
    Chat history model for storing user conversations and responses.

    This model tracks all chat interactions, including queries, responses,
    model usage, and source documents for RAG queries.

    Attributes:
        id: Primary key
        user_query: User's original query
        response: System response
        model_used: LLM model identifier
        collection_name: ChromaDB collection used (for RAG queries)
        query_type: Type of query ('direct', 'rag', 'hybrid')
        response_time_ms: Response time in milliseconds
        timestamp: Query timestamp
        session_id: Session identifier for grouping related queries
        source_documents: JSON array of source documents used
    """
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    user_query = Column(Text)
    response = Column(Text)
    model_used = Column(String)
    collection_name = Column(String)
    query_type = Column(String)
    response_time_ms = Column(Integer)
    timestamp = Column(DateTime, default=datetime.now(timezone.utc), index=True)
    session_id = Column(String, index=True)
    source_documents = Column(JSON)


# Composite indexes for better query performance
Index('idx_chat_session_timestamp', ChatHistory.session_id, ChatHistory.timestamp)
Index('idx_chat_model_type', ChatHistory.model_used, ChatHistory.query_type)
