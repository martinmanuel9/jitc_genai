"""
DEPRECATED: This file is maintained for backward compatibility only.

The model registry has been moved to llm_config/llm_config.py to provide a single
source of truth for both Streamlit and FastAPI services.

All new code should import from llm_config.llm_config instead:
    from llm_config.llm_config import (
        ModelConfig,
        MODEL_REGISTRY,
        get_model_config,
        get_models_by_provider,
        list_supported_models
    )

This file now re-exports those functions to maintain compatibility with existing code.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path to import llm_config module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import from centralized configuration
from llm_config.llm_config import (
    ModelConfig,
    MODEL_REGISTRY,
    MODEL_DISPLAY_MAP,
    MODEL_KEY_MAP,
    get_model_config,
    get_models_by_provider,
    list_supported_models,
)

# Re-export for backward compatibility
__all__ = [
    "ModelConfig",
    "MODEL_REGISTRY",
    "MODEL_DISPLAY_MAP",
    "MODEL_KEY_MAP",
    "get_model_config",
    "get_models_by_provider",
    "list_supported_models",
]
