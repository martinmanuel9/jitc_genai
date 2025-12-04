"""
Repositories package.

This package contains all data access layer repositories following the Repository Pattern.
Each repository extends BaseRepository and provides domain-specific data operations.

Usage:
    from repositories import AgentRepository, SessionRepository, CitationRepository
    from core.database import get_db

    # In a FastAPI route with dependency injection:
    def get_agents(db: Session = Depends(get_db)):
        repo = AgentRepository(db)
        return repo.get_all()

    # Or with Unit of Work pattern:
    from repositories import UnitOfWork

    def create_agent(db: Session = Depends(get_db)):
        with UnitOfWork(db) as uow:
            agent = uow.agents.create_agent(agent_data)
            uow.commit()
            return agent
"""

from repositories.base import BaseRepository
from repositories.agent_repository import AgentRepository
from repositories.session_repository import SessionRepository
from repositories.response_repository import ResponseRepository, ComplianceRepository
from repositories.citation_repository import CitationRepository
from repositories.chat_repository import ChatRepository
from repositories.unit_of_work import UnitOfWork, UnitOfWorkFactory

__all__ = [
    "BaseRepository",
    "AgentRepository",
    "SessionRepository",
    "ResponseRepository",
    "ComplianceRepository",
    "CitationRepository",
    "ChatRepository",
    "UnitOfWork",
    "UnitOfWorkFactory",
]
