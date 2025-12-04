from services.generate_docs_service import DocumentService
from services.rag_service import RAGService
from services.llm_service import LLMService
from services.agent_service import AgentService
import os
from functools import lru_cache


# Lazy initialization - don't connect to ChromaDB at import time
_doc_service = None


@lru_cache()
def get_document_service() -> DocumentService:
    """
    Get or create the DocumentService instance.
    Uses lazy initialization to avoid connecting to ChromaDB at module import time.
    """
    global _doc_service
    if _doc_service is None:
        _doc_service = DocumentService(
            rag_service=RAGService(),
            agent_service=AgentService(),
            llm_service=LLMService(),
            chroma_url=os.getenv("CHROMA_URL", "http://chromadb:8000"),
            agent_api_url=os.getenv("FASTAPI_URL", "http://localhost:9020")
        )
    return _doc_service


# doc service dependency
def document_service_dep() -> DocumentService:
    return get_document_service()