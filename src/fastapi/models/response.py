"""
Response ORM models.

This module contains SQLAlchemy models for agent responses:
- AgentResponse: Individual agent responses within sessions
- ComplianceResult: Compliance check results
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, ForeignKey, DateTime, Index
from sqlalchemy.orm import relationship

from models.base import Base


class AgentResponse(Base):
    """
    Individual agent response within a session.

    This model stores each agent's response within an AgentSession,
    supporting tracking of multi-agent debates, RAG usage, and
    compliance analysis results.

    Attributes:
        id: Primary key
        session_id: Foreign key to AgentSession
        agent_id: Foreign key to ComplianceAgent
        response_text: Agent's response text
        processing_method: Method used ('langchain', 'rag_enhanced', 'direct_llm')
        response_time_ms: Response time in milliseconds
        sequence_order: Order in debate/sequence (for multi-agent sessions)
        rag_used: Whether RAG was used for this response
        documents_found: Number of documents retrieved (RAG)
        rag_context: The retrieved RAG context
        confidence_score: Confidence score (0.0-1.0)
        analysis_summary: Summary of analysis results
        created_at: Response timestamp
        model_used: LLM model identifier

    Relationships:
        session: The AgentSession this response belongs to
        agent: The ComplianceAgent that generated this response
        citations: RAGCitation records for this response
    """
    __tablename__ = "agent_responses"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("agent_sessions.session_id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(Integer, ForeignKey("compliance_agents.id", ondelete="CASCADE"), nullable=False)

    # Response details
    response_text = Column(Text, nullable=False)
    processing_method = Column(String, nullable=False)  # langchain, rag_enhanced, direct_llm, etc.
    response_time_ms = Column(Integer, nullable=True)

    # Sequence information (for debates)
    sequence_order = Column(Integer, nullable=True)  # Order in debate sequence

    # RAG information
    rag_used = Column(Boolean, default=False)
    documents_found = Column(Integer, default=0)
    rag_context = Column(Text, nullable=True)  # The retrieved context

    # Compliance/Analysis results
    confidence_score = Column(Float, nullable=True)
    analysis_summary = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.now(timezone.utc), index=True)
    model_used = Column(String, nullable=False)

    # Relationships
    session = relationship("AgentSession", back_populates="agent_responses")
    agent = relationship("ComplianceAgent")
    citations = relationship("RAGCitation", back_populates="agent_response", cascade="all, delete-orphan")


class ComplianceResult(Base):
    """
    Compliance check result model.

    This model stores results from compliance checking operations,
    tracking which agents were used, confidence scores, and reasoning.

    Attributes:
        id: Primary key
        session_id: Session identifier (groups related checks)
        agent_id: Foreign key to ComplianceAgent
        data_sample: Input data that was checked
        confidence_score: Confidence score (0.0-1.0)
        reason: Reasoning/explanation for the result
        raw_response: Raw LLM response
        processing_method: Method used for processing
        response_time_ms: Response time in milliseconds
        model_used: LLM model identifier
        created_at: Result timestamp

    Relationships:
        agent: The ComplianceAgent that performed the check
    """
    __tablename__ = "compliance_results"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    agent_id = Column(Integer, ForeignKey("compliance_agents.id"), nullable=False)
    data_sample = Column(Text, nullable=False)
    confidence_score = Column(Float)
    reason = Column(Text)
    raw_response = Column(Text)
    processing_method = Column(String)
    response_time_ms = Column(Integer)
    model_used = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), index=True)

    # Relationship
    agent = relationship("ComplianceAgent")


# Composite indexes for better query performance
Index('idx_compliance_session_agent', ComplianceResult.session_id, ComplianceResult.agent_id)
Index('idx_compliance_agent_created', ComplianceResult.agent_id, ComplianceResult.created_at)
