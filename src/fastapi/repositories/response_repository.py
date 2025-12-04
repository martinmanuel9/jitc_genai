"""
Response Repository

This module provides data access layer for AgentResponse and ComplianceResult operations.
Handles logging agent responses and compliance results.
"""

from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import logging

from models.response import AgentResponse, ComplianceResult
from repositories.base import BaseRepository

logger = logging.getLogger("RESPONSE_REPOSITORY")


class ResponseRepository(BaseRepository[AgentResponse]):
    """
    Repository for managing AgentResponse database operations.

    Extends BaseRepository to provide:
    - Standard CRUD operations
    - Response creation with full metadata
    - Response retrieval by session
    """

    def __init__(self, db: Session):
        """
        Initialize the response repository.

        Args:
            db: SQLAlchemy database session
        """
        super().__init__(AgentResponse, db)

    def create_response(
        self,
        session_id: str,
        agent_id: int,
        response_text: str,
        processing_method: str,
        response_time_ms: int,
        model_used: str,
        sequence_order: Optional[int] = None,
        rag_used: bool = False,
        documents_found: int = 0,
        rag_context: Optional[str] = None,
        confidence_score: Optional[float] = None,
        analysis_summary: Optional[str] = None
    ) -> AgentResponse:
        """
        Create a new agent response with full metadata.

        Args:
            session_id: Session identifier
            agent_id: Agent identifier
            response_text: Response text
            processing_method: Method used for processing
            response_time_ms: Response time in milliseconds
            model_used: Model identifier
            sequence_order: Order in debate sequence
            rag_used: Whether RAG was used
            documents_found: Number of documents retrieved
            rag_context: Retrieved RAG context
            confidence_score: Confidence score
            analysis_summary: Analysis summary

        Returns:
            Created AgentResponse with ID
        """
        try:
            response = AgentResponse(
                session_id=session_id,
                agent_id=agent_id,
                response_text=response_text,
                processing_method=processing_method,
                response_time_ms=response_time_ms,
                sequence_order=sequence_order,
                rag_used=rag_used,
                documents_found=documents_found,
                rag_context=rag_context,
                confidence_score=confidence_score,
                analysis_summary=analysis_summary,
                model_used=model_used
            )
            created_response = self.create(response)
            logger.info(f"Response created: ID={created_response.id}, session={session_id}")
            return created_response
        except Exception as e:
            logger.error(f"Error creating response for session {session_id}: {e}")
            raise

    def get_by_session(self, session_id: str) -> List[AgentResponse]:
        """
        Get all responses for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of AgentResponse objects ordered by sequence/creation
        """
        try:
            return self.db.query(AgentResponse).filter(
                AgentResponse.session_id == session_id
            ).order_by(
                AgentResponse.sequence_order.asc(),
                AgentResponse.created_at.asc()
            ).all()
        except Exception as e:
            logger.error(f"Error retrieving responses for session {session_id}: {e}")
            return []

    def get_by_agent(self, agent_id: int, limit: int = 100) -> List[AgentResponse]:
        """
        Get responses by agent.

        Args:
            agent_id: Agent identifier
            limit: Maximum number of responses

        Returns:
            List of AgentResponse objects
        """
        return self.get_by_filter({"agent_id": agent_id}, limit=limit, order_by="created_at")


class ComplianceRepository(BaseRepository[ComplianceResult]):
    """
    Repository for managing ComplianceResult database operations.

    Extends BaseRepository to provide:
    - Standard CRUD operations
    - Compliance result creation
    - Result retrieval by session/agent
    """

    def __init__(self, db: Session):
        """
        Initialize the compliance repository.

        Args:
            db: SQLAlchemy database session
        """
        super().__init__(ComplianceResult, db)

    def create_result(
        self,
        agent_id: int,
        data_sample: str,
        confidence_score: Optional[float],
        reason: str,
        raw_response: str,
        processing_method: str,
        response_time_ms: int,
        model_used: str,
        session_id: Optional[str] = None
    ) -> ComplianceResult:
        """
        Create a new compliance result.

        Args:
            agent_id: Agent identifier
            data_sample: Input data that was analyzed
            confidence_score: Confidence score
            reason: Reasoning for the result
            raw_response: Raw LLM response
            processing_method: Processing method used
            response_time_ms: Response time in milliseconds
            model_used: Model identifier
            session_id: Optional session identifier

        Returns:
            Created ComplianceResult
        """
        try:
            result = ComplianceResult(
                session_id=session_id,
                agent_id=agent_id,
                data_sample=data_sample,
                confidence_score=confidence_score,
                reason=reason,
                raw_response=raw_response,
                processing_method=processing_method,
                response_time_ms=response_time_ms,
                model_used=model_used
            )
            created_result = self.create(result)
            logger.info(f"Compliance result created: ID={created_result.id}, agent={agent_id}")
            return created_result
        except Exception as e:
            logger.error(f"Error creating compliance result for agent {agent_id}: {e}")
            raise

    def get_by_session(self, session_id: str) -> List[ComplianceResult]:
        """
        Get all compliance results for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of ComplianceResult objects
        """
        return self.get_by_filter({"session_id": session_id}, order_by="created_at")

    def get_by_agent(self, agent_id: int, limit: int = 100) -> List[ComplianceResult]:
        """
        Get compliance results by agent.

        Args:
            agent_id: Agent identifier
            limit: Maximum number of results

        Returns:
            List of ComplianceResult objects
        """
        return self.get_by_filter({"agent_id": agent_id}, limit=limit, order_by="created_at")
