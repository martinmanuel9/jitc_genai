from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
import requests
from typing import Optional, List
from pydantic import BaseModel
from repositories.chromadb_repository  import document_service_dep
from services.generate_docs_service import DocumentService
# New dependency injection imports
from core.dependencies import get_db, get_db_session, get_chat_repository
from repositories import ChatRepository
from services.evaluate_doc_service import EvaluationService
from models.agent import ComplianceAgent
from services.rag_service import RAGService
from services.llm_service import LLMService
from schemas import EvaluateRequest, EvaluateResponse
import os
from services.word_export_service import WordExportService
from services.test_card_service import TestCardService
from services.markdown_sanitization_service import MarkdownSanitizationService
from services.pairwise_synthesis_service import PairwiseSynthesisService
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
import logging
from typing import Dict, Any
import uuid
import base64
import redis
from datetime import datetime
import asyncio
import json
from schemas.test_card import (
    TestCardRequest,
    TestCardResponse,
    TestCardBatchRequest,
    TestCardBatchResponse,
    ExportTestPlanWithCardsRequest,
    ExportTestPlanWithCardsResponse,
)
from integrations.chromadb_client import get_chroma_client
from tasks.test_card_tasks import generate_test_cards as generate_test_cards_task

logger = logging.getLogger("DOC_GEN_API_LOGGER")
# Lazy initialization - don't connect at import time
# chroma_client = get_chroma_client()  # Removed - use get_chroma_client() directly in endpoints
doc_gen_api_router = APIRouter(prefix="/doc_gen", tags=["doc_gen"])

class GenerateRequest(BaseModel):
    source_collections:   Optional[List[str]]   = None
    source_doc_ids:       Optional[List[str]]   = None
    use_rag:              bool                  = True
    top_k:                int                   = 5
    doc_title:            str                   = None
    pairwise_merge:       Optional[bool]        = False
    actor_models:         Optional[List[str]]   = None
    critic_model:         Optional[str]         = None
    coverage_strategy:    Optional[str]         = "rag_by_heading"  # rag_by_heading | full_document | hybrid
    max_actor_workers:    Optional[int]         = 4
    critic_batch_size:    Optional[int]         = 15
    critic_batch_char_cap: Optional[int]        = 8000
    sectioning_strategy:  Optional[str]         = "auto"   # auto | by_chunks | by_metadata | by_pages
    chunks_per_section:   Optional[int]         = 5
    agent_set_id:         int                   = None  # Required agent set for orchestration

@doc_gen_api_router.post("/generate_documents")
async def generate_documents(
    req: GenerateRequest,
    doc_service: DocumentService = Depends(document_service_dep),
    db: Session = Depends(get_db)):
    logger.info("Received /generate_documents ⇒ %s", req)

    # Validate agent_set_id is provided
    if req.agent_set_id is None:
        raise HTTPException(
            status_code=400,
            detail="agent_set_id is required. Please select an agent set from the Agent Set Manager or use the default 'Standard Test Plan Pipeline'."
        )

    # Validate agent set exists and is active
    from repositories.agent_set_repository import AgentSetRepository
    agent_set_repo = AgentSetRepository()
    agent_set = agent_set_repo.get_by_id(req.agent_set_id, db)

    if not agent_set:
        raise HTTPException(
            status_code=404,
            detail=f"Agent set with ID {req.agent_set_id} not found. Please create an agent set or use the default 'Standard Test Plan Pipeline' (ID: 1)."
        )

    if not agent_set.is_active:
        raise HTTPException(
            status_code=400,
            detail=f"Agent set '{agent_set.name}' (ID: {req.agent_set_id}) is inactive. Please select an active agent set."
        )

    logger.info(f"Using agent set: {agent_set.name} (ID: {req.agent_set_id})")

    # Note: DocumentService.generate_test_plan is now used for document generation
    # The additional parameters in GenerateRequest are preserved for backward compatibility
    # but are not currently used by the underlying service
    docs = await run_in_threadpool(
        doc_service.generate_test_plan,
        req.source_collections,
        req.source_doc_ids,
        req.doc_title,
        req.agent_set_id
    )
    return {"documents": docs}

class OptimizedTestPlanRequest(BaseModel):
    source_collections:   Optional[List[str]]   = None
    source_doc_ids:       Optional[List[str]]   = None
    doc_title:            Optional[str]         = "Comprehensive Test Plan"
    max_workers:          Optional[int]         = 4
    sectioning_strategy:  Optional[str]         = "auto"
    chunks_per_section:   Optional[int]         = 5
    agent_set_id:         int                   = None  # Required agent set for orchestration

@doc_gen_api_router.post("/generate_optimized_test_plan")
async def generate_optimized_test_plan(
    req: OptimizedTestPlanRequest,
    doc_service: DocumentService = Depends(document_service_dep),
    db: Session = Depends(get_db)):
    """
    Generate test plan using the new optimized multi-agent workflow:
    1. Extract rules/requirements per section with caching
    2. Generate test steps per section
    3. Consolidate into comprehensive test plan
    4. Critic review and approval
    5. O(log n) performance optimization
    """
    logger.info("Received /generate_optimized_test_plan ⇒ %s", req)

    # Validate agent_set_id is provided
    if req.agent_set_id is None:
        raise HTTPException(
            status_code=400,
            detail="agent_set_id is required. Please select an agent set from the Agent Set Manager or use the default 'Standard Test Plan Pipeline'."
        )

    # Validate agent set exists and is active
    from repositories.agent_set_repository import AgentSetRepository
    agent_set_repo = AgentSetRepository()
    agent_set = agent_set_repo.get_by_id(req.agent_set_id, db)

    if not agent_set:
        raise HTTPException(
            status_code=404,
            detail=f"Agent set with ID {req.agent_set_id} not found. Please create an agent set or use the default 'Standard Test Plan Pipeline' (ID: 1)."
        )

    if not agent_set.is_active:
        raise HTTPException(
            status_code=400,
            detail=f"Agent set '{agent_set.name}' (ID: {req.agent_set_id}) is inactive. Please select an active agent set."
        )

    logger.info(f"Using agent set: {agent_set.name} (ID: {req.agent_set_id})")

    try:
        docs = await run_in_threadpool(
            doc_service.generate_test_plan,
            req.source_collections,
            req.source_doc_ids,
            req.doc_title,
            req.agent_set_id
        )
        return {"documents": docs}
    except Exception as e:
        logger.error(f"Error in optimized test plan generation: {e}")
        raise HTTPException(status_code=500, detail=f"Test plan generation failed: {str(e)}")


# ============================================================================
# BACKGROUND TASK ENDPOINTS (No Timeout)
# ============================================================================

def _run_generation_background(
    source_collections: List[str],
    source_doc_ids: List[str],
    doc_title: str,
    agent_set_id: int,
    doc_service: DocumentService,
    pipeline_id: str
):
    """
    Background task for document generation.

    Note: Pipeline ID is generated upfront by the API endpoint and passed through
    to the service to ensure single pipeline creation.
    """
    try:
        logger.info(f"Background generation started for: {doc_title} (pipeline: {pipeline_id})")

        # Run generation (this can take 20+ minutes)
        # Pass pipeline_id to service so it uses our pre-generated ID
        docs = doc_service.generate_test_plan(
            source_collections,
            source_doc_ids,
            doc_title,
            agent_set_id,
            pipeline_id
        )

        if docs and len(docs) > 0:
            doc = docs[0]
            meta = doc.get("meta", {})

            logger.info(f"Background generation completed: {pipeline_id}")
            logger.info(f"Generated {meta.get('total_sections', 0)} sections, "
                       f"{meta.get('total_requirements', 0)} requirements, "
                       f"{meta.get('total_test_procedures', 0)} test procedures")
            logger.info(f"ChromaDB saved: {meta.get('chromadb_saved', False)}, "
                       f"Document ID: {doc.get('document_id', 'N/A')}")

            # Save result to Redis for retrieval
            redis_host = os.getenv("REDIS_HOST", "redis")
            redis_port = int(os.getenv("REDIS_PORT", 6379))
            redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

            result_data = {
                "title": doc.get("title", ""),
                "content": doc.get("content", ""),
                "docx_b64": doc.get("docx_b64", ""),
                "total_sections": str(meta.get("total_sections", 0)),
                "total_requirements": str(meta.get("total_requirements", 0)),
                "total_test_procedures": str(meta.get("total_test_procedures", 0)),
                "document_id": doc.get("document_id", ""),
                "collection_name": doc.get("collection_name", ""),
                "generated_at": doc.get("generated_at", ""),
                "chromadb_saved": str(meta.get("chromadb_saved", False))
            }

            # Use Redis pipeline for atomic operations
            # This ensures result is saved BEFORE status is set to completed
            pipe = redis_client.pipeline()

            # Save result
            pipe.hset(f"pipeline:{pipeline_id}:result", mapping=result_data)
            pipe.expire(f"pipeline:{pipeline_id}:result", 604800)  # 7 days

            # Update status to completed
            now = datetime.now().isoformat()
            pipe.hset(f"pipeline:{pipeline_id}:meta", mapping={
                "status": "completed",
                "completed_at": now,
                "last_updated_at": now,
                "progress_message": "Generation completed successfully"
            })

            # Execute all commands atomically
            pipe.execute()

            logger.info(f"Result saved atomically to Redis for pipeline {pipeline_id}")
            return doc
        else:
            raise ValueError("No documents generated")

    except Exception as e:
        logger.error(f"Background generation failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

        # Mark pipeline as failed in Redis
        try:
            redis_host = os.getenv("REDIS_HOST", "redis")
            redis_port = int(os.getenv("REDIS_PORT", 6379))
            redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

            now = datetime.now().isoformat()
            redis_client.hset(f"pipeline:{pipeline_id}:meta", mapping={
                "status": "failed",
                "error": str(e),
                "failed_at": now,
                "last_updated_at": now,
                "progress_message": f"Generation failed: {str(e)}"
            })
        except Exception as redis_error:
            logger.error(f"Failed to update Redis with error status: {redis_error}")

        raise


@doc_gen_api_router.post("/generate_documents_async")
async def generate_documents_async(
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    doc_service: DocumentService = Depends(document_service_dep),
    db: Session = Depends(get_db)):
    """
    Start document generation as a background task (no timeout).
    Returns pipeline_id immediately for progress tracking.
    """
    logger.info("Received /generate_documents_async ⇒ %s", req)

    # Validate agent_set_id is provided
    if req.agent_set_id is None:
        raise HTTPException(
            status_code=400,
            detail="agent_set_id is required. Please select an agent set from the Agent Set Manager or use the default 'Standard Test Plan Pipeline'."
        )

    # Validate agent set exists and is active
    from repositories.agent_set_repository import AgentSetRepository
    agent_set_repo = AgentSetRepository()
    agent_set = agent_set_repo.get_by_id(req.agent_set_id, db)

    if not agent_set:
        raise HTTPException(
            status_code=404,
            detail=f"Agent set with ID {req.agent_set_id} not found. Please create an agent set or use the default 'Standard Test Plan Pipeline' (ID: 1)."
        )

    if not agent_set.is_active:
        raise HTTPException(
            status_code=400,
            detail=f"Agent set '{agent_set.name}' (ID: {req.agent_set_id}) is inactive. Please select an active agent set."
        )

    logger.info(f"Using agent set: {agent_set.name} (ID: {req.agent_set_id})")

    # Generate pipeline_id upfront so we can return it immediately
    pipeline_id = f"pipeline_{uuid.uuid4().hex[:12]}"

    # Initialize pipeline metadata in Redis immediately (so UI can check status)
    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

    now = datetime.now().isoformat()
    pipeline_meta = {
        "pipeline_id": pipeline_id,
        "doc_title": req.doc_title or "Test Plan",
        "agent_set_name": agent_set.name,
        "status": "queued",
        "created_at": now,
        "last_updated_at": now,
        "progress_message": "Generation queued - waiting to start..."
    }
    redis_client.hset(f"pipeline:{pipeline_id}:meta", mapping=pipeline_meta)
    redis_client.expire(f"pipeline:{pipeline_id}:meta", 604800)  # 7 days

    # Add background task - pass pipeline_id so service uses it
    background_tasks.add_task(
        _run_generation_background,
        req.source_collections,
        req.source_doc_ids,
        req.doc_title,
        req.agent_set_id,
        doc_service,
        pipeline_id  # Pass to service so it doesn't create another one
    )

    logger.info(f"Background task queued: {pipeline_id}")

    # Return immediately - pipeline metadata already created
    return {
        "pipeline_id": pipeline_id,
        "status": "queued",
        "message": "Document generation started in background. Use /generation-status/{pipeline_id} to check progress.",
        "doc_title": req.doc_title or "Test Plan",
        "agent_set_name": agent_set.name
    }


@doc_gen_api_router.get("/generation-status/{pipeline_id}")
async def get_generation_status(pipeline_id: str):
    """Get the status of a document generation pipeline"""
    try:
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

        # Get metadata
        meta = redis_client.hgetall(f"pipeline:{pipeline_id}:meta")

        if not meta:
            raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id} not found or expired")

        # Get additional progress info if available
        progress_info = {
            "pipeline_id": pipeline_id,
            "status": meta.get("status", "unknown"),
            "doc_title": meta.get("doc_title", ""),
            "agent_set_name": meta.get("agent_set_name", ""),
            "created_at": meta.get("created_at", ""),
            "progress_message": meta.get("progress_message", ""),
            "sections_processed": meta.get("sections_processed", "0"),
            "total_sections": meta.get("total_sections", "0")
        }

        # If failed, include error
        if meta.get("status", "").upper() == "FAILED":
            progress_info["error"] = meta.get("error", "Unknown error")

        # If completed, check if result is available and include document info
        if meta.get("status", "").upper() == "COMPLETED":
            result_exists = redis_client.exists(f"pipeline:{pipeline_id}:result")
            progress_info["result_available"] = bool(result_exists)
            progress_info["completed_at"] = meta.get("completed_at", "")

            # Include document_id and collection_name from metadata
            if meta.get("generated_document_id"):
                progress_info["document_id"] = meta.get("generated_document_id")
                progress_info["collection_name"] = meta.get("collection", "generated_test_plan")

        return progress_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking status for {pipeline_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@doc_gen_api_router.get("/generation-result/{pipeline_id}")
async def get_generation_result(pipeline_id: str):
    """Get the completed document from a generation pipeline"""
    try:
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

        # Check status first
        meta = redis_client.hgetall(f"pipeline:{pipeline_id}:meta")
        if not meta:
            raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id} not found or expired")

        status = meta.get("status", "").upper()
        if status != "COMPLETED":
            raise HTTPException(
                status_code=400,
                detail=f"Pipeline is not completed yet. Current status: {status}"
            )

        # Get result
        result = redis_client.hgetall(f"pipeline:{pipeline_id}:result")
        if not result:
            raise HTTPException(status_code=404, detail=f"Result for pipeline {pipeline_id} not found or expired")

        return {
            "documents": [{
                "title": result.get("title", ""),
                "content": result.get("content", ""),
                "docx_b64": result.get("docx_b64", ""),
                "total_sections": int(result.get("total_sections", 0)),
                "total_requirements": int(result.get("total_requirements", 0)),
                "total_test_procedures": int(result.get("total_test_procedures", 0)),
                "pipeline_id": pipeline_id,
                "document_id": result.get("document_id", ""),
                "collection_name": result.get("collection_name", "generated_test_plan"),
                "generated_at": result.get("generated_at", ""),
                "chromadb_saved": result.get("chromadb_saved", "False").lower() == "true"
            }]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving result for {pipeline_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@doc_gen_api_router.get("/list-pipelines")
async def list_pipelines(limit: int = 50):
    """List all active and recent pipelines"""
    try:
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

        # Get all pipeline metadata keys
        pipeline_keys = redis_client.keys("pipeline:*:meta")

        pipelines = []
        for key in pipeline_keys[:limit]:
            # Extract pipeline_id from key (format: pipeline:PIPELINE_ID:meta)
            pipeline_id = key.replace("pipeline:", "").replace(":meta", "")

            # Get metadata
            meta = redis_client.hgetall(key)

            if meta:
                # Check if result exists
                result_exists = redis_client.exists(f"pipeline:{pipeline_id}:result")

                pipelines.append({
                    "pipeline_id": pipeline_id,
                    "status": meta.get("status", "unknown"),
                    "doc_title": meta.get("doc_title", "Untitled"),
                    "agent_set_name": meta.get("agent_set_name", ""),
                    "created_at": meta.get("created_at", ""),
                    "progress_message": meta.get("progress_message", ""),
                    "result_available": bool(result_exists)
                })

        # Sort by created_at descending (most recent first)
        pipelines.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return {
            "pipelines": pipelines,
            "total": len(pipelines)
        }

    except Exception as e:
        logger.error(f"Error listing pipelines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@doc_gen_api_router.post("/cancel-pipeline/{pipeline_id}")
async def cancel_pipeline(pipeline_id: str):
    """
    Cancel/abort a running pipeline.

    Sets the abort flag - the pipeline will stop at the next checkpoint
    and return partial results.
    """
    try:
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

        # Check if pipeline exists
        meta = redis_client.hgetall(f"pipeline:{pipeline_id}:meta")
        if not meta:
            raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id} not found or expired")

        current_status = meta.get("status", "")
        current_status_upper = current_status.upper()

        # Can only cancel queued or processing pipelines
        if current_status_upper not in ["QUEUED", "PROCESSING"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel pipeline with status '{current_status}'. Only queued or processing pipelines can be cancelled."
            )

        # Set abort flag
        redis_client.set(f"pipeline:{pipeline_id}:abort", "1", ex=60 * 60 * 24)  # 24 hour expiry

        # Update metadata
        redis_client.hset(f"pipeline:{pipeline_id}:meta", mapping={
            "status": "cancelling",
            "progress_message": "Cancellation requested - stopping at next checkpoint..."
        })

        logger.info(f"Cancellation requested for pipeline {pipeline_id}")

        return {
            "pipeline_id": pipeline_id,
            "message": "Cancellation requested. Pipeline will stop at next checkpoint and return partial results.",
            "previous_status": current_status,
            "new_status": "cancelling"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling pipeline {pipeline_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@doc_gen_api_router.post("/cleanup-stale-pipelines")
async def cleanup_stale_pipelines(max_age_minutes: int = 30):
    """
    Detect and mark stale pipelines as failed.

    A pipeline is considered stale if:
    - Status is "queued", "processing", or "initializing"
    - last_updated_at is more than max_age_minutes ago

    This handles cases where background tasks died (container restart, crash, etc.)
    """
    try:
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

        # Get all pipeline metadata keys
        pipeline_keys = redis_client.keys("pipeline:*:meta")

        stale_pipelines = []
        now = datetime.now()

        for key in pipeline_keys:
            try:
                meta = redis_client.hgetall(key)
                if not meta:
                    continue

                status = meta.get("status", "")
                status_lower = status.lower()
                last_updated_str = meta.get("last_updated_at", "")
                pipeline_id = meta.get("pipeline_id", key.split(":")[1])

                # Only check active pipelines
                if status_lower not in ["queued", "processing", "initializing"]:
                    continue

                # Check if last_updated_at exists and parse it
                if not last_updated_str:
                    # No timestamp - assume it's stale and mark as failed
                    logger.warning(f"Pipeline {pipeline_id} has no last_updated_at timestamp - marking as stale")
                    stale_pipelines.append(pipeline_id)

                    failed_at = datetime.now().isoformat()
                    redis_client.hset(f"pipeline:{pipeline_id}:meta", mapping={
                        "status": "failed",
                        "error": "Pipeline stale - missing last_updated_at timestamp (likely from before stale detection was implemented)",
                        "failed_at": failed_at,
                        "last_updated_at": failed_at,
                        "progress_message": "Pipeline marked as failed - no timestamp"
                    })
                    continue

                try:
                    last_updated = datetime.fromisoformat(last_updated_str.replace('Z', '+00:00'))
                    # Remove timezone info for comparison
                    if last_updated.tzinfo:
                        last_updated = last_updated.replace(tzinfo=None)

                    age_minutes = (now - last_updated).total_seconds() / 60

                    if age_minutes > max_age_minutes:
                        logger.warning(f"Pipeline {pipeline_id} is stale ({age_minutes:.1f} minutes old)")
                        stale_pipelines.append(pipeline_id)

                        # Mark as failed
                        failed_at = datetime.now().isoformat()
                        redis_client.hset(f"pipeline:{pipeline_id}:meta", mapping={
                            "status": "failed",
                            "error": f"Pipeline stale - no updates for {age_minutes:.1f} minutes (likely died due to container restart)",
                            "failed_at": failed_at,
                            "last_updated_at": failed_at,
                            "progress_message": f"Pipeline marked as failed - stale for {age_minutes:.1f} minutes"
                        })

                except (ValueError, AttributeError) as e:
                    logger.error(f"Failed to parse timestamp for pipeline {pipeline_id}: {e}")
                    stale_pipelines.append(pipeline_id)

            except Exception as e:
                logger.error(f"Error checking pipeline {key}: {e}")
                continue

        return {
            "stale_pipelines_found": len(stale_pipelines),
            "stale_pipeline_ids": stale_pipelines,
            "max_age_minutes": max_age_minutes,
            "checked_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error during stale pipeline cleanup: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class PreviewRequest(BaseModel):
    source_collections:   Optional[List[str]]   = None
    source_doc_ids:       Optional[List[str]]   = None
    sectioning_strategy:  Optional[str]         = "auto"
    chunks_per_section:   Optional[int]         = 5
    use_rag:              Optional[bool]        = True
    top_k:                Optional[int]         = 5


@doc_gen_api_router.post("/preview-sections")
async def preview_sections(
    req: PreviewRequest,
    doc_service: DocumentService = Depends(document_service_dep)):
    try:    
        sections = await run_in_threadpool(
            doc_service._extract_document_sections,
            req.source_collections,
            req.source_doc_ids,
            req.use_rag,
            req.top_k,
            req.sectioning_strategy,
            req.chunks_per_section,
        )
        names = list(sections.keys())
        return {"count": len(names), "section_names": names[:500]}
    except Exception as e:
        logger.error(f"Preview sections failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@doc_gen_api_router.get("/generated-documents")
async def get_generated_documents():
    """Get list of all generated documents from vector store"""
    try:
        # Query the generated_documents collection
        chroma_url = os.getenv("CHROMA_URL", "http://chromadb:8000")
        response = requests.get(
            f"{chroma_url}/documents",
            params={"collection_name": "generated_documents"},
            timeout=10
        )
        
        if response.status_code == 404:
            return {"documents": [], "message": "No generated documents found"}
        
        response.raise_for_status()
        data = response.json()
        
        documents = data.get("documents", [])
        metadatas = data.get("metadatas", [])
        ids = data.get("ids", [])
        
        # Combine document info
        generated_docs = []
        for doc_id, content, metadata in zip(ids, documents, metadatas):
            generated_docs.append({
                "document_id": doc_id,
                "title": metadata.get("title", "Untitled"),
                "generated_at": metadata.get("generated_at", "Unknown"),
                "template_collection": metadata.get("template_collection", "Unknown"),
                "agent_ids": metadata.get("agent_ids", "[]"),
                "session_id": metadata.get("session_id", ""),
                "word_count": metadata.get("word_count", 0),
                "char_count": metadata.get("char_count", 0),
                "preview": content[:300] + "..." if len(content) > 300 else content
            })
        
        # Sort by generation date (newest first)
        generated_docs.sort(key=lambda x: x["generated_at"], reverse=True)
        
        return {
            "documents": generated_docs,
            "total_count": len(generated_docs)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@doc_gen_api_router.post("/export-testplan-word")
async def export_testplan_word(
    payload: Dict[str, Any],
    word_export_service: WordExportService = Depends(WordExportService)):
    """
    Export a generated test plan (stored in ChromaDB) to a Word document.
    Body: {"document_id": str, "collection_name": str?}
    Defaults to collection 'generated_test_plan' if not provided.
    """
    try:
        document_id = payload.get("document_id")
        collection_name = payload.get("collection_name") or os.getenv("GENERATED_TESTPLAN_COLLECTION", "generated_test_plan")
        if not document_id:
            raise HTTPException(status_code=400, detail="document_id is required")

        # Fetch documents from Chroma and find the one we need
        chroma_url = os.getenv("CHROMA_URL", "http://chromadb:8000")
        resp = requests.get(f"{chroma_url}/documents", params={"collection_name": collection_name}, timeout=30)
        if not resp.ok:
            raise HTTPException(status_code=resp.status_code, detail=f"Failed to fetch collection: {resp.text}")
        data = resp.json()
        ids = data.get("ids", [])
        docs = data.get("documents", [])
        metas = data.get("metadatas", [])

        try:
            idx = ids.index(document_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Document not found in collection")

        content = docs[idx] or ""
        title = (metas[idx] or {}).get("title") or "Generated Test Plan"

        # Export using WordExportService
        word_bytes = word_export_service.export_markdown_to_word(title, content)
        b64 = base64.b64encode(word_bytes).decode("utf-8")
        filename = f"{title.replace(' ', '_')}.docx"
        return {"filename": filename, "content_b64": b64}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export test plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@doc_gen_api_router.get("/export-pipeline-word/{pipeline_id}")
async def export_pipeline_word(
    pipeline_id: str, 
    word_export_service: WordExportService = Depends(WordExportService)):
    """
    Export the final consolidated test plan for a given pipeline ID from Redis
    as a Word document (no Chroma dependency).
    """
    try:
        rhost = os.getenv("REDIS_HOST", "redis")
        rport = int(os.getenv("REDIS_PORT", 6379))
        rcli = redis.Redis(host=rhost, port=rport, decode_responses=True)

        key = f"pipeline:{pipeline_id}:final_result"
        if not rcli.exists(key):
            raise HTTPException(status_code=404, detail="Pipeline final result not found")

        final_data = rcli.hgetall(key)
        title = final_data.get("title") or "Generated Test Plan"
        markdown = final_data.get("consolidated_markdown") or ""
        if not markdown:
            raise HTTPException(status_code=400, detail="No consolidated content available to export")

        word_bytes = word_export_service.export_markdown_to_word(title, markdown)
        b64 = base64.b64encode(word_bytes).decode("utf-8")
        filename = f"{title.replace(' ', '_')}.docx"
        return {"filename": filename, "content_b64": b64}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export pipeline {pipeline_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@doc_gen_api_router.delete("/generated-documents/{document_id}")
async def delete_generated_document(document_id: str):
    """Delete a generated document from vector store"""
    try:
        chroma_url = os.getenv("CHROMA_URL", "http://chromadb:8000")

        # Delete from ChromaDB
        payload = {
            "collection_name": "generated_documents",
            "ids": [document_id]
        }
        
        response = requests.post(
            f"{chroma_url}/documents/delete",
            json=payload,
            timeout=10
        )
        
        if response.ok:
            return {"message": f"Document {document_id} deleted successfully"}
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to delete document: {response.text}"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_evaluation_service() -> EvaluationService:
    """Dependency provider for EvaluationService"""
    return EvaluationService(
        rag=RAGService(),
        llm=LLMService()
    )

def get_test_card_service() -> TestCardService:
    """Dependency provider for TestCardService"""
    return TestCardService(llm_service=LLMService())

def get_word_export_service() -> WordExportService:
    """Dependency provider for WordExportService"""
    return WordExportService()

def get_pairwise_synthesis_service() -> PairwiseSynthesisService:
    """Dependency provider for PairwiseSynthesisService"""
    return PairwiseSynthesisService(llm_service=LLMService())

def get_redis_client() -> redis.Redis:
    """Dependency provider for Redis client"""
    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    return redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

@doc_gen_api_router.post("/evaluate_doc", response_model=EvaluateResponse)
async def evaluate_doc(
    req: EvaluateRequest,
    chat_repo: ChatRepository = Depends(get_chat_repository),
    db: Session = Depends(get_db),
    eval_service: EvaluationService = Depends(get_evaluation_service)):
    try:
        # generate a session_id so you can track history
        doc_session_id = str(uuid.uuid4())

        # Evaluate document with citation support
        answer, rt_ms, metadata_list, formatted_citations = eval_service.evaluate_document(
            document_id     = req.document_id,
            collection_name = req.collection_name,
            prompt          = req.prompt,
            top_k           = req.top_k,
            model_name      = req.model_name,
            session_id      = doc_session_id,
            include_citations = True,
        )

        # Combine answer with formatted citations for storage (same as chat)
        full_response = answer
        if formatted_citations:
            full_response = answer + "\n\n" + formatted_citations

        # Save chat history with citations included
        try:
            chat_repo.create_chat_entry(
                user_query=req.prompt,
                response=full_response,
                model_used=req.model_name,
                collection_name=req.collection_name,
                query_type="rag",
                response_time_ms=rt_ms,
                session_id=doc_session_id
            )
            db.commit()
        except Exception as e:
            logger.error(f"Failed to save evaluation history: {e}")
            db.rollback()

        # Prepare citation data for response
        citations = []
        if metadata_list:
            for meta in metadata_list:
                # Extract citation information from metadata
                citation_data = {
                    "document_index": meta.get("document_index"),
                    "distance": meta.get("distance"),
                    "quality_tier": meta.get("quality_tier"),
                    "distance_explanation": meta.get("distance_explanation"),
                    "excerpt": meta.get("metadata", {}).get("text", meta.get("document_text", ""))[:500],  # First 500 chars
                    "source_file": meta.get("metadata", {}).get("document_name", ""),
                    "page_number": meta.get("metadata", {}).get("page_number"),
                    "section_name": meta.get("metadata", {}).get("section_title"),
                }
                citations.append(citation_data)

        return EvaluateResponse(
            document_id     = req.document_id,
            collection_name = req.collection_name,
            prompt          = req.prompt,
            model_name      = req.model_name,
            response        = answer,
            response_time_ms= rt_ms,
            session_id      = doc_session_id,
            citations       = citations if citations else None,
            formatted_citations = formatted_citations if formatted_citations else None,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@doc_gen_api_router.post("/export-agents-word")
async def export_agents_to_word(
    agent_ids: List[int] = None,
    export_format: str = "detailed",
    word_export_service: WordExportService = Depends(WordExportService),
    db: Session = Depends(get_db_session)):
    """
    Export agent configurations to a Word document.
    
    Args:
        agent_ids: Optional list of specific agent IDs to export. If None, exports all agents.
        export_format: "summary" or "detailed" export format
    """
    try:
        # Get agents from database
        if agent_ids:
            agents_query = db.query(ComplianceAgent).filter(ComplianceAgent.id.in_(agent_ids))
        else:
            agents_query = db.query(ComplianceAgent).all()
        
        agents = agents_query.all() if hasattr(agents_query, 'all') else agents_query
        
        if not agents:
            raise HTTPException(status_code=404, detail="No agents found")
        
        # Convert to dict format for export
        agents_data = []
        for agent in agents:
            agents_data.append({
                "id": agent.id,
                "name": agent.name,
                "model_name": agent.model_name,
                "system_prompt": agent.system_prompt,
                "user_prompt_template": agent.user_prompt_template,
                "temperature": agent.temperature,
                "max_tokens": agent.max_tokens,
                "created_at": agent.created_at.isoformat() if agent.created_at else None,
                "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
                "created_by": agent.created_by,
                "is_active": agent.is_active,
                "total_queries": agent.total_queries,
                "avg_response_time_ms": agent.avg_response_time_ms,
                "success_rate": agent.success_rate,
                "chain_type": agent.chain_type
            })
        
        # Generate Word document
        word_bytes = word_export_service.export_agents_to_word(agents_data, export_format)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"agents_export_{timestamp}.docx"
        
        # Return as base64 for frontend download
        word_b64 = base64.b64encode(word_bytes).decode('utf-8')
        
        return {
            "filename": filename,
            "content_b64": word_b64,
            "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "agents_exported": len(agents_data),
            "export_format": export_format
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export agents to Word: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@doc_gen_api_router.post("/export-chat-history-word")
async def export_chat_history_to_word(
    session_id: Optional[str] = None,
    limit: int = 50,
    word_export_service: WordExportService = Depends(WordExportService),
    chat_repo: ChatRepository = Depends(get_chat_repository)
):
    """
    Export chat history to a Word document.

    Args:
        session_id: Optional session ID to filter by
        limit: Maximum number of chat records to export
    """
    try:
        # Query chat history
        chat_records = chat_repo.get_all(limit=limit, order_by="timestamp")

        if not chat_records:
            raise HTTPException(status_code=404, detail="No chat history found")
        
        # Convert to dict format
        chat_data = []
        for chat in chat_records:
            chat_data.append({
                "id": chat.id,
                "user_query": chat.user_query,
                "response": chat.response,
                "model_used": chat.model_used,
                "query_type": chat.query_type,
                "response_time_ms": chat.response_time_ms,
                "timestamp": chat.timestamp,
                "session_id": chat.session_id,
            })
        
        # Generate Word document
        word_bytes = word_export_service.export_chat_history_to_word(chat_data, session_id)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_suffix = f"_session_{session_id[:8]}" if session_id else ""
        filename = f"chat_history{session_suffix}_{timestamp}.docx"
        
        # Return as base64
        word_b64 = base64.b64encode(word_bytes).decode('utf-8')
        
        return {
            "filename": filename,
            "content_b64": word_b64,
            "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "records_exported": len(chat_data),
            "session_filter": session_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export chat history to Word: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@doc_gen_api_router.post("/export-simulation-word")
async def export_agent_simulation_to_word(
    simulation_data: Dict[str, Any],
    word_export_service: WordExportService = Depends(WordExportService)):
    """
    Export agent simulation results to a Word document.
    
    Args:
        simulation_data: Dictionary containing simulation results
    """
    try:
        # Generate Word document
        word_bytes = word_export_service.export_agent_simulation_to_word(simulation_data)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = simulation_data.get('session_id', 'unknown')[:8]
        filename = f"agent_simulation_{session_id}_{timestamp}.docx"
        
        # Return as base64
        word_b64 = base64.b64encode(word_bytes).decode('utf-8')
        
        return {
            "filename": filename,
            "content_b64": word_b64,
            "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "session_id": simulation_data.get('session_id'),
            "simulation_type": simulation_data.get('type', 'unknown')
        }
        
    except Exception as e:
        logger.error(f"Failed to export agent simulation to Word: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@doc_gen_api_router.post("/export-rag-assessment-word")
async def export_rag_assessment_to_word(
    assessment_data: Dict[str, Any],
    word_export_service: WordExportService = Depends(WordExportService)):
    """
    Export RAG assessment results to a Word document.
    
    Args:
        assessment_data: Dictionary containing RAG assessment results
    """
    try:
        # Generate Word document
        word_bytes = word_export_service.export_rag_assessment_to_word(assessment_data)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = assessment_data.get('performance_metrics', {}).get('session_id', 'unknown')[:8]
        filename = f"rag_assessment_{session_id}_{timestamp}.docx"
        
        # Return as base64
        word_b64 = base64.b64encode(word_bytes).decode('utf-8')
        
        return {
            "filename": filename,
            "content_b64": word_b64,
            "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "session_id": assessment_data.get('performance_metrics', {}).get('session_id')
        }
        
    except Exception as e:
        logger.error(f"Failed to export RAG assessment to Word: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

@doc_gen_api_router.post("/export-reconstructed-word")
async def export_reconstructed_document_to_word(
    reconstructed: Dict[str, Any],
    word_export_service: WordExportService = Depends(WordExportService)):
    """Export a reconstructed document (from ChromaDB) to a Word document using the central WordExportService."""
    try:
        word_bytes = word_export_service.export_reconstructed_document_to_word(reconstructed)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = reconstructed.get('document_name') or 'reconstructed_document'
        # sanitize filename
        safe_base = "".join(c for c in base if c.isalnum() or c in (' ', '_', '-')).strip() or 'reconstructed_document'
        filename = f"{safe_base}_{timestamp}.docx"
        word_b64 = base64.b64encode(word_bytes).decode('utf-8')
        return {
            "filename": filename,
            "content_b64": word_b64,
            "content_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
    except Exception as e:
        logger.error(f"Failed to export reconstructed document to Word: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@doc_gen_api_router.get("/export-word-demo")
async def word_export_demo():
    """
    Demo endpoint showing example usage of Word export capabilities.
    """
    return {
        "demo": "Word Export Service",
        "description": "Export agents, chat history, and simulation results to Word documents",
        "available_exports": [
            {
                "endpoint": "POST /doc_gen/export-agents-word",
                "description": "Export agent configurations",
                "parameters": {
                    "agent_ids": "Optional list of specific agent IDs",
                    "export_format": "summary or detailed"
                }
            },
            {
                "endpoint": "POST /doc_gen/export-chat-history-word",
                "description": "Export chat conversation history",
                "parameters": {
                    "session_id": "Optional session ID filter",
                    "limit": "Maximum records to export"
                }
            },
            {
                "endpoint": "POST /doc_gen/export-simulation-word",
                "description": "Export agent simulation results",
                "parameters": {
                    "simulation_data": "Complete simulation results dictionary"
                }
            },
            {
                "endpoint": "POST /doc_gen/export-rag-assessment-word",
                "description": "Export RAG assessment results",
                "parameters": {
                    "assessment_data": "Complete assessment results dictionary"
                }
            }
        ],
        "features": [
            "Professional Word document formatting",
            "Structured data presentation with tables",
            "Session-based organization",
            "Performance metrics inclusion",
            "Base64 encoding for easy frontend integration",
            "Automatic filename generation with timestamps"
        ],
        "example_usage": {
            "export_all_agents": {
                "endpoint": "POST /doc_gen/export-agents-word",
                "payload": {
                    "export_format": "detailed"
                }
            },
            "export_specific_session": {
                "endpoint": "POST /doc_gen/export-chat-history-word",
                "payload": {
                    "session_id": "abc123def456",
                    "limit": 25
                }
            }
        }
    }


# ============================================================================
# TEST CARD GENERATION ENDPOINTS (Phase 2)
# ============================================================================

@doc_gen_api_router.post("/generate-test-card", response_model=TestCardResponse)
async def generate_test_card(
    req: TestCardRequest,
    test_card_service: TestCardService = Depends(get_test_card_service)
):
    """
    Generate a test card from test rules markdown.

    Converts test procedures and rules into an executable test card with:
    - Test ID
    - Test Title
    - Step-by-step procedures
    - Expected results
    - Acceptance criteria
    - Pass/Fail tracking checkboxes

    Args:
        req: Test card request with section title and rules markdown

    Returns:
        Test card in requested format (markdown_table, json, or docx_table)

    Example:
        ```json
        {
            "section_title": "4.1 Power Supply Requirements",
            "rules_markdown": "## Requirements\n**Test Rules:**\n1. Verify voltage...",
            "format": "markdown_table"
        }
        ```
    """
    try:
        logger.info(f"Generating test card for section: {req.section_title}")

        test_card_content = await run_in_threadpool(
            test_card_service.generate_test_card_from_rules,
            section_title=req.section_title,
            rules_markdown=req.rules_markdown,
            format=req.format
        )

        # Count tests based on format
        test_count = 0
        if req.format == "markdown_table":
            # Count rows starting with | TC-
            test_count = len([line for line in test_card_content.split('\n')
                            if line.strip().startswith('| TC-')])
        elif req.format == "json":
            import json
            try:
                test_cards = json.loads(test_card_content)
                test_count = len(test_cards)
            except json.JSONDecodeError:
                test_count = 0

        logger.info(f"Generated {test_count} test cards for {req.section_title}")

        return TestCardResponse(
            section_title=req.section_title,
            test_card_content=test_card_content,
            format=req.format,
            test_count=test_count
        )

    except Exception as e:
        logger.error(f"Test card generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Test card generation failed: {str(e)}")


@doc_gen_api_router.post("/generate-test-cards-batch", response_model=TestCardBatchResponse)
async def generate_test_cards_batch(
    req: TestCardBatchRequest,
    test_card_service: TestCardService = Depends(get_test_card_service),
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """
    Generate test cards for multiple sections in a pipeline.

    Retrieves section data from Redis pipeline and generates test cards
    for all sections or a specified subset.

    Args:
        req: Batch request with pipeline ID and optional section filter

    Returns:
        Dictionary mapping section titles to test card content

    Example:
        ```json
        {
            "pipeline_id": "pipeline_abc123def456",
            "format": "markdown_table",
            "section_titles": ["Section 4.1", "Section 4.2"]  // optional
        }
        ```
    """
    try:
        logger.info(f"Generating test cards for pipeline: {req.pipeline_id}")

        # Generate test cards for all sections in pipeline
        test_cards = await run_in_threadpool(
            test_card_service.generate_test_cards_for_pipeline,
            pipeline_id=req.pipeline_id,
            redis_client=redis_client,
            format=req.format
        )

        # Filter by section titles if specified
        if req.section_titles:
            test_cards = {
                title: content
                for title, content in test_cards.items()
                if title in req.section_titles
            }

        # Count total tests
        total_tests = 0
        for content in test_cards.values():
            if req.format == "markdown_table":
                total_tests += len([line for line in content.split('\n')
                                  if line.strip().startswith('| TC-')])
            elif req.format == "json":
                import json
                try:
                    total_tests += len(json.loads(content))
                except json.JSONDecodeError:
                    pass

        logger.info(f"Generated test cards for {len(test_cards)} sections, {total_tests} total tests")

        return TestCardBatchResponse(
            pipeline_id=req.pipeline_id,
            test_cards=test_cards,
            total_sections=len(test_cards),
            total_tests=total_tests,
            format=req.format
        )

    except Exception as e:
        logger.error(f"Batch test card generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Batch generation failed: {str(e)}")


@doc_gen_api_router.post("/export-test-plan-with-cards", response_model=ExportTestPlanWithCardsResponse)
async def export_test_plan_with_cards(
    req: ExportTestPlanWithCardsRequest,
    test_card_service: TestCardService = Depends(get_test_card_service),
    word_export_service: WordExportService = Depends(get_word_export_service),
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """
    Export test plan with embedded test cards to Word document.

    Features:
    - Includes test card tables after each section
    - Supports Pandoc export (professional formatting with TOC)
    - Supports python-docx export (standard formatting)
    - Automatic markdown sanitization
    - Optional reference document for styling

    Args:
        req: Export request with pipeline ID and formatting options

    Returns:
        Word document as base64-encoded bytes with metadata

    Example:
        ```json
        {
            "pipeline_id": "pipeline_abc123def456",
            "include_test_cards": true,
            "export_format": "pandoc",
            "include_toc": true,
            "number_sections": true
        }
        ```
    """
    try:
        logger.info(f"Exporting test plan with cards: {req.pipeline_id}, format={req.export_format}")

        # Get test plan from Redis
        final_data = redis_client.hgetall(f"pipeline:{req.pipeline_id}:final_result")
        if not final_data:
            raise HTTPException(status_code=404, detail=f"Pipeline result not found: {req.pipeline_id}")

        title = final_data.get("title", "Test Plan")
        markdown = final_data.get("consolidated_markdown", "")

        if not markdown:
            raise HTTPException(status_code=404, detail="No markdown content found in pipeline")

        # Enhance markdown with test cards if requested
        if req.include_test_cards:
            logger.info("Adding test cards to markdown...")
            enhanced_markdown = await _add_test_cards_to_markdown(
                markdown=markdown,
                test_card_service=test_card_service,
                pipeline_id=req.pipeline_id,
                redis_client=redis_client
            )
        else:
            enhanced_markdown = markdown

        # Export based on format
        if req.export_format == "pandoc":
            logger.info("Exporting with Pandoc...")
            word_bytes = await run_in_threadpool(
                word_export_service.export_markdown_to_word_with_pandoc,
                title=title,
                markdown_content=enhanced_markdown,
                reference_docx=req.reference_docx,
                include_toc=req.include_toc,
                number_sections=req.number_sections
            )
        else:
            logger.info("Exporting with python-docx...")
            # Use existing export_markdown_to_word method if available
            # For now, we'll use Pandoc with fallback
            word_bytes = await run_in_threadpool(
                word_export_service.export_markdown_to_word_with_pandoc,
                title=title,
                markdown_content=enhanced_markdown,
                reference_docx=None,
                include_toc=False,
                number_sections=False
            )

        # Encode to base64
        b64 = base64.b64encode(word_bytes).decode("utf-8")

        # Generate filename
        safe_title = title.replace(' ', '_').replace('/', '_')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{safe_title}_with_test_cards_{timestamp}.docx"

        logger.info(f"Export complete: {len(word_bytes)} bytes, filename={filename}")

        return ExportTestPlanWithCardsResponse(
            filename=filename,
            content_b64=b64,
            format=req.export_format,
            includes_test_cards=req.include_test_cards,
            file_size_bytes=len(word_bytes)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export with test cards failed: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# ============================ PAIRWISE SYNTHESIS ============================

class PairwiseSynthesisRequest(BaseModel):
    """Request for pairwise section synthesis"""
    pipeline_id: str
    synthesis_mode: str = "pairwise"  # "pairwise" or "consecutive"
    max_workers: int = 4

    class Config:
        json_schema_extra = {
            "example": {
                "pipeline_id": "pipeline_abc123def456",
                "synthesis_mode": "pairwise",
                "max_workers": 4
            }
        }


class PairwiseSynthesisResponse(BaseModel):
    """Response from pairwise synthesis"""
    pipeline_id: str
    synthesis_mode: str
    original_sections: int
    synthesized_sections: int
    sections: Dict[str, str]  # section_title -> synthesized_content

    class Config:
        json_schema_extra = {
            "example": {
                "pipeline_id": "pipeline_abc123",
                "synthesis_mode": "pairwise",
                "original_sections": 10,
                "synthesized_sections": 5,
                "sections": {
                    "Section 4.1 & 4.2 Combined": "Synthesized content...",
                    "Section 4.3 & 4.4 Combined": "Synthesized content..."
                }
            }
        }


@doc_gen_api_router.post("/pairwise-synthesis", response_model=PairwiseSynthesisResponse)
async def pairwise_synthesis(
    req: PairwiseSynthesisRequest,
    pairwise_service: PairwiseSynthesisService = Depends(get_pairwise_synthesis_service),
    redis_client: redis.Redis = Depends(get_redis_client)
):
    """
    Apply pairwise synthesis to an existing pipeline's sections.

    This reduces redundancy by combining adjacent sections and identifying
    cross-section dependencies. Based on the notebook's approach.

    Synthesis Modes:
    - **pairwise**: Combine non-overlapping pairs (1+2, 3+4, 5+6...)
    - **consecutive**: Combine overlapping pairs (1+2, 2+3, 3+4...)

    Args:
        req: Pairwise synthesis request

    Returns:
        Synthesized sections

    Example:
        Original: 10 sections
        Pairwise mode: 5 combined sections
        Consecutive mode: 9 combined sections
    """
    try:
        logger.info(f"Starting pairwise synthesis for pipeline: {req.pipeline_id} (mode: {req.synthesis_mode})")

        # Synthesize sections from pipeline
        synthesized_sections = await run_in_threadpool(
            pairwise_service.synthesize_with_redis_pipeline,
            req.pipeline_id,
            redis_client,
            req.synthesis_mode,
            req.max_workers
        )

        if not synthesized_sections:
            logger.warning(f"No sections synthesized for pipeline: {req.pipeline_id}")
            raise HTTPException(
                status_code=404,
                detail=f"No sections found for pipeline or synthesis failed: {req.pipeline_id}"
            )

        # Count original sections
        pattern = f"pipeline:{req.pipeline_id}:critic:*"
        original_keys = redis_client.keys(pattern)
        original_count = len(original_keys)

        logger.info(f"Pairwise synthesis complete: {original_count} → {len(synthesized_sections)} sections")

        # Optionally: Store synthesized sections back to Redis with new keys
        # For now, just return them
        for section_title, content in synthesized_sections.items():
            # Store with pairwise prefix for retrieval
            key = f"pipeline:{req.pipeline_id}:pairwise:{section_title}"
            redis_client.hset(key, mapping={
                "section_title": section_title,
                "synthesized_content": content,
                "synthesis_mode": req.synthesis_mode,
                "timestamp": datetime.now().isoformat()
            })

        return PairwiseSynthesisResponse(
            pipeline_id=req.pipeline_id,
            synthesis_mode=req.synthesis_mode,
            original_sections=original_count,
            synthesized_sections=len(synthesized_sections),
            sections=synthesized_sections
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pairwise synthesis failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Pairwise synthesis failed: {str(e)}")


async def _add_test_cards_to_markdown(
    markdown: str,
    test_card_service: TestCardService,
    pipeline_id: str,
    redis_client: redis.Redis
) -> str:
    """
    Add test card tables after each section in markdown.

    Strategy:
    1. Parse markdown to identify sections
    2. For each section, get critic result from Redis
    3. Generate test card from critic's synthesized rules
    4. Insert test card table after section

    Args:
        markdown: Original markdown content
        test_card_service: Test card service instance
        pipeline_id: Redis pipeline ID
        redis_client: Redis client instance

    Returns:
        Enhanced markdown with test cards inserted
    """
    try:
        # Get all section critic results from Redis
        pattern = f"pipeline:{pipeline_id}:critic:*"
        critic_keys = redis_client.keys(pattern)

        logger.info(f"Found {len(critic_keys)} critic sections for pipeline {pipeline_id}")

        sections_with_cards = {}
        for key in critic_keys:
            try:
                critic_data = redis_client.hgetall(key)
                section_title = critic_data.get("section_title", "")
                synthesized_rules = critic_data.get("synthesized_rules", "")

                if section_title and synthesized_rules:
                    # Generate test card
                    test_card = await run_in_threadpool(
                        test_card_service.generate_test_card_from_rules,
                        section_title=section_title,
                        rules_markdown=synthesized_rules,
                        format="markdown_table"
                    )
                    sections_with_cards[section_title] = test_card
                    logger.debug(f"Generated test card for: {section_title}")
            except Exception as e:
                logger.warning(f"Failed to generate test card for key {key}: {e}")
                continue

        if not sections_with_cards:
            logger.warning("No test cards generated, returning original markdown")
            return markdown

        # Insert test cards into markdown
        lines = markdown.split('\n')
        enhanced_lines = []
        current_section = None
        section_content_started = False

        for i, line in enumerate(lines):
            enhanced_lines.append(line)

            # Detect main section headers (## level)
            if line.startswith('## '):
                section_header = line[3:].strip()

                # If we just finished a section, insert its test card
                if current_section and current_section in sections_with_cards:
                    enhanced_lines.insert(-1, '\n### Test Card\n')
                    enhanced_lines.insert(-1, sections_with_cards[current_section])
                    enhanced_lines.insert(-1, '\n')

                current_section = section_header
                section_content_started = True

            # Check if this is the last line - insert test card for final section
            if i == len(lines) - 1 and current_section and current_section in sections_with_cards:
                enhanced_lines.append('\n### Test Card\n')
                enhanced_lines.append(sections_with_cards[current_section])
                enhanced_lines.append('\n')

        enhanced_markdown = '\n'.join(enhanced_lines)
        logger.info(f"Enhanced markdown: added {len(sections_with_cards)} test cards")

        return enhanced_markdown

    except Exception as e:
        logger.error(f"Failed to add test cards to markdown: {e}")
        # Return original markdown on error
        return markdown


# ============================================================================
# TEST CARD DOCUMENT MANAGEMENT (New Design - Separate Documents)
# ============================================================================

class GenerateTestCardsFromPlanRequest(BaseModel):
    """Request to generate test card documents from a test plan"""
    test_plan_id: str
    collection_name: str = "generated_test_plan"
    format: str = "markdown_table"  # markdown_table, json, docx_table

    class Config:
        json_schema_extra = {
            "example": {
                "test_plan_id": "testplan_multiagent_pipeline_abc123_def456",
                "collection_name": "generated_test_plan",
                "format": "markdown_table"
            }
        }


class GenerateTestCardsFromPlanResponse(BaseModel):
    """Response from test card generation"""
    test_plan_id: str
    test_plan_title: str
    test_cards_generated: int
    test_cards: List[Dict[str, Any]]
    chromadb_saved: bool
    collection_name: str

    class Config:
        json_schema_extra = {
            "example": {
                "test_plan_id": "testplan_multiagent_pipeline_abc123",
                "test_plan_title": "System Integration Test Plan",
                "test_cards_generated": 25,
                "test_cards": [
                    {
                        "document_id": "testcard_testplan_abc123_TC-001_xyz789",
                        "document_name": "TC-001 Power Supply Voltage Test",
                        "test_id": "TC-001"
                    }
                ],
                "chromadb_saved": True,
                "collection_name": "test_cards"
            }
        }


class QueryTestCardsRequest(BaseModel):
    """Request to query test cards"""
    test_plan_id: Optional[str] = None
    execution_status: Optional[str] = None  # not_executed, passed, failed, in_progress
    collection_name: str = "test_cards"

    class Config:
        json_schema_extra = {
            "example": {
                "test_plan_id": "testplan_multiagent_pipeline_abc123",
                "execution_status": "not_executed",
                "collection_name": "test_cards"
            }
        }


class QueryTestCardsResponse(BaseModel):
    """Response from test card query"""
    test_cards: List[Dict[str, Any]]
    total_count: int
    filters_applied: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "test_cards": [
                    {
                        "document_id": "testcard_abc123_TC-001_xyz",
                        "document_name": "TC-001 Voltage Test",
                        "test_id": "TC-001",
                        "execution_status": "not_executed",
                        "test_plan_id": "testplan_abc123"
                    }
                ],
                "total_count": 25,
                "filters_applied": {
                    "test_plan_id": "testplan_abc123",
                    "execution_status": "not_executed"
                }
            }
        }


class BulkUpdateTestCardsRequest(BaseModel):
    """Request to bulk update test cards"""
    collection_name: str = "test_cards"
    updates: List[Dict[str, Any]]  # List of {document_id, updates: {...}}

    class Config:
        json_schema_extra = {
            "example": {
                "collection_name": "test_cards",
                "updates": [
                    {
                        "document_id": "testcard_abc123_TC-001_xyz",
                        "updates": {
                            "execution_status": "completed",
                            "passed": "true",
                            "notes": "Test completed successfully"
                        }
                    }
                ]
            }
        }


class BulkUpdateTestCardsResponse(BaseModel):
    """Response from bulk update operation"""
    updated_count: int
    failed_count: int
    errors: List[str]

    class Config:
        json_schema_extra = {
            "example": {
                "updated_count": 5,
                "failed_count": 0,
                "errors": []
            }
        }


class UpdateTestCardExecutionRequest(BaseModel):
    """Request to update test card execution status"""
    execution_status: str  # not_executed, in_progress, passed, failed
    executed_by: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "execution_status": "passed",
                "executed_by": "John Smith",
                "notes": "All criteria met. Test passed successfully."
            }
        }


class UpdateTestCardExecutionResponse(BaseModel):
    """Response from test card execution update"""
    document_id: str
    updated: bool
    message: str
    execution_status: str

    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "testcard_abc123_TC-001_xyz",
                "updated": True,
                "message": "Test card execution status updated successfully",
                "execution_status": "passed"
            }
        }


@doc_gen_api_router.post("/generate-test-cards-from-plan", response_model=GenerateTestCardsFromPlanResponse)
async def generate_test_cards_from_plan(
    req: GenerateTestCardsFromPlanRequest,
    test_card_service: TestCardService = Depends(get_test_card_service)
):
    """
    Generate individual test card documents from a test plan stored in ChromaDB.

    Each test procedure in the test plan becomes a separate test card document
    stored in the 'test_cards' collection with execution tracking metadata.

    Args:
        req: Request with test_plan_id and collection details

    Returns:
        List of generated test cards with document IDs

    Example:
        Test Plan with 10 test procedures → 10 separate test card documents
    """
    try:
        logger.info(f"Generating test cards from test plan: {req.test_plan_id}")
        logger.info(f"Looking in collection: {req.collection_name}")

        # Fetch test plan from ChromaDB via FastAPI vectordb API
        fastapi_url = os.getenv("FASTAPI_URL", "http://localhost:9020")
        response = requests.get(
            f"{fastapi_url}/api/vectordb/documents",
            params={"collection_name": req.collection_name},
            timeout=30
        )

        logger.info(f"ChromaDB response status: {response.status_code}")

        if not response.ok:
            logger.error(f"Failed to fetch from ChromaDB: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to fetch test plan from collection '{req.collection_name}': {response.text}"
            )

        data = response.json()
        ids = data.get("ids", [])
        documents = data.get("documents", [])
        metadatas = data.get("metadatas", [])

        logger.info(f"Found {len(ids)} documents in collection '{req.collection_name}'")
        if len(ids) > 0:
            logger.info(f"Sample document IDs: {ids[:5]}")
            logger.info(f"Looking for document ID: {req.test_plan_id}")

        # Find the test plan document with fallback search
        idx = None

        # Try 1: Exact ID match
        try:
            idx = ids.index(req.test_plan_id)
            logger.info(f"✓ Found test plan by exact ID match at index {idx}")
        except ValueError:
            logger.warning(f"Exact ID match failed for '{req.test_plan_id}'")

            # Try 2: Case-insensitive ID match
            for i, doc_id in enumerate(ids):
                if doc_id.lower() == req.test_plan_id.lower():
                    idx = i
                    logger.info(f"✓ Found test plan by case-insensitive ID match at index {idx}")
                    break

            # Try 3: Partial ID match (useful if UI sends shortened ID)
            if idx is None:
                for i, doc_id in enumerate(ids):
                    if req.test_plan_id in doc_id or doc_id in req.test_plan_id:
                        idx = i
                        logger.info(f"✓ Found test plan by partial ID match: '{doc_id}' at index {idx}")
                        break

            # Try 4: Match by document title in metadata
            if idx is None:
                logger.info("Attempting to find document by title match...")
                for i, metadata in enumerate(metadatas):
                    if metadata:
                        doc_title = metadata.get("title", "").lower()
                        search_term = req.test_plan_id.lower().replace("_", " ")
                        if doc_title and search_term in doc_title:
                            idx = i
                            logger.info(f"✓ Found test plan by title match: '{metadata.get('title')}' at index {idx}")
                            break

        # If still not found, provide helpful error
        if idx is None:
            logger.error(f"Test plan '{req.test_plan_id}' not found in collection '{req.collection_name}'")

            # Build helpful error message with available options
            available_docs = []
            for doc_id, metadata in zip(ids[:10], metadatas[:10]):  # Show first 10
                title = metadata.get("title", "Untitled") if metadata else "Untitled"
                available_docs.append(f"- ID: {doc_id}, Title: {title}")

            available_list = "\n".join(available_docs)

            error_detail = (
                f"Test plan '{req.test_plan_id}' not found in collection '{req.collection_name}'.\n\n"
                f"Available test plans ({len(ids)} total, showing first 10):\n{available_list}\n\n"
                f"Tips:\n"
                f"- Copy the exact Document ID from the 'View Test Plans' tab\n"
                f"- Document IDs are case-sensitive\n"
                f"- Make sure the test plan was successfully saved to ChromaDB"
            )

            logger.error(f"Available document IDs: {ids[:10]}")
            raise HTTPException(
                status_code=404,
                detail=error_detail
            )

        test_plan_content = documents[idx]
        test_plan_metadata = metadatas[idx] or {}
        test_plan_title = test_plan_metadata.get("title", "Test Plan")

        logger.info(f"Found test plan: {test_plan_title}")

        # Generate test card documents
        test_cards = await run_in_threadpool(
            test_card_service.generate_test_cards_from_test_plan,
            test_plan_id=req.test_plan_id,
            test_plan_content=test_plan_content,
            test_plan_title=test_plan_title,
            format=req.format
        )

        if not test_cards:
            raise HTTPException(
                status_code=400,
                detail="No test procedures found in test plan. Unable to generate test cards."
            )

        logger.info(f"Generated {len(test_cards)} test card documents")

        # Save test cards to ChromaDB
        save_result = await run_in_threadpool(
            test_card_service.save_test_cards_to_chromadb,
            test_cards=test_cards,
            collection_name="test_cards"
        )

        # Prepare response
        test_card_summary = [
            {
                "document_id": card["document_id"],
                "document_name": card["document_name"],
                "test_id": card["metadata"]["test_id"],
                "section_title": card["metadata"]["section_title"]
            }
            for card in test_cards
        ]

        logger.info(f"Test cards saved to ChromaDB: {save_result.get('saved', False)}")

        return GenerateTestCardsFromPlanResponse(
            test_plan_id=req.test_plan_id,
            test_plan_title=test_plan_title,
            test_cards_generated=len(test_cards),
            test_cards=test_card_summary,
            chromadb_saved=save_result.get("saved", False),
            collection_name=save_result.get("collection_name", "test_cards")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate test cards from plan: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Test card generation failed: {str(e)}")


# ============================================================================
# TEST CARD GENERATION - ASYNC/BACKGROUND VERSION
# ============================================================================

@doc_gen_api_router.post("/generate-test-cards-from-plan-async")
async def generate_test_cards_from_plan_async(
    req: GenerateTestCardsFromPlanRequest
):
    """
    Start test card generation as a Celery background task (no timeout).
    Returns job_id immediately for progress tracking.

    This endpoint uses Celery for proper distributed task processing,
    ideal for large test plans that may take several minutes to process.
    """
    try:
        logger.info(f"Starting async test card generation for test plan: {req.test_plan_id}")

        # Generate job_id upfront
        job_id = f"testcard_job_{uuid.uuid4().hex[:12]}"

        # Initialize job metadata in Redis
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

        now = datetime.now().isoformat()
        job_meta = {
            "job_id": job_id,
            "test_plan_id": req.test_plan_id,
            "test_plan_title": "",  # Will be updated when plan is loaded
            "collection_name": req.collection_name,
            "format": req.format,
            "status": "queued",
            "created_at": now,
            "last_updated_at": now,
            "progress_message": "Test card generation queued - waiting for Celery worker...",
            "sections_processed": "0",
            "total_sections": "0",
            "test_cards_generated": "0",
            "celery_task_id": ""  # Will be updated when task starts
        }
        redis_client.hset(f"testcard_job:{job_id}:meta", mapping=job_meta)
        redis_client.expire(f"testcard_job:{job_id}:meta", 604800)  # 7 days

        # Submit task to Celery
        celery_task = generate_test_cards_task.apply_async(
            args=[job_id, req.test_plan_id, req.collection_name, req.format],
            task_id=f"celery_{job_id}",  # Use custom task ID for easier tracking
        )

        # Update metadata with Celery task ID
        redis_client.hset(f"testcard_job:{job_id}:meta", "celery_task_id", celery_task.id)

        logger.info(f"Celery task queued: {job_id} (Celery Task ID: {celery_task.id})")

        return {
            "job_id": job_id,
            "test_plan_id": req.test_plan_id,
            "status": "queued",
            "message": "Test card generation started in Celery queue. Use /test-card-generation-status/{job_id} to check progress.",
            "collection_name": req.collection_name,
            "celery_task_id": celery_task.id
        }

    except Exception as e:
        logger.error(f"Failed to start async test card generation: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start job: {str(e)}")


# ============================================================================
# NOTE: Old BackgroundTasks implementation (replaced by Celery)
# The old function _run_test_card_generation_background has been removed
# in favor of the Celery-based approach using tasks/test_card_tasks.py
# ============================================================================


@doc_gen_api_router.get("/list-test-card-jobs")
async def list_test_card_jobs(limit: int = 50):
    """List all active and recent test card generation jobs"""
    try:
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

        # Get all test card job metadata keys
        job_keys = redis_client.keys("testcard_job:*:meta")

        jobs = []
        for key in job_keys[:limit]:
            # Extract job_id from key (format: testcard_job:JOB_ID:meta)
            job_id = key.replace("testcard_job:", "").replace(":meta", "")

            # Get metadata
            meta = redis_client.hgetall(key)

            if meta:
                # Check if result exists
                result_exists = redis_client.exists(f"testcard_job:{job_id}:result")

                jobs.append({
                    "job_id": job_id,
                    "status": meta.get("status", "unknown"),
                    "test_plan_id": meta.get("test_plan_id", ""),
                    "test_plan_title": meta.get("test_plan_title", "Untitled"),
                    "created_at": meta.get("created_at", ""),
                    "progress_message": meta.get("progress_message", ""),
                    "test_cards_generated": meta.get("test_cards_generated", "0"),
                    "result_available": bool(result_exists)
                })

        # Sort by created_at descending (most recent first)
        jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return {
            "jobs": jobs,
            "total": len(jobs)
        }

    except Exception as e:
        logger.error(f"Error listing test card jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@doc_gen_api_router.get("/test-card-generation-status/{job_id}")
async def get_test_card_generation_status(job_id: str):
    """Get the status of a test card generation job"""
    try:
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

        # Get metadata
        meta = redis_client.hgetall(f"testcard_job:{job_id}:meta")

        if not meta:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found or expired")

        # Build progress info
        progress_info = {
            "job_id": job_id,
            "test_plan_id": meta.get("test_plan_id", ""),
            "test_plan_title": meta.get("test_plan_title", ""),
            "status": meta.get("status", "unknown"),
            "created_at": meta.get("created_at", ""),
            "progress_message": meta.get("progress_message", ""),
            "sections_processed": meta.get("sections_processed", "0"),
            "total_sections": meta.get("total_sections", "0"),
            "test_cards_generated": meta.get("test_cards_generated", "0")
        }

        # If failed, include error
        if meta.get("status", "").lower() == "failed":
            progress_info["error"] = meta.get("error", "Unknown error")

        # If completed, check if result is available
        if meta.get("status", "").lower() == "completed":
            result_exists = redis_client.exists(f"testcard_job:{job_id}:result")
            progress_info["result_available"] = bool(result_exists)
            progress_info["completed_at"] = meta.get("completed_at", "")

        return progress_info

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking status for {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@doc_gen_api_router.get("/test-card-generation-result/{job_id}")
async def get_test_card_generation_result(job_id: str):
    """Get the completed result from a test card generation job"""
    try:
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

        # Check status first
        meta = redis_client.hgetall(f"testcard_job:{job_id}:meta")

        if not meta:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found or expired")

        status = meta.get("status", "").lower()

        if status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Job is not completed yet. Current status: {status}. Use /test-card-generation-status/{job_id} to check progress."
            )

        # Get result
        result = redis_client.hgetall(f"testcard_job:{job_id}:result")

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Result for job {job_id} not found. It may have expired."
            )

        # Parse test cards JSON
        test_cards_json = result.get("test_cards", "[]")
        test_cards = json.loads(test_cards_json)

        return {
            "test_plan_id": result.get("test_plan_id", ""),
            "test_plan_title": result.get("test_plan_title", ""),
            "test_cards_generated": int(result.get("test_cards_generated", 0)),
            "test_cards": test_cards,
            "chromadb_saved": result.get("chromadb_saved", "false").lower() == "true",
            "collection_name": result.get("collection_name", "test_cards")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving result for {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@doc_gen_api_router.post("/query-test-cards", response_model=QueryTestCardsResponse)
async def query_test_cards(req: QueryTestCardsRequest):
    """
    Query test card documents by test_plan_id, execution_status, or other filters.

    Args:
        req: Query parameters (test_plan_id, execution_status, etc.)

    Returns:
        List of test cards matching the filters

    Example:
        Get all test cards for a test plan:
        {"test_plan_id": "testplan_abc123"}

        Get all failed test cards:
        {"execution_status": "failed"}
    """
    try:
        logger.info(f"Querying test cards with filters: test_plan_id={req.test_plan_id}, "
                   f"execution_status={req.execution_status}")

        # Fetch test cards from ChromaDB via FastAPI vectordb API
        # Use ChromaDB client directly for better performance with filters
        from integrations.chromadb_client import get_chroma_client
        chroma_client = get_chroma_client()

        try:
            collection = chroma_client.get_collection(name=req.collection_name)
        except Exception as e:
            logger.info(f"Collection '{req.collection_name}' not found: {e}")
            return QueryTestCardsResponse(
                test_cards=[],
                total_count=0,
                filters_applied={"test_plan_id": req.test_plan_id, "execution_status": req.execution_status}
            )

        # Build ChromaDB where clause for efficient filtering
        where = {}
        if req.test_plan_id:
            where["test_plan_id"] = req.test_plan_id
        if req.execution_status:
            where["execution_status"] = req.execution_status

        # Query ChromaDB with filters (much faster than fetching all and filtering)
        if where:
            result = collection.get(
                where=where,
                limit=1000,  # Reasonable limit
                include=["documents", "metadatas"]
            )
        else:
            # If no filters, get recent test cards only
            result = collection.get(
                limit=100,  # Default limit when no filters
                include=["documents", "metadatas"]
            )

        ids = result.get("ids", [])
        documents = result.get("documents", [])
        metadatas = result.get("metadatas", [])

        # Build response from ChromaDB results (already filtered)
        filtered_cards = []
        for doc_id, content, metadata in zip(ids, documents, metadatas):
            metadata = metadata or {}

            # Build test card object
            filtered_cards.append({
                "document_id": doc_id,
                "document_name": metadata.get("document_name", ""),
                "test_id": metadata.get("test_id", ""),
                "test_plan_id": metadata.get("test_plan_id", ""),
                "test_plan_title": metadata.get("test_plan_title", ""),
                "section_title": metadata.get("section_title", ""),
                "requirement_id": metadata.get("requirement_id", ""),
                "requirement_text": metadata.get("requirement_text", ""),
                "execution_status": metadata.get("execution_status", "not_executed"),
                "executed_by": metadata.get("executed_by", ""),
                "passed": metadata.get("passed", False),
                "failed": metadata.get("failed", False),
                "notes": metadata.get("notes", ""),
                "content_preview": content[:200] + "..." if len(content) > 200 else content,
                "content": content  # Include full content for editing
            })

        logger.info(f"Found {len(filtered_cards)} test cards matching filters")

        return QueryTestCardsResponse(
            test_cards=filtered_cards,
            total_count=len(filtered_cards),
            filters_applied={
                "test_plan_id": req.test_plan_id,
                "execution_status": req.execution_status,
                "collection_name": req.collection_name
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to query test cards: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@doc_gen_api_router.get("/test-cards/{card_id}")
async def get_test_card(card_id: str, collection_name: str = "test_cards"):
    """
    Retrieve a single test card by document ID.

    Args:
        card_id: Test card document ID
        collection_name: ChromaDB collection name (default: test_cards)

    Returns:
        Complete test card document with all metadata and content
    """
    try:
        logger.info(f"Retrieving test card: {card_id}")

        # Fetch from ChromaDB via FastAPI vectordb API
        fastapi_url = os.getenv("FASTAPI_URL", "http://localhost:9020")
        response = requests.get(
            f"{fastapi_url}/api/vectordb/documents",
            params={"collection_name": collection_name},
            timeout=30
        )

        if not response.ok:
            logger.error(f"Failed to fetch test cards: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to fetch test cards: {response.text}"
            )

        data = response.json()
        ids = data.get("ids", [])
        documents = data.get("documents", [])
        metadatas = data.get("metadatas", [])

        # Find the test card
        try:
            idx = ids.index(card_id)
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail=f"Test card '{card_id}' not found in collection '{collection_name}'"
            )

        content = documents[idx]
        metadata = metadatas[idx] or {}

        return {
            "document_id": card_id,
            "document_name": metadata.get("document_name", ""),
            "content": content,
            "metadata": metadata,
            "test_id": metadata.get("test_id", ""),
            "test_plan_id": metadata.get("test_plan_id", ""),
            "test_plan_title": metadata.get("test_plan_title", ""),
            "section_title": metadata.get("section_title", ""),
            "execution_status": metadata.get("execution_status", "not_executed"),
            "executed_by": metadata.get("executed_by", ""),
            "passed": metadata.get("passed", False),
            "failed": metadata.get("failed", False),
            "notes": metadata.get("notes", "")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve test card: {e}")
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")


@doc_gen_api_router.put("/test-cards/{card_id}/execute", response_model=UpdateTestCardExecutionResponse)
async def update_test_card_execution(
    card_id: str,
    req: UpdateTestCardExecutionRequest,
    collection_name: str = "test_cards"
):
    """
    Update test card execution status and tracking information.

    Supports marking test cards as:
    - not_executed
    - in_progress
    - passed
    - failed

    Args:
        card_id: Test card document ID
        req: Execution update details (status, executed_by, notes)
        collection_name: ChromaDB collection name (default: test_cards)

    Returns:
        Updated test card status
    """
    try:
        logger.info(f"Updating test card execution: {card_id} → {req.execution_status}")

        # Validate execution_status
        valid_statuses = ["not_executed", "in_progress", "passed", "failed"]
        if req.execution_status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid execution_status. Must be one of: {', '.join(valid_statuses)}"
            )

        # Fetch current test card via FastAPI vectordb API
        fastapi_url = os.getenv("FASTAPI_URL", "http://localhost:9020")
        response = requests.get(
            f"{fastapi_url}/api/vectordb/documents",
            params={"collection_name": collection_name},
            timeout=30
        )

        if not response.ok:
            logger.error(f"Failed to fetch test cards: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to fetch test cards: {response.text}"
            )

        data = response.json()
        ids = data.get("ids", [])
        documents = data.get("documents", [])
        metadatas = data.get("metadatas", [])

        # Find the test card
        try:
            idx = ids.index(card_id)
        except ValueError:
            raise HTTPException(
                status_code=404,
                detail=f"Test card '{card_id}' not found in collection '{collection_name}'"
            )

        # Update metadata
        current_metadata = metadatas[idx] or {}
        updated_metadata = current_metadata.copy()

        updated_metadata["execution_status"] = req.execution_status
        updated_metadata["passed"] = req.execution_status == "passed"
        updated_metadata["failed"] = req.execution_status == "failed"

        if req.executed_by:
            updated_metadata["executed_by"] = req.executed_by

        if req.notes:
            updated_metadata["notes"] = req.notes

        updated_metadata["last_updated"] = datetime.now().isoformat()

        # Update in ChromaDB via FastAPI vectordb API
        update_payload = {
            "collection_name": collection_name,
            "ids": [card_id],
            "metadatas": [updated_metadata]
        }

        update_response = requests.post(
            f"{fastapi_url}/api/vectordb/documents/update",
            json=update_payload,
            timeout=30
        )

        if not update_response.ok:
            logger.error(f"Failed to update test card: {update_response.status_code} - {update_response.text}")
            raise HTTPException(
                status_code=update_response.status_code,
                detail=f"Failed to update test card: {update_response.text}"
            )

        logger.info(f"Test card {card_id} updated successfully")

        return UpdateTestCardExecutionResponse(
            document_id=card_id,
            updated=True,
            message=f"Test card execution status updated to '{req.execution_status}'",
            execution_status=req.execution_status
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update test card execution: {e}")
        raise HTTPException(status_code=500, detail=f"Update failed: {str(e)}")

@doc_gen_api_router.post("/test-cards/export-docx")
async def export_test_cards_to_docx(req: QueryTestCardsRequest):
    """
    Export test cards to a DOCX file.
    Filters test cards by test_plan_id and exports them to a downloadable Word document.

    Args:
        req: Query parameters (test_plan_id, execution_status, collection_name)

    Returns:
        Word document as downloadable file
    """
    from fastapi.responses import Response
    
    try:
        logger.info(f"Exporting test cards to DOCX for test_plan_id={req.test_plan_id}")

        # Query test cards (reuse query logic)
        from integrations.chromadb_client import get_chroma_client
        chroma_client = get_chroma_client()

        try:
            collection = chroma_client.get_collection(name=req.collection_name)
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Collection not found: {e}")

        # Build where clause
        where = {}
        if req.test_plan_id:
            where["test_plan_id"] = req.test_plan_id
        if req.execution_status:
            where["execution_status"] = req.execution_status

        # Query ChromaDB
        if where:
            result = collection.get(
                where=where,
                limit=1000,
                include=["documents", "metadatas"]
            )
        else:
            result = collection.get(
                limit=100,
                include=["documents", "metadatas"]
            )

        ids = result.get("ids", [])
        documents = result.get("documents", [])
        metadatas = result.get("metadatas", [])

        if not ids:
            raise HTTPException(status_code=404, detail="No test cards found matching filters")

        # Build test cards list for export
        test_cards = []
        for doc_id, content, metadata in zip(ids, documents, metadatas):
            test_cards.append({
                "document_id": doc_id,
                "content": content,
                "metadata": metadata or {}
            })

        # Get test plan title
        test_plan_title = metadatas[0].get("test_plan_title", "Test Plan") if metadatas else "Test Plan"

        # Export to DOCX
        word_export_service = WordExportService()
        docx_bytes = word_export_service.export_test_cards_to_word(test_cards, test_plan_title)

        # Create filename
        plan_id_safe = req.test_plan_id or "all"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test_cards_{plan_id_safe}_{timestamp}.docx"

        logger.info(f"Exported {len(test_cards)} test cards to DOCX: {filename}")

        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f"attachment; filename=\"{filename}\""
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export test cards to DOCX: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@doc_gen_api_router.post("/test-cards/export-markdown")
async def export_test_cards_to_markdown(req: QueryTestCardsRequest):
    """
    Export test cards to a Markdown file.
    Filters test cards by test_plan_id and exports them to a downloadable Markdown document.

    Args:
        req: Query parameters (test_plan_id, execution_status, collection_name)

    Returns:
        Markdown document as downloadable file
    """
    from fastapi.responses import Response

    try:
        logger.info(f"Exporting test cards to Markdown for test_plan_id={req.test_plan_id}")

        # Query test cards (reuse query logic)
        from integrations.chromadb_client import get_chroma_client
        chroma_client = get_chroma_client()

        try:
            collection = chroma_client.get_collection(name=req.collection_name)
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Collection not found: {e}")

        # Build where clause
        where = {}
        if req.test_plan_id:
            where["test_plan_id"] = req.test_plan_id
        if req.execution_status:
            where["execution_status"] = req.execution_status

        # Query ChromaDB
        if where:
            result = collection.get(
                where=where,
                limit=1000,
                include=["documents", "metadatas"]
            )
        else:
            result = collection.get(
                limit=100,
                include=["documents", "metadatas"]
            )

        ids = result.get("ids", [])
        documents = result.get("documents", [])
        metadatas = result.get("metadatas", [])

        if not ids:
            raise HTTPException(status_code=404, detail="No test cards found matching filters")

        # Get test plan title
        test_plan_title = metadatas[0].get("test_plan_title", "Test Plan") if metadatas else "Test Plan"

        # Build markdown content
        markdown_content = f"# {test_plan_title} - Test Cards\n\n"
        markdown_content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        markdown_content += f"Total Test Cards: {len(ids)}\n\n"
        markdown_content += "---\n\n"

        # Group by section if available
        sections = {}
        for doc_id, content, metadata in zip(ids, documents, metadatas):
            section_title = metadata.get("section_title", "Uncategorized")
            if section_title not in sections:
                sections[section_title] = []

            sections[section_title].append({
                "test_id": metadata.get("test_id", ""),
                "requirement_text": metadata.get("requirement_text", ""),
                "content": content,
                "execution_status": metadata.get("execution_status", "not_executed"),
                "passed": metadata.get("passed", False),
                "failed": metadata.get("failed", False),
                "notes": metadata.get("notes", "")
            })

        # Write sections
        for section_title, cards in sections.items():
            markdown_content += f"## {section_title}\n\n"

            for card in cards:
                markdown_content += f"### Test Card: {card['test_id']}\n\n"
                markdown_content += f"**Requirement:** {card['requirement_text']}\n\n"
                markdown_content += f"**Status:** {card['execution_status']}\n\n"

                if card['content']:
                    markdown_content += f"{card['content']}\n\n"

                if card['notes']:
                    markdown_content += f"**Notes:** {card['notes']}\n\n"

                markdown_content += "---\n\n"

        # Create filename
        plan_id_safe = req.test_plan_id or "all"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test_cards_{plan_id_safe}_{timestamp}.md"

        logger.info(f"Exported {len(ids)} test cards to Markdown: {filename}")

        return Response(
            content=markdown_content.encode('utf-8'),
            media_type="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename=\"{filename}\""
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export test cards to Markdown: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@doc_gen_api_router.post("/test-cards/bulk-update", response_model=BulkUpdateTestCardsResponse)
async def bulk_update_test_cards(req: BulkUpdateTestCardsRequest):
    """
    Bulk update test cards in ChromaDB.
    Accepts a list of updates with document IDs and metadata changes.
    """
    try:
        logger.info(f"Bulk updating {len(req.updates)} test cards in collection: {req.collection_name}")

        from integrations.chromadb_client import get_chroma_client
        chroma_client = get_chroma_client()
        collection = chroma_client.get_collection(name=req.collection_name)

        updated_count = 0
        failed_count = 0
        errors = []

        for update_item in req.updates:
            document_id = update_item.get("document_id")
            updates = update_item.get("updates", {})

            if not document_id:
                failed_count += 1
                errors.append("Missing document_id in update item")
                continue

            try:
                # Get existing document and metadata
                existing = collection.get(ids=[document_id], include=["documents", "metadatas"])

                if not existing["ids"]:
                    failed_count += 1
                    errors.append(f"Document not found: {document_id}")
                    continue

                # Separate content updates from metadata updates
                content_update = updates.pop("content", None)

                # Merge existing metadata with updates
                existing_metadata = existing["metadatas"][0] if existing["metadatas"] else {}
                updated_metadata = {**existing_metadata, **updates}

                # Build update parameters
                update_params = {
                    "ids": [document_id],
                    "metadatas": [updated_metadata]
                }

                # If content (test procedures) is being updated, include it
                if content_update is not None:
                    update_params["documents"] = [content_update]

                # Update the document in ChromaDB
                collection.update(**update_params)

                updated_count += 1
                logger.debug(f"Updated test card: {document_id}")

            except Exception as e:
                failed_count += 1
                error_msg = f"Failed to update {document_id}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

        logger.info(f"Bulk update complete: {updated_count} updated, {failed_count} failed")

        return BulkUpdateTestCardsResponse(
            updated_count=updated_count,
            failed_count=failed_count,
            errors=errors
        )

    except Exception as e:
        logger.error(f"Bulk update failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Bulk update failed: {str(e)}")

