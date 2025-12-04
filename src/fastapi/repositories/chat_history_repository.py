# ============================================================================
# DEPRECATED: This file is deprecated and will be removed in a future release.
#
# Please use repositories.chat_repository.ChatRepository instead:
#   from core.dependencies import get_chat_repository
#   from repositories import ChatRepository
#
#   # In FastAPI route:
#   def endpoint(chat_repo: ChatRepository = Depends(get_chat_repository)):
#       chat_repo.create_chat_entry(...)
#       # Remember to call db.commit() explicitly
#
# See DEPRECATED_CODE.md for migration guide.
# ============================================================================
import warnings
from models.chat import ChatHistory
import logging

warnings.warn(
    "repositories.chat_history_repository is deprecated. "
    "Use ChatRepository from repositories.chat_repository instead. "
    "See DEPRECATED_CODE.md for migration guide.",
    DeprecationWarning,
    stacklevel=2
)

logger = logging.getLogger("CHAT_HISTORY_REPO_LOGGER")

def save_chat_history(db_session, user_query, response, model_used, query_type, response_time_ms, session_id):
    """Saves a chat history record to the database."""
    try:
        history = ChatHistory(
            user_query=user_query,
            response=response,
            model_used=model_used,
            query_type=query_type,
            response_time_ms=response_time_ms,
            session_id=session_id
        )
        db_session.add(history)
        db_session.commit()
        
        
    except Exception as e:
        logger.error(f"Failed to save chat history: {e}")
        db_session.rollback()
        
def list_chat_history(db_session):
    """Retrieves the latest chat history records."""
    try:
        records = db_session.query(ChatHistory).all()
        return [
        {
            "id": record.id,
            "user_query": record.user_query,
            "response": record.response,
            "timestamp": record.timestamp
        } for record in records
    ]
    except Exception as e:
        logger.error(f"Failed to retrieve chat history: {e}")
        return []