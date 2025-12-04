
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import os


@dataclass(frozen=True)
class ModelConfig:
    """Metadata describing a supported LLM."""

    model_id: str
    display_name: str
    description: str
    provider: str  # e.g. "openai", "anthropic"
    supports_temperature: bool = True  # Whether model supports temperature parameter
    supports_max_tokens: bool = True  # Whether model supports max_tokens parameter
    default_temperature: Optional[float] = None  # Model-specific default temperature (None = use global default)
    max_context_tokens: Optional[int] = None  # Maximum context window size

    def __hash__(self):
        return hash(self.model_id)


# ============================================================================
# SINGLE SOURCE OF TRUTH FOR ALL SUPPORTED MODELS
# ============================================================================

MODEL_REGISTRY: Dict[str, ModelConfig] = {
    # --- OpenAI Models ---
    # "gpt-5.1": ModelConfig(
    #     model_id="gpt-5.1",
    #     display_name="GPT-5.1",
    #     description="Next-generation GPT-5.1 model with advanced reasoning and creativity capabilities",
    #     provider="openai",
    #     max_context_tokens=256000,
    # ),
    # "gpt-5": ModelConfig(
    #     model_id="gpt-5",
    #     display_name="GPT-5",
    #     description="State-of-the-art GPT-5 model for unparalleled performance in diverse tasks",
    #     provider="openai",
    #     max_context_tokens=256000,
    # ),
    # "gpt-5-mini": ModelConfig(
    #     model_id="gpt-5-mini",
    #     display_name="GPT-5 Mini",
    #     description="Compact GPT-5 variant optimized for efficiency and cost-effectiveness",
    #     provider="openai",
    #     max_context_tokens=256000,
    # ),
    # "gpt-5-nano": ModelConfig(
    #     model_id="gpt-5-nano",
    #     display_name="GPT-5 Nano",
    #     description="Ultra-lightweight GPT-5 model for rapid inference and minimal resource usage",
    #     provider="openai",
    #     max_context_tokens=256000,
    # ),
    # "gpt-4.1": ModelConfig(
    #     model_id="gpt-4.1",
    #     display_name="GPT-4.1",
    #     description="Enhanced GPT-4 model with improved contextual understanding and generation quality",
    #     provider="openai",
    #     max_context_tokens=128000,
    # ),
    # "gpt-4": ModelConfig(
    #     model_id="gpt-4",
    #     display_name="GPT-4",
    #     description="Most capable GPT-4 model for complex analysis and reasoning tasks",
    #     provider="openai",
    #     max_context_tokens=8192,
    # ),
    # "gpt-4o": ModelConfig(
    #     model_id="gpt-4o",
    #     display_name="GPT-4o",
    #     description="Flagship multimodal OpenAI model with improved speed, cost, and vision support",
    #     provider="openai",
    #     max_context_tokens=128000,
    # ),
    # "gpt-4o-mini": ModelConfig(
    #     model_id="gpt-4o-mini",
    #     display_name="GPT-4o Mini",
    #     description="Lightweight GPT-4o variant optimized for cost-effective, high-volume workloads",
    #     provider="openai",
    #     max_context_tokens=128000,
    # ),
    # "gpt-3.5-turbo": ModelConfig(
    #     model_id="gpt-3.5-turbo",
    #     display_name="GPT-3.5-Turbo",
    #     description="Fast and cost-effective model for general tasks and conversations",
    #     provider="openai",
    #     max_context_tokens=16385,
    # ),
    # "gpt-4-turbo": ModelConfig(
    #     model_id="gpt-4-turbo",
    #     display_name="GPT-4-Turbo",
    #     description="Faster and cheaper variant of GPT-4 for scalable applications",
    #     provider="openai",
    #     max_context_tokens=128000,
    # ),
    # # OpenAI Reasoning Models (o-series) - Do NOT support temperature parameter
    # "o1": ModelConfig(
    #     model_id="o1",
    #     display_name="OpenAI o1",
    #     description="Advanced reasoning model optimized for complex problem-solving (no temperature control)",
    #     provider="openai",
    #     supports_temperature=False,  # o1 models don't support temperature
    #     default_temperature=1.0,  # Fixed temperature
    #     max_context_tokens=200000,
    # ),
    # "o1-mini": ModelConfig(
    #     model_id="o1-mini",
    #     display_name="OpenAI o1-mini",
    #     description="Efficient reasoning model for faster inference (no temperature control)",
    #     provider="openai",
    #     supports_temperature=False,  # o1 models don't support temperature
    #     default_temperature=1.0,  # Fixed temperature
    #     max_context_tokens=128000,
    # ),
    # "o3-mini": ModelConfig(
    #     model_id="o3-mini",
    #     display_name="OpenAI o3-mini",
    #     description="Latest reasoning model with improved capabilities (no temperature control)",
    #     provider="openai",
    #     supports_temperature=False,  # o3 models don't support temperature
    #     default_temperature=1.0,  # Fixed temperature
    #     max_context_tokens=200000,
    # ),

    # --- Ollama Local Models (US-Based Organizations Only) ---
    # All models below are from US-based organizations and run completely on-premises

    # Meta (US - California) - Llama 3.2 Series
    "llama3.2:1b": ModelConfig(
        model_id="llama3.2:1b",
        display_name="Llama 3.2 1B (Local)",
        description="Meta's smallest Llama model - Ultra-lightweight, CPU-optimized (1GB RAM, 1.3GB disk)",
        provider="ollama",
        max_context_tokens=128000,
    ),
    "llama3.2:3b": ModelConfig(
        model_id="llama3.2:3b",
        display_name="Llama 3.2 3B (Local)",
        description="Meta's balanced Llama 3.2 model - Good performance with reasonable resources (2GB disk)",
        provider="ollama",
        max_context_tokens=128000,
    ),

    # Meta (US - California) - Llama 3.1 Series
    "llama3.1:8b": ModelConfig(
        model_id="llama3.1:8b",
        display_name="Llama 3.1 8B (Local)",
        description="Meta's powerful 8B model - Excellent for complex tasks (4.7GB disk)",
        provider="ollama",
        max_context_tokens=128000,
    ),

    # Microsoft (US - Washington) - Phi Series
    "phi3:mini": ModelConfig(
        model_id="phi3:mini",
        display_name="Phi-3 Mini (Local)",
        description="Microsoft's efficient small model - Excellent quality-to-size ratio (2.3GB disk)",
        provider="ollama",
        max_context_tokens=128000,
    ),
    "llava:7b": ModelConfig(
        model_id="llava:7b",
        display_name="LLaVA 1.6 7B (Local)",
        description="Vision-language model for image understanding tasks (4.7GB disk)",
        provider="ollama",
        max_context_tokens=128000,
    ),
    "llava:13b": ModelConfig(
        model_id="llava:13b",
        display_name="LLaVA 1.6 13B (Local)",
        description="Larger multimodal model for advanced image understanding (8GB disk)",
        provider="ollama",
        max_context_tokens=128000,
    ),
    "granite3.2-vision:2b": ModelConfig(
        model_id="granite3.2-vision:2b",
        display_name="Granite 3.2 Vision 2B (Local)",
        description="Granite 3.2 model with vision capabilities for image understanding tasks (3.5GB disk)",
        provider="ollama",
        max_context_tokens=128000,
    ),
}


# ============================================================================
# CONVENIENCE MAPPINGS
# ============================================================================


# Display name (exact case) -> Model ID (for Streamlit compatibility)
MODEL_KEY_MAP: Dict[str, str] = {
    cfg.display_name: cfg.model_id
    for cfg in MODEL_REGISTRY.values()
}

# Model ID -> Description (for Streamlit compatibility)
MODEL_DESCRIPTIONS: Dict[str, str] = {
    cfg.model_id: cfg.description
    for cfg in MODEL_REGISTRY.values()
}

# Model ID -> Display Name
MODEL_ID_TO_DISPLAY: Dict[str, str] = {
    cfg.model_id: cfg.display_name
    for cfg in MODEL_REGISTRY.values()
}

# Display name (lowercase) -> Model ID (for case-insensitive lookups)
MODEL_DISPLAY_MAP: Dict[str, str] = {
    cfg.display_name.lower(): cfg.model_id
    for cfg in MODEL_REGISTRY.values()
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_model_config(model_name: Optional[str]) -> Optional[ModelConfig]:
    """
    Resolve a model by either its canonical ID (e.g. 'gpt-4o') or display name.

    Args:
        model_name: Model identifier (can be model_id or display_name, case-insensitive)

    Returns:
        ModelConfig if found, None otherwise

    Examples:
        >>> get_model_config("gpt-4")  # By ID
        ModelConfig(model_id="gpt-4", ...)

        >>> get_model_config("GPT-4")  # By display name
        ModelConfig(model_id="gpt-4", ...)

        >>> get_model_config("Claude 3 Opus")  # By display name
        ModelConfig(model_id="claude-3-opus-20240229", ...)
    """
    if not model_name:
        return None

    key = model_name.strip()

    # Try exact match on model ID
    if key in MODEL_REGISTRY:
        return MODEL_REGISTRY[key]

    # Try case-insensitive display name match
    lowered = key.lower()
    if lowered in MODEL_DISPLAY_MAP:
        canonical_id = MODEL_DISPLAY_MAP[lowered]
        return MODEL_REGISTRY[canonical_id]

    return None


def validate_model(model_name: Optional[str]) -> tuple[bool, str]:
    """
    Validate if a model is supported.

    Args:
        model_name: Model identifier to validate

    Returns:
        Tuple of (is_valid, error_message)
        If valid: (True, "")
        If invalid: (False, "error message")
    """
    if not model_name:
        return False, "Model name is required"

    config = get_model_config(model_name)
    if not config:
        supported = ", ".join(MODEL_REGISTRY.keys())
        return False, f"Unsupported model: '{model_name}'. Supported models: {supported}"

    return True, ""


def get_models_by_provider(provider: str) -> List[ModelConfig]:
    """
    Return all models belonging to a specific provider.

    Args:
        provider: Provider name (e.g., "openai", "anthropic")

    Returns:
        List of ModelConfig objects for that provider
    """
    provider_l = provider.lower()
    return [
        cfg for cfg in MODEL_REGISTRY.values()
        if cfg.provider.lower() == provider_l
    ]


def list_supported_models() -> List[ModelConfig]:
    """Return all supported models."""
    return list(MODEL_REGISTRY.values())


def get_openai_models() -> List[ModelConfig]:
    """Return all OpenAI models."""
    return get_models_by_provider("openai")


def get_anthropic_models() -> List[ModelConfig]:
    """Return all Anthropic models."""
    return get_models_by_provider("anthropic")


def get_model_display_name(model_id: str) -> str:
    """Get display name for a model ID, returns model_id if not found."""
    return MODEL_ID_TO_DISPLAY.get(model_id, model_id)


def get_model_capabilities(model_name: str) -> Dict[str, Any]:
    """
    Get model capabilities and constraints.

    Args:
        model_name: Model identifier

    Returns:
        Dictionary with model capabilities:
        - supports_temperature: bool
        - supports_max_tokens: bool
        - max_context_tokens: int or None
        - default_temperature: float or None

    Example:
        >>> caps = get_model_capabilities("o1")
        >>> print(caps["supports_temperature"])  # False
        >>> print(caps["max_context_tokens"])  # 200000
    """
    config = get_model_config(model_name)
    if not config:
        return {
            "supports_temperature": True,
            "supports_max_tokens": True,
            "max_context_tokens": None,
            "default_temperature": None
        }

    return {
        "supports_temperature": config.supports_temperature,
        "supports_max_tokens": config.supports_max_tokens,
        "max_context_tokens": config.max_context_tokens,
        "default_temperature": config.default_temperature
    }


# ============================================================================
# ENVIRONMENT CONFIGURATION
# ============================================================================

class LLMEnvironment:
    """Centralized environment configuration for LLM services."""

    def __init__(self):
        # Standardized API key names (without underscores for consistency)
        self.openai_api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_AI_API_KEY")
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

        # LangChain settings
        self.langchain_tracing = os.getenv("LANGCHAIN_TRACING_V2", "false")
        self.langchain_endpoint = os.getenv("LANGCHAIN_ENDPOINT", "")
        self.langchain_api_key = os.getenv("LANGCHAIN_API_KEY", "")

        # Model defaults
        self.default_temperature = float(os.getenv("LLM_DEFAULT_TEMPERATURE", "0.7"))
        self.default_max_tokens = int(os.getenv("LLM_DEFAULT_MAX_TOKENS", "2000"))

    def validate_provider_keys(self, provider: str) -> tuple[bool, str]:
        """
        Validate that API keys are configured for a provider.

        Args:
            provider: Provider name (e.g., "openai", "anthropic", "ollama")

        Returns:
            Tuple of (is_valid, error_message)
        """
        provider_l = provider.lower()

        if provider_l == "openai":
            if not self.openai_api_key:
                return False, "OPENAI_API_KEY environment variable is not set"
        elif provider_l == "anthropic":
            if not self.anthropic_api_key:
                return False, "ANTHROPIC_API_KEY environment variable is not set"
        elif provider_l == "ollama":
            # Ollama runs locally and doesn't require API keys
            return True, ""
        else:
            return False, f"Unknown provider: {provider}"

        return True, ""

    def validate_model(self, model_name: str) -> tuple[bool, str]:
        """
        Validate model and its required API keys.

        Args:
            model_name: Model identifier

        Returns:
            Tuple of (is_valid, error_message)
        """
        # First validate model exists
        is_valid, error = validate_model(model_name)
        if not is_valid:
            return is_valid, error

        # Then validate API keys
        config = get_model_config(model_name)
        return self.validate_provider_keys(config.provider)


# Export singleton
llm_env = LLMEnvironment()


# ============================================================================
# MIGRATION HELPERS (for backward compatibility)
# ============================================================================

def get_model_configs_dict() -> Dict[str, Dict[str, str]]:
    """
    Return model configurations in the old format for backward compatibility.

    Returns:
        Dict mapping display_name to config dict
    """
    return {
        cfg.display_name: {
            "model_id": cfg.model_id,
            "display_name": cfg.display_name,
            "description": cfg.description,
            "provider": cfg.provider
        }
        for cfg in MODEL_REGISTRY.values()
    }


# Expose old format for backward compatibility
MODEL_CONFIGS = get_model_configs_dict()
