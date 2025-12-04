"""
Agent Set ORM models.

This module contains SQLAlchemy models for agent set orchestration:
- AgentSet: Reusable collections of agents with execution configuration
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, JSON, DateTime

from models.base import Base


class AgentSet(Base):
    """
    Agent set model for configurable test plan orchestration.

    Agent sets define reusable collections of agents that execute together in a pipeline.
    Similar to AI Agent Simulation's sequence builder, this allows users to create
    custom workflows like:
    - "Actor (3x parallel) → Critic → QA (Contradiction + Gap)"
    - "Quick Draft: Actor (1x) → Critic"
    - "Custom: Critic + Actor + Gap (parallel) → Synthesis"

    Integrates with MultiAgentTestPlanService for dynamic pipeline execution.
    Replaces hardcoded agent orchestration with database-backed, user-configurable pipelines.

    Attributes:
        id: Primary key
        name: Unique set name (e.g., "Standard Test Plan Pipeline")
        description: Human-readable description of set's purpose and use case
        set_type: Type of set ('sequence' for ordered execution, 'parallel' for concurrent)
        set_config: JSON configuration defining stages, agents, and execution modes
            Example structure:
            {
                "stages": [
                    {
                        "stage_name": "actor",
                        "agent_ids": [1, 1, 1],  # Can include same agent multiple times
                        "execution_mode": "parallel",
                        "description": "3 actor agents analyze sections in parallel"
                    },
                    {
                        "stage_name": "critic",
                        "agent_ids": [2],
                        "execution_mode": "sequential",
                        "description": "Critic synthesizes actor outputs"
                    },
                    {
                        "stage_name": "qa",
                        "agent_ids": [3, 4],  # Contradiction and Gap Analysis
                        "execution_mode": "parallel",
                        "description": "QA agents run in parallel"
                    }
                ]
            }
        is_system_default: Whether this is a system-provided default set
        is_active: Active status flag (soft delete)
        usage_count: Number of times this set has been used (incremented on each generation)
        created_at: Creation timestamp
        updated_at: Last update timestamp
        created_by: User who created/modified the set
    """
    __tablename__ = "agent_sets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text)
    set_type = Column(String, nullable=False, default='sequence', index=True)
    set_config = Column(JSON, nullable=False)
    is_system_default = Column(Boolean, default=False, index=True)
    is_active = Column(Boolean, default=True, index=True)
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), index=True, onupdate=datetime.now(timezone.utc))
    created_by = Column(String)
