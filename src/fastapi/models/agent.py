"""
Agent ORM models.

This module contains SQLAlchemy models for agent entities:
- Agent: Basic agent configuration
- ComplianceAgent: Extended agent with compliance-specific features
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, JSON, DateTime
from sqlalchemy.orm import relationship

from models.base import Base


class Agent(Base):
    """
    Basic agent model.

    Attributes:
        id: Primary key
        name: Unique agent name
        model_name: LLM model identifier
        description: Agent description
        created_at: Creation timestamp
        updated_at: Last update timestamp
        is_active: Active status flag
    """
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    model_name = Column(String, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), index=True, onupdate=datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)


class ComplianceAgent(Base):
    """
    Unified agent model supporting all agent types and workflows.

    This model stores agents for compliance checking, document analysis,
    test plan generation, and multi-agent debate scenarios.

    Unified Architecture (supports all workflows):
    - Compliance agents: compliance checking and document analysis
    - Test plan agents: actor, critic, contradiction, gap_analysis
    - Custom agents: user-defined agents for specialized tasks

    Attributes:
        id: Primary key
        name: Unique agent name
        model_name: LLM model identifier (e.g., 'gpt-4', 'claude-3')
        system_prompt: System-level instruction prompt
        user_prompt_template: Template for user prompts
        temperature: LLM temperature (0.0-1.0)
        max_tokens: Maximum tokens for response

        # Unified fields (from test_plan_agents)
        agent_type: Type classification (actor, critic, contradiction, gap_analysis, compliance, custom)
        is_system_default: Whether this is a system-provided default agent
        description: Human-readable description of agent's purpose
        agent_metadata: Additional flexible configuration (JSON)

        # Advanced features
        use_structured_output: Whether to use structured JSON output
        output_schema: JSON schema for structured output
        chain_type: LangChain chain type ('basic', 'sequential', etc.)
        memory_enabled: Whether conversational memory is enabled
        tools_enabled: JSON list of enabled tools

        # Performance tracking
        total_queries: Total number of queries processed
        avg_response_time_ms: Average response time in milliseconds
        success_rate: Success rate (0.0-1.0)

        # Metadata
        created_at: Creation timestamp
        updated_at: Last update timestamp
        created_by: User who created the agent
        is_active: Active status flag

    Relationships:
        sequences: ComplianceSequence records for this agent
        debate_sessions: DebateSession records for this agent
    """
    __tablename__ = "compliance_agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    model_name = Column(String, nullable=False)
    system_prompt = Column(Text, nullable=False)
    user_prompt_template = Column(Text, nullable=False)
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=300)

    # Unified fields for modular agent system
    agent_type = Column(String, index=True)  # actor, critic, contradiction, gap_analysis, compliance, custom
    workflow_type = Column(String, index=True)  # document_analysis, test_plan_generation, general
    is_system_default = Column(Boolean, default=False, index=True)
    description = Column(Text)
    agent_metadata = Column(JSON, default={})

    # Advanced features
    use_structured_output = Column(Boolean, default=False)
    output_schema = Column(JSON)
    chain_type = Column(String, default='basic')
    memory_enabled = Column(Boolean, default=False)
    tools_enabled = Column(JSON, default={})

    # Performance tracking
    total_queries = Column(Integer, default=0)
    avg_response_time_ms = Column(Float)
    success_rate = Column(Float)

    # Metadata
    created_at = Column(DateTime, default=datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), index=True, onupdate=datetime.now(timezone.utc))
    created_by = Column(String)
    is_active = Column(Boolean, default=True)


