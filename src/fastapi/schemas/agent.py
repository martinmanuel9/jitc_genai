"""
Agent-related Pydantic schemas.

This module contains schemas for:
- Agent creation and updates
- Agent responses
- Agent listings
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any


class CreateAgentRequest(BaseModel):
    """
    Request schema for creating a new compliance agent.

    Attributes:
        name: Unique agent name
        model_name: LLM model identifier (e.g., 'gpt-4', 'claude-3')
        system_prompt: System-level instruction defining agent's role
        user_prompt_template: Template for user prompts (must contain {data_sample})
    """
    name: str = Field(..., min_length=1, max_length=200, description="Agent name")
    model_name: str = Field(..., description="Model to use for this agent")
    system_prompt: str = Field(..., min_length=10, description="System prompt defining the agent's role")
    user_prompt_template: str = Field(..., min_length=10, description="User prompt template with {data_sample} placeholder")


class UpdateAgentRequest(BaseModel):
    """
    Request schema for updating an existing agent.

    All fields are optional - only provided fields will be updated.

    Attributes:
        name: Updated agent name
        model_name: Updated model identifier
        system_prompt: Updated system prompt
        user_prompt_template: Updated prompt template (must contain {data_sample})
        temperature: LLM temperature (0.0-1.0)
        max_tokens: Maximum tokens for response (100-4000)
        is_active: Whether agent is active
    """
    name: Optional[str] = Field(None, min_length=3, max_length=200, description="Updated agent name")
    model_name: Optional[str] = Field(None, description="Updated model name")
    system_prompt: Optional[str] = Field(None, min_length=10, description="Updated system prompt")
    user_prompt_template: Optional[str] = Field(None, min_length=10, description="Updated user prompt template")
    temperature: Optional[float] = Field(None, ge=0.0, le=1.0, description="Updated temperature")
    max_tokens: Optional[int] = Field(None, ge=100, le=4000, description="Updated max tokens")
    is_active: Optional[bool] = Field(None, description="Whether agent is active")

    @field_validator('user_prompt_template')
    def validate_prompt_template(cls, v):
        """Ensure user_prompt_template contains {data_sample} placeholder."""
        if v is not None and '{data_sample}' not in v:
            raise ValueError('User prompt template must contain {data_sample} placeholder')
        return v


class CreateAgentResponse(BaseModel):
    """
    Response schema for agent creation.

    Attributes:
        message: Success message
        agent_id: ID of created agent
        agent_name: Name of created agent
    """
    message: str
    agent_id: int
    agent_name: str


class UpdateAgentResponse(BaseModel):
    """
    Response schema for agent updates.

    Attributes:
        message: Success message
        agent_id: ID of updated agent
        agent_name: Name of updated agent
        updated_fields: List of fields that were updated
    """
    message: str
    agent_id: int
    agent_name: str
    updated_fields: List[str]


class AgentResponse(BaseModel):
    """
    Individual agent response in multi-agent scenarios.

    Attributes:
        agent_id: Agent identifier
        agent_name: Agent name
        model_name: Model used
        response: Agent's response text
        processing_time: Time taken to process (seconds)
    """
    agent_id: int
    agent_name: str
    model_name: str
    response: str
    processing_time: Optional[float] = None


class GetAgentsResponse(BaseModel):
    """
    Response schema for listing agents.

    Attributes:
        agents: List of agent dictionaries with full details
        total_count: Total number of agents
    """
    agents: List[Dict[str, Any]]
    total_count: int


class AgentPerformanceMetrics(BaseModel):
    """
    Agent performance metrics.

    Attributes:
        agent_id: Agent identifier
        agent_name: Agent name
        total_queries: Total queries processed
        avg_response_time_ms: Average response time (milliseconds)
        success_rate: Success rate (0.0-1.0)
    """
    agent_id: int
    agent_name: str
    total_queries: int
    avg_response_time_ms: float
    success_rate: float
