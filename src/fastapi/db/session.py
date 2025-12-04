"""
Database session management utilities and context managers.

This module provides enhanced session management tools for working with
SQLAlchemy sessions in a safe and consistent manner.
"""

from contextlib import contextmanager
from typing import Generator
from sqlalchemy.orm import Session

from core.database import SessionLocal
from core.exceptions import DatabaseException


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions with automatic cleanup.

    Provides a database session that automatically commits on success
    and rolls back on exceptions.

    Yields:
        Session: SQLAlchemy database session

    Raises:
        DatabaseException: If database operation fails

    Example:
        with get_db_context() as db:
            user = db.query(User).first()
            user.name = "New Name"
            # Automatically commits on exit
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        raise DatabaseException(f"Database operation failed: {str(e)}") from e
    finally:
        db.close()


@contextmanager
def get_db_context_no_commit() -> Generator[Session, None, None]:
    """
    Context manager for database sessions without automatic commit.

    Useful for read-only operations or when you want to control commits manually.

    Yields:
        Session: SQLAlchemy database session

    Example:
        with get_db_context_no_commit() as db:
            users = db.query(User).all()
            # No commit happens
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        raise DatabaseException(f"Database operation failed: {str(e)}") from e
    finally:
        db.close()


class SessionManager:
    """
    Session manager for manual session lifecycle management.

    This class provides explicit control over session lifecycle,
    useful for complex transactions or background tasks.

    Example:
        manager = SessionManager()
        try:
            db = manager.get_session()
            # Do work with db
            manager.commit()
        except Exception:
            manager.rollback()
        finally:
            manager.close()
    """

    def __init__(self):
        self._session: Session = None

    def get_session(self) -> Session:
        """
        Get or create a database session.

        Returns:
            Session: SQLAlchemy database session
        """
        if self._session is None:
            self._session = SessionLocal()
        return self._session

    def commit(self) -> None:
        """Commit the current transaction."""
        if self._session:
            try:
                self._session.commit()
            except Exception as e:
                self._session.rollback()
                raise DatabaseException(f"Commit failed: {str(e)}") from e

    def rollback(self) -> None:
        """Rollback the current transaction."""
        if self._session:
            self._session.rollback()

    def close(self) -> None:
        """Close the database session."""
        if self._session:
            self._session.close()
            self._session = None

    def __enter__(self):
        """Context manager entry."""
        return self.get_session()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with automatic cleanup."""
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()
