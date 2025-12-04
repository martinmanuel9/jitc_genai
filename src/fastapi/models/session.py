"""
Session ORM models.

This module contains SQLAlchemy models for tracking agent sessions:
- AgentSession: Main session tracking for agent interactions
- DebateSession: Specialized session for multi-agent debates
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, ForeignKey, Enum, JSON, DateTime
from sqlalchemy.orm import relationship

from models.base import Base
from models.enums import SessionType, AnalysisType


class AgentSession(Base):
    """
    Agent session model for tracking all types of agent interactions.

    This model serves as the central record for agent execution sessions,
    supporting single-agent queries, multi-agent debates, RAG-enhanced
    analysis, and compliance checks.

    Attributes:
        id: Primary key
        session_id: Unique session identifier (UUID)
        session_type: Type of session (SessionType enum)
        analysis_type: Type of analysis (AnalysisType enum)
        user_query: Original user query
        collection_name: ChromaDB collection (for RAG sessions)
        created_at: Session start timestamp
        completed_at: Session completion timestamp
        total_response_time_ms: Total time for all agent responses
        status: Session status ('active', 'completed', 'failed')
        error_message: Error message if failed
        overall_result: JSON summary of results
        agent_count: Number of agents involved

    Relationships:
        agent_responses: All AgentResponse records for this session
    """
    __tablename__ = "agent_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, nullable=False, index=True)
    session_type = Column(Enum(SessionType), nullable=False)
    analysis_type = Column(Enum(AnalysisType), nullable=False)

    # Input data
    user_query = Column(Text, nullable=False)
    collection_name = Column(String, nullable=True)  # For RAG sessions

    # Session metadata
    created_at = Column(DateTime, default=datetime.now(timezone.utc), index=True)
    completed_at = Column(DateTime, nullable=True)
    total_response_time_ms = Column(Integer, nullable=True)

    # Session status
    status = Column(String, default='active')  # active, completed, failed
    error_message = Column(Text, nullable=True)

    # Results summary
    overall_result = Column(JSON, nullable=True)  # Summary of all agent responses
    agent_count = Column(Integer, default=0)

    # Relationships
    agent_responses = relationship("AgentResponse", back_populates="session", cascade="all, delete-orphan")


class DebateSession(Base):
    """
    Debate session model for multi-agent debate tracking.

    This model tracks individual agent contributions within a multi-agent
    debate, preserving debate order and agent-specific results.

    Attributes:
        id: Primary key
        session_id: Session identifier (groups multiple debate turns)
        compliance_agent_id: Foreign key to ComplianceAgent
        debate_order: Order of this agent in the debate (1, 2, 3, ...)
        created_at: Creation timestamp
        status: Debate turn status ('active', 'completed', etc.)
        initial_data: Input data for this debate turn
        agent_response: Agent's response text
        response_time_ms: Response time for this agent

    Relationships:
        compliance_agent: The ComplianceAgent participating in this debate
    """
    __tablename__ = "debate_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    compliance_agent_id = Column(Integer, ForeignKey("compliance_agents.id"), nullable=False)
    debate_order = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), index=True)
    status = Column(String, default='active')
    initial_data = Column(Text)
    agent_response = Column(Text)
    response_time_ms = Column(Integer)

    # Relationship
    compliance_agent = relationship("ComplianceAgent", back_populates="debate_sessions")
