"""
Agent Set Pydantic Schemas

API contract schemas for agent set orchestration endpoints.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime


class StageConfig(BaseModel):
    """Configuration for a single pipeline stage"""
    stage_name: str = Field(..., description="Name of the stage (e.g., 'actor', 'critic', 'qa')")
    agent_ids: List[int] = Field(..., min_length=1, description="List of agent IDs to execute in this stage")
    execution_mode: str = Field(..., description="Execution mode: 'parallel', 'sequential', or 'batched'")
    description: Optional[str] = Field(None, description="Human-readable description of this stage")
    batch_size: Optional[int] = Field(None, ge=1, description="Batch size for batched execution mode")

    @field_validator('execution_mode')
    @classmethod
    def validate_execution_mode(cls, v):
        """Validate execution mode"""
        valid_modes = ['parallel', 'sequential', 'batched']
        if v not in valid_modes:
            raise ValueError(f"execution_mode must be one of: {', '.join(valid_modes)}")
        return v


class SetConfig(BaseModel):
    """Complete set configuration structure"""
    stages: List[StageConfig] = Field(..., min_length=1, description="List of pipeline stages")


class AgentSetBase(BaseModel):
    """Base schema for agent set"""
    name: str = Field(..., min_length=1, max_length=255, description="Unique set name")
    description: Optional[str] = Field(None, description="Human-readable description of the set's purpose")
    set_type: str = Field(default='sequence', description="Type of set: 'sequence' or 'parallel'")
    set_config: Dict[str, Any] = Field(..., description="JSON configuration defining stages and agents")

    @field_validator('set_type')
    @classmethod
    def validate_set_type(cls, v):
        """Validate set type"""
        valid_types = ['sequence', 'parallel', 'custom']
        if v not in valid_types:
            raise ValueError(f"set_type must be one of: {', '.join(valid_types)}")
        return v

    @field_validator('set_config')
    @classmethod
    def validate_set_config(cls, v):
        """Validate set_config structure"""
        if not isinstance(v, dict):
            raise ValueError("set_config must be a dictionary")

        if 'stages' not in v:
            raise ValueError("set_config must contain 'stages' key")

        if not isinstance(v['stages'], list) or len(v['stages']) == 0:
            raise ValueError("set_config.stages must be a non-empty list")

        # Validate each stage
        for idx, stage in enumerate(v['stages']):
            if not isinstance(stage, dict):
                raise ValueError(f"Stage {idx} must be a dictionary")

            required_fields = ['stage_name', 'agent_ids', 'execution_mode']
            for field in required_fields:
                if field not in stage:
                    raise ValueError(f"Stage {idx} missing required field: {field}")

            if not isinstance(stage['agent_ids'], list) or len(stage['agent_ids']) == 0:
                raise ValueError(f"Stage {idx} agent_ids must be a non-empty list")

            valid_modes = ['parallel', 'sequential', 'batched']
            if stage['execution_mode'] not in valid_modes:
                raise ValueError(f"Stage {idx} execution_mode must be one of: {', '.join(valid_modes)}")

        return v


class CreateAgentSetRequest(AgentSetBase):
    """Request schema for creating an agent set"""
    is_system_default: bool = Field(default=False, description="Whether this is a system default set")
    is_active: bool = Field(default=True, description="Whether set is active")
    created_by: Optional[str] = Field(None, description="User creating the set")


class UpdateAgentSetRequest(BaseModel):
    """Request schema for updating an agent set"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Set name")
    description: Optional[str] = Field(None, description="Description")
    set_type: Optional[str] = Field(None, description="Set type")
    set_config: Optional[Dict[str, Any]] = Field(None, description="Set configuration")
    is_active: Optional[bool] = Field(None, description="Whether set is active")
    created_by: Optional[str] = Field(None, description="User modifying the set")

    @field_validator('set_type')
    @classmethod
    def validate_set_type(cls, v):
        """Validate set type if provided"""
        if v is not None:
            valid_types = ['sequence', 'parallel', 'custom']
            if v not in valid_types:
                raise ValueError(f"set_type must be one of: {', '.join(valid_types)}")
        return v

    @field_validator('set_config')
    @classmethod
    def validate_set_config(cls, v):
        """Validate set_config structure if provided"""
        if v is not None:
            # Run same validation as AgentSetBase
            if not isinstance(v, dict):
                raise ValueError("set_config must be a dictionary")

            if 'stages' not in v:
                raise ValueError("set_config must contain 'stages' key")

            if not isinstance(v['stages'], list) or len(v['stages']) == 0:
                raise ValueError("set_config.stages must be a non-empty list")

            for idx, stage in enumerate(v['stages']):
                if not isinstance(stage, dict):
                    raise ValueError(f"Stage {idx} must be a dictionary")

                required_fields = ['stage_name', 'agent_ids', 'execution_mode']
                for field in required_fields:
                    if field not in stage:
                        raise ValueError(f"Stage {idx} missing required field: {field}")

        return v


class AgentSetResponse(AgentSetBase):
    """Response schema for agent set"""
    id: int
    is_system_default: bool
    is_active: bool
    usage_count: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )


class AgentSetListResponse(BaseModel):
    """Response schema for list of agent sets"""
    agent_sets: List[AgentSetResponse]
    total_count: int
    set_type_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of sets by type"
    )


class CloneAgentSetRequest(BaseModel):
    """Request schema for cloning an agent set"""
    new_name: str = Field(..., min_length=1, max_length=255, description="Name for cloned set")
    created_by: Optional[str] = Field(None, description="User creating the clone")


class CloneAgentSetResponse(BaseModel):
    """Response schema for clone operation"""
    message: str
    source_set_id: int
    cloned_set: AgentSetResponse


class DeleteAgentSetResponse(BaseModel):
    """Response schema for delete operation"""
    message: str
    set_id: int
    set_name: str
    soft_delete: bool


class AgentSetUsageResponse(BaseModel):
    """Response schema for incrementing usage count"""
    message: str
    set_id: int
    set_name: str
    usage_count: int


class AgentSetValidationResponse(BaseModel):
    """Response schema for agent set validation"""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    missing_agents: List[int] = Field(default_factory=list, description="Agent IDs referenced but not found")
    inactive_agents: List[int] = Field(default_factory=list, description="Agent IDs referenced but inactive")


class SearchAgentSetsRequest(BaseModel):
    """Request schema for searching agent sets"""
    search_term: str = Field(..., min_length=1, description="Search term")
    set_type: Optional[str] = Field(None, description="Filter by set type")
    include_inactive: bool = Field(default=False, description="Include inactive sets")


class BulkAgentSetOperationRequest(BaseModel):
    """Request schema for bulk operations on agent sets"""
    set_ids: List[int] = Field(..., min_length=1, description="List of set IDs")
    operation: str = Field(..., description="Operation to perform (activate, deactivate, delete)")

    @field_validator('operation')
    @classmethod
    def validate_operation(cls, v):
        """Validate operation type"""
        valid_operations = ['activate', 'deactivate', 'delete']
        if v not in valid_operations:
            raise ValueError(f"operation must be one of: {', '.join(valid_operations)}")
        return v


class BulkAgentSetOperationResponse(BaseModel):
    """Response schema for bulk operations"""
    message: str
    successful_count: int
    failed_count: int
    errors: List[Dict[str, Any]] = Field(default_factory=list)
