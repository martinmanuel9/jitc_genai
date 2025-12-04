"""
Celery tasks for test card generation.
"""

from celery import Task
from celery_app import celery_app
from services.test_card_service import TestCardService
from integrations.chromadb_client import get_chroma_client
import redis
import os
import json
import logging
from datetime import datetime

logger = logging.getLogger("TEST_CARD_TASKS")


class CallbackTask(Task):
    """Base task with callbacks for progress updates."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails."""
        logger.error(f"Task {task_id} failed: {exc}")

    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds."""
        logger.info(f"Task {task_id} completed successfully")


@celery_app.task(base=CallbackTask, bind=True, name="tasks.test_card_tasks.generate_test_cards")
def generate_test_cards(
    self,
    job_id: str,
    test_plan_id: str,
    collection_name: str,
    format: str
):
    """
    Celery task to generate test cards from a test plan.

    Args:
        self: Celery task instance (bound)
        job_id: Unique job identifier
        test_plan_id: ID of the test plan document
        collection_name: ChromaDB collection containing the test plan
        format: Output format for test cards

    Returns:
        dict: Result summary with generated test cards
    """
    try:
        logger.info(f"[{job_id}] Starting test card generation (Celery Task ID: {self.request.id})")

        # Initialize services
        from services.llm_service import LLMService

        chroma_client = get_chroma_client()
        llm_service = LLMService()  # Initialize without db for Celery context
        test_card_service = TestCardService(llm_service)

        # Get Redis connection for progress updates
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

        # Update status to processing
        redis_client.hset(f"testcard_job:{job_id}:meta", mapping={
            "status": "processing",
            "celery_task_id": self.request.id,
            "progress_message": "Loading test plan from ChromaDB...",
            "last_updated_at": datetime.now().isoformat()
        })

        # Update Celery task state
        self.update_state(
            state="PROGRESS",
            meta={"status": "Loading test plan from ChromaDB..."}
        )

        # Fetch test plan from ChromaDB (direct client call, no HTTP timeout)
        collection = chroma_client.get_collection(name=collection_name)
        result = collection.get()

        ids = result.get("ids", [])
        documents = result.get("documents", [])
        metadatas = result.get("metadatas", [])

        logger.info(f"[{job_id}] Found {len(ids)} documents in collection '{collection_name}'")

        # Find test plan with fallback search
        idx = None
        try:
            idx = ids.index(test_plan_id)
            logger.info(f"[{job_id}] ✓ Found test plan by exact ID match at index {idx}")
        except ValueError:
            logger.warning(f"[{job_id}] Exact ID match failed for '{test_plan_id}', trying fallback searches")

            # Try fallback searches
            for i, doc_id in enumerate(ids):
                if doc_id.lower() == test_plan_id.lower() or test_plan_id in doc_id:
                    idx = i
                    logger.info(f"[{job_id}] ✓ Found test plan by fallback match: '{doc_id}' at index {idx}")
                    break

        if idx is None:
            available_ids = ids[:5] if len(ids) > 5 else ids
            raise Exception(
                f"Test plan '{test_plan_id}' not found in collection '{collection_name}'. "
                f"Available IDs: {available_ids}"
            )

        test_plan_content = documents[idx]
        test_plan_metadata = metadatas[idx] or {}
        test_plan_title = test_plan_metadata.get("title", "Test Plan")

        logger.info(f"[{job_id}] Found test plan: {test_plan_title}")

        # Update progress
        redis_client.hset(f"testcard_job:{job_id}:meta", mapping={
            "test_plan_title": test_plan_title,
            "progress_message": "Parsing test plan into sections...",
            "last_updated_at": datetime.now().isoformat()
        })

        self.update_state(
            state="PROGRESS",
            meta={"status": "Parsing test plan into sections..."}
        )

        # Generate test cards
        logger.info(f"[{job_id}] Generating test cards...")
        test_cards = test_card_service.generate_test_cards_from_test_plan(
            test_plan_id=test_plan_id,
            test_plan_content=test_plan_content,
            test_plan_title=test_plan_title,
            format=format
        )

        if not test_cards:
            raise Exception("No test procedures found in test plan")

        logger.info(f"[{job_id}] Generated {len(test_cards)} test card documents")

        # Update progress
        redis_client.hset(f"testcard_job:{job_id}:meta", mapping={
            "test_cards_generated": str(len(test_cards)),
            "progress_message": f"Saving {len(test_cards)} test cards to ChromaDB...",
            "last_updated_at": datetime.now().isoformat()
        })

        self.update_state(
            state="PROGRESS",
            meta={"status": f"Saving {len(test_cards)} test cards to ChromaDB..."}
        )

        # Save to ChromaDB
        save_result = test_card_service.save_test_cards_to_chromadb(
            test_cards=test_cards,
            collection_name="test_cards"
        )

        # Store result in Redis
        test_card_summary = [
            {
                "document_id": card["document_id"],
                "document_name": card["document_name"],
                "test_id": card["metadata"]["test_id"],
                "section_title": card["metadata"]["section_title"]
            }
            for card in test_cards
        ]

        result_data = {
            "test_plan_id": test_plan_id,
            "test_plan_title": test_plan_title,
            "test_cards_generated": str(len(test_cards)),
            "test_cards": json.dumps(test_card_summary),
            "chromadb_saved": str(save_result.get("saved", False)),
            "collection_name": save_result.get("collection_name", "test_cards")
        }
        redis_client.hset(f"testcard_job:{job_id}:result", mapping=result_data)
        redis_client.expire(f"testcard_job:{job_id}:result", 604800)

        # Update final status
        redis_client.hset(f"testcard_job:{job_id}:meta", mapping={
            "status": "completed",
            "progress_message": f"Successfully generated {len(test_cards)} test cards",
            "completed_at": datetime.now().isoformat(),
            "last_updated_at": datetime.now().isoformat()
        })

        logger.info(f"[{job_id}] Test card generation completed successfully")

        return {
            "job_id": job_id,
            "test_plan_id": test_plan_id,
            "test_plan_title": test_plan_title,
            "test_cards_generated": len(test_cards),
            "status": "completed"
        }

    except Exception as e:
        logger.error(f"[{job_id}] Test card generation failed: {e}")
        import traceback
        logger.error(traceback.format_exc())

        # Update status to failed
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

        redis_client.hset(f"testcard_job:{job_id}:meta", mapping={
            "status": "failed",
            "error": str(e),
            "progress_message": f"Failed: {str(e)}",
            "last_updated_at": datetime.now().isoformat()
        })

        # Re-raise exception for Celery to mark task as failed
        raise
