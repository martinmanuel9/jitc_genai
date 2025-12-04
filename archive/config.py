# config.py
# ============================================================================
# DEPRECATED: This file is deprecated and will be removed in a future release.
#
# Please use core.dependencies instead:
#   from core.dependencies import (
#       get_llm_service,
#       get_rag_service,
#       get_db,
#       get_agent_repository
#   )
#
# See DEPRECATED_CODE.md for migration guide.
# ============================================================================
import warnings
from functools import lru_cache
from services.llm_service import LLMService
from services.rag_service import RAGService
from services.agent_service import AgentService
from services.rag_assessment_service import RAGAssessmentService
from core.database import SessionLocal
from typing import Generator
from sqlalchemy.orm import Session
from repositories.agent_repository import AgentRepository

warnings.warn(
    "repositories.config is deprecated. Use core.dependencies instead. "
    "See DEPRECATED_CODE.md for migration guide.",
    DeprecationWarning,
    stacklevel=2
)

@lru_cache
def get_llm_service() -> LLMService:
    return LLMService()

@lru_cache
def get_rag_service() -> RAGService:
    return RAGService()

@lru_cache
def get_agent_service() -> AgentService:
    return AgentService()

@lru_cache
def get_rag_assessment_service() -> RAGAssessmentService:
    return RAGAssessmentService()

def llm_service_dep() -> LLMService:
    return get_llm_service()

def rag_service_dep() -> RAGService:
    return get_rag_service()

def agent_service_dep() -> AgentService:
    return get_agent_service()

def rag_assessment_service_dep() -> RAGAssessmentService:
    return get_rag_assessment_service()

def agent_repository_dep() -> AgentRepository:
    """Dependency provider for AgentRepository"""
    return AgentRepository()

def get_db_session()-> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()