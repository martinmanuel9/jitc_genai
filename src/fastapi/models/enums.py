"""
Enumeration types used across ORM models.

This module centralizes all enum definitions to ensure consistency
across the application and make them easy to import.
"""

import enum


class SessionType(enum.Enum):
    """
    Types of agent sessions.

    Attributes:
        SINGLE_AGENT: Single agent executing a task
        MULTI_AGENT_DEBATE: Multiple agents in debate/discussion mode
        RAG_ANALYSIS: RAG-enhanced analysis with a single agent
        RAG_DEBATE: RAG-enhanced multi-agent debate
        COMPLIANCE_CHECK: Compliance verification workflow
    """
    SINGLE_AGENT = "single_agent"
    MULTI_AGENT_DEBATE = "multi_agent_debate"
    RAG_ANALYSIS = "rag_analysis"
    RAG_DEBATE = "rag_debate"
    COMPLIANCE_CHECK = "compliance_check"


class AnalysisType(enum.Enum):
    """
    Types of analysis methods.

    Attributes:
        DIRECT_LLM: Direct LLM call without RAG
        RAG_ENHANCED: RAG-enhanced with vector retrieval
        HYBRID: Combination of direct LLM and RAG
    """
    DIRECT_LLM = "direct_llm"
    RAG_ENHANCED = "rag_enhanced"
    HYBRID = "hybrid"


class SessionStatus(enum.Enum):
    """
    Status of a session.

    Attributes:
        ACTIVE: Session is currently active
        COMPLETED: Session completed successfully
        FAILED: Session failed with an error
        CANCELLED: Session was cancelled
    """
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentStatus(enum.Enum):
    """
    Status of an agent.

    Attributes:
        ACTIVE: Agent is active and can be used
        INACTIVE: Agent is inactive and should not be used
        ARCHIVED: Agent is archived for historical purposes
    """
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"
