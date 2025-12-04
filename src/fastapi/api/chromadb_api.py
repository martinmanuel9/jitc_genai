from fastapi import APIRouter, Depends, HTTPException
import logging
# New dependency injection imports
from core.dependencies import get_rag_service
from typing import Optional
from services.rag_service import RAGService

logger = logging.getLogger("CHROMADB_API_LOGGER")

chromadb_api_router = APIRouter(prefix="/chromadb", tags=["chromadb"])

@chromadb_api_router.get("/collections/{collection_name}/info")
async def get_collection_info(
    collection_name: str,
    rag_service: RAGService = Depends(get_rag_service)
):
    """Get information about a specific collection"""
    try:
        info = rag_service.query_collection_info(collection_name)
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
