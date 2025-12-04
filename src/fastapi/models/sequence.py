"""
Compliance sequence ORM model.

This module contains the ComplianceSequence model for managing
sequential agent execution workflows.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from models.base import Base


class ComplianceSequence(Base):
    """
    Compliance sequence model for ordered agent execution.

    This model defines the order in which compliance agents should be executed
    in sequential workflows. Useful for multi-step compliance checks where
    agents build upon previous results.

    Attributes:
        id: Primary key
        compliance_agent_id: Foreign key to ComplianceAgent
        sequence_order: Order position in the sequence (1, 2, 3, ...)
        created_at: Creation timestamp

    Relationships:
        compliance_agent: The ComplianceAgent associated with this sequence
    """
    __tablename__ = "compliance_sequence"

    id = Column(Integer, primary_key=True, index=True)
    compliance_agent_id = Column(Integer, ForeignKey("compliance_agents.id"), nullable=False)
    sequence_order = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), index=True)

    # Relationship
    compliance_agent = relationship("ComplianceAgent", back_populates="sequences")
