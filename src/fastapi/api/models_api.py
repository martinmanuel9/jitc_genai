"""
Models API endpoint for exposing LLM configuration to frontend clients.

This endpoint provides model metadata to React or other frontends that cannot
directly import Python modules. It serves as the API layer for the centralized
configuration in shared/llm_config.py.
"""
from fastapi import APIRouter
from typing import List, Dict, Any
import sys
from pathlib import Path

# Add parent directory to path to import llm_config module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from llm_config.llm_config import (
    MODEL_REGISTRY,
    MODEL_KEY_MAP,
    MODEL_DESCRIPTIONS,
    list_supported_models,
    get_models_by_provider,
    get_model_config,
    ModelConfig,
)

models_api_router = APIRouter(prefix="/models", tags=["models"])


@models_api_router.get("")
def get_models() -> List[Dict[str, Any]]:
    """
    Get all supported models with their configurations.

    Returns:
        List of model configurations including:
        - model_id: Canonical model identifier
        - display_name: Human-readable name for UI display
        - description: Model capabilities description
        - provider: Model provider (openai, anthropic, etc.)

    Example:
        GET /api/models
        [
            {
                "model_id": "gpt-4",
                "display_name": "GPT-4",
                "description": "Most capable GPT-4 model...",
                "provider": "openai"
            },
            ...
        ]
    """
    models = list_supported_models()
    return [
        {
            "model_id": model.model_id,
            "display_name": model.display_name,
            "description": model.description,
            "provider": model.provider,
        }
        for model in models
    ]


@models_api_router.get("/by-provider/{provider}")
def get_models_by_provider_endpoint(provider: str) -> List[Dict[str, Any]]:
    """
    Get all models for a specific provider.

    Args:
        provider: Provider name (e.g., "openai", "anthropic")

    Returns:
        List of model configurations for that provider

    Example:
        GET /api/models/by-provider/openai
    """
    models = get_models_by_provider(provider)
    return [
        {
            "model_id": model.model_id,
            "display_name": model.display_name,
            "description": model.description,
            "provider": model.provider,
        }
        for model in models
    ]


@models_api_router.get("/{model_identifier}")
def get_model_details(model_identifier: str) -> Dict[str, Any]:
    """
    Get details for a specific model by ID or display name.

    Args:
        model_identifier: Model ID (e.g., "gpt-4") or display name (e.g., "GPT-4")

    Returns:
        Model configuration details

    Example:
        GET /api/models/gpt-4
        GET /api/models/GPT-4
    """
    model = get_model_config(model_identifier)
    if not model:
        return {"error": f"Model not found: {model_identifier}"}

    return {
        "model_id": model.model_id,
        "display_name": model.display_name,
        "description": model.description,
        "provider": model.provider,
    }


@models_api_router.get("/map/display-to-id")
def get_display_name_mapping() -> Dict[str, str]:
    """
    Get mapping of display names to model IDs for frontend dropdowns.

    Returns:
        Dictionary mapping display names to model IDs

    Example:
        GET /api/models/map/display-to-id
        {
            "GPT-4": "gpt-4",
            "GPT-4o": "gpt-4o",
            "Claude 3 Opus": "claude-3-opus-20240229",
            ...
        }
    """
    return MODEL_KEY_MAP


@models_api_router.get("/providers/list")
def get_providers() -> List[str]:
    """
    Get list of all available providers.

    Returns:
        List of unique provider names

    Example:
        GET /api/models/providers/list
        ["openai", "anthropic"]
    """
    providers = set(model.provider for model in list_supported_models())
    return sorted(list(providers))
