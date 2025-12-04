"""
Base Agent Class for Test Plan Generation

Defines the interface that all test plan generation agents must implement.
Provides common functionality for agent execution, result handling, and error management.

This follows the same pattern as other core classes in the application.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging
import time

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """
    Context information passed to agents during execution.

    Attributes:
        section_title: Title of the section being processed
        section_content: Content of the section
        pipeline_id: Unique pipeline identifier
        section_idx: Section index in the document
        metadata: Additional context metadata
        previous_results: Results from previous agent executions
    """
    section_title: str
    section_content: str
    pipeline_id: str
    section_idx: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    previous_results: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """
    Base result from any agent execution.

    Attributes:
        agent_id: Unique agent instance identifier
        agent_type: Type of agent (actor, critic, contradiction, etc.)
        agent_name: Human-readable agent name
        model_name: LLM model used
        section_title: Section processed
        output: Raw output from agent
        processing_time: Time taken in seconds
        timestamp: ISO format timestamp
        success: Whether execution succeeded
        error_message: Error message if failed
        metadata: Additional result metadata
    """
    agent_id: str
    agent_type: str
    agent_name: str
    model_name: str
    section_title: str
    output: str
    processing_time: float
    timestamp: str
    success: bool
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseTestPlanAgent(ABC):
    """
    Abstract base class for all test plan generation agents.

    All agents must implement:
    - get_system_prompt(): System prompt for LLM
    - get_user_prompt(): User prompt for LLM
    - parse_response(): Parse LLM response into structured data
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        agent_name: str,
        model_name: str,
        llm_service: Any,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize base agent.

        Args:
            agent_id: Unique identifier for this agent instance
            agent_type: Type of agent (e.g., 'actor', 'critic')
            agent_name: Human-readable name
            model_name: LLM model to use (e.g., 'gpt-4')
            llm_service: LLM service instance
            config: Optional configuration dictionary
        """
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.agent_name = agent_name
        self.model_name = model_name
        self.llm_service = llm_service
        self.config = config or {}

        # LLM parameters
        self.temperature = self.config.get('temperature', 0.7)
        self.max_tokens = self.config.get('max_tokens', 4000)
        self.timeout = self.config.get('timeout', 120)

    @abstractmethod
    def get_system_prompt(self, context: AgentContext) -> str:
        """Generate system prompt for this agent."""
        pass

    @abstractmethod
    def get_user_prompt(self, context: AgentContext) -> str:
        """Generate user prompt for this agent."""
        pass

    @abstractmethod
    def parse_response(self, response: str, context: AgentContext) -> Any:
        """Parse LLM response into structured data."""
        pass

    def execute(self, context: AgentContext) -> AgentResult:
        """
        Execute agent with given context.

        Args:
            context: Agent execution context

        Returns:
            AgentResult with execution results
        """
        start_time = time.time()

        try:
            if not self.validate_context(context):
                raise ValueError("Invalid context provided to agent")

            # Generate prompts
            system_prompt = self.get_system_prompt(context)
            user_prompt = self.get_user_prompt(context)

            logger.info(
                f"Executing {self.agent_type} agent '{self.agent_name}' "
                f"on section: {context.section_title}"
            )

            # Call LLM
            response = self._invoke_llm(system_prompt, user_prompt)

            # Parse response
            parsed_output = self.parse_response(response, context)

            # Build result
            processing_time = time.time() - start_time

            result = AgentResult(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                agent_name=self.agent_name,
                model_name=self.model_name,
                section_title=context.section_title,
                output=response,
                processing_time=processing_time,
                timestamp=datetime.now().isoformat(),
                success=True,
                metadata={
                    'parsed_output': parsed_output,
                    'temperature': self.temperature,
                    'max_tokens': self.max_tokens
                }
            )

            logger.info(
                f"{self.agent_type} agent '{self.agent_name}' "
                f"completed in {processing_time:.2f}s"
            )
            return result

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"{self.agent_type} agent '{self.agent_name}' failed: {e}")

            return AgentResult(
                agent_id=self.agent_id,
                agent_type=self.agent_type,
                agent_name=self.agent_name,
                model_name=self.model_name,
                section_title=context.section_title,
                output="",
                processing_time=processing_time,
                timestamp=datetime.now().isoformat(),
                success=False,
                error_message=str(e)
            )

    def _invoke_llm(self, system_prompt: str, user_prompt: str) -> str:
        """
        Invoke LLM with prompts using the LLM service.

        Args:
            system_prompt: System prompt
            user_prompt: User prompt

        Returns:
            LLM response text
        """
        try:
            # Try query_direct method (used in multi_agent_test_plan_service)
            if hasattr(self.llm_service, 'query_direct'):
                # Combine prompts for query_direct
                combined_prompt = f"{system_prompt}\n\n{user_prompt}"
                response = self.llm_service.query_direct(
                    model_name=self.model_name,
                    query=combined_prompt
                )[0]
                return response

            # Try invoke_llm_unified method
            elif hasattr(self.llm_service, 'invoke_llm_unified'):
                response = self.llm_service.invoke_llm_unified(
                    model_name=self.model_name,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )
                return response

            else:
                raise AttributeError(
                    "LLM service does not have expected methods "
                    "(query_direct or invoke_llm_unified)"
                )

        except Exception as e:
            logger.error(f"LLM invocation failed: {e}")
            raise

    def validate_context(self, context: AgentContext) -> bool:
        """
        Validate that context has required information.

        Args:
            context: Agent execution context

        Returns:
            True if context is valid
        """
        if not context.section_title or not context.section_title.strip():
            logger.error("Context missing section_title")
            return False

        if not context.section_content or not context.section_content.strip():
            logger.error("Context missing section_content")
            return False

        return True
