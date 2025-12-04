"""
Environment variable management
Centralized access to environment variables with defaults
"""
import os
from typing import Optional


def get_env(key: str, default: Optional[str] = None) -> str:
    return os.getenv(key, default)


def get_env_bool(key: str, default: bool = False) -> bool:
    value = os.getenv(key, str(default))
    return value.lower() in ('true', '1', 'yes', 'on')


def get_env_int(key: str, default: int = 0) -> int:
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


# Environment configuration
class EnvironmentConfig:
    """Environment configuration singleton"""

    def __init__(self):
        # API Configuration
        self.fastapi_url = get_env("FASTAPI_URL", "http://localhost:9020")
        self.chromadb_url = get_env("CHROMADB_URL", "")  # Optional separate URL

        # API Keys
        self.openai_api_key = get_env("OPENAI_API_KEY", "")
        self.anthropic_api_key = get_env("ANTHROPIC_API_KEY", "")

        # Application Settings
        self.environment = get_env("ENVIRONMENT", "development")
        self.debug = get_env_bool("DEBUG", False)
        self.log_level = get_env("LOG_LEVEL", "INFO")

        # Feature Flags
        self.enable_legal_research = get_env_bool("ENABLE_LEGAL_RESEARCH", True)
        self.enable_rag = get_env_bool("ENABLE_RAG", True)
        self.enable_vision_models = get_env_bool("ENABLE_VISION_MODELS", True)

        # Performance Settings
        self.request_timeout = get_env_int("REQUEST_TIMEOUT", 300)
        self.max_upload_size_mb = get_env_int("MAX_UPLOAD_SIZE_MB", 100)
        self.cache_ttl_seconds = get_env_int("CACHE_TTL_SECONDS", 300)

    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.environment == "production"

    @classmethod
    def get_instance(cls):
        """Get singleton instance"""
        if not hasattr(cls, '_instance'):
            cls._instance = cls()
        return cls._instance


# Export singleton
env = EnvironmentConfig.get_instance()
