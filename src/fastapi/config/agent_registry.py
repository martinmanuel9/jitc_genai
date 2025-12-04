"""
Agent Registry for Test Plan Generation

Central configuration registry for all test plan generation agents.
Similar to model_registry.py, this provides a single place to configure
and manage all agents used in the test plan generation pipeline.

IMPORTANT: This registry references llm_config/llm_config.py for model validation
and configuration, ensuring a single source of truth for all LLM models.
"""

import os
import sys
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Type
import logging

# Add parent directory to path to import llm_config module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from llm_config.llm_config import (
    ModelConfig,
    MODEL_REGISTRY,
    get_model_config,
    validate_model,
    llm_env
)

logger = logging.getLogger(__name__)


class AgentType(Enum):
    """Enumeration of all available agent types"""
    ACTOR = "actor"
    CRITIC = "critic"
    CONTRADICTION = "contradiction"
    GAP_ANALYSIS = "gap_analysis"
    FINAL_CRITIC = "final_critic"


class ExecutionMode(Enum):
    """Agent execution modes"""
    PARALLEL = "parallel"      # Multiple agents run in parallel
    SEQUENTIAL = "sequential"  # Agents run one after another
    SINGLE = "single"          # Single agent execution


@dataclass
class AgentConfig:
    """Configuration for a specific agent"""
    agent_type: AgentType
    model_name: str
    temperature: float = 0.7
    max_tokens: int = 4000
    timeout: int = 120
    enabled: bool = True
    execution_mode: ExecutionMode = ExecutionMode.SINGLE
    count: int = 1  # Number of agents of this type to run
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineStage:
    """
    A stage in the agent pipeline.

    A stage can contain multiple agents that execute together.
    """
    stage_name: str
    agent_type: AgentType
    execution_mode: ExecutionMode
    depends_on: List[str] = field(default_factory=list)
    enabled: bool = True
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentRegistry:
    """
    Central registry for test plan generation agents.

    Manages agent configurations, pipeline stages, and provides
    factory methods for creating agent instances.
    """

    # Default configurations for each agent type
    DEFAULT_CONFIGS: Dict[AgentType, Dict[str, Any]] = {
        AgentType.ACTOR: {
            "temperature": 0.7,
            "max_tokens": 4000,
            "timeout": 120,
            "execution_mode": ExecutionMode.PARALLEL,
            "default_count": 3,
            "description": "Extract testable requirements from document sections"
        },
        AgentType.CRITIC: {
            "temperature": 0.5,
            "max_tokens": 4000,
            "timeout": 180,
            "execution_mode": ExecutionMode.SINGLE,
            "default_count": 1,
            "description": "Synthesize and deduplicate actor outputs"
        },
        AgentType.CONTRADICTION: {
            "temperature": 0.3,
            "max_tokens": 4000,
            "timeout": 180,
            "execution_mode": ExecutionMode.SINGLE,
            "default_count": 1,
            "description": "Detect contradictions and conflicts in test procedures"
        },
        AgentType.GAP_ANALYSIS: {
            "temperature": 0.3,
            "max_tokens": 4000,
            "timeout": 180,
            "execution_mode": ExecutionMode.SINGLE,
            "default_count": 1,
            "description": "Identify requirement gaps and missing test coverage"
        },
        AgentType.FINAL_CRITIC: {
            "temperature": 0.5,
            "max_tokens": 8000,
            "timeout": 300,
            "execution_mode": ExecutionMode.SINGLE,
            "default_count": 1,
            "description": "Consolidate all sections into final test plan"
        }
    }

    # Default pipeline configuration
    DEFAULT_PIPELINE = [
        PipelineStage(
            stage_name="actor_extraction",
            agent_type=AgentType.ACTOR,
            execution_mode=ExecutionMode.PARALLEL,
            enabled=True,
            description="Extract requirements from sections"
        ),
        PipelineStage(
            stage_name="critic_synthesis",
            agent_type=AgentType.CRITIC,
            execution_mode=ExecutionMode.SINGLE,
            depends_on=["actor_extraction"],
            enabled=True,
            description="Synthesize actor outputs"
        ),
        PipelineStage(
            stage_name="contradiction_detection",
            agent_type=AgentType.CONTRADICTION,
            execution_mode=ExecutionMode.SINGLE,
            depends_on=["critic_synthesis"],
            enabled=True,
            description="Detect contradictions and conflicts"
        ),
        PipelineStage(
            stage_name="gap_analysis",
            agent_type=AgentType.GAP_ANALYSIS,
            execution_mode=ExecutionMode.SINGLE,
            depends_on=["critic_synthesis"],
            enabled=True,
            description="Analyze requirement coverage gaps"
        )
    ]

    def __init__(self):
        """Initialize agent registry with database-first configuration"""
        # Initialize storage for agent data
        self.actor_agents_db = []
        self.critic_agent_db = None
        self.contradiction_agent_db = None
        self.gap_analysis_agent_db = None
        self.final_critic_agent_db = None

        # Load configuration
        self._load_from_environment()

    def _load_from_environment(self):
        """
        Load agent configurations with database-first strategy.

        Loading order:
        1. Try to load from database
        2. Fall back to hardcoded defaults if database unavailable
        3. Apply environment variable overrides

        All model references are validated against llm_config.MODEL_REGISTRY
        to ensure they are supported and properly configured.
        """
        # Try database first
        db_loaded = False
        try:
            self._load_from_database()
            db_loaded = True
            logger.info("Successfully loaded test plan agents from database")
        except Exception as e:
            logger.warning(
                f"Failed to load agents from database: {e}. "
                f"Using hardcoded defaults."
            )
            self._load_hardcoded_defaults()

        # Apply environment variable overrides
        self._apply_env_overrides()

        # Cross-section analysis window
        self.cross_section_window = int(os.getenv("CROSS_SECTION_WINDOW", "3"))

        logger.info(
            f"Agent Registry initialized (source: {'database' if db_loaded else 'hardcoded'}):\n"
            f"  - Actors: {len(self.actor_models)} ({', '.join(self.actor_models)})\n"
            f"  - Critic: {self.critic_model}\n"
            f"  - Final Critic: {self.final_critic_model}\n"
            f"  - Contradiction Detection: {self.enable_contradiction} ({self.contradiction_model})\n"
            f"  - Gap Analysis: {self.enable_gap_analysis} ({self.gap_analysis_model})\n"
            f"  - Cross-section window: {self.cross_section_window}"
        )

    def _load_from_database(self):
        """
        Load test plan agents from database.

        Raises:
            Exception: If database loading fails
        """
        from repositories.test_plan_agent_repository import TestPlanAgentRepository
        from core.database import SessionLocal

        repo = TestPlanAgentRepository()
        session = SessionLocal()

        try:
            # Load actor agents (can be multiple)
            actors = repo.get_by_type('actor', session)
            if actors:
                self.actor_agents_db = [self._agent_to_dict(a) for a in actors]

                # Determine how many actor instances to create
                # If ENV specifies count, use that; otherwise default to 3
                actor_count_env = os.getenv("ACTOR_AGENT_COUNT")
                if actor_count_env:
                    try:
                        actor_count = int(actor_count_env)
                    except ValueError:
                        actor_count = 3  # Default to 3
                else:
                    actor_count = 3  # Default to 3 parallel actors

                # Build actor models list
                # If we have multiple DB agents, use them in order
                # If we have fewer DB agents than needed, duplicate them cyclically
                self.actor_models = []
                for i in range(actor_count):
                    agent_index = i % len(self.actor_agents_db)
                    self.actor_models.append(self.actor_agents_db[agent_index]['model_name'])

                logger.info(f"Loaded {len(self.actor_agents_db)} actor agent template(s) from DB, creating {actor_count} instances")
            else:
                # No actors found, will use hardcoded
                raise ValueError("No actor agents found in database")

            # Load critic agent (single)
            critics = repo.get_by_type('critic', session)
            if critics:
                self.critic_agent_db = self._agent_to_dict(critics[0])
                self.critic_model = self.critic_agent_db['model_name']
            else:
                raise ValueError("No critic agent found in database")

            # Load contradiction detection agent (single)
            contradiction_agents = repo.get_by_type('contradiction', session)
            if contradiction_agents:
                self.contradiction_agent_db = self._agent_to_dict(contradiction_agents[0])
                self.contradiction_model = self.contradiction_agent_db['model_name']
            else:
                self.contradiction_model = "gpt-4"

            # Load gap analysis agent (single)
            gap_agents = repo.get_by_type('gap_analysis', session)
            if gap_agents:
                self.gap_analysis_agent_db = self._agent_to_dict(gap_agents[0])
                self.gap_analysis_model = self.gap_analysis_agent_db['model_name']
            else:
                self.gap_analysis_model = "gpt-4"

            # Final critic is same as critic for now (can be customized later)
            self.final_critic_model = self.critic_model

            # Enable features if agents exist
            self.enable_contradiction = contradiction_agents is not None and len(contradiction_agents) > 0
            self.enable_gap_analysis = gap_agents is not None and len(gap_agents) > 0

        finally:
            session.close()

    def _load_hardcoded_defaults(self):
        """
        Load hardcoded default agent configurations.

        This is a fallback when database is unavailable.
        """
        # Actor agent configuration
        try:
            count = int(os.getenv("ACTOR_AGENT_COUNT", "3"))
        except ValueError:
            count = 3
        base_model = os.getenv("ACTOR_BASE_MODEL", "gpt-4")

        # Validate base model
        is_valid, error = validate_model(base_model)
        if not is_valid:
            logger.warning(f"Invalid ACTOR_BASE_MODEL '{base_model}': {error}. Using gpt-4.")
            base_model = "gpt-4"

        self.actor_models = [base_model for _ in range(max(1, count))]

        # Critic models
        self.critic_model = self._validate_and_get_model(
            os.getenv("CRITIC_MODEL", "gpt-4"),
            "CRITIC_MODEL",
            "gpt-4"
        )
        self.final_critic_model = self._validate_and_get_model(
            os.getenv("FINAL_CRITIC_MODEL", self.critic_model),
            "FINAL_CRITIC_MODEL",
            self.critic_model
        )

        # Contradiction detection
        self.contradiction_model = self._validate_and_get_model(
            os.getenv("CONTRADICTION_AGENT_MODEL", "gpt-4"),
            "CONTRADICTION_AGENT_MODEL",
            "gpt-4"
        )
        self.enable_contradiction = os.getenv("ENABLE_CONTRADICTION_DETECTION", "true").lower() == "true"

        # Gap analysis
        self.gap_analysis_model = self._validate_and_get_model(
            os.getenv("GAP_ANALYSIS_MODEL", "gpt-4"),
            "GAP_ANALYSIS_MODEL",
            "gpt-4"
        )
        self.enable_gap_analysis = os.getenv("ENABLE_GAP_ANALYSIS", "true").lower() == "true"

    def _apply_env_overrides(self):
        """
        Apply environment variable overrides to database-loaded configuration.

        ENV vars take precedence over database configuration.
        """
        # Actor models override
        actor_models_env = os.getenv("ACTOR_MODELS")
        if actor_models_env:
            raw_models = [m.strip() for m in actor_models_env.split(",") if m.strip()]
            # Validate each model
            validated_models = []
            for model in raw_models:
                is_valid, error = validate_model(model)
                if is_valid:
                    validated_models.append(model)
                else:
                    logger.warning(f"Invalid actor model '{model}': {error}. Skipping.")

            if validated_models:
                self.actor_models = validated_models
                logger.info(f"ENV override: ACTOR_MODELS = {', '.join(validated_models)}")

        # Critic model override
        critic_env = os.getenv("CRITIC_MODEL")
        if critic_env:
            validated = self._validate_and_get_model(critic_env, "CRITIC_MODEL", self.critic_model)
            if validated != self.critic_model:
                self.critic_model = validated
                logger.info(f"ENV override: CRITIC_MODEL = {validated}")

        # Final critic override
        final_critic_env = os.getenv("FINAL_CRITIC_MODEL")
        if final_critic_env:
            validated = self._validate_and_get_model(final_critic_env, "FINAL_CRITIC_MODEL", self.final_critic_model)
            if validated != self.final_critic_model:
                self.final_critic_model = validated
                logger.info(f"ENV override: FINAL_CRITIC_MODEL = {validated}")

        # Contradiction model override
        contradiction_env = os.getenv("CONTRADICTION_AGENT_MODEL")
        if contradiction_env:
            validated = self._validate_and_get_model(contradiction_env, "CONTRADICTION_AGENT_MODEL", self.contradiction_model)
            if validated != self.contradiction_model:
                self.contradiction_model = validated
                logger.info(f"ENV override: CONTRADICTION_AGENT_MODEL = {validated}")

        # Gap analysis model override
        gap_env = os.getenv("GAP_ANALYSIS_MODEL")
        if gap_env:
            validated = self._validate_and_get_model(gap_env, "GAP_ANALYSIS_MODEL", self.gap_analysis_model)
            if validated != self.gap_analysis_model:
                self.gap_analysis_model = validated
                logger.info(f"ENV override: GAP_ANALYSIS_MODEL = {validated}")

        # Enable/disable overrides
        contradiction_enable_env = os.getenv("ENABLE_CONTRADICTION_DETECTION")
        if contradiction_enable_env:
            self.enable_contradiction = contradiction_enable_env.lower() == "true"
            logger.info(f"ENV override: ENABLE_CONTRADICTION_DETECTION = {self.enable_contradiction}")

        gap_enable_env = os.getenv("ENABLE_GAP_ANALYSIS")
        if gap_enable_env:
            self.enable_gap_analysis = gap_enable_env.lower() == "true"
            logger.info(f"ENV override: ENABLE_GAP_ANALYSIS = {self.enable_gap_analysis}")

    def _agent_to_dict(self, agent) -> Dict[str, Any]:
        """
        Convert a TestPlanAgent ORM object to a dictionary.

        Args:
            agent: TestPlanAgent ORM object

        Returns:
            Dictionary representation of the agent
        """
        return {
            'id': agent.id,
            'name': agent.name,
            'agent_type': agent.agent_type,
            'model_name': agent.model_name,
            'system_prompt': agent.system_prompt,
            'user_prompt_template': agent.user_prompt_template,
            'temperature': agent.temperature,
            'max_tokens': agent.max_tokens,
            'description': agent.description,
            'metadata': agent.agent_metadata,  # Map ORM attribute to API key
            'is_system_default': agent.is_system_default,
            'is_active': agent.is_active
        }

    def _validate_and_get_model(self, model_name: str, env_var_name: str, fallback: str) -> str:
        """
        Validate a model name against llm_config.MODEL_REGISTRY.

        Args:
            model_name: Model name to validate
            env_var_name: Name of environment variable (for logging)
            fallback: Fallback model if validation fails

        Returns:
            Valid model name (either provided or fallback)
        """
        is_valid, error = validate_model(model_name)
        if is_valid:
            return model_name
        else:
            logger.warning(
                f"Invalid {env_var_name} '{model_name}': {error}. "
                f"Using fallback: {fallback}"
            )
            return fallback

    def get_default_config(self, agent_type: AgentType) -> Dict[str, Any]:
        """
        Get default configuration for an agent type.

        Args:
            agent_type: Type of agent

        Returns:
            Default configuration dictionary
        """
        return self.DEFAULT_CONFIGS.get(agent_type, {})

    def create_agent_config(
        self,
        agent_type: AgentType,
        model_name: str = None,
        **kwargs
    ) -> AgentConfig:
        """
        Create an agent configuration with defaults.

        Args:
            agent_type: Type of agent
            model_name: LLM model to use (defaults from env if not provided)
            **kwargs: Override default configuration values

        Returns:
            AgentConfig instance
        """
        defaults = self.get_default_config(agent_type)

        # Use environment-configured model if not specified
        if model_name is None:
            if agent_type == AgentType.ACTOR:
                model_name = self.actor_models[0] if self.actor_models else "gpt-4"
            elif agent_type == AgentType.CRITIC:
                model_name = self.critic_model
            elif agent_type == AgentType.CONTRADICTION:
                model_name = self.contradiction_model
            elif agent_type == AgentType.GAP_ANALYSIS:
                model_name = self.gap_analysis_model
            elif agent_type == AgentType.FINAL_CRITIC:
                model_name = self.final_critic_model
            else:
                model_name = "gpt-4"

        return AgentConfig(
            agent_type=agent_type,
            model_name=model_name,
            temperature=kwargs.get('temperature', defaults.get('temperature', 0.7)),
            max_tokens=kwargs.get('max_tokens', defaults.get('max_tokens', 4000)),
            timeout=kwargs.get('timeout', defaults.get('timeout', 120)),
            enabled=kwargs.get('enabled', True),
            execution_mode=kwargs.get('execution_mode', defaults.get('execution_mode', ExecutionMode.SINGLE)),
            count=kwargs.get('count', defaults.get('default_count', 1)),
            metadata=kwargs.get('metadata', {})
        )

    def get_pipeline_config(self) -> List[PipelineStage]:
        """
        Get the configured pipeline stages.

        Returns:
            List of PipelineStage configurations
        """
        pipeline = list(self.DEFAULT_PIPELINE)

        # Apply environment-based enables/disables
        for stage in pipeline:
            if stage.agent_type == AgentType.CONTRADICTION:
                stage.enabled = self.enable_contradiction
            elif stage.agent_type == AgentType.GAP_ANALYSIS:
                stage.enabled = self.enable_gap_analysis

        return pipeline

    def get_actor_configs(self) -> List[AgentConfig]:
        """
        Get configurations for all actor agents.

        Returns:
            List of AgentConfig for actor agents
        """
        configs = []
        for model in self.actor_models:
            config = self.create_agent_config(
                agent_type=AgentType.ACTOR,
                model_name=model
            )
            configs.append(config)
        return configs

    def is_stage_enabled(self, agent_type: AgentType) -> bool:
        """
        Check if a specific agent stage is enabled.

        Args:
            agent_type: Type of agent to check

        Returns:
            True if enabled, False otherwise
        """
        if agent_type == AgentType.CONTRADICTION:
            return self.enable_contradiction
        elif agent_type == AgentType.GAP_ANALYSIS:
            return self.enable_gap_analysis
        else:
            return True  # Other stages always enabled

    def get_supported_models(self) -> List[str]:
        """
        Get list of all supported model IDs from llm_config.

        Returns:
            List of model IDs
        """
        return list(MODEL_REGISTRY.keys())

    def get_model_info(self, model_name: str) -> Optional[ModelConfig]:
        """
        Get detailed information about a model from llm_config.

        Args:
            model_name: Model name or ID

        Returns:
            ModelConfig if found, None otherwise
        """
        return get_model_config(model_name)

    def get_model_provider(self, model_name: str) -> Optional[str]:
        """
        Get the provider for a model (openai, anthropic, ollama).

        Args:
            model_name: Model name or ID

        Returns:
            Provider name if found, None otherwise
        """
        config = get_model_config(model_name)
        return config.provider if config else None

    def validate_agent_config(self, agent_config: AgentConfig) -> tuple[bool, str]:
        """
        Validate an agent configuration.

        Args:
            agent_config: Agent configuration to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate model
        is_valid, error = validate_model(agent_config.model_name)
        if not is_valid:
            return False, f"Invalid model: {error}"

        # Validate model has required API keys
        is_valid, error = llm_env.validate_model(agent_config.model_name)
        if not is_valid:
            return False, f"Model configuration error: {error}"

        # Validate parameters
        if agent_config.temperature < 0.0 or agent_config.temperature > 1.0:
            return False, "Temperature must be between 0.0 and 1.0"

        if agent_config.max_tokens < 1:
            return False, "Max tokens must be positive"

        if agent_config.timeout < 1:
            return False, "Timeout must be positive"

        return True, ""

    def get_actor_agent_prompts(self, index: int = 0) -> Optional[Dict[str, str]]:
        """
        Get prompts for a specific actor agent from database.

        Args:
            index: Index of actor agent (0-based)

        Returns:
            Dictionary with 'system_prompt' and 'user_prompt_template' keys,
            or None if not loaded from database
        """
        if self.actor_agents_db and index < len(self.actor_agents_db):
            agent = self.actor_agents_db[index]
            return {
                'system_prompt': agent['system_prompt'],
                'user_prompt_template': agent['user_prompt_template'],
                'temperature': agent['temperature'],
                'max_tokens': agent['max_tokens']
            }
        return None

    def get_critic_agent_prompts(self) -> Optional[Dict[str, str]]:
        """
        Get prompts for critic agent from database.

        Returns:
            Dictionary with prompt configuration, or None if not loaded from database
        """
        if self.critic_agent_db:
            return {
                'system_prompt': self.critic_agent_db['system_prompt'],
                'user_prompt_template': self.critic_agent_db['user_prompt_template'],
                'temperature': self.critic_agent_db['temperature'],
                'max_tokens': self.critic_agent_db['max_tokens']
            }
        return None

    def get_contradiction_agent_prompts(self) -> Optional[Dict[str, str]]:
        """
        Get prompts for contradiction detection agent from database.

        Returns:
            Dictionary with prompt configuration, or None if not loaded from database
        """
        if self.contradiction_agent_db:
            return {
                'system_prompt': self.contradiction_agent_db['system_prompt'],
                'user_prompt_template': self.contradiction_agent_db['user_prompt_template'],
                'temperature': self.contradiction_agent_db['temperature'],
                'max_tokens': self.contradiction_agent_db['max_tokens']
            }
        return None

    def get_gap_analysis_agent_prompts(self) -> Optional[Dict[str, str]]:
        """
        Get prompts for gap analysis agent from database.

        Returns:
            Dictionary with prompt configuration, or None if not loaded from database
        """
        if self.gap_analysis_agent_db:
            return {
                'system_prompt': self.gap_analysis_agent_db['system_prompt'],
                'user_prompt_template': self.gap_analysis_agent_db['user_prompt_template'],
                'temperature': self.gap_analysis_agent_db['temperature'],
                'max_tokens': self.gap_analysis_agent_db['max_tokens']
            }
        return None

    def is_using_database(self) -> bool:
        """
        Check if registry is using database-loaded agents.

        Returns:
            True if agents were loaded from database, False if using hardcoded defaults
        """
        return len(self.actor_agents_db) > 0 or self.critic_agent_db is not None


# Global registry instance
_agent_registry: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    """
    Get the global agent registry instance (singleton pattern).

    Returns:
        AgentRegistry instance
    """
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = AgentRegistry()
    return _agent_registry
