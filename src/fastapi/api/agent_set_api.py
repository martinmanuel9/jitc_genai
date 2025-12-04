"""
Agent Set Management API

REST API endpoints for managing agent sets (orchestration pipelines).
Provides CRUD operations and utility endpoints for agent set configuration.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from repositories.agent_set_repository import AgentSetRepository
from repositories.test_plan_agent_repository import TestPlanAgentRepository
from schemas.agent_set import (
    CreateAgentSetRequest,
    UpdateAgentSetRequest,
    AgentSetResponse,
    AgentSetListResponse,
    CloneAgentSetRequest,
    CloneAgentSetResponse,
    DeleteAgentSetResponse,
    AgentSetUsageResponse,
    AgentSetValidationResponse,
    SearchAgentSetsRequest,
    BulkAgentSetOperationRequest,
    BulkAgentSetOperationResponse
)
from core.exceptions import DatabaseException


# Create router
router = APIRouter(
    prefix="/agent-sets",
    tags=["Agent Sets"]
)


def get_repository() -> AgentSetRepository:
    """Dependency for getting repository instance"""
    return AgentSetRepository()


def get_agent_repository() -> TestPlanAgentRepository:
    """Dependency for getting agent repository instance"""
    return TestPlanAgentRepository()


# ============================================================================
# CRUD Operations
# ============================================================================

@router.get("", response_model=AgentSetListResponse)
async def list_agent_sets(
    set_type: str = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    repo: AgentSetRepository = Depends(get_repository)
):
    """
    Get all agent sets.

    Query Parameters:
    - set_type: Filter by set type (sequence, parallel, custom)
    - include_inactive: Include inactive sets in results
    """
    try:
        if set_type:
            sets = repo.get_by_type(set_type, db, include_inactive=include_inactive)
        else:
            sets = repo.get_all(db, include_inactive=include_inactive)

        # Calculate type counts
        type_counts = {}
        for agent_set in sets:
            type_counts[agent_set.set_type] = type_counts.get(agent_set.set_type, 0) + 1

        return AgentSetListResponse(
            agent_sets=[AgentSetResponse.from_orm(s) for s in sets],
            total_count=len(sets),
            set_type_counts=type_counts
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list agent sets: {str(e)}"
        )


@router.get("/{set_id}", response_model=AgentSetResponse)
async def get_agent_set(
    set_id: int,
    db: Session = Depends(get_db),
    repo: AgentSetRepository = Depends(get_repository)
):
    """Get a specific agent set by ID"""
    try:
        agent_set = repo.get_by_id(set_id, db)
        if not agent_set:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent set with ID {set_id} not found"
            )

        return AgentSetResponse.from_orm(agent_set)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent set: {str(e)}"
        )


@router.post("", response_model=AgentSetResponse, status_code=status.HTTP_201_CREATED)
async def create_agent_set(
    request: CreateAgentSetRequest,
    db: Session = Depends(get_db),
    repo: AgentSetRepository = Depends(get_repository),
    agent_repo: TestPlanAgentRepository = Depends(get_agent_repository)
):
    """Create a new agent set"""
    try:
        # Validate that all referenced agents exist
        validation_errors = []
        if 'stages' in request.set_config:
            for idx, stage in enumerate(request.set_config['stages']):
                for agent_id in stage.get('agent_ids', []):
                    agent = agent_repo.get_by_id(agent_id, db)
                    if not agent:
                        validation_errors.append(f"Stage {idx}: Agent ID {agent_id} not found")
                    elif not agent.is_active:
                        validation_errors.append(f"Stage {idx}: Agent ID {agent_id} is inactive")

        if validation_errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Agent validation failed: {'; '.join(validation_errors)}"
            )

        # Create agent set
        set_data = request.dict()
        agent_set = repo.create(set_data, db)

        return AgentSetResponse.from_orm(agent_set)

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
            detail=f"Failed to create agent set: {str(e)}"
        )


@router.put("/{set_id}", response_model=AgentSetResponse)
async def update_agent_set(
    set_id: int,
    request: UpdateAgentSetRequest,
    db: Session = Depends(get_db),
    repo: AgentSetRepository = Depends(get_repository),
    agent_repo: TestPlanAgentRepository = Depends(get_agent_repository)
):
    """Update an existing agent set"""
    try:
        # Validate agents if set_config is being updated
        if request.set_config and 'stages' in request.set_config:
            validation_errors = []
            for idx, stage in enumerate(request.set_config['stages']):
                for agent_id in stage.get('agent_ids', []):
                    agent = agent_repo.get_by_id(agent_id, db)
                    if not agent:
                        validation_errors.append(f"Stage {idx}: Agent ID {agent_id} not found")

            if validation_errors:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Agent validation failed: {'; '.join(validation_errors)}"
                )

        # Update agent set
        set_data = request.dict(exclude_unset=True)
        agent_set = repo.update(set_id, set_data, db)

        return AgentSetResponse.from_orm(agent_set)

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
            detail=f"Failed to update agent set: {str(e)}"
        )


@router.delete("/{set_id}", response_model=DeleteAgentSetResponse)
async def delete_agent_set(
    set_id: int,
    soft_delete: bool = True,
    db: Session = Depends(get_db),
    repo: AgentSetRepository = Depends(get_repository)
):
    """
    Delete an agent set.

    Query Parameters:
    - soft_delete: If true, mark as inactive; if false, permanently delete (default: true)
    """
    try:
        # Get set name before deletion
        agent_set = repo.get_by_id(set_id, db)
        if not agent_set:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent set with ID {set_id} not found"
            )

        set_name = agent_set.name

        # Delete agent set
        repo.delete(set_id, db, soft_delete=soft_delete)

        return DeleteAgentSetResponse(
            message=f"Agent set {'deactivated' if soft_delete else 'deleted'} successfully",
            set_id=set_id,
            set_name=set_name,
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
            detail=f"Failed to delete agent set: {str(e)}"
        )


# ============================================================================
# Query Operations
# ============================================================================

@router.get("/type/{set_type}", response_model=AgentSetListResponse)
async def get_sets_by_type(
    set_type: str,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    repo: AgentSetRepository = Depends(get_repository)
):
    """Get all agent sets of a specific type"""
    try:
        sets = repo.get_by_type(set_type, db, include_inactive=include_inactive)

        return AgentSetListResponse(
            agent_sets=[AgentSetResponse.from_orm(s) for s in sets],
            total_count=len(sets),
            set_type_counts={set_type: len(sets)}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent sets by type: {str(e)}"
        )


@router.get("/defaults/all", response_model=AgentSetListResponse)
async def get_default_sets(
    set_type: str = None,
    db: Session = Depends(get_db),
    repo: AgentSetRepository = Depends(get_repository)
):
    """
    Get system default agent sets.

    Query Parameters:
    - set_type: Optional filter by set type
    """
    try:
        sets = repo.get_default_sets(db, set_type=set_type)

        # Calculate type counts
        type_counts = {}
        for agent_set in sets:
            type_counts[agent_set.set_type] = type_counts.get(agent_set.set_type, 0) + 1

        return AgentSetListResponse(
            agent_sets=[AgentSetResponse.from_orm(s) for s in sets],
            total_count=len(sets),
            set_type_counts=type_counts
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get default agent sets: {str(e)}"
        )


@router.get("/most-used/top", response_model=AgentSetListResponse)
async def get_most_used_sets(
    limit: int = 10,
    db: Session = Depends(get_db),
    repo: AgentSetRepository = Depends(get_repository)
):
    """
    Get most frequently used agent sets.

    Query Parameters:
    - limit: Maximum number of sets to return (default: 10)
    """
    try:
        sets = repo.get_most_used_sets(db, limit=limit)

        # Calculate type counts
        type_counts = {}
        for agent_set in sets:
            type_counts[agent_set.set_type] = type_counts.get(agent_set.set_type, 0) + 1

        return AgentSetListResponse(
            agent_sets=[AgentSetResponse.from_orm(s) for s in sets],
            total_count=len(sets),
            set_type_counts=type_counts
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get most used agent sets: {str(e)}"
        )


@router.post("/search", response_model=AgentSetListResponse)
async def search_agent_sets(
    request: SearchAgentSetsRequest,
    db: Session = Depends(get_db),
    repo: AgentSetRepository = Depends(get_repository)
):
    """
    Search agent sets by name or description.

    Request Body:
    - search_term: Search term (required)
    - set_type: Optional filter by set type
    - include_inactive: Include inactive sets
    """
    try:
        sets = repo.search(
            request.search_term,
            db,
            set_type=request.set_type,
            include_inactive=request.include_inactive
        )

        # Calculate type counts
        type_counts = {}
        for agent_set in sets:
            type_counts[agent_set.set_type] = type_counts.get(agent_set.set_type, 0) + 1

        return AgentSetListResponse(
            agent_sets=[AgentSetResponse.from_orm(s) for s in sets],
            total_count=len(sets),
            set_type_counts=type_counts
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search agent sets: {str(e)}"
        )


@router.get("/using-agent/{agent_id}", response_model=AgentSetListResponse)
async def get_sets_using_agent(
    agent_id: int,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    repo: AgentSetRepository = Depends(get_repository)
):
    """
    Find all agent sets that use a specific agent.

    Path Parameters:
    - agent_id: Agent ID to search for

    Query Parameters:
    - include_inactive: Include inactive sets
    """
    try:
        sets = repo.get_sets_using_agent(agent_id, db, include_inactive=include_inactive)

        # Calculate type counts
        type_counts = {}
        for agent_set in sets:
            type_counts[agent_set.set_type] = type_counts.get(agent_set.set_type, 0) + 1

        return AgentSetListResponse(
            agent_sets=[AgentSetResponse.from_orm(s) for s in sets],
            total_count=len(sets),
            set_type_counts=type_counts
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find sets using agent: {str(e)}"
        )


# ============================================================================
# Utility Operations
# ============================================================================

@router.post("/{set_id}/clone", response_model=CloneAgentSetResponse, status_code=status.HTTP_201_CREATED)
async def clone_agent_set(
    set_id: int,
    request: CloneAgentSetRequest,
    db: Session = Depends(get_db),
    repo: AgentSetRepository = Depends(get_repository)
):
    """Clone an existing agent set with a new name"""
    try:
        cloned_set = repo.clone_set(
            set_id,
            request.new_name,
            db,
            created_by=request.created_by
        )

        return CloneAgentSetResponse(
            message=f"Agent set cloned successfully as '{request.new_name}'",
            source_set_id=set_id,
            cloned_set=AgentSetResponse.from_orm(cloned_set)
        )

    except DatabaseException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clone agent set: {str(e)}"
        )


@router.post("/{set_id}/increment-usage", response_model=AgentSetUsageResponse)
async def increment_usage_count(
    set_id: int,
    db: Session = Depends(get_db),
    repo: AgentSetRepository = Depends(get_repository)
):
    """Increment usage count for an agent set (called when set is used for generation)"""
    try:
        agent_set = repo.increment_usage_count(set_id, db)

        return AgentSetUsageResponse(
            message=f"Usage count incremented for set '{agent_set.name}'",
            set_id=set_id,
            set_name=agent_set.name,
            usage_count=agent_set.usage_count
        )

    except DatabaseException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to increment usage count: {str(e)}"
        )


@router.post("/bulk", response_model=BulkAgentSetOperationResponse)
async def bulk_operation(
    request: BulkAgentSetOperationRequest,
    db: Session = Depends(get_db),
    repo: AgentSetRepository = Depends(get_repository)
):
    """
    Perform bulk operations on multiple agent sets.

    Supported operations:
    - activate: Activate multiple sets
    - deactivate: Deactivate multiple sets
    - delete: Soft-delete multiple sets
    """
    try:
        successful_count = 0
        failed_count = 0
        errors = []

        for set_id in request.set_ids:
            try:
                if request.operation == "activate":
                    repo.activate(set_id, db)
                elif request.operation == "deactivate":
                    repo.update(set_id, {"is_active": False}, db)
                elif request.operation == "delete":
                    repo.delete(set_id, db, soft_delete=True)
                successful_count += 1
            except Exception as e:
                failed_count += 1
                errors.append({
                    "set_id": set_id,
                    "error": str(e)
                })

        return BulkAgentSetOperationResponse(
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


@router.post("/validate", response_model=AgentSetValidationResponse)
async def validate_agent_set_config(
    request: CreateAgentSetRequest,
    db: Session = Depends(get_db),
    agent_repo: TestPlanAgentRepository = Depends(get_agent_repository)
):
    """
    Validate an agent set configuration without creating it.

    Checks:
    - All referenced agents exist
    - All referenced agents are active
    - Set configuration structure is valid
    - Execution modes are valid
    """
    errors = []
    warnings = []
    missing_agents = []
    inactive_agents = []

    # Validate agents in configuration
    if 'stages' in request.set_config:
        for idx, stage in enumerate(request.set_config['stages']):
            stage_name = stage.get('stage_name', f'Stage {idx}')

            # Check agents exist and are active
            for agent_id in stage.get('agent_ids', []):
                agent = agent_repo.get_by_id(agent_id, db)
                if not agent:
                    errors.append(f"{stage_name}: Agent ID {agent_id} not found")
                    missing_agents.append(agent_id)
                elif not agent.is_active:
                    warnings.append(f"{stage_name}: Agent ID {agent_id} ({agent.name}) is inactive")
                    inactive_agents.append(agent_id)

            # Validate execution mode
            execution_mode = stage.get('execution_mode')
            if execution_mode not in ['parallel', 'sequential', 'batched']:
                errors.append(f"{stage_name}: Invalid execution mode '{execution_mode}'")

            # Check batch_size for batched mode
            if execution_mode == 'batched' and 'batch_size' not in stage:
                warnings.append(f"{stage_name}: Batched execution mode without batch_size specified")

        # Check for duplicate stage names
        stage_names = [s.get('stage_name') for s in request.set_config['stages']]
        duplicates = set([name for name in stage_names if stage_names.count(name) > 1])
        if duplicates:
            warnings.append(f"Duplicate stage names found: {', '.join(duplicates)}")

    else:
        errors.append("set_config missing 'stages' key")

    return AgentSetValidationResponse(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        missing_agents=missing_agents,
        inactive_agents=inactive_agents
    )
