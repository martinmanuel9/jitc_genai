from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
# New dependency injection imports
from core.dependencies import (
    get_llm_service,
    get_rag_service,
    get_rag_assessment_service
)
from core.database import get_database_health
from services.llm_service import LLMService
from services.rag_assessment_service import RAGAssessmentService
from services.rag_service import RAGService
from datetime import datetime, timezone
import os
import logging 

logger = logging.getLogger("HEALTH_API_LOGGER")

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

health_api_router = APIRouter(prefix="/health", tags=["health"])
VISION_CONFIG = {
            "openai_enabled": bool(openai_api_key),
            "ollama_enabled": True, 
            "huggingface_enabled": True,  
            "enhanced_local_enabled": True,
            # "ollama_url": os.getenv("OLLAMA_URL", "http://ollama:11434"),
            # "ollama_model": os.getenv("OLLAMA_VISION_MODEL", "llava"),
            "huggingface_model": os.getenv("HUGGINGFACE_VISION_MODEL", "Salesforce/blip-image-captioning-base")
        }

# Image storage directory
IMAGES_DIR = os.path.join(os.getcwd(), "stored_images")

@health_api_router.get("")
async def health_status(
    llm_service: LLMService = Depends(get_llm_service),
    rag_service: RAGService = Depends(get_rag_service),
    rag_assessment_service: RAGAssessmentService = Depends(get_rag_assessment_service),
):
    """
    Aggregate health check used by the Streamlit sidebar button.
    Returns status information about critical subsystems so the UI
    can display a single consolidated response.
    """
    overall_status = "healthy"
    services = {}

    # LLM + Chroma status
    try:
        llm_health = llm_service.health_check()
        services["llm_service"] = llm_health
        if llm_health.get("status") != "healthy":
            overall_status = "degraded"
    except Exception as exc:
        services["llm_service"] = {"status": "unhealthy", "error": str(exc)}
        overall_status = "degraded"

    # Database connectivity
    database_health = get_database_health()
    services["database"] = database_health
    if database_health.get("status") != "healthy":
        overall_status = "degraded"

    # RAG API connectivity (Chroma API reachability)
    try:
        rag_ok = rag_service.test_connection()
        chroma_host = os.getenv("CHROMA_HOST", "chromadb")
        chroma_port = os.getenv("CHROMA_PORT", "8000")
        services["rag_service"] = {
            "status": "healthy" if rag_ok else "unhealthy",
            "chromadb_connection": f"{chroma_host}:{chroma_port}",
        }
        if not rag_ok:
            overall_status = "degraded"
    except Exception as exc:
        services["rag_service"] = {"status": "unhealthy", "error": str(exc)}
        overall_status = "degraded"

    # RAG assessment metrics snapshot
    try:
        services["rag_assessment"] = {
            "status": "healthy",
            "active_sessions": len(rag_assessment_service.performance_metrics),
            "quality_assessments": len(rag_assessment_service.quality_assessments),
        }
    except Exception as exc:
        services["rag_assessment"] = {"status": "unhealthy", "error": str(exc)}
        overall_status = "degraded"

    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": services,
    }

@health_api_router.get("/llm_health")
async def llm_health_check(llm_service: LLMService = Depends(get_llm_service)):
    try:
        health = llm_service.health_check()
        return health
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


@health_api_router.get("/rag-health")
async def rag_assessment_health(
    rag_assessment_service: RAGAssessmentService = Depends(get_rag_assessment_service)
):
    """
    Health check for RAG Assessment Service.
    """
    try:
        # Get basic stats from the assessment service
        current_sessions = len(rag_assessment_service.performance_metrics)
        quality_assessments = len(rag_assessment_service.quality_assessments)
        
        return {
            "service": "RAG Assessment Service",
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "active_sessions": current_sessions,
                "quality_assessments": quality_assessments
            },
            "endpoints": [
                "/rag-assessment",
                "/rag-analytics", 
                "/rag-benchmark",
                "/rag-collection-performance/{collection_name}",
                "/rag-export-metrics",
                "/rag-health"
            ]
        }
        
    except Exception as e:
        logger.error(f"RAG assessment health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@health_api_router.get("/db")
def root_health_check():
    """Basic health check."""
    return {"status": "ok", "detail": "ChromaDB custom server running."}

@health_api_router.get("/availability")
def health_check():
    """Enhanced health check endpoint with vision model status"""
    return {
        "status": "ok",
        "markitdown_available": True,
        "supported_formats": ["pdf", "docx", "xlsx", "csv", "txt", "pptx", "html"],
        "embedding_model": "multi-qa-mpnet-base-dot-v1",
        "images_directory": IMAGES_DIR,
        "vision_models": {
            "openai_enabled": VISION_CONFIG["openai_enabled"],
            "ollama_enabled": VISION_CONFIG["ollama_enabled"],
            "huggingface_enabled": VISION_CONFIG["huggingface_enabled"],
            "enhanced_local_enabled": VISION_CONFIG["enhanced_local_enabled"],
        },
        "api_keys": {
            "openai_configured": bool(openai_api_key)
        }
    }