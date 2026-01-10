"""
Calendar Pydantic Schemas
"""

from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator


VALID_RECURRENCE_FREQUENCIES = {"daily", "weekly", "monthly"}


class CalendarEventBase(BaseModel):
    """Base calendar event fields."""

    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    start_at: datetime
    end_at: Optional[datetime] = None
    timezone: Optional[str] = Field(None, max_length=100)
    owner_user_id: Optional[int] = None
    test_plan_id: Optional[int] = None
    test_card_id: Optional[int] = None
    recurrence_frequency: Optional[str] = Field(None, description="daily, weekly, or monthly")
    recurrence_interval: int = Field(1, ge=1)
    recurrence_end_date: Optional[date] = None
    percent_complete: float = Field(0, ge=0, le=100)

    @field_validator("recurrence_frequency")
    @classmethod
    def validate_recurrence_frequency(cls, v):
        if v is None:
            return v
        if v not in VALID_RECURRENCE_FREQUENCIES:
            raise ValueError("recurrence_frequency must be daily, weekly, or monthly")
        return v


class CreateCalendarEventRequest(CalendarEventBase):
    """Request schema for creating a calendar event."""


class UpdateCalendarEventRequest(BaseModel):
    """Request schema for updating a calendar event."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    timezone: Optional[str] = Field(None, max_length=100)
    owner_user_id: Optional[int] = None
    test_plan_id: Optional[int] = None
    test_card_id: Optional[int] = None
    recurrence_frequency: Optional[str] = Field(None, description="daily, weekly, or monthly")
    recurrence_interval: Optional[int] = Field(None, ge=1)
    recurrence_end_date: Optional[date] = None
    percent_complete: Optional[float] = Field(None, ge=0, le=100)

    @field_validator("recurrence_frequency")
    @classmethod
    def validate_recurrence_frequency(cls, v):
        if v is None:
            return v
        if v not in VALID_RECURRENCE_FREQUENCIES:
            raise ValueError("recurrence_frequency must be daily, weekly, or monthly")
        return v


class CalendarEventResponse(CalendarEventBase):
    """Response schema for a calendar event."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class CalendarEventListResponse(BaseModel):
    """Response schema for listing calendar events."""

    events: List[CalendarEventResponse]
    total_count: int
