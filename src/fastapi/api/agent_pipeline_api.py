# api/agent_pipeline_api.py
"""
Agent Pipeline API - REST endpoints for running agent set pipelines on direct text input.

This API provides endpoints for:
- Running agent pipelines synchronously
- Running agent pipelines asynchronously (background tasks)
- Checking pipeline status
- Retrieving pipeline results
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool
import logging
import uuid
import redis
import os
from datetime import datetime
import json

from core.dependencies import get_db, get_chat_repository
from services.agent_pipeline_service import AgentPipelineService, PipelineResult
from repositories.agent_set_repository import AgentSetRepository
from repositories.chat_repository import ChatRepository

logger = logging.getLogger("AGENT_PIPELINE_API")

agent_pipeline_router = APIRouter(prefix="/agent-pipeline", tags=["agent-pipeline"])

# Lazy initialization of service
_agent_pipeline_service: Optional[AgentPipelineService] = None


def get_agent_pipeline_service() -> AgentPipelineService:
    """Get or create the agent pipeline service instance"""
    global _agent_pipeline_service
    if _agent_pipeline_service is None:
        _agent_pipeline_service = AgentPipelineService()
    return _agent_pipeline_service


# ============================================================================
# Request/Response Models
# ============================================================================

class RunPipelineRequest(BaseModel):
    """Request model for running an agent pipeline"""
    text_input: str = Field(..., description="The text content to process through the pipeline")
    agent_set_id: int = Field(..., description="ID of the agent set to use")
    title: str = Field(default="Agent Pipeline Result", description="Title for the pipeline result")
    section_mode: str = Field(
        default="auto",
        description="How to split the text: 'auto' (detect sections), 'single' (one section), 'manual' (use manual_sections)"
    )
    manual_sections: Optional[Dict[str, str]] = Field(
        default=None,
        description="Manual section mapping (title -> content) when section_mode='manual'"
    )
    # RAG parameters
    use_rag: bool = Field(default=False, description="Enable RAG context retrieval from ChromaDB")
    rag_collection: Optional[str] = Field(default=None, description="ChromaDB collection name for RAG")
    rag_document_id: Optional[str] = Field(default=None, description="Optional specific document ID to filter RAG results")
    rag_top_k: int = Field(default=5, description="Number of top documents to retrieve for RAG context")


class PipelineStatusResponse(BaseModel):
    """Response model for pipeline status"""
    pipeline_id: str
    status: str
    title: str
    agent_set_name: str
    total_sections: int
    progress: int
    progress_message: str
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None


class AgentResultResponse(BaseModel):
    """Response model for individual agent results"""
    agent_id: int
    agent_name: str
    agent_type: str
    model_name: str
    section_title: str
    output: str
    processing_time: float
    success: bool
    error: Optional[str] = None


class StageResultResponse(BaseModel):
    """Response model for stage results"""
    stage_name: str
    execution_mode: str
    agent_results: List[AgentResultResponse]
    combined_output: str
    processing_time: float


class SectionResultResponse(BaseModel):
    """Response model for section results"""
    section_title: str
    section_content_preview: str
    stage_results: List[StageResultResponse]
    final_output: str
    processing_time: float


class PipelineResultResponse(BaseModel):
    """Response model for complete pipeline results"""
    pipeline_id: str
    title: str
    input_text_preview: str
    total_sections: int
    total_stages_executed: int
    total_agents_executed: int
    section_results: List[SectionResultResponse]
    consolidated_output: str
    processing_status: str
    processing_time: float
    agent_set_name: str
    agent_set_id: int
    rag_context_used: bool = False
    rag_collection: Optional[str] = None
    formatted_citations: str = ""  # Formatted citations for explainability when RAG is used
    created_at: str


# ============================================================================
# Helper Functions
# ============================================================================

def _convert_pipeline_result_to_response(result: PipelineResult) -> PipelineResultResponse:
    """Convert internal PipelineResult to API response model"""
    section_responses = []
    for section in result.section_results:
        stage_responses = []
        for stage in section.stage_results:
            agent_responses = [
                AgentResultResponse(
                    agent_id=ar.agent_id,
                    agent_name=ar.agent_name,
                    agent_type=ar.agent_type,
                    model_name=ar.model_name,
                    section_title=ar.section_title,
                    output=ar.output,
                    processing_time=ar.processing_time,
                    success=ar.success,
                    error=ar.error
                )
                for ar in stage.agent_results
            ]
            stage_responses.append(StageResultResponse(
                stage_name=stage.stage_name,
                execution_mode=stage.execution_mode,
                agent_results=agent_responses,
                combined_output=stage.combined_output,
                processing_time=stage.processing_time
            ))
        section_responses.append(SectionResultResponse(
            section_title=section.section_title,
            section_content_preview=section.section_content[:200] + "..." if len(section.section_content) > 200 else section.section_content,
            stage_results=stage_responses,
            final_output=section.final_output,
            processing_time=section.processing_time
        ))

    return PipelineResultResponse(
        pipeline_id=result.pipeline_id,
        title=result.title,
        input_text_preview=result.input_text_preview,
        total_sections=result.total_sections,
        total_stages_executed=result.total_stages_executed,
        total_agents_executed=result.total_agents_executed,
        section_results=section_responses,
        consolidated_output=result.consolidated_output,
        processing_status=result.processing_status,
        processing_time=result.processing_time,
        agent_set_name=result.agent_set_name,
        agent_set_id=result.agent_set_id,
        rag_context_used=result.rag_context_used,
        rag_collection=result.rag_collection,
        formatted_citations=result.formatted_citations,
        created_at=result.created_at
    )


def _run_pipeline_background(
    text_input: str,
    agent_set_id: int,
    title: str,
    section_mode: str,
    manual_sections: Optional[Dict[str, str]],
    pipeline_id: str,
    use_rag: bool = False,
    rag_collection: Optional[str] = None,
    rag_document_id: Optional[str] = None,
    rag_top_k: int = 5,
    agent_set_name: str = ""
):
    """Background task for running the pipeline"""
    try:
        logger.info(f"Background pipeline started: {pipeline_id}")
        logger.info(f"RAG enabled: {use_rag}, Collection: {rag_collection}")

        service = get_agent_pipeline_service()
        result = service.run_pipeline(
            text_input=text_input,
            agent_set_id=agent_set_id,
            title=title,
            section_mode=section_mode,
            manual_sections=manual_sections,
            pipeline_id=pipeline_id,
            use_rag=use_rag,
            rag_collection=rag_collection,
            rag_document_id=rag_document_id,
            rag_top_k=rag_top_k
        )

        # Save result to Redis for retrieval
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

        # Serialize result for storage
        result_data = {
            "pipeline_id": result.pipeline_id,
            "title": result.title,
            "input_text_preview": result.input_text_preview,
            "total_sections": str(result.total_sections),
            "total_stages_executed": str(result.total_stages_executed),
            "total_agents_executed": str(result.total_agents_executed),
            "consolidated_output": result.consolidated_output,
            "processing_status": result.processing_status,
            "processing_time": str(result.processing_time),
            "agent_set_name": result.agent_set_name,
            "agent_set_id": str(result.agent_set_id),
            "rag_context_used": str(result.rag_context_used),
            "rag_collection": result.rag_collection or "",
            "formatted_citations": result.formatted_citations or "",
            "created_at": result.created_at,
            # Store full section results as JSON
            "section_results_json": json.dumps([
                {
                    "section_title": sr.section_title,
                    "section_content": sr.section_content,
                    "final_output": sr.final_output,
                    "processing_time": sr.processing_time,
                    "stage_results": [
                        {
                            "stage_name": st.stage_name,
                            "execution_mode": st.execution_mode,
                            "combined_output": st.combined_output,
                            "processing_time": st.processing_time,
                            "agent_results": [
                                {
                                    "agent_id": ar.agent_id,
                                    "agent_name": ar.agent_name,
                                    "agent_type": ar.agent_type,
                                    "model_name": ar.model_name,
                                    "section_title": ar.section_title,
                                    "output": ar.output,
                                    "processing_time": ar.processing_time,
                                    "success": ar.success,
                                    "error": ar.error
                                }
                                for ar in st.agent_results
                            ]
                        }
                        for st in sr.stage_results
                    ]
                }
                for sr in result.section_results
            ])
        }

        # Save result atomically
        pipe = redis_client.pipeline()
        pipe.hset(f"agent_pipeline:{pipeline_id}:result", mapping=result_data)
        pipe.expire(f"agent_pipeline:{pipeline_id}:result", 604800)  # 7 days

        # Update status
        pipe.hset(f"agent_pipeline:{pipeline_id}:meta", mapping={
            "status": result.processing_status,
            "completed_at": datetime.now().isoformat(),
            "progress": "100",
            "progress_message": "Pipeline completed"
        })
        pipe.execute()

        # Save to chat history for persistence
        try:
            from core.dependencies import get_db_context
            from models.chat import ChatHistory

            with get_db_context() as db:
                session_id = f"agent_pipeline_{pipeline_id}"
                chat_entry = ChatHistory(
                    user_query=text_input[:1000] + ("..." if len(text_input) > 1000 else ""),
                    response=result.consolidated_output,
                    model_used=f"agent_set:{agent_set_name or result.agent_set_name}",
                    collection_name=rag_collection if use_rag else None,
                    query_type="agent_pipeline",
                    response_time_ms=int(result.processing_time * 1000),
                    session_id=session_id
                )
                db.add(chat_entry)
                db.commit()
                logger.info(f"Chat history saved for background pipeline {pipeline_id}")
        except Exception as chat_error:
            logger.warning(f"Failed to save chat history for background pipeline: {chat_error}")
            # Don't fail the pipeline if chat history save fails

        logger.info(f"Background pipeline completed: {pipeline_id}")
        return result

    except Exception as e:
        logger.error(f"Background pipeline failed: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

        # Mark as failed
        try:
            redis_host = os.getenv("REDIS_HOST", "redis")
            redis_port = int(os.getenv("REDIS_PORT", 6379))
            redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

            redis_client.hset(f"agent_pipeline:{pipeline_id}:meta", mapping={
                "status": "FAILED",
                "error": str(e),
                "failed_at": datetime.now().isoformat(),
                "progress_message": f"Pipeline failed: {str(e)}"
            })
        except Exception as redis_error:
            logger.error(f"Failed to update Redis with error status: {redis_error}")

        raise


# ============================================================================
# API Endpoints
# ============================================================================

@agent_pipeline_router.post("/run", response_model=PipelineResultResponse)
async def run_pipeline(
    req: RunPipelineRequest,
    db: Session = Depends(get_db),
    chat_repo: ChatRepository = Depends(get_chat_repository)
):
    """
    Run an agent pipeline synchronously on provided text.

    This endpoint will block until the pipeline completes.
    For long-running pipelines, use /run-async instead.
    """
    logger.info(f"Received /run request - Agent Set ID: {req.agent_set_id}")

    # Validate text input
    if not req.text_input or len(req.text_input.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="text_input is required and must be at least 10 characters"
        )

    # Validate agent set exists and is active
    agent_set_repo = AgentSetRepository()
    agent_set = agent_set_repo.get_by_id(req.agent_set_id, db)

    if not agent_set:
        raise HTTPException(
            status_code=404,
            detail=f"Agent set with ID {req.agent_set_id} not found"
        )

    if not agent_set.is_active:
        raise HTTPException(
            status_code=400,
            detail=f"Agent set '{agent_set.name}' (ID: {req.agent_set_id}) is inactive"
        )

    logger.info(f"Using agent set: {agent_set.name}")
    logger.info(f"RAG enabled: {req.use_rag}, Collection: {req.rag_collection}")

    # Validate RAG parameters
    if req.use_rag and not req.rag_collection:
        raise HTTPException(
            status_code=400,
            detail="rag_collection is required when use_rag is enabled"
        )

    try:
        service = get_agent_pipeline_service()
        result = await run_in_threadpool(
            service.run_pipeline,
            req.text_input,
            req.agent_set_id,
            req.title,
            req.section_mode,
            req.manual_sections,
            None,  # pipeline_id
            req.use_rag,
            req.rag_collection,
            req.rag_document_id,
            req.rag_top_k
        )

        # Increment usage count
        agent_set_repo.increment_usage_count(req.agent_set_id, db)

        # Save to chat history for persistence
        try:
            session_id = f"agent_pipeline_{result.pipeline_id}"
            chat_repo.create_chat_entry(
                user_query=req.text_input[:1000] + ("..." if len(req.text_input) > 1000 else ""),
                response=result.consolidated_output,
                model_used=f"agent_set:{agent_set.name}",
                collection_name=req.rag_collection if req.use_rag else None,
                query_type="agent_pipeline",
                response_time_ms=int(result.processing_time * 1000),
                session_id=session_id
            )
            db.commit()
            logger.info(f"Chat history saved for pipeline {result.pipeline_id}")
        except Exception as chat_error:
            logger.warning(f"Failed to save chat history for pipeline: {chat_error}")
            # Don't fail the request if chat history save fails

        return _convert_pipeline_result_to_response(result)

    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {str(e)}")


@agent_pipeline_router.post("/run-async")
async def run_pipeline_async(
    req: RunPipelineRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Start an agent pipeline as a background task.

    Returns a pipeline_id immediately for progress tracking.
    Use /status/{pipeline_id} to check progress.
    Use /result/{pipeline_id} to retrieve the completed result.
    """
    logger.info(f"Received /run-async request - Agent Set ID: {req.agent_set_id}")

    # Validate text input
    if not req.text_input or len(req.text_input.strip()) < 10:
        raise HTTPException(
            status_code=400,
            detail="text_input is required and must be at least 10 characters"
        )

    # Validate agent set exists and is active
    agent_set_repo = AgentSetRepository()
    agent_set = agent_set_repo.get_by_id(req.agent_set_id, db)

    if not agent_set:
        raise HTTPException(
            status_code=404,
            detail=f"Agent set with ID {req.agent_set_id} not found"
        )

    if not agent_set.is_active:
        raise HTTPException(
            status_code=400,
            detail=f"Agent set '{agent_set.name}' (ID: {req.agent_set_id}) is inactive"
        )

    # Validate RAG parameters
    if req.use_rag and not req.rag_collection:
        raise HTTPException(
            status_code=400,
            detail="rag_collection is required when use_rag is enabled"
        )

    # Generate pipeline ID upfront
    pipeline_id = f"agent_pipeline_{uuid.uuid4().hex[:12]}"

    # Initialize pipeline in Redis
    try:
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

        redis_client.hset(f"agent_pipeline:{pipeline_id}:meta", mapping={
            "status": "QUEUED",
            "title": req.title,
            "agent_set_name": agent_set.name,
            "agent_set_id": str(req.agent_set_id),
            "use_rag": str(req.use_rag),
            "rag_collection": req.rag_collection or "",
            "created_at": datetime.now().isoformat(),
            "progress": "0",
            "progress_message": "Pipeline queued for processing..."
        })
        redis_client.expire(f"agent_pipeline:{pipeline_id}:meta", 604800)  # 7 days
    except Exception as e:
        logger.warning(f"Failed to initialize pipeline in Redis: {e}")

    # Add background task
    background_tasks.add_task(
        _run_pipeline_background,
        req.text_input,
        req.agent_set_id,
        req.title,
        req.section_mode,
        req.manual_sections,
        pipeline_id,
        req.use_rag,
        req.rag_collection,
        req.rag_document_id,
        req.rag_top_k,
        agent_set.name
    )

    # Increment usage count
    agent_set_repo.increment_usage_count(req.agent_set_id, db)

    logger.info(f"Pipeline {pipeline_id} queued for background processing")

    return {
        "pipeline_id": pipeline_id,
        "status": "QUEUED",
        "message": f"Pipeline started. Use /agent-pipeline/status/{pipeline_id} to check progress."
    }


@agent_pipeline_router.get("/status/{pipeline_id}", response_model=PipelineStatusResponse)
async def get_pipeline_status(pipeline_id: str):
    """Get the current status of a pipeline"""
    service = get_agent_pipeline_service()
    status = service.get_pipeline_status(pipeline_id)

    if not status:
        raise HTTPException(
            status_code=404,
            detail=f"Pipeline {pipeline_id} not found"
        )

    return PipelineStatusResponse(**status)


@agent_pipeline_router.get("/result/{pipeline_id}")
async def get_pipeline_result(pipeline_id: str):
    """Get the completed result of a pipeline"""
    try:
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

        # Check status first
        meta = redis_client.hgetall(f"agent_pipeline:{pipeline_id}:meta")
        if not meta:
            raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id} not found")

        status = meta.get("status", "UNKNOWN")
        if status == "QUEUED" or status == "PROCESSING":
            return {
                "pipeline_id": pipeline_id,
                "status": status,
                "message": "Pipeline is still processing. Check back later.",
                "progress": int(meta.get("progress", 0)),
                "progress_message": meta.get("progress_message", "")
            }

        if status == "FAILED":
            return {
                "pipeline_id": pipeline_id,
                "status": "FAILED",
                "error": meta.get("error", "Unknown error")
            }

        # Get result
        result = redis_client.hgetall(f"agent_pipeline:{pipeline_id}:result")
        if not result:
            raise HTTPException(status_code=404, detail=f"Pipeline result not found for {pipeline_id}")

        # Parse section results from JSON
        section_results_json = result.get("section_results_json", "[]")
        section_results = json.loads(section_results_json)

        return {
            "pipeline_id": result.get("pipeline_id", pipeline_id),
            "title": result.get("title", ""),
            "input_text_preview": result.get("input_text_preview", ""),
            "total_sections": int(result.get("total_sections", 0)),
            "total_stages_executed": int(result.get("total_stages_executed", 0)),
            "total_agents_executed": int(result.get("total_agents_executed", 0)),
            "section_results": section_results,
            "consolidated_output": result.get("consolidated_output", ""),
            "processing_status": result.get("processing_status", "COMPLETED"),
            "processing_time": float(result.get("processing_time", 0)),
            "agent_set_name": result.get("agent_set_name", ""),
            "agent_set_id": int(result.get("agent_set_id", 0)),
            "rag_context_used": result.get("rag_context_used", "False") == "True",
            "rag_collection": result.get("rag_collection", "") or None,
            "formatted_citations": result.get("formatted_citations", ""),
            "created_at": result.get("created_at", "")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pipeline result: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get pipeline result: {str(e)}")


@agent_pipeline_router.get("/list")
async def list_pipelines(limit: int = 20):
    """List recent pipelines"""
    try:
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

        # Scan for pipeline keys
        pipelines = []
        cursor = 0
        pattern = "agent_pipeline:*:meta"

        while True:
            cursor, keys = redis_client.scan(cursor, match=pattern, count=100)
            for key in keys:
                pipeline_id = key.split(":")[1]
                meta = redis_client.hgetall(key)
                if meta:
                    pipelines.append({
                        "pipeline_id": pipeline_id,
                        "status": meta.get("status", "UNKNOWN"),
                        "title": meta.get("title", ""),
                        "agent_set_name": meta.get("agent_set_name", ""),
                        "created_at": meta.get("created_at", ""),
                        "progress": int(meta.get("progress", 0))
                    })
            if cursor == 0:
                break

        # Sort by created_at descending
        pipelines.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return {
            "pipelines": pipelines[:limit],
            "total": len(pipelines)
        }

    except Exception as e:
        logger.error(f"Failed to list pipelines: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list pipelines: {str(e)}")
