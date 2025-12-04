"""
Base SQLAlchemy declarative class and common model mixins.

This module provides the foundation for all ORM models in the application.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from sqlalchemy.ext.declarative import declarative_base, declared_attr


# Create base declarative class
Base = declarative_base()


class TimestampMixin:
    """
    Mixin that adds created_at and updated_at timestamp fields.

    Attributes:
        created_at: Timestamp when the record was created (UTC)
        updated_at: Timestamp when the record was last updated (UTC)
    """

    created_at = Column(DateTime, default=datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        nullable=False,
        index=True
    )


class AuditMixin(TimestampMixin):
    """
    Mixin that adds audit tracking fields (timestamps + user tracking).

    Attributes:
        created_at: Timestamp when the record was created (UTC)
        updated_at: Timestamp when the record was last updated (UTC)
        created_by: User who created the record
        updated_by: User who last updated the record
    """

    @declared_attr
    def created_by(cls):
        return Column(String(100), nullable=True)

    @declared_attr
    def updated_by(cls):
        return Column(String(100), nullable=True)


# Note: Individual model classes will be imported here after Phase 2 extraction
# Example:
# from models.agent import Agent, ComplianceAgent
# from models.session import AgentSession, DebateSession
# etc.
