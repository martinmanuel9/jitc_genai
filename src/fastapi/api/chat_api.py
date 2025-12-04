from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
import time
import uuid
import logging
import sys
from pathlib import Path

from schemas.requests import ChatRequest, QueryType
from schemas.responses import ChatResponse, BaseResponse, DataResponse

# New dependency injection imports
from core.dependencies import (
    get_db,
    get_chat_repository,
    get_llm_service,
    get_rag_service
)
from repositories import ChatRepository
from services.llm_service import LLMService
from services.rag_service import RAGService
from services.llm_invoker import LLMInvoker

# Add parent directory to path to import llm_config module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from llm_config.llm_config import validate_model, get_model_config, llm_env

logger = logging.getLogger("CHAT_API_LOGGER")

chat_api_router = APIRouter(prefix="/chat", tags=["chat"])
    
@chat_api_router.post("", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    chat_repo: ChatRepository = Depends(get_chat_repository),
    llm_service: LLMService = Depends(get_llm_service),
    rag_service: RAGService = Depends(get_rag_service),
    db: Session = Depends(get_db)
):
    """
    Chat endpoint that handles both direct LLM and RAG-enhanced responses.

    Validates model availability and API keys before processing to provide
    early error feedback to users.

    """
    try:
        # Use session_id from request or generate new one
        session_id = request.session_id or str(uuid.uuid4())

        # ========================================================================
        # EARLY MODEL VALIDATION - Fail fast if model is unsupported or misconfigured
        # ========================================================================
        is_valid, validation_error = validate_model(request.model_name)
        if not is_valid:
            logger.error(f"Model validation failed: {validation_error}")
            raise HTTPException(status_code=400, detail=validation_error)

        # Validate API keys for the model's provider
        model_config = get_model_config(request.model_name)
        keys_valid, key_error = llm_env.validate_provider_keys(model_config.provider)
        if not keys_valid:
            logger.error(f"API key validation failed for {model_config.provider}: {key_error}")
            raise HTTPException(
                status_code=500,
                detail=f"{key_error}. Please configure the required API key in your environment."
            )

        # Determine if RAG is needed based on query_type
        use_rag = request.query_type in [QueryType.RAG, QueryType.RAG_ENHANCED]

        logger.info(f"Processing chat request with model={request.model_name}, query_type={request.query_type}")

        if use_rag and request.collection_name:
            # RAG mode: fetch docs via RAGService, then run a retrieval chain
            answer, response_time, metadata_list, formatted_citations = rag_service.process_query_with_rag(
                query_text=request.query,
                collection_name=request.collection_name,
                model_name=request.model_name,
            )

            # Save chat history using repository
            chat_repo.create_chat_entry(
                user_query=request.query,
                response=answer,
                model_used=request.model_name,
                collection_name=request.collection_name,
                query_type=request.query_type.value,
                response_time_ms=response_time,
                session_id=session_id
            )
            db.commit()

            # Extract source document names for response
            source_documents = []
            if metadata_list:
                for meta in metadata_list:
                    doc_name = meta.get("metadata", {}).get("document_name", "")
                    if doc_name and doc_name not in source_documents:
                        source_documents.append(doc_name)

            # Return standardized ChatResponse
            return ChatResponse(
                success=True,
                message="Query processed successfully with RAG",
                response=answer,
                model_used=request.model_name,
                query_type=request.query_type.value,
                response_time_ms=response_time,
                session_id=session_id,
                formatted_citations=formatted_citations,
                source_documents=source_documents,
                documents_found=len(metadata_list) if metadata_list else 0
            )
        else:
            # Direct LLM mode - Using LLMInvoker utility for simplified invocation
            start_time = time.time()

            # Use LLMInvoker for standardized LLM invocation
            answer = LLMInvoker.invoke(
                model_name=request.model_name,
                prompt=request.query,
                temperature=request.temperature,
                retry_count=0
            )

            response_time_ms = int((time.time() - start_time) * 1000)

            # Save chat history using repository
            chat_repo.create_chat_entry(
                user_query=request.query,
                response=answer,
                model_used=request.model_name,
                collection_name=None,
                query_type=request.query_type.value,
                response_time_ms=response_time_ms,
                session_id=session_id
            )
            db.commit()

            # Return standardized ChatResponse
            return ChatResponse(
                success=True,
                message="Query processed successfully",
                response=answer,
                model_used=request.model_name,
                query_type=request.query_type.value,
                response_time_ms=response_time_ms,
                session_id=session_id,
                documents_found=0
            )

    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    

@chat_api_router.get("/history", response_model=DataResponse)
def get_chat_history(
    limit: int = 100,
    offset: int = 0,
    chat_repo: ChatRepository = Depends(get_chat_repository)
):
    """
    Get chat history with pagination support.

    Args:
        limit: Maximum number of entries to return (default: 100)
        offset: Number of entries to skip (default: 0)
        chat_repo: Chat repository (injected)

    Returns:
        Standardized response with chat history list in data field
    """
    history = chat_repo.get_all(skip=offset, limit=limit, order_by="timestamp")

    # Transform to list of dictionaries
    history_data = [
        {
            "id": entry.id,
            "user_query": entry.user_query,
            "response": entry.response,
            "model_used": entry.model_used,
            "collection_name": entry.collection_name,
            "query_type": entry.query_type,
            "response_time_ms": entry.response_time_ms,
            "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
            "session_id": entry.session_id
        }
        for entry in history
    ]

    return {
        "success": True,
        "message": f"Retrieved {len(history_data)} chat history entries",
        "timestamp": datetime.utcnow(),
        "data": history_data
    }