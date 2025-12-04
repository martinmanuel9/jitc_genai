"""
Celery application configuration for async task processing.
Uses Redis as both broker and result backend.
"""

from celery import Celery
import os
import logging

logger = logging.getLogger("CELERY_APP")

# Get Redis connection details from environment
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("CELERY_REDIS_DB", 1))  # Use DB 1 for Celery to separate from other Redis usage

# Construct Redis URL
BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# Create Celery app
celery_app = Celery(
    "test_card_generation",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=["tasks.test_card_tasks"]  # Import task modules
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Result backend settings
    result_expires=604800,  # 7 days (in seconds)
    result_extended=True,  # Store additional metadata

    # Task execution settings
    task_acks_late=True,  # Acknowledge task after completion, not before
    task_reject_on_worker_lost=True,  # Requeue tasks if worker dies
    task_track_started=True,  # Track when task starts

    # Worker settings
    worker_prefetch_multiplier=1,  # Only prefetch one task at a time (good for long-running tasks)
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks to prevent memory leaks

    # Timeouts
    task_soft_time_limit=1800,  # 30 minutes soft limit (logs warning)
    task_time_limit=3600,  # 60 minutes hard limit (kills task)

    # Logging
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s",
)

logger.info(f"Celery app configured with broker: {BROKER_URL}")
