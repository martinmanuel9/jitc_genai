import os
from langchain_openai import ChatOpenAI
import sys
from pathlib import Path

# Make sure the shared llm_config package is importable in both local and container contexts
_CURRENT_FILE = Path(__file__).resolve()
for _candidate in (_CURRENT_FILE.parents[2], _CURRENT_FILE.parents[1]):
    if (_candidate / "llm_config").exists():
        sys.path.insert(0, str(_candidate))
        break

from llm_config.llm_config import get_model_config, llm_env, validate_model

# Disable LangSmith tracing to avoid rate limits
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGCHAIN_ENDPOINT"] = ""
os.environ["LANGCHAIN_API_KEY"] = ""

def get_llm(model_name: str, temperature: float = None, max_tokens: int = None):
    """
    Get an LLM instance for the specified model.

    Args:
        model_name: Name of the model (e.g., "gpt-4", "claude-3-sonnet")
        temperature: Optional temperature override (will be ignored if model doesn't support it)
        max_tokens: Optional max_tokens override

    Returns:
        Configured LLM instance

    Raises:
        ValueError: If model is invalid or API keys are missing
    """
    # Validate model exists
    is_valid, error = validate_model(model_name)
    if not is_valid:
        raise ValueError(error)

    # Get model configuration
    model_config = get_model_config(model_name)
    resolved_model_id = model_config.model_id
    provider = model_config.provider.lower()

    # Validate API keys for provider
    keys_valid, key_error = llm_env.validate_provider_keys(provider)
    if not keys_valid:
        raise ValueError(f"{key_error}. Please configure the required API key.")

    # Determine temperature to use
    if temperature is None:
        # Use model-specific default if available, otherwise global default
        temperature = model_config.default_temperature if model_config.default_temperature is not None else llm_env.default_temperature

    # Build kwargs for LLM initialization
    llm_kwargs = {"model": resolved_model_id}

    # Add temperature only if model supports it
    if model_config.supports_temperature:
        llm_kwargs["temperature"] = temperature

    # Add max_tokens if provided and model supports it
    if max_tokens is not None and model_config.supports_max_tokens:
        llm_kwargs["max_tokens"] = max_tokens

    # OpenAI Chat models
    if provider == "openai":
        llm_kwargs["openai_api_key"] = llm_env.openai_api_key
        return ChatOpenAI(**llm_kwargs)

    # Anthropic Claude models
    elif provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
            llm_kwargs["anthropic_api_key"] = llm_env.anthropic_api_key
            # Remove 'model' key and use the correct parameter name
            model_id = llm_kwargs.pop("model")
            llm_kwargs["model_name"] = model_id if "claude" in model_id else model_id
            return ChatAnthropic(**llm_kwargs)
        except ImportError:
            raise ValueError(
                f"Claude models require 'langchain-anthropic' package. "
                f"Install with: pip install langchain-anthropic"
            )

    # Ollama models - local CPU-based inference
    elif provider == "ollama":
        ollama_host = os.getenv("LLM_OLLAMA_HOST", "http://ollama:11434")
        try:
            from langchain_ollama import OllamaLLM
            llm_kwargs["base_url"] = ollama_host
            return OllamaLLM(**llm_kwargs)
        except ImportError:
            raise ValueError(
                f"Ollama models require 'langchain-ollama' package. "
                f"Install with: pip install langchain-ollama"
            )

    else:
        raise ValueError(
            f"Unsupported provider: {provider} for model {model_name}. "
            f"Currently supported providers: openai, anthropic, ollama"
        )
