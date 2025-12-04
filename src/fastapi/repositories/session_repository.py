"""
Session Repository

This module provides data access layer for AgentSession operations.
Handles session tracking, history retrieval, and completion tracking.
"""

from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import logging

from models.session import AgentSession
from models.response import AgentResponse
from models.enums import SessionType, AnalysisType
from repositories.base import BaseRepository
from core.exceptions import NotFoundException

logger = logging.getLogger("SESSION_REPOSITORY")


class SessionRepository(BaseRepository[AgentSession]):
    """
    Repository for managing AgentSession database operations.

    Extends BaseRepository to provide:
    - Standard CRUD operations
    - Session creation and completion
    - Session history retrieval
    - Session details with responses
    """

    def __init__(self, db: Session):
        """
        Initialize the session repository.

        Args:
            db: SQLAlchemy database session
        """
        super().__init__(AgentSession, db)

    def create_session(
        self,
        session_id: str,
        session_type: SessionType,
        analysis_type: AnalysisType,
        user_query: str,
        collection_name: Optional[str] = None
    ) -> AgentSession:
        """
        Create a new agent session.

        Args:
            session_id: Unique session identifier
            session_type: Type of session (SessionType enum)
            analysis_type: Type of analysis (AnalysisType enum)
            user_query: User's query
            collection_name: ChromaDB collection (for RAG sessions)

        Returns:
            Created AgentSession
        """
        try:
            session = AgentSession(
                session_id=session_id,
                session_type=session_type,
                analysis_type=analysis_type,
                user_query=user_query,
                collection_name=collection_name,
                status='active'
            )
            created_session = self.create(session)
            logger.info(f"Session created: {session_id}, type: {session_type.value}")
            return created_session
        except Exception as e:
            logger.error(f"Error creating session {session_id}: {e}")
            raise

    def get_by_session_id(self, session_id: str) -> Optional[AgentSession]:
        """
        Get session by session_id (UUID).

        Args:
            session_id: Session identifier

        Returns:
            AgentSession if found, None otherwise
        """
        try:
            return self.db.query(AgentSession).filter(
                AgentSession.session_id == session_id
            ).first()
        except Exception as e:
            logger.error(f"Error retrieving session {session_id}: {e}")
            return None

    def complete_session(
        self,
        session_id: str,
        overall_result: Dict[str, Any],
        agent_count: int,
        total_response_time_ms: Optional[int] = None,
        status: str = 'completed',
        error_message: Optional[str] = None
    ) -> Optional[AgentSession]:
        """
        Mark a session as completed and update results.

        Args:
            session_id: Session identifier
            overall_result: Summary of results
            agent_count: Number of agents involved
            total_response_time_ms: Total processing time
            status: Final status ('completed', 'failed', etc.)
            error_message: Error message if failed

        Returns:
            Updated AgentSession or None if not found
        """
        try:
            session = self.get_by_session_id(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found for completion")
                return None

            session.completed_at = datetime.now(timezone.utc)
            session.overall_result = overall_result
            session.agent_count = agent_count
            session.total_response_time_ms = total_response_time_ms
            session.status = status
            session.error_message = error_message

            updated_session = self.update(session)
            logger.info(f"Session completed: {session_id}, status: {status}")
            return updated_session
        except Exception as e:
            logger.error(f"Error completing session {session_id}: {e}")
            raise

    def get_history(
        self,
        limit: int = 50,
        session_type: Optional[SessionType] = None,
        skip: int = 0
    ) -> List[AgentSession]:
        """
        Get recent session history with optional filtering.

        Args:
            limit: Maximum number of sessions
            session_type: Filter by session type
            skip: Number of records to skip

        Returns:
            List of AgentSession objects
        """
        try:
            query = self.db.query(AgentSession).order_by(desc(AgentSession.created_at))

            if session_type:
                query = query.filter(AgentSession.session_type == session_type)

            return query.offset(skip).limit(limit).all()
        except Exception as e:
            logger.error(f"Error retrieving session history: {e}")
            return []

    def get_details(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a session including all responses.

        Args:
            session_id: Session identifier

        Returns:
            Dictionary with session info and responses, or None if not found
        """
        try:
            session = self.get_by_session_id(session_id)
            if not session:
                return None

            # Get all agent responses for this session
            responses = self.db.query(AgentResponse).filter(
                AgentResponse.session_id == session_id
            ).order_by(
                AgentResponse.sequence_order.asc(),
                AgentResponse.created_at.asc()
            ).all()

            session_data = {
                "session_info": {
                    "session_id": session.session_id,
                    "session_type": session.session_type.value,
                    "analysis_type": session.analysis_type.value,
                    "user_query": session.user_query,
                    "collection_name": session.collection_name,
                    "created_at": session.created_at,
                    "completed_at": session.completed_at,
                    "status": session.status,
                    "error_message": session.error_message,
                    "overall_result": session.overall_result,
                    "agent_count": session.agent_count,
                    "total_response_time_ms": session.total_response_time_ms
                },
                "agent_responses": []
            }

            for response in responses:
                response_data = {
                    "agent_id": response.agent_id,
                    "agent_name": response.agent.name if response.agent else "Unknown",
                    "response_text": response.response_text,
                    "processing_method": response.processing_method,
                    "response_time_ms": response.response_time_ms,
                    "sequence_order": response.sequence_order,
                    "rag_used": response.rag_used,
                    "documents_found": response.documents_found,
                    "confidence_score": response.confidence_score,
                    "model_used": response.model_used,
                    "created_at": response.created_at
                }
                session_data["agent_responses"].append(response_data)

            return session_data
        except Exception as e:
            logger.error(f"Error retrieving session details for {session_id}: {e}")
            return None

    def get_active_sessions(self, limit: int = 100) -> List[AgentSession]:
        """
        Get all active (not completed) sessions.

        Args:
            limit: Maximum number of sessions

        Returns:
            List of active AgentSession objects
        """
        return self.get_by_filter({"status": "active"}, limit=limit)

    def count_by_type(self, session_type: SessionType) -> int:
        """
        Count sessions by type.

        Args:
            session_type: Session type to count

        Returns:
            Count of sessions
        """
        return self.count({"session_type": session_type})
