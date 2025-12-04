# main.py
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from core.database import init_db
import uvicorn
import logging
from api.chat_api import chat_api_router
from api.agent_api import agent_api_router
from api.rag_api import rag_api_router
from api.health_api import health_api_router
from api.document_generation_api import doc_gen_api_router
from api.analytics_api import analytics_api_router
from api.chromadb_api import chromadb_api_router
from api.redis_api import redis_api_router
from api.vectordb_api import vectordb_api_router
from api.models_api import models_api_router
from api.test_plan_agent_api import router as test_plan_agent_router
from api.agent_set_api import router as agent_set_router
from api.agent_pipeline_api import agent_pipeline_router

app = FastAPI()

@app.on_event("startup")
def on_startup():
    # Configure database initialization loggers to show migration info
    # Enable INFO level for all database-related loggers
    for logger_name in ["db.init_db", "db.migrations.run_migrations"]:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        # Ensure it has a handler (use uvicorn's handler)
        if not logger.handlers:
            uvicorn_logger = logging.getLogger("uvicorn")
            if uvicorn_logger.handlers:
                logger.addHandler(uvicorn_logger.handlers[0])

    init_db()

app.include_router(chat_api_router, prefix="/api")
app.include_router(agent_api_router, prefix="/api")
app.include_router(rag_api_router, prefix="/api")
app.include_router(health_api_router, prefix="/api")
app.include_router(doc_gen_api_router, prefix="/api")
app.include_router(analytics_api_router, prefix="/api")
app.include_router(chromadb_api_router, prefix="/api")
app.include_router(redis_api_router, prefix="/api")
app.include_router(vectordb_api_router, prefix="/api")
app.include_router(models_api_router, prefix="/api")
app.include_router(test_plan_agent_router, prefix="/api")
app.include_router(agent_set_router, prefix="/api")
app.include_router(agent_pipeline_router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "Welcome to the FastAPI Service"}

if __name__ == "__main__":
    import os

    # Determine environment mode
    env = os.getenv("ENVIRONMENT", "development").lower()

    if env == "production":
        # Production: Multiple workers, no reload
        uvicorn.run("main:app", host="0.0.0.0", port=9020, workers=4)
    else:
        # Development: Single worker with hot reload
        # Note: reload=True is incompatible with workers > 1
        uvicorn.run("main:app", host="0.0.0.0", port=9020, reload=True)