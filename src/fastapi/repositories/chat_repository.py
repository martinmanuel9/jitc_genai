
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import logging

from models.chat import ChatHistory
from repositories.base import BaseRepository

logger = logging.getLogger("CHAT_REPOSITORY")


class ChatRepository(BaseRepository[ChatHistory]):
    """
    Repository for managing ChatHistory database operations.

    Extends BaseRepository to provide:
    - Standard CRUD operations
    - Chat history retrieval by session
    - Session-based queries
    - Analytics queries
    """

    def __init__(self, db: Session):
        """
        Initialize the chat repository.

        Args:
            db: SQLAlchemy database session
        """
        super().__init__(ChatHistory, db)

    def create_chat_entry(
        self,
        user_query: str,
        response: str,
        model_used: str,
        collection_name: Optional[str],
        query_type: str,
        response_time_ms: int,
        session_id: str,
        source_documents: Optional[List[Dict[str, Any]]] = None
    ) -> ChatHistory:
        """
        Create a new chat history entry.

        Args:
            user_query: User's query
            response: System response
            model_used: Model identifier
            collection_name: ChromaDB collection (if RAG)
            query_type: Type of query ('direct', 'rag', 'hybrid')
            response_time_ms: Response time in milliseconds
            session_id: Session identifier
            source_documents: Source documents (if RAG)

        Returns:
            Created ChatHistory entry
        """
        try:
            chat = ChatHistory(
                user_query=user_query,
                response=response,
                model_used=model_used,
                collection_name=collection_name,
                query_type=query_type,
                response_time_ms=response_time_ms,
                session_id=session_id,
                source_documents=source_documents
            )
            created_chat = self.create(chat)
            logger.info(f"Chat entry created: session={session_id}, type={query_type}")
            return created_chat
        except Exception as e:
            logger.error(f"Error creating chat entry: {e}")
            raise

    def get_by_session(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[ChatHistory]:
        """
        Get chat history for a session.

        Args:
            session_id: Session identifier
            limit: Maximum number of entries
            offset: Number of entries to skip

        Returns:
            List of ChatHistory entries ordered by timestamp
        """
        try:
            return self.db.query(ChatHistory).filter(
                ChatHistory.session_id == session_id
            ).order_by(ChatHistory.timestamp.asc()).offset(offset).limit(limit).all()
        except Exception as e:
            logger.error(f"Error retrieving chat history for session {session_id}: {e}")
            return []

    def count_by_session(self, session_id: str) -> int:
        """
        Count messages in a session.

        Args:
            session_id: Session identifier

        Returns:
            Count of messages
        """
        return self.count({"session_id": session_id})

    def get_recent_sessions(
        self,
        limit: int = 50,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get recent chat sessions with summary info.

        Args:
            limit: Maximum number of sessions
            hours: Time window in hours

        Returns:
            List of session summaries
        """
        try:
            since = datetime.utcnow() - timedelta(hours=hours)

            # Group by session_id and get summary stats
            sessions = self.db.query(
                ChatHistory.session_id,
                func.min(ChatHistory.timestamp).label('first_message'),
                func.max(ChatHistory.timestamp).label('last_message'),
                func.count(ChatHistory.id).label('message_count'),
                ChatHistory.model_used,
                ChatHistory.collection_name
            ).filter(
                ChatHistory.timestamp >= since
            ).group_by(
                ChatHistory.session_id,
                ChatHistory.model_used,
                ChatHistory.collection_name
            ).order_by(
                desc('last_message')
            ).limit(limit).all()

            result = []
            for session in sessions:
                result.append({
                    "session_id": session.session_id,
                    "first_message_timestamp": session.first_message,
                    "last_message_timestamp": session.last_message,
                    "message_count": session.message_count,
                    "model_used": session.model_used,
                    "collection_name": session.collection_name
                })

            return result
        except Exception as e:
            logger.error(f"Error retrieving recent sessions: {e}")
            return []

    def get_by_model(
        self,
        model_name: str,
        limit: int = 100
    ) -> List[ChatHistory]:
        """
        Get chat history by model.

        Args:
            model_name: Model identifier
            limit: Maximum number of entries

        Returns:
            List of ChatHistory entries
        """
        return self.get_by_filter({"model_used": model_name}, limit=limit, order_by="timestamp")

    def get_rag_queries(
        self,
        collection_name: Optional[str] = None,
        limit: int = 100
    ) -> List[ChatHistory]:
        """
        Get RAG-enhanced queries.

        Args:
            collection_name: Optional collection filter
            limit: Maximum number of entries

        Returns:
            List of ChatHistory entries with RAG
        """
        try:
            query = self.db.query(ChatHistory).filter(
                ChatHistory.query_type.in_(['rag', 'hybrid'])
            )

            if collection_name:
                query = query.filter(ChatHistory.collection_name == collection_name)

            return query.order_by(desc(ChatHistory.timestamp)).limit(limit).all()
        except Exception as e:
            logger.error(f"Error retrieving RAG queries: {e}")
            return []

    def get_average_response_time(
        self,
        session_id: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> Optional[float]:
        """
        Calculate average response time.

        Args:
            session_id: Optional session filter
            model_name: Optional model filter

        Returns:
            Average response time in milliseconds, or None if no data
        """
        try:
            query = self.db.query(func.avg(ChatHistory.response_time_ms))

            if session_id:
                query = query.filter(ChatHistory.session_id == session_id)
            if model_name:
                query = query.filter(ChatHistory.model_used == model_name)

            result = query.scalar()
            return float(result) if result else None
        except Exception as e:
            logger.error(f"Error calculating average response time: {e}")
            return None
