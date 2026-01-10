"""
User Repository

Data access layer for user records.
"""

from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models.user import User
from repositories.base import BaseRepository
from core.exceptions import DuplicateException


class UserRepository(BaseRepository[User]):
    """Repository for user records."""

    def __init__(self, db: Session):
        super().__init__(User, db)

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def create_user(self, user_data: dict) -> User:
        existing = self.get_by_email(user_data.get("email"))
        if existing:
            raise DuplicateException("User", "email", user_data.get("email"))

        try:
            return self.create_from_dict(user_data)
        except IntegrityError as e:
            self.db.rollback()
            raise DuplicateException("User", "email", user_data.get("email")) from e
