"""
Unit of Work Pattern

This module implements the Unit of Work pattern to coordinate transactions
across multiple repositories. It provides atomic operations and simplifies
service layer logic by managing commit/rollback operations.

The Unit of Work pattern ensures that:
- All repository operations within a transaction share the same database session
- Multiple operations can be grouped together and committed atomically
- Failed operations trigger rollback of all changes
- Resources are properly cleaned up

Usage:
    # Basic usage with manual commit
    from core.database import get_db

    db = next(get_db())
    uow = UnitOfWork(db)
    try:
        agent = uow.agents.create_agent(agent_data)
        session = uow.sessions.create_session(session_data)
        uow.commit()
    except Exception:
        uow.rollback()
        raise
    finally:
        db.close()

    # Recommended: Use as context manager for automatic cleanup
    with UnitOfWork(db) as uow:
        agent = uow.agents.create_agent(agent_data)
        response = uow.responses.create_response(response_data)
        uow.citations.bulk_create_citations(response.id, citation_data)
        uow.commit()  # Commits all changes atomically
    # Automatic rollback on exception, cleanup on exit

    # In FastAPI routes with dependency injection
    def create_analysis(
        data: AnalysisRequest,
        db: Session = Depends(get_db)
    ):
        with UnitOfWork(db) as uow:
            session = uow.sessions.create_session(...)
            response = uow.responses.create_response(...)
            uow.commit()
            return response
"""

from sqlalchemy.orm import Session
from typing import Optional
import logging

from repositories.agent_repository import AgentRepository
from repositories.session_repository import SessionRepository
from repositories.response_repository import ResponseRepository, ComplianceRepository
from repositories.citation_repository import CitationRepository
from repositories.chat_repository import ChatRepository

logger = logging.getLogger("UNIT_OF_WORK")


class UnitOfWork:
    """
    Unit of Work pattern implementation for coordinating transactions.

    Manages a single database session shared across multiple repositories,
    ensuring atomic operations and proper transaction handling.

    All repositories share the same database session, so changes across
    repositories can be committed or rolled back together.

    Attributes:
        db: SQLAlchemy database session
        agents: AgentRepository instance
        sessions: SessionRepository instance
        responses: ResponseRepository instance
        compliance: ComplianceRepository instance
        citations: CitationRepository instance
        chat: ChatRepository instance
        _committed: Flag tracking whether changes have been committed
    """

    def __init__(self, db: Session):
        """
        Initialize the Unit of Work with a database session.

        Creates instances of all repositories, all sharing the same
        database session for coordinated transactions.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self._committed = False

        # Initialize all repositories with the same session
        self.agents = AgentRepository(db)
        self.sessions = SessionRepository(db)
        self.responses = ResponseRepository(db)
        self.compliance = ComplianceRepository(db)
        self.citations = CitationRepository(db)
        self.chat = ChatRepository(db)

        logger.debug("Unit of Work initialized with shared database session")

    def commit(self) -> None:
        """
        Commit all pending changes in the current transaction.

        This commits all changes made through any of the repositories
        in this Unit of Work atomically. Either all changes succeed
        or none do.

        Raises:
            Exception: If commit fails, triggers rollback
        """
        try:
            self.db.commit()
            self._committed = True
            logger.debug("Unit of Work committed successfully")
        except Exception as e:
            logger.error(f"Error during commit, rolling back: {e}")
            self.rollback()
            raise

    def rollback(self) -> None:
        """
        Roll back all pending changes in the current transaction.

        Discards all uncommitted changes made through any of the
        repositories in this Unit of Work.
        """
        try:
            self.db.rollback()
            logger.debug("Unit of Work rolled back")
        except Exception as e:
            logger.error(f"Error during rollback: {e}")
            raise

    def flush(self) -> None:
        """
        Flush pending changes to the database without committing.

        This synchronizes the ORM state with the database, making
        objects available for queries within the same transaction,
        but doesn't commit the transaction.

        Useful when you need to access auto-generated IDs before
        committing the transaction.
        """
        try:
            self.db.flush()
            logger.debug("Unit of Work flushed")
        except Exception as e:
            logger.error(f"Error during flush: {e}")
            raise

    def refresh(self, obj) -> None:
        """
        Refresh an object from the database.

        Reloads the object's state from the database, discarding
        any uncommitted changes to that object.

        Args:
            obj: SQLAlchemy model instance to refresh
        """
        self.db.refresh(obj)

    def expunge(self, obj) -> None:
        """
        Remove an object from the session.

        The object will no longer be tracked by the session and
        changes to it will not be persisted.

        Args:
            obj: SQLAlchemy model instance to expunge
        """
        self.db.expunge(obj)

    def expunge_all(self) -> None:
        """
        Remove all objects from the session.

        All objects will no longer be tracked by the session.
        """
        self.db.expunge_all()

    def close(self) -> None:
        """
        Close the database session.

        This should typically be handled by the context manager,
        but is available for manual session management if needed.
        """
        try:
            self.db.close()
            logger.debug("Unit of Work session closed")
        except Exception as e:
            logger.error(f"Error closing session: {e}")

    def __enter__(self):
        """
        Enter the context manager.

        Returns:
            Self for use in with statements
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the context manager.

        Automatically rolls back the transaction if an exception occurred
        and the transaction hasn't been committed yet.

        Args:
            exc_type: Exception type if an exception was raised
            exc_val: Exception value if an exception was raised
            exc_tb: Exception traceback if an exception was raised

        Returns:
            False to propagate exceptions
        """
        if exc_type is not None:
            # Exception occurred
            if not self._committed:
                logger.warning(f"Exception in Unit of Work context, rolling back: {exc_type.__name__}")
                self.rollback()

        # Always return False to propagate exceptions
        return False


class UnitOfWorkFactory:
    """
    Factory for creating Unit of Work instances.

    Useful for dependency injection scenarios where you want to
    create UnitOfWork instances from a session factory.

    Usage:
        factory = UnitOfWorkFactory(SessionLocal)

        with factory.create() as uow:
            # Use uow
            uow.commit()
    """

    def __init__(self, session_factory):
        """
        Initialize the factory with a session factory.

        Args:
            session_factory: Callable that returns a database session
        """
        self.session_factory = session_factory

    def create(self) -> UnitOfWork:
        """
        Create a new Unit of Work instance with a new session.

        Returns:
            UnitOfWork instance with a new database session
        """
        db = self.session_factory()
        return UnitOfWork(db)
