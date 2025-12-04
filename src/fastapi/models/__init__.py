"""
ORM Models package.

This package contains all SQLAlchemy ORM models organized by domain.
All models are imported here for easy access and to ensure proper
model registration with SQLAlchemy.

Usage:
    from models import ComplianceAgent, AgentSession, RAGCitation
    from models.base import Base
    from models.enums import SessionType, AnalysisType
"""

# Import Base and enums
from models.base import Base, TimestampMixin, AuditMixin
from models.enums import SessionType, AnalysisType, SessionStatus, AgentStatus

# Import all models
from models.agent import Agent, ComplianceAgent
from models.chat import ChatHistory
from models.sequence import ComplianceSequence
from models.session import AgentSession, DebateSession
from models.response import AgentResponse, ComplianceResult
from models.citation import RAGCitation

# Configure relationships (bidirectional relationships must be configured after all models are imported)
from sqlalchemy.orm import relationship

# ComplianceAgent relationships
ComplianceAgent.sequences = relationship(
    "ComplianceSequence",
    order_by=ComplianceSequence.sequence_order,
    back_populates="compliance_agent",
    cascade="all, delete-orphan"
)

ComplianceAgent.debate_sessions = relationship(
    "DebateSession",
    order_by=DebateSession.debate_order,
    back_populates="compliance_agent",
    cascade="all, delete-orphan"
)

# Export all models and utilities
__all__ = [
    # Base classes
    "Base",
    "TimestampMixin",
    "AuditMixin",

    # Enums
    "SessionType",
    "AnalysisType",
    "SessionStatus",
    "AgentStatus",

    # Models
    "Agent",
    "ComplianceAgent",
    "ChatHistory",
    "ComplianceSequence",
    "AgentSession",
    "DebateSession",
    "AgentResponse",
    "ComplianceResult",
    "RAGCitation",
]
