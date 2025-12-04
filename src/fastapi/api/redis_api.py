from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import requests
import os
import logging
import redis
from datetime import datetime, timezone

logger = logging.getLogger("REDIS_API_LOGGER")

redis_api_router = APIRouter(prefix="/redis", tags=["redis"])

@redis_api_router.get("/generated-testplans")
async def list_generated_testplans(limit: int = Query(20, ge=1, le=200)):
    """List recent test plan runs indexed in Redis with basic metadata"""
    try:
        rhost = os.getenv("REDIS_HOST", "redis")
        rport = int(os.getenv("REDIS_PORT", 6379))
        rcli = redis.Redis(host=rhost, port=rport, decode_responses=True)
        ids = rcli.zrevrange("doc:recent", 0, limit - 1) or []
        results = []
        for doc_id in ids:
            meta = rcli.hgetall(f"doc:{doc_id}:meta") or {}
            section_count = rcli.scard(f"doc:{doc_id}:sections")
            results.append({
                "redis_document_id": doc_id,
                "title": meta.get("title", "Comprehensive Test Plan"),
                "collection": meta.get("collection"),
                "created_at": meta.get("created_at"),
                "completed_at": meta.get("completed_at"),
                "status": meta.get("status", "UNKNOWN"),
                "section_count": int(section_count) if section_count is not None else None,
                "total_testable_items": int(meta.get("total_testable_items", "0") or 0),
                "total_test_procedures": int(meta.get("total_test_procedures", "0") or 0),
                "generated_document_id": meta.get("generated_document_id")
            })
        return {"count": len(results), "runs": results}
    except Exception as e:
        logger.error(f"Failed to list generated test plans: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@redis_api_router.get("/testplan/pipelines")
async def list_testplan_pipelines(
    limit: int = Query(20, ge=1, le=200), 
    status: Optional[str] = Query(None, description="Filter by status: processing|recent")):
    """List multi-agent test plan pipelines. Use status=processing to show only in-progress runs."""
    try:
        rhost = os.getenv("REDIS_HOST", "redis")
        rport = int(os.getenv("REDIS_PORT", 6379))
        rcli = redis.Redis(host=rhost, port=rport, decode_responses=True)

        if status and status.lower() == "processing":
            ids = rcli.zrevrange("pipeline:processing", 0, limit - 1) or []
        else:
            ids = rcli.zrevrange("pipeline:recent", 0, limit - 1) or []
        results = []

        for pid in ids:
            meta = rcli.hgetall(f"pipeline:{pid}:meta") or {}
            # Try to read final result status if present
            final_meta = rcli.hgetall(f"pipeline:{pid}:final_result") or {}
            results.append({
                "pipeline_id": pid,
                "title": meta.get("title", "Comprehensive Test Plan"),
                "status": meta.get("status", "UNKNOWN"),
                "total_sections": int(meta.get("total_sections", "0") or 0),
                "sections_processed": int(meta.get("sections_processed", "0") or 0),
                "created_at": meta.get("created_at"),
                "completed_at": meta.get("completed_at"),
                "actor_agents": int(meta.get("actor_agents", "0") or 0),
                "generated_document_id": meta.get("generated_document_id"),
                "generated_collection": meta.get("collection"),
                "model_fallback": meta.get("model_fallback"),
                "fallback_reason": meta.get("fallback_reason"),
                "has_final_result": bool(final_meta.get("processing_status") == "COMPLETED"),
            })

        return {"count": len(results), "pipelines": results}
    except Exception as e:
        logger.error(f"Failed to list pipelines: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@redis_api_router.get("/testplan/pipelines/processing")
async def list_processing_testplan_pipelines(limit: int = Query(20, ge=1, le=200)):
    """Convenience endpoint to list only in-progress pipelines."""
    return await list_testplan_pipelines(limit=limit, status="processing")

@redis_api_router.get("/testplan/pipelines/{pipeline_id}")
async def get_testplan_pipeline(pipeline_id: str):
    """Get detailed status for a specific multi-agent test plan pipeline."""
    try:
        rhost = os.getenv("REDIS_HOST", "redis")
        rport = int(os.getenv("REDIS_PORT", 6379))
        rcli = redis.Redis(host=rhost, port=rport, decode_responses=True)

        meta_key = f"pipeline:{pipeline_id}:meta"
        if not rcli.exists(meta_key):
            raise HTTPException(status_code=404, detail="Pipeline not found")

        meta = rcli.hgetall(meta_key)

        # Collect section statuses
        section_keys = rcli.keys(f"pipeline:{pipeline_id}:section:*")
        sections = []
        for sk in sorted(section_keys, key=lambda x: int(x.rsplit(":", 1)[-1])):
            data = rcli.hgetall(sk) or {}
            try:
                idx = int(data.get("index", sk.rsplit(":", 1)[-1]))
            except ValueError:
                idx = sk.rsplit(":", 1)[-1]
            sections.append({
                "index": idx,
                "title": data.get("title", "Unnamed Section"),
                "status": data.get("status", "UNKNOWN"),
            })

        # Final result if available
        final_result = rcli.hgetall(f"pipeline:{pipeline_id}:final_result") or None

        return {
            "pipeline_id": pipeline_id,
            "meta": meta,
            "sections": sections,
            "final_result": final_result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pipeline {pipeline_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@redis_api_router.post("/testplan/pipelines/{pipeline_id}/abort")
async def abort_testplan_pipeline(pipeline_id: str, purge: bool = True):
    """Signal an in-progress pipeline to abort and stop further processing."""
    try:
        rhost = os.getenv("REDIS_HOST", "redis")
        rport = int(os.getenv("REDIS_PORT", 6379))
        rcli = redis.Redis(host=rhost, port=rport, decode_responses=True)

        meta_key = f"pipeline:{pipeline_id}:meta"
        if not rcli.exists(meta_key):
            raise HTTPException(status_code=404, detail="Pipeline not found")

        # Capture meta before changing it (for possible Chroma deletion)
        meta_before = rcli.hgetall(meta_key) or {}

        # Flag abort and set final status to ABORTED immediately
        rcli.set(f"pipeline:{pipeline_id}:abort", "1", ex=3600)
        rcli.hset(meta_key, mapping={
            "status": "ABORTED",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "purge_on_abort": "1" if purge else "0",
        })

        # Remove from processing set immediately
        try:
            rcli.zrem("pipeline:processing", pipeline_id)
        except Exception:
            pass

        # On purge, hard-delete pipeline keys and remove from listings; also delete saved Chroma doc if present
        if purge:
            # Remove from recent set
            try:
                rcli.zrem("pipeline:recent", pipeline_id)
            except Exception:
                pass
            # Delete keys
            pattern = f"pipeline:{pipeline_id}:*"
            keys = rcli.keys(pattern) or []
            if keys:
                rcli.delete(*keys)

            # Delete Chroma document if one was recorded
            chroma_deleted = False
            chroma_error = None
            try:
                doc_id = meta_before.get("generated_document_id")
                collection = meta_before.get("collection") or os.getenv("GENERATED_TESTPLAN_COLLECTION", "generated_test_plan")
                if doc_id:
                    chroma_url = os.getenv("CHROMA_URL", "http://chromadb:8000")
                    payload = {"collection_name": collection, "ids": [doc_id]}
                    resp = requests.post(f"{chroma_url}/documents/delete", json=payload, timeout=15)
                    chroma_deleted = resp.ok
                    if not resp.ok:
                        chroma_error = resp.text
            except Exception as e:
                chroma_error = str(e)

            return {
                "message": f"Pipeline {pipeline_id} aborted and purged",
                "purged_keys": len(keys),
                "chroma_deleted": chroma_deleted,
                "chroma_error": chroma_error,
            }

        return {"message": f"Pipeline {pipeline_id} aborted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to abort pipeline {pipeline_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@redis_api_router.post("/testplan/pipelines/{pipeline_id}/purge")
async def purge_testplan_pipeline(pipeline_id: str, delete_chroma: bool = True):
    """Hard-purge a pipeline's Redis keys and optionally delete any saved Chroma doc."""
    try:
        rhost = os.getenv("REDIS_HOST", "redis")
        rport = int(os.getenv("REDIS_PORT", 6379))
        rcli = redis.Redis(host=rhost, port=rport, decode_responses=True)

        meta_key = f"pipeline:{pipeline_id}:meta"
        meta = rcli.hgetall(meta_key) or {}
        # Remove from index sets
        try:
            rcli.zrem("pipeline:recent", pipeline_id)
            rcli.zrem("pipeline:processing", pipeline_id)
        except Exception:
            pass
        # Delete all keys
        pattern = f"pipeline:{pipeline_id}:*"
        keys = rcli.keys(pattern) or []
        if keys:
            rcli.delete(*keys)

        deleted = False
        chroma_error = None
        if delete_chroma:
            try:
                doc_id = meta.get("generated_document_id")
                collection = meta.get("collection") or os.getenv("GENERATED_TESTPLAN_COLLECTION", "generated_test_plan")
                if doc_id:
                    chroma_url = os.getenv("CHROMA_URL", "http://chromadb:8000")
                    payload = {"collection_name": collection, "ids": [doc_id]}
                    resp = requests.post(f"{chroma_url}/documents/delete", json=payload, timeout=15)
                    deleted = resp.ok
                    if not resp.ok:
                        chroma_error = resp.text
            except Exception as e:
                chroma_error = str(e)

        return {
            "pipeline_id": pipeline_id,
            "purged_keys": len(keys),
            "chroma_deleted": deleted,
            "chroma_error": chroma_error,
        }
    except Exception as e:
        logger.error(f"Failed to purge pipeline {pipeline_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@redis_api_router.delete("/generated-testplan/{document_id}")
async def delete_generated_testplan(document_id: str, collection_name: Optional[str] = None):
    """Delete a generated test plan from Chroma (defaults to generated_test_plan collection)."""
    try:
        chroma_url = os.getenv("CHROMA_URL", "http://chromadb:8000")
        collection = collection_name or os.getenv("GENERATED_TESTPLAN_COLLECTION", "generated_test_plan")
        payload = {"collection_name": collection, "ids": [document_id]}
        resp = requests.post(f"{chroma_url}/documents/delete", json=payload, timeout=15)
        if resp.ok:
            return {"message": f"Deleted {document_id} from {collection}"}
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete generated test plan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))