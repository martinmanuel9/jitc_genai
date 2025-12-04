from typing import Generator
from functools import lru_cache
from contextlib import contextmanager
from sqlalchemy.orm import Session
from fastapi import Depends

from core.database import get_db, SessionLocal
from core.config import get_settings, Settings
import logging

logger = logging.getLogger('CORE_DEPENDENCIES')


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """
    Context manager for database sessions in background tasks.

    Use this when you need a database session outside of FastAPI's
    dependency injection (e.g., in background tasks).

    Example:
        with get_db_context() as db:
            chat_entry = ChatHistory(...)
            db.add(chat_entry)
            db.commit()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# Configuration Dependencies
# ============================================================================

@lru_cache()
def get_settings_cached() -> Settings:
    """
    Get cached application settings.

    Returns:
        Settings: Application configuration

    Example:
        @router.get("/config")
        def get_config(settings: Settings = Depends(get_settings_cached)):
            return {"db_host": settings.db_host}
    """
    return get_settings()


# ============================================================================
# Database Dependencies
# ============================================================================

def get_db_session() -> Generator[Session, None, None]:
    """
    Get database session for dependency injection.

    This is an alias for get_db() for backward compatibility and clarity.

    Yields:
        Session: SQLAlchemy database session

    Example:
        @router.get("/items")
        def get_items(db: Session = Depends(get_db_session)):
            return db.query(Item).all()
    """
    yield from get_db()


# ============================================================================
# Unit of Work Dependencies
# ============================================================================

def get_uow(db: Session = Depends(get_db)):
    """
    Get Unit of Work instance for coordinating transactions.

    Args:
        db: Database session (automatically injected)

    Returns:
        UnitOfWork: Coordinated repository access

    Example:
        @router.post("/complex-operation")
        def create_complex(
            data: ComplexData,
            uow: UnitOfWork = Depends(get_uow)
        ):
            with uow:
                session = uow.sessions.create_session(...)
                response = uow.responses.create_response(...)
                uow.citations.bulk_create_citations(...)
                uow.commit()
            return session
    """
    from repositories import UnitOfWork
    return UnitOfWork(db)


# ============================================================================
# Repository Dependencies
# ============================================================================

def get_agent_repository(db: Session = Depends(get_db)):
    """
    Get AgentRepository instance.

    Args:
        db: Database session (automatically injected)

    Returns:
        AgentRepository: Agent data access layer

    Example:
        @router.get("/agents/{agent_id}")
        def get_agent(
            agent_id: int,
            repo: AgentRepository = Depends(get_agent_repository)
        ):
            return repo.get(agent_id)
    """
    from repositories import AgentRepository
    return AgentRepository(db)


def get_response_repository(db: Session = Depends(get_db)):
    """
    Get ResponseRepository instance.

    Args:
        db: Database session (automatically injected)

    Returns:
        ResponseRepository: Agent response data access layer
    """
    from repositories import ResponseRepository
    return ResponseRepository(db)


def get_compliance_repository(db: Session = Depends(get_db)):
    """
    Get ComplianceRepository instance.

    Args:
        db: Database session (automatically injected)

    Returns:
        ComplianceRepository: Compliance result data access layer
    """
    from repositories import ComplianceRepository
    return ComplianceRepository(db)


def get_citation_repository(db: Session = Depends(get_db)):
    """
    Get CitationRepository instance.

    Args:
        db: Database session (automatically injected)

    Returns:
        CitationRepository: RAG citation data access layer
    """
    from repositories import CitationRepository
    return CitationRepository(db)


def get_session_repository(db: Session = Depends(get_db)):
    """
    Get session repository for database operations.

    Args:
        db: Database session (automatically injected)

    Returns:
        SessionRepository: Repository instance for session CRUD operations
    """
    from repositories.session_repository import SessionRepository
    return SessionRepository(db)


def get_chat_repository(db: Session = Depends(get_db)):
    """
    Get ChatRepository instance.

    Args:
        db: Database session (automatically injected)

    Returns:
        ChatRepository: Chat history data access layer
    """
    from repositories import ChatRepository
    return ChatRepository(db)


# ============================================================================
# Service Dependencies
# ============================================================================

# Removed: get_compliance_service and get_citation_service (unused services)


def get_llm_service(db: Session = Depends(get_db)):
    """
    Get LLMService instance.

    Args:
        db: Database session (automatically injected)

    Returns:
        LLMService: LLM query service with database integration

    Example:
        @router.post("/query")
        def query_llm(
            query: str,
            llm_service: LLMService = Depends(get_llm_service)
        ):
            return llm_service.query_direct("gpt-4", query)
    """
    from services.llm_service import LLMService
    return LLMService(db=db)


# ============================================================================
# External Service Dependencies
# ============================================================================

@lru_cache()
def get_chromadb_client():
    """
    Get ChromaDB client singleton.

    Returns:
        ChromaDBClient: Shared ChromaDB client instance

    Example:
        @router.get("/collections")
        def list_collections(
            chroma: ChromaDBClient = Depends(get_chromadb_client)
        ):
            return chroma.list_collections()
    """
    from integrations import get_chroma_client
    return get_chroma_client()


@lru_cache()
def get_redis_client():
    """
    Get Redis client singleton.

    Returns:
        RedisClient: Shared Redis client instance

    Example:
        @router.get("/job/{job_id}/status")
        def get_job_status(
            job_id: str,
            redis: RedisClient = Depends(get_redis_client)
        ):
            return redis.get_job_status(job_id)
    """
    from integrations import get_redis_client
    return get_redis_client()


# ============================================================================
# Legacy Service Dependencies (Backward Compatibility)
# ============================================================================

def get_rag_service(db: Session = Depends(get_db)):
    """
    Get RAGService instance (legacy - not yet migrated).

    Args:
        db: Database session (automatically injected)

    Returns:
        RAGService: RAG query service

    Note:
        This service has not been migrated to use repositories yet.
        It's included for backward compatibility.
    """
    from services.rag_service import RAGService
    return RAGService()


def get_rag_assessment_service(db: Session = Depends(get_db)):
    """
    Get RAGAssessmentService instance.

    Args:
        db: Database session (automatically injected)

    Returns:
        RAGAssessmentService: RAG assessment service

    Note:
        This service provides RAG quality assessment and metrics.
    """
    from services.rag_assessment_service import RAGAssessmentService
    return RAGAssessmentService()


def get_agent_service_legacy():
    """
    Get AgentService instance (legacy - not yet migrated).

    Returns:
        AgentService: Legacy agent service

    Note:
        This is the existing AgentService that handles LangChain operations.
        It has not been migrated to use repositories yet.
    """
    from services.agent_service import AgentService
    return AgentService()


