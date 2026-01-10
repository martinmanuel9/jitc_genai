"""
Calendar Repository

Data access layer for calendar events.
"""

from sqlalchemy.orm import Session

from models.calendar import CalendarEvent
from repositories.base import BaseRepository


class CalendarEventRepository(BaseRepository[CalendarEvent]):
    """Repository for calendar events."""

    def __init__(self, db: Session):
        super().__init__(CalendarEvent, db)
