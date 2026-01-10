"""
Calendar ORM model.

Supports scheduling for test plans and test cards with simple recurrence.
"""

from datetime import datetime, timezone as dt_timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Date, ForeignKey
from sqlalchemy.orm import relationship

from models.base import Base


class CalendarEvent(Base):
    """Calendar event tied to a user and optional plan/card."""

    __tablename__ = "calendar_events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    start_at = Column(DateTime, nullable=False, index=True)
    end_at = Column(DateTime, nullable=True)
    timezone = Column(String, nullable=True)
    owner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    test_plan_id = Column(Integer, ForeignKey("test_plans.id", ondelete="SET NULL"), nullable=True)
    test_card_id = Column(Integer, ForeignKey("test_cards.id", ondelete="SET NULL"), nullable=True)
    recurrence_frequency = Column(String, nullable=True)
    recurrence_interval = Column(Integer, default=1)
    recurrence_end_date = Column(Date, nullable=True)
    percent_complete = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.now(dt_timezone.utc), index=True)
    updated_at = Column(
        DateTime,
        default=datetime.now(dt_timezone.utc),
        onupdate=datetime.now(dt_timezone.utc),
        index=True
    )

    owner = relationship("User", back_populates="calendar_events")
    test_plan = relationship("TestPlan", back_populates="calendar_events")
    test_card = relationship("TestCard", back_populates="calendar_events")
