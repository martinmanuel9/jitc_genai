"""
Calendar Events API
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from repositories.calendar_repository import CalendarEventRepository
from models.calendar import CalendarEvent
from schemas.calendar import (
    CreateCalendarEventRequest,
    UpdateCalendarEventRequest,
    CalendarEventResponse,
    CalendarEventListResponse,
)


router = APIRouter(
    prefix="/calendar",
    tags=["Calendar"]
)


@router.get("/events", response_model=CalendarEventListResponse)
async def list_events(
    owner_user_id: Optional[int] = None,
    start_at: Optional[datetime] = None,
    end_at: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    repo = CalendarEventRepository(db)
    query = db.query(CalendarEvent)

    if owner_user_id is not None:
        query = query.filter(CalendarEvent.owner_user_id == owner_user_id)
    if start_at is not None:
        query = query.filter(CalendarEvent.start_at >= start_at)
    if end_at is not None:
        query = query.filter(CalendarEvent.start_at <= end_at)

    total = query.count()
    events = (
        query.order_by(CalendarEvent.start_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return CalendarEventListResponse(
        events=[CalendarEventResponse.from_orm(event) for event in events],
        total_count=total
    )


@router.get("/events/{event_id}", response_model=CalendarEventResponse)
async def get_event(event_id: int, db: Session = Depends(get_db)):
    repo = CalendarEventRepository(db)
    event = repo.get(event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return CalendarEventResponse.from_orm(event)


@router.post("/events", response_model=CalendarEventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(request: CreateCalendarEventRequest, db: Session = Depends(get_db)):
    repo = CalendarEventRepository(db)
    event = repo.create_from_dict(request.dict())
    return CalendarEventResponse.from_orm(event)


@router.put("/events/{event_id}", response_model=CalendarEventResponse)
async def update_event(
    event_id: int,
    request: UpdateCalendarEventRequest,
    db: Session = Depends(get_db)
):
    repo = CalendarEventRepository(db)
    updates = request.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    event = repo.update_by_id(event_id, updates)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return CalendarEventResponse.from_orm(event)


@router.delete("/events/{event_id}")
async def delete_event(event_id: int, db: Session = Depends(get_db)):
    repo = CalendarEventRepository(db)
    event = repo.get(event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    repo.delete(event)
    return {"message": "Event deleted", "event_id": event_id}
