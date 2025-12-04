"""
llm_config package

Centralized access point for LLM configuration that is shared between
FastAPI and Streamlit services.
"""

from .llm_config import (  # noqa: F401
    ModelConfig,
    MODEL_REGISTRY,
    MODEL_DISPLAY_MAP,
    MODEL_KEY_MAP,
    MODEL_DESCRIPTIONS,
    MODEL_ID_TO_DISPLAY,
    get_model_config,
    validate_model,
    get_models_by_provider,
    list_supported_models,
    get_openai_models,
    get_anthropic_models,
    get_model_display_name,
    llm_env,
    MODEL_CONFIGS,
)

__all__ = [
    "ModelConfig",
    "MODEL_REGISTRY",
    "MODEL_DISPLAY_MAP",
    "MODEL_KEY_MAP",
    "MODEL_DESCRIPTIONS",
    "MODEL_ID_TO_DISPLAY",
    "get_model_config",
    "validate_model",
    "get_models_by_provider",
    "list_supported_models",
    "get_openai_models",
    "get_anthropic_models",
    "get_model_display_name",
    "llm_env",
    "MODEL_CONFIGS",
]
