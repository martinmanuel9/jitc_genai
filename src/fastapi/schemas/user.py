"""
User Pydantic Schemas
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime


class UserBase(BaseModel):
    """Base user fields."""

    name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., min_length=3, max_length=255)
    org: Optional[str] = Field(None, max_length=255)
    role: Optional[str] = Field(None, max_length=255)


class CreateUserRequest(UserBase):
    """Request schema for creating a user."""


class UpdateUserRequest(BaseModel):
    """Request schema for updating a user."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[str] = Field(None, min_length=3, max_length=255)
    org: Optional[str] = Field(None, max_length=255)
    role: Optional[str] = Field(None, max_length=255)


class UserResponse(UserBase):
    """Response schema for a user."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class UserListResponse(BaseModel):
    """Response schema for listing users."""

    users: List[UserResponse]
    total_count: int
