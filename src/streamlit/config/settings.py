"""
Application Settings
Centralized configuration - Single Source of Truth for all endpoints and settings
Maps directly to config/settings.ts in React/Next.js
"""
from dataclasses import dataclass
from typing import Dict, Optional
from .env import env
from .constants import MODEL_CONFIGS, MODEL_KEY_MAP, MODEL_DESCRIPTIONS

@dataclass
class APIEndpoints:
    base: str
    api: str
    vectordb: str
    chat: str
    history: str
    health: str
    legal_assist: str
    doc_gen: str
    redis: str
    agent: str

    def get_url(self, endpoint_key: str) -> str:
        return getattr(self, endpoint_key, self.base)


@dataclass
class ModelConfig:
    display_name: str
    model_id: str
    description: str
    provider: str  # 'openai' | 'anthropic'


class AppConfig:
    def __init__(self):
        # Environment
        self.env = env

        # Base URLs
        self.fastapi_url = env.fastapi_url.rstrip('/')

        # API Endpoints - SINGLE SOURCE OF TRUTH
        self.endpoints = APIEndpoints(
            base=self.fastapi_url,
            api=f"{self.fastapi_url}/api",
            vectordb=f"{self.fastapi_url}/api/vectordb",
            chat=f"{self.fastapi_url}/api/chat",
            history=f"{self.fastapi_url}/api/chat/history",
            health=f"{self.fastapi_url}/api/health",
            legal_assist=f"{self.fastapi_url}/api/legal-assist",
            doc_gen=f"{self.fastapi_url}/api/doc_gen",
            redis=f"{self.fastapi_url}/api/redis",
            agent=f"{self.fastapi_url}/api/agent"
        )

        # Model Configurations
        self.models: Dict[str, ModelConfig] = {}
        for name, config_dict in MODEL_CONFIGS.items():
            self.models[name] = ModelConfig(
                display_name=config_dict["display_name"],
                model_id=config_dict["model_id"],
                description=config_dict["description"],
                provider=config_dict["provider"]
            )

        # Convenience mappings
        self.model_key_map = MODEL_KEY_MAP
        self.model_descriptions = MODEL_DESCRIPTIONS

        # API Keys
        self.openai_api_key = env.openai_api_key
        self.anthropic_api_key = env.anthropic_api_key

    def get_model_by_key(self, key: str) -> Optional[ModelConfig]:
        return self.models.get(key)

    def get_model_id(self, display_name: str) -> Optional[str]:
        model = self.models.get(display_name)
        return model.model_id if model else None

    def get_available_models(self) -> list[str]:
        return list(self.models.keys())

    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.env.is_development

    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.env.is_production

    @classmethod
    def get_instance(cls):
        if not hasattr(cls, '_instance'):
            cls._instance = cls()
        return cls._instance

# Export singleton instance - Use this throughout the app
config = AppConfig.get_instance()


# Convenience functions for backward compatibility during migration
def get_endpoint(name: str) -> str:
    return config.endpoints.get_url(name)


def get_model_config(name: str) -> Optional[ModelConfig]:
    return config.get_model_by_key(name)
