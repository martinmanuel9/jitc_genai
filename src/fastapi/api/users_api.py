"""
User Management API
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from repositories.user_repository import UserRepository
from schemas.user import (
    CreateUserRequest,
    UpdateUserRequest,
    UserResponse,
    UserListResponse,
)
from core.exceptions import DuplicateException


router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


@router.get("", response_model=UserListResponse)
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    repo = UserRepository(db)
    users = repo.get_all(skip=skip, limit=limit, order_by="created_at", order_desc=True)
    total = repo.count()
    return UserListResponse(
        users=[UserResponse.from_orm(user) for user in users],
        total_count=total
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    repo = UserRepository(db)
    user = repo.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse.from_orm(user)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(request: CreateUserRequest, db: Session = Depends(get_db)):
    repo = UserRepository(db)
    try:
        user = repo.create_user(request.dict())
    except DuplicateException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)
    return UserResponse.from_orm(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    request: UpdateUserRequest,
    db: Session = Depends(get_db)
):
    repo = UserRepository(db)
    updates = request.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    try:
        user = repo.update_by_id(user_id, updates)
    except DuplicateException as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=e.message)

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse.from_orm(user)


@router.delete("/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(get_db)):
    repo = UserRepository(db)
    user = repo.get(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    repo.delete(user)
    return {"message": "User deleted", "user_id": user_id}
