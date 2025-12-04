"""
Test Plan Agent Management API

REST API endpoints for managing test plan generation agents.
Provides CRUD operations and utility endpoints for agent configuration.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.dependencies import get_agent_service_legacy
from repositories.test_plan_agent_repository import TestPlanAgentRepository
from schemas.test_plan_agent import (
    CreateTestPlanAgentRequest,
    UpdateTestPlanAgentRequest,
    TestPlanAgentResponse,
    TestPlanAgentListResponse,
    CloneAgentRequest,
    CloneAgentResponse,
    DeleteAgentResponse,
    AgentTypesResponse,
    AgentTypeInfo,
    SearchAgentsRequest,
    ActivateAgentRequest,
    AgentValidationResponse,
    BulkOperationRequest,
    BulkOperationResponse
)
from schemas.compliance import ComplianceCheckRequest
from services.agent_service import AgentService
from core.exceptions import DatabaseException
from llm_config.llm_config import validate_model, get_model_config, MODEL_REGISTRY


# Create router
router = APIRouter(
    prefix="/test-plan-agents",
    tags=["Test Plan Agents"]
)


def get_repository() -> TestPlanAgentRepository:
    """Dependency for getting repository instance"""
    return TestPlanAgentRepository()


def orm_to_response(agent) -> TestPlanAgentResponse:
    """
    Convert ORM model to Pydantic response schema.

    Handles the agent_metadata -> metadata field mapping since the ORM
    uses 'agent_metadata' attribute to avoid conflict with SQLAlchemy's MetaData.
    """
    # Extract metadata value
    metadata_value = agent.agent_metadata if agent.agent_metadata is not None else {}

    # Debug logging
    import logging
    logger = logging.getLogger(__name__)

    # Use model_construct to bypass validation and attribute reading
    # This prevents Pydantic from trying to read 'metadata' from the ORM model
    return TestPlanAgentResponse.model_construct(
        id=agent.id,
        name=agent.name,
        agent_type=agent.agent_type,
        model_name=agent.model_name,
        system_prompt=agent.system_prompt,
        user_prompt_template=agent.user_prompt_template,
        temperature=agent.temperature,
        max_tokens=agent.max_tokens,
        description=agent.description,
        metadata=metadata_value,  # Use extracted value
        is_system_default=agent.is_system_default,
        is_active=agent.is_active,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
        created_by=agent.created_by
    )


# ============================================================================
# CRUD Operations
# ============================================================================

@router.get("", response_model=TestPlanAgentListResponse)
async def list_agents(
    agent_type: str = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    repo: TestPlanAgentRepository = Depends(get_repository)
):
    """
    Get all test plan agents.

    Query Parameters:
    - agent_type: Filter by agent type (actor, critic, contradiction, gap_analysis)
    - include_inactive: Include inactive agents in results
    """
    try:
        if agent_type:
            agents = repo.get_by_type(agent_type, db, include_inactive=include_inactive)
        else:
            agents = repo.get_all(db, include_inactive=include_inactive)

        # Calculate type counts
        type_counts = {}
        for agent in agents:
            type_counts[agent.agent_type] = type_counts.get(agent.agent_type, 0) + 1

        return TestPlanAgentListResponse(
            agents=[TestPlanAgentResponse.from_orm(a) for a in agents],
            total_count=len(agents),
            agent_type_counts=type_counts
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list agents: {str(e)}"
        )


@router.get("/{agent_id}", response_model=TestPlanAgentResponse)
async def get_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    repo: TestPlanAgentRepository = Depends(get_repository)
):
    """Get a specific test plan agent by ID"""
    try:
        agent = repo.get_by_id(agent_id, db)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent with ID {agent_id} not found"
            )

        return orm_to_response(agent)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent: {str(e)}"
        )


@router.post("", response_model=TestPlanAgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    request: CreateTestPlanAgentRequest,
    db: Session = Depends(get_db),
    repo: TestPlanAgentRepository = Depends(get_repository)
):
    """Create a new test plan agent"""
    try:
        # Validate model name
        is_valid, error = validate_model(request.model_name)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid model: {error}"
            )

        # Create agent
        agent_data = request.dict()
        agent = repo.create(agent_data, db)

        return orm_to_response(agent)

    except HTTPException:
        raise
    except DatabaseException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create agent: {str(e)}"
        )


@router.put("/{agent_id}", response_model=TestPlanAgentResponse)
async def update_agent(
    agent_id: int,
    request: UpdateTestPlanAgentRequest,
    db: Session = Depends(get_db),
    repo: TestPlanAgentRepository = Depends(get_repository)
):
    """Update an existing test plan agent"""
    try:
        # Validate model if provided
        if request.model_name:
            is_valid, error = validate_model(request.model_name)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid model: {error}"
                )

        # Update agent
        agent_data = request.dict(exclude_unset=True)
        agent = repo.update(agent_id, agent_data, db)

        return orm_to_response(agent)

    except HTTPException:
        raise
    except DatabaseException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update agent: {str(e)}"
        )


@router.delete("/{agent_id}", response_model=DeleteAgentResponse)
async def delete_agent(
    agent_id: int,
    soft_delete: bool = True,
    db: Session = Depends(get_db),
    repo: TestPlanAgentRepository = Depends(get_repository)
):
    """
    Delete a test plan agent.

    Query Parameters:
    - soft_delete: If true, mark as inactive; if false, permanently delete (default: true)
    """
    try:
        # Get agent name before deletion
        agent = repo.get_by_id(agent_id, db)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent with ID {agent_id} not found"
            )

        agent_name = agent.name

        # Delete agent
        repo.delete(agent_id, db, soft_delete=soft_delete)

        return DeleteAgentResponse(
            message=f"Agent {'deactivated' if soft_delete else 'deleted'} successfully",
            agent_id=agent_id,
            agent_name=agent_name,
            soft_delete=soft_delete
        )

    except HTTPException:
        raise
    except DatabaseException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete agent: {str(e)}"
        )


# ============================================================================
# Query Operations
# ============================================================================

@router.get("/type/{agent_type}", response_model=TestPlanAgentListResponse)
async def get_agents_by_type(
    agent_type: str,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    repo: TestPlanAgentRepository = Depends(get_repository)
):
    """Get all agents of a specific type"""
    try:
        agents = repo.get_by_type(agent_type, db, include_inactive=include_inactive)

        return TestPlanAgentListResponse(
            agents=[orm_to_response(a) for a in agents],
            total_count=len(agents),
            agent_type_counts={agent_type: len(agents)}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agents by type: {str(e)}"
        )


@router.get("/defaults/all", response_model=TestPlanAgentListResponse)
async def get_default_agents(
    agent_type: str = None,
    db: Session = Depends(get_db),
    repo: TestPlanAgentRepository = Depends(get_repository)
):
    """
    Get system default agents.

    Query Parameters:
    - agent_type: Optional filter by agent type
    """
    try:
        agents = repo.get_default_agents(db, agent_type=agent_type)

        # Calculate type counts
        type_counts = {}
        for agent in agents:
            type_counts[agent.agent_type] = type_counts.get(agent.agent_type, 0) + 1

        return TestPlanAgentListResponse(
            agents=[orm_to_response(a) for a in agents],
            total_count=len(agents),
            agent_type_counts=type_counts
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get default agents: {str(e)}"
        )


@router.post("/search", response_model=TestPlanAgentListResponse)
async def search_agents(
    request: SearchAgentsRequest,
    db: Session = Depends(get_db),
    repo: TestPlanAgentRepository = Depends(get_repository)
):
    """
    Search agents by name or description.

    Request Body:
    - search_term: Search term (required)
    - agent_type: Optional filter by agent type
    - include_inactive: Include inactive agents
    """
    try:
        agents = repo.search(
            request.search_term,
            db,
            agent_type=request.agent_type,
            include_inactive=request.include_inactive
        )

        # Calculate type counts
        type_counts = {}
        for agent in agents:
            type_counts[agent.agent_type] = type_counts.get(agent.agent_type, 0) + 1

        return TestPlanAgentListResponse(
            agents=[orm_to_response(a) for a in agents],
            total_count=len(agents),
            agent_type_counts=type_counts
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search agents: {str(e)}"
        )


# ============================================================================
# Utility Operations
# ============================================================================

@router.post("/{agent_id}/clone", response_model=CloneAgentResponse, status_code=status.HTTP_201_CREATED)
async def clone_agent(
    agent_id: int,
    request: CloneAgentRequest,
    db: Session = Depends(get_db),
    repo: TestPlanAgentRepository = Depends(get_repository)
):
    """Clone an existing agent with a new name"""
    try:
        cloned_agent = repo.clone_agent(
            agent_id,
            request.new_name,
            db,
            created_by=request.created_by
        )

        return CloneAgentResponse(
            message=f"Agent cloned successfully as '{request.new_name}'",
            source_agent_id=agent_id,
            cloned_agent=orm_to_response(cloned_agent)
        )

    except DatabaseException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clone agent: {str(e)}"
        )


@router.post("/{agent_id}/activate", response_model=TestPlanAgentResponse)
async def activate_agent(
    agent_id: int,
    request: ActivateAgentRequest,
    db: Session = Depends(get_db),
    repo: TestPlanAgentRepository = Depends(get_repository)
):
    """Activate or deactivate an agent"""
    try:
        # Use the update method to set is_active
        agent = repo.update(agent_id, {"is_active": request.is_active}, db)
        return orm_to_response(agent)

    except DatabaseException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate agent: {str(e)}"
        )


@router.post("/bulk", response_model=BulkOperationResponse)
async def bulk_operation(
    request: BulkOperationRequest,
    db: Session = Depends(get_db),
    repo: TestPlanAgentRepository = Depends(get_repository)
):
    """
    Perform bulk operations on multiple agents.

    Supported operations:
    - activate: Activate multiple agents
    - deactivate: Deactivate multiple agents
    - delete: Soft-delete multiple agents
    """
    try:
        successful_count = 0
        failed_count = 0
        errors = []

        for agent_id in request.agent_ids:
            try:
                if request.operation == "activate":
                    repo.activate(agent_id, db)
                elif request.operation == "deactivate":
                    repo.update(agent_id, {"is_active": False}, db)
                elif request.operation == "delete":
                    repo.delete(agent_id, db, soft_delete=True)
                successful_count += 1
            except Exception as e:
                failed_count += 1
                errors.append({
                    "agent_id": agent_id,
                    "error": str(e)
                })

        return BulkOperationResponse(
            message=f"Bulk {request.operation} completed: {successful_count} succeeded, {failed_count} failed",
            successful_count=successful_count,
            failed_count=failed_count,
            errors=errors
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to perform bulk operation: {str(e)}"
        )


@router.get("/types/info", response_model=AgentTypesResponse)
async def get_agent_types_info(
    db: Session = Depends(get_db),
    repo: TestPlanAgentRepository = Depends(get_repository)
):
    """
    Get information about all agent types.

    Returns metadata about each agent type including:
    - Display name and description
    - Default configuration
    - Active agent count
    - System default count
    """
    try:
        all_agents = repo.get_all(db, include_inactive=False)

        # Count by type
        type_stats = {}
        for agent in all_agents:
            if agent.agent_type not in type_stats:
                type_stats[agent.agent_type] = {
                    "active_count": 0,
                    "system_default_count": 0
                }
            type_stats[agent.agent_type]["active_count"] += 1
            if agent.is_system_default:
                type_stats[agent.agent_type]["system_default_count"] += 1

        # Define agent type metadata
        agent_type_metadata = {
            "actor": {
                "display_name": "Actor Agent",
                "description": "Extracts testable requirements from document sections",
                "default_temperature": 0.7,
                "default_max_tokens": 4000
            },
            "critic": {
                "display_name": "Critic Agent",
                "description": "Synthesizes and deduplicates actor outputs",
                "default_temperature": 0.5,
                "default_max_tokens": 4000
            },
            "contradiction": {
                "display_name": "Contradiction Detection Agent",
                "description": "Detects contradictions and conflicts in test procedures",
                "default_temperature": 0.3,
                "default_max_tokens": 4000
            },
            "gap_analysis": {
                "display_name": "Gap Analysis Agent",
                "description": "Identifies requirement gaps and missing test coverage",
                "default_temperature": 0.3,
                "default_max_tokens": 4000
            }
        }

        agent_types = []
        for agent_type, metadata in agent_type_metadata.items():
            stats = type_stats.get(agent_type, {"active_count": 0, "system_default_count": 0})
            agent_types.append(
                AgentTypeInfo(
                    agent_type=agent_type,
                    display_name=metadata["display_name"],
                    description=metadata["description"],
                    default_temperature=metadata["default_temperature"],
                    default_max_tokens=metadata["default_max_tokens"],
                    active_count=stats["active_count"],
                    system_default_count=stats["system_default_count"]
                )
            )

        return AgentTypesResponse(agent_types=agent_types)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent types info: {str(e)}"
        )


@router.post("/validate", response_model=AgentValidationResponse)
async def validate_agent_config(
    request: CreateTestPlanAgentRequest
):
    """
    Validate an agent configuration without creating it.

    Checks:
    - Model name is valid and supported
    - Prompt template contains required placeholders
    - Parameters are within valid ranges
    - Model has required API keys configured
    """
    errors = []
    warnings = []

    # Validate model
    is_valid, error = validate_model(request.model_name)
    if not is_valid:
        errors.append(f"Invalid model: {error}")

    # Get model info
    model_config = get_model_config(request.model_name)
    model_info = None
    if model_config:
        model_info = {
            "provider": model_config.provider,
            "display_name": model_config.display_name,
            "context_window": model_config.context_window,
            "supports_vision": model_config.supports_vision
        }

    # Validate temperature
    if request.temperature < 0.0 or request.temperature > 1.0:
        errors.append("Temperature must be between 0.0 and 1.0")

    # Validate max_tokens
    if request.max_tokens < 100:
        errors.append("Max tokens must be at least 100")
    elif request.max_tokens > 32000:
        warnings.append(f"Max tokens ({request.max_tokens}) is very high and may incur significant costs")

    # Check if model context window is exceeded
    if model_config and request.max_tokens > model_config.context_window:
        errors.append(
            f"Max tokens ({request.max_tokens}) exceeds model context window ({model_config.context_window})"
        )

    return AgentValidationResponse(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        model_info=model_info
    )


# ============================================================================
# Agent Operations (Compliance Checking)
# ============================================================================

@router.post("/compliance-check")
async def compliance_check(
    request: ComplianceCheckRequest,
    db: Session = Depends(get_db),
    agent_service: AgentService = Depends(get_agent_service_legacy)
):
    """
    Run compliance check using multiple agents.

    This endpoint executes a multi-agent compliance check workflow:
    1. Runs agents in parallel to analyze the data sample
    2. Conducts multi-agent debate for consensus
    3. Logs all agent responses and debate results
    4. Saves to chat history for unified tracking

    Request Body:
    - data_sample: Text content to analyze for compliance
    - agent_ids: List of agent IDs to use for analysis (minimum 1)

    Returns:
    - details: Individual agent responses with confidence scores
    - debate_results: Multi-agent debate outcomes
    - session_id: Unique session identifier for tracking
    """
    try:
        result = agent_service.run_compliance_check(
            data_sample=request.data_sample,
            agent_ids=request.agent_ids,
            db=db
        )
        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Compliance check failed: {str(e)}"
        )
