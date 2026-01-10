"""
Versioning ORM models for documents, test plans, and test cards.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Float,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from models.base import Base


class TestPlan(Base):
    """Logical test plan record with progress tracking."""

    __tablename__ = "test_plans"

    id = Column(Integer, primary_key=True, index=True)
    plan_key = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=True)
    collection_name = Column(String, nullable=True)
    percent_complete = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), index=True)
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        index=True
    )

    versions = relationship(
        "TestPlanVersion",
        back_populates="plan",
        cascade="all, delete-orphan"
    )
    test_cards = relationship("TestCard", back_populates="plan")
    calendar_events = relationship("CalendarEvent", back_populates="test_plan")


class TestPlanVersion(Base):
    """Version record for a test plan stored in Chroma."""

    __tablename__ = "test_plan_versions"
    __table_args__ = (
        UniqueConstraint("plan_id", "version_number", name="uq_test_plan_version"),
    )

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("test_plans.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    document_id = Column(String, nullable=False)
    based_on_version_id = Column(Integer, ForeignKey("test_plan_versions.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), index=True)

    plan = relationship("TestPlan", back_populates="versions")
    based_on_version = relationship("TestPlanVersion", remote_side=[id])


class TestCard(Base):
    """Logical test card record with progress tracking."""

    __tablename__ = "test_cards"

    id = Column(Integer, primary_key=True, index=True)
    card_key = Column(String, unique=True, nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("test_plans.id", ondelete="SET NULL"), nullable=True)
    title = Column(String, nullable=True)
    requirement_id = Column(String, nullable=True)
    percent_complete = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), index=True)
    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc),
        index=True
    )

    versions = relationship(
        "TestCardVersion",
        back_populates="card",
        cascade="all, delete-orphan"
    )
    plan = relationship("TestPlan", back_populates="test_cards")
    calendar_events = relationship("CalendarEvent", back_populates="test_card")


class TestCardVersion(Base):
    """Version record for a test card stored in Chroma."""

    __tablename__ = "test_card_versions"
    __table_args__ = (
        UniqueConstraint("card_id", "version_number", name="uq_test_card_version"),
    )

    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("test_cards.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    document_id = Column(String, nullable=False)
    plan_version_id = Column(Integer, ForeignKey("test_plan_versions.id", ondelete="SET NULL"), nullable=True)
    based_on_version_id = Column(Integer, ForeignKey("test_card_versions.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), index=True)

    card = relationship("TestCard", back_populates="versions")
    based_on_version = relationship("TestCardVersion", remote_side=[id])
    plan_version = relationship("TestPlanVersion")


class DocumentVersion(Base):
    """Version record for a source document stored in Chroma."""

    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_key", "version_number", name="uq_document_version"),
    )

    id = Column(Integer, primary_key=True, index=True)
    document_key = Column(String, nullable=False, index=True)
    document_id = Column(String, nullable=False)
    collection_name = Column(String, nullable=False)
    document_name = Column(String, nullable=True)
    version_number = Column(Integer, nullable=False)
    based_on_version_id = Column(Integer, ForeignKey("document_versions.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), index=True)

    based_on_version = relationship("DocumentVersion", remote_side=[id])
