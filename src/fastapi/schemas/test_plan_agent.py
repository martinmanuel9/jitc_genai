"""
Test Plan Agent Pydantic Schemas

API contract schemas for test plan agent endpoints.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime


class TestPlanAgentBase(BaseModel):
    """Base schema for test plan agent"""
    name: str = Field(..., min_length=1, max_length=200, description="Agent name")
    agent_type: str = Field(..., description="Type of agent (actor, critic, contradiction, gap_analysis)")
    workflow_type: Optional[str] = Field(default="general", description="Workflow category (document_analysis, test_plan_generation, general)")
    model_name: str = Field(..., description="LLM model identifier (e.g., 'gpt-4', 'claude-3-5-sonnet')")
    system_prompt: str = Field(..., min_length=10, description="System-level instruction prompt")
    user_prompt_template: str = Field(..., min_length=10, description="Template for user prompts")
    temperature: float = Field(default=0.7, ge=0.0, le=1.0, description="LLM temperature")
    max_tokens: int = Field(default=4000, ge=100, le=32000, description="Maximum tokens for response")
    description: Optional[str] = Field(None, description="Human-readable description")
    metadata: Optional[Dict[str, Any]] = Field(default={}, validation_alias="agent_metadata", serialization_alias="metadata", description="Additional configuration")

    @field_validator('agent_type')
    @classmethod
    def validate_agent_type(cls, v):
        """Validate agent type - supports all unified agent types"""
        valid_types = ['actor', 'critic', 'contradiction', 'gap_analysis', 'general', 'rule_development', 'custom', 'compliance']
        if v not in valid_types:
            raise ValueError(f"agent_type must be one of: {', '.join(valid_types)}")
        return v

    @field_validator('workflow_type')
    @classmethod
    def validate_workflow_type(cls, v):
        """Validate workflow type - distinguishes agent purpose"""
        if v is not None:
            valid_types = ['document_analysis', 'test_plan_generation', 'general']
            if v not in valid_types:
                raise ValueError(f"workflow_type must be one of: {', '.join(valid_types)}")
        return v

    # Removed strict placeholder validation - different agent types use different placeholders
    # Document Analysis agents use {data_sample}
    # Test Plan Generation agents use {section_title}, {section_content}, {actor_outputs}, etc.
    # General agents use flexible placeholders


class CreateTestPlanAgentRequest(TestPlanAgentBase):
    """Request schema for creating a test plan agent"""
    workflow_type: str = Field(..., description="Workflow category (document_analysis, test_plan_generation, general)")
    is_system_default: bool = Field(default=False, description="Whether this is a system default agent")
    is_active: bool = Field(default=True, description="Whether agent is active")
    created_by: Optional[str] = Field(None, description="User creating the agent")


class UpdateTestPlanAgentRequest(BaseModel):
    """Request schema for updating a test plan agent"""
    name: Optional[str] = Field(None, min_length=1, max_length=200, description="Agent name")
    workflow_type: Optional[str] = Field(None, description="Workflow category")
    model_name: Optional[str] = Field(None, description="LLM model identifier")
    system_prompt: Optional[str] = Field(None, min_length=10, description="System prompt")
    user_prompt_template: Optional[str] = Field(None, min_length=10, description="User prompt template")
    temperature: Optional[float] = Field(None, ge=0.0, le=1.0, description="LLM temperature")
    max_tokens: Optional[int] = Field(None, ge=100, le=32000, description="Maximum tokens")
    is_active: Optional[bool] = Field(None, description="Whether agent is active")
    description: Optional[str] = Field(None, description="Description")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional configuration")

    @field_validator('workflow_type')
    @classmethod
    def validate_workflow_type(cls, v):
        """Validate workflow type if provided"""
        if v is not None:
            valid_types = ['document_analysis', 'test_plan_generation', 'general']
            if v not in valid_types:
                raise ValueError(f"workflow_type must be one of: {', '.join(valid_types)}")
        return v

    # Removed strict placeholder validation - see TestPlanAgentBase for explanation


class TestPlanAgentResponse(TestPlanAgentBase):
    """Response schema for test plan agent"""
    id: int
    is_system_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]

    # Use Pydantic v2 ConfigDict for configuration
    # Note: metadata field is aliased to agent_metadata to match ORM attribute
    model_config = ConfigDict(
        from_attributes=True,  # Enable ORM mode
        populate_by_name=True  # Allow population by field name or alias
    )


class TestPlanAgentListResponse(BaseModel):
    """Response schema for list of agents"""
    agents: List[TestPlanAgentResponse]
    total_count: int
    agent_type_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of agents by type"
    )


class CloneAgentRequest(BaseModel):
    """Request schema for cloning an agent"""
    new_name: str = Field(..., min_length=1, max_length=200, description="Name for cloned agent")
    created_by: Optional[str] = Field(None, description="User creating the clone")


class CloneAgentResponse(BaseModel):
    """Response schema for clone operation"""
    message: str
    source_agent_id: int
    cloned_agent: TestPlanAgentResponse


class DeleteAgentResponse(BaseModel):
    """Response schema for delete operation"""
    message: str
    agent_id: int
    agent_name: str
    soft_delete: bool


class AgentTypeInfo(BaseModel):
    """Information about an agent type"""
    agent_type: str
    display_name: str
    description: str
    default_temperature: float
    default_max_tokens: int
    active_count: int
    system_default_count: int


class AgentTypesResponse(BaseModel):
    """Response schema for agent type information"""
    agent_types: List[AgentTypeInfo]


class SearchAgentsRequest(BaseModel):
    """Request schema for searching agents"""
    search_term: str = Field(..., min_length=1, description="Search term")
    agent_type: Optional[str] = Field(None, description="Filter by agent type")
    include_inactive: bool = Field(default=False, description="Include inactive agents")


class ActivateAgentRequest(BaseModel):
    """Request schema for activating/deactivating an agent"""
    is_active: bool = Field(..., description="Whether to activate (True) or deactivate (False) the agent")


class AgentValidationResponse(BaseModel):
    """Response schema for agent validation"""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    model_info: Optional[Dict[str, Any]] = None


class BulkOperationRequest(BaseModel):
    """Request schema for bulk operations"""
    agent_ids: List[int] = Field(..., min_items=1, description="List of agent IDs")
    operation: str = Field(..., description="Operation to perform (activate, deactivate, delete)")

    @field_validator('operation')
    @classmethod
    def validate_operation(cls, v):
        """Validate operation type"""
        valid_operations = ['activate', 'deactivate', 'delete']
        if v not in valid_operations:
            raise ValueError(f"operation must be one of: {', '.join(valid_operations)}")
        return v


class BulkOperationResponse(BaseModel):
    """Response schema for bulk operations"""
    message: str
    successful_count: int
    failed_count: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)
