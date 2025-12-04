"""
Application constants
Centralized constant definitions extracted from utils.py

Model configurations are now imported from shared/llm_config.py to ensure
consistency between Streamlit and FastAPI services.
"""
from typing import Dict
import sys
from pathlib import Path

# Add parent directory to path to import shared module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import model configurations from centralized source
from llm_config.llm_config import (
    MODEL_CONFIGS,
    MODEL_KEY_MAP,
    MODEL_DESCRIPTIONS,
    MODEL_REGISTRY,
    get_model_config,
    list_supported_models,
)

# Embedding Model Configuration
EMBEDDING_MODEL_NAME = "multi-qa-mpnet-base-dot-v1"

# Document Processing Defaults
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200
DEFAULT_TOP_K_RESULTS = 5

# Vision Model Options
VISION_MODELS = {
    "openai": "OpenAI Vision (GPT-4V)",
    "huggingface": "HuggingFace BLIP",
    "llava_7b": "Ollama LLaVA 1.6 7B",
    "llava_13b": "Ollama LLaVA 1.6 13B",
    "granite_vision_2b": "Ollama Granite Vision 2B",
    "enhanced_local": "Enhanced Local Vision",
    "basic": "Basic Vision Model"
}

# File Upload Settings
SUPPORTED_FILE_TYPES = ['pdf', 'docx', 'txt', 'xlsx', 'pptx', 'html', 'csv']
MAX_FILE_SIZE_MB = 100

# UI Constants
UI_CONSTANTS = {
    "page_title": "ClaimPilot",
    "page_icon": "",
    "layout": "wide",
    "sidebar_state": "expanded"
}

# Cache Settings
CACHE_TTL_MODELS = 1200         # 20 minutes for models
CACHE_TTL_COLLECTIONS = 300     # 5 minutes for collections
CACHE_TTL_DOCUMENTS = 300       # 5 minutes for documents

# Timeout Settings (in seconds)
TIMEOUT_CHAT = 300
TIMEOUT_UPLOAD = 600
TIMEOUT_HEALTH_CHECK = 10
TIMEOUT_COLLECTION_OPS = 30

# Agent Configuration Defaults
DEFAULT_AGENT_TEMPERATURE = 0.7
DEFAULT_AGENT_MAX_TOKENS = None

# Export Format Options
EXPORT_FORMATS = ["docx", "pdf", "json", "csv"]

# Status Messages
STATUS_MESSAGES = {
    "loading": "Loading...",
    "processing": "Processing...",
    "uploading": "Uploading files...",
    "analyzing": "Analyzing with AI...",
    "success": "Operation completed successfully",
    "error": "An error occurred"
}

# Error Messages
ERROR_MESSAGES = {
    "no_collections": "No collections available. Please create or upload to a collection first.",
    "no_documents": "No documents found in this collection.",
    "no_agents": "No agents available. Please create an agent first.",
    "connection_error": "Could not connect to the server. Please check your connection.",
    "timeout_error": "Request timed out. Please try again.",
    "invalid_input": "Invalid input. Please check your data and try again."
}

# Help Text
HELP_TEXT = {
    "rag": "Retrieval Augmented Generation (RAG) enhances AI responses with content from your uploaded documents.",
    "chunk_size": "Number of characters in each document chunk. Larger chunks preserve context, smaller chunks improve precision.",
    "chunk_overlap": "Number of overlapping characters between chunks to maintain context continuity.",
    "vision_models": "Select which AI models to use for analyzing images in documents.",
    "temperature": "Controls randomness in AI responses. Lower values (0.1) are more focused, higher values (0.9) are more creative."
}
