"""
API routers package for the FastAPI application.

This package contains all API endpoint routers organized by domain:
- chat_api: Chat and LLM interaction endpoints
- agent_api: Agent CRUD and management endpoints
- rag_api: RAG queries and assessment endpoints
- health_api: Health check endpoints
- document_generation_api: Document generation and export endpoints
- analytics_api: Analytics and metrics endpoints
- chromadb_api: ChromaDB collection management endpoints
- redis_api: Redis pipeline and cache management endpoints
"""

from .chat_api import chat_api_router
# from .agent_api import agent_api_router
from .rag_api import rag_api_router
from .health_api import health_api_router
from .document_generation_api import doc_gen_api_router
from .analytics_api import analytics_api_router
from .chromadb_api import chromadb_api_router
from .redis_api import redis_api_router
from .vectordb_api import vectordb_api_router
from .models_api import models_api_router

__all__ = [
    "chat_api_router",
    "agent_api_router",
    "rag_api_router",
    "health_api_router",
    "doc_gen_api_router",
    "analytics_api_router",
    "chromadb_api_router",
    "redis_api_router",
    "vectordb_api_router",
    "models_api_router",
]
