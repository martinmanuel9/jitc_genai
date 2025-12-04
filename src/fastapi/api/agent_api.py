import warnings
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from schemas import ComplianceCheckRequest, CreateAgentResponse, CreateAgentRequest, GetAgentsResponse, UpdateAgentRequest, UpdateAgentResponse
# New dependency injection imports
from core.dependencies import get_db, get_agent_service_legacy, get_agent_repository
from models.agent import ComplianceAgent
from models.session import DebateSession
from services.agent_service import AgentService
from repositories import AgentRepository
import time
import uuid
from datetime import datetime, timezone
import logging

# Issue deprecation warning when module is imported
warnings.warn(
    "agent_api module is deprecated. Use test_plan_agent_api instead. "
    "See /api/test-plan-agents/* for new endpoints.",
    DeprecationWarning,
    stacklevel=2
)

logger = logging.getLogger("AGENT_API_LOGGER")

agent_api_router = APIRouter(
    prefix="/agent",
    tags=["agent (DEPRECATED)"],
    deprecated=True
)


def add_deprecation_headers(response: Response):
    """Add deprecation headers to response"""
    response.headers["X-API-Deprecated"] = "true"
    response.headers["X-API-Deprecation-Info"] = "Migrate to /api/test-plan-agents/*"
    response.headers["X-API-Sunset"] = "2026-01-01"  # Planned removal date
    response.headers["Link"] = '</api/test-plan-agents>; rel="alternate"'


@agent_api_router.post("/compliance-check")
async def compliance_check(
    request: ComplianceCheckRequest,
    response: Response,
    db: Session = Depends(get_db),
    agent_service: AgentService = Depends(get_agent_service_legacy)):
    """
    DEPRECATED: Use POST /api/test-plan-agents/compliance-check instead

    This endpoint will be removed in the next major version.
    """
    add_deprecation_headers(response)

    try:
        result = agent_service.run_compliance_check(
            data_sample=request.data_sample,
            agent_ids=request.agent_ids,
            db=db
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@agent_api_router.post("/create-agent", response_model=CreateAgentResponse)
async def create_agent(
    request: CreateAgentRequest,
    response: Response,
    agent_repo: AgentRepository = Depends(get_agent_repository),
    db: Session = Depends(get_db)):
    """
    DEPRECATED: Use POST /api/test-plan-agents instead

    Create a new compliance agent using repository pattern.
    This endpoint will be removed in the next major version.
    """
    add_deprecation_headers(response)
    try:
        # Check if agent name already exists using repository
        if agent_repo.exists_by_name(request.name):
            raise HTTPException(
                status_code=400,
                detail=f"Agent with name '{request.name}' already exists"
            )

        # Validate that user_prompt_template contains a supported placeholder
        # Supports: {data_sample} (compliance), {section_content} (test plan), or custom placeholders
        supported_placeholders = ["{data_sample}", "{section_content}"]
        has_placeholder = any(placeholder in request.user_prompt_template for placeholder in supported_placeholders)

        if not has_placeholder:
            raise HTTPException(
                status_code=400,
                detail=f"User prompt template must contain at least one supported placeholder: {', '.join(supported_placeholders)}"
            )

        # Prepare agent data
        tools_enabled = getattr(request, 'tools_enabled', {})
        if not tools_enabled:
            tools_enabled = {}

        agent_data = {
            "name": request.name,
            "model_name": request.model_name,
            "system_prompt": request.system_prompt,
            "user_prompt_template": request.user_prompt_template,
            "temperature": getattr(request, 'temperature', 0.7),
            "max_tokens": getattr(request, 'max_tokens', 300),
            "created_by": getattr(request, 'created_by', 'streamlit'),
            "is_active": True,
            "total_queries": 0,
            "chain_type": 'basic',
            "memory_enabled": False,
            "tools_enabled": tools_enabled
        }

        # Create agent using repository
        new_agent = agent_repo.create_agent(agent_data)
        db.commit()

        return CreateAgentResponse(
            message=f"Agent '{request.name}' created successfully",
            agent_id=new_agent.id,
            agent_name=new_agent.name
        )

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Agent with name '{request.name}' already exists"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating agent: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create agent: {str(e)}"
        )

@agent_api_router.get("/get-agents", response_model=GetAgentsResponse)
async def get_agents(
    response: Response,
    agent_repo: AgentRepository = Depends(get_agent_repository)):
    """
    DEPRECATED: Use GET /api/test-plan-agents instead

    Get all compliance agents using repository pattern.
    This endpoint will be removed in the next major version.
    """
    add_deprecation_headers(response)
    try:
        agents = agent_repo.get_all()

        # Convert agents to dict format using repository method
        agents_data = [agent_repo.to_dict(agent) for agent in agents]

        logger.info(f"Retrieved {len(agents_data)} agents")

        return GetAgentsResponse(
            agents=agents_data,
            total_count=len(agents_data)
        )

    except Exception as e:
        logger.error(f"Error getting agents: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve agents: {str(e)}"
        )

@agent_api_router.put("/update-agent/{agent_id}", response_model=UpdateAgentResponse)
async def update_agent(
    agent_id: int,
    request: UpdateAgentRequest,
    response: Response,
    agent_repo: AgentRepository = Depends(get_agent_repository),
    db: Session = Depends(get_db)):
    """
    DEPRECATED: Use PUT /api/test-plan-agents/{agent_id} instead

    Update an existing compliance agent using repository pattern.
    This endpoint will be removed in the next major version.
    """
    add_deprecation_headers(response)
    try:
        # Check if agent exists
        existing_agent = agent_repo.get(agent_id)
        if not existing_agent:
            raise HTTPException(
                status_code=404,
                detail=f"Agent with ID {agent_id} not found"
            )

        # Track which fields are being updated
        updated_fields = []
        update_data = {}

        # Check if name is being changed and if new name already exists
        if request.name is not None:
            if agent_repo.exists_by_name(request.name, exclude_id=agent_id):
                raise HTTPException(
                    status_code=400,
                    detail=f"Agent with name '{request.name}' already exists"
                )
            update_data["name"] = request.name
            updated_fields.append("name")

        # Build update dictionary for other fields
        if request.model_name is not None:
            update_data["model_name"] = request.model_name
            updated_fields.append("model_name")

        if request.system_prompt is not None:
            update_data["system_prompt"] = request.system_prompt
            updated_fields.append("system_prompt")

        if request.user_prompt_template is not None:
            update_data["user_prompt_template"] = request.user_prompt_template
            updated_fields.append("user_prompt_template")

        if request.temperature is not None:
            update_data["temperature"] = request.temperature
            updated_fields.append("temperature")

        if request.max_tokens is not None:
            update_data["max_tokens"] = request.max_tokens
            updated_fields.append("max_tokens")

        if request.is_active is not None:
            update_data["is_active"] = request.is_active
            updated_fields.append("is_active")

        # Update agent using repository
        updated_agent = agent_repo.update_agent(agent_id, update_data)
        db.commit()
        updated_fields.append("updated_at")  # Repository automatically updates this

        logger.info(f"Agent updated successfully: ID={agent_id}, Updated fields={updated_fields}")

        return UpdateAgentResponse(
            message=f"Agent '{updated_agent.name}' updated successfully",
            agent_id=updated_agent.id,
            agent_name=updated_agent.name,
            updated_fields=updated_fields
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating agent: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update agent: {str(e)}"
        )

@agent_api_router.get("/get-agent/{agent_id}")
async def get_agent_by_id(
    agent_id: int,
    response: Response,
    agent_repo: AgentRepository = Depends(get_agent_repository)):
    """
    DEPRECATED: Use GET /api/test-plan-agents/{agent_id} instead

    Get a specific agent by ID using repository pattern.
    This endpoint will be removed in the next major version.
    """
    add_deprecation_headers(response)
    try:
        agent = agent_repo.get(agent_id)

        if not agent:
            raise HTTPException(
                status_code=404,
                detail=f"Agent with ID {agent_id} not found"
            )

        return agent_repo.to_dict(agent)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent by ID: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve agent: {str(e)}"
        )

@agent_api_router.delete("/delete-agent/{agent_id}")
async def delete_agent(
    agent_id: int,
    response: Response,
    agent_repo: AgentRepository = Depends(get_agent_repository),
    db: Session = Depends(get_db)):
    """
    DEPRECATED: Use DELETE /api/test-plan-agents/{agent_id} instead

    Delete a compliance agent and handle foreign key relationships using repository pattern.
    This endpoint will be removed in the next major version.
    """
    add_deprecation_headers(response)
    try:
        deletion_result = agent_repo.delete_cascade(agent_id)
        db.commit()

        return {
            "message": f"Agent '{deletion_result['agent_name']}' deleted successfully",
            **deletion_result
        }

    except ValueError as e:
        db.rollback()
        # Agent not found
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting agent: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete agent: {str(e)}"
        )

@agent_api_router.patch("/toggle-agent-status/{agent_id}")
async def toggle_agent_status(
    agent_id: int,
    response: Response,
    agent_repo: AgentRepository = Depends(get_agent_repository),
    db: Session = Depends(get_db)):
    """
    DEPRECATED: Use POST /api/test-plan-agents/{agent_id}/activate instead

    Toggle agent active/inactive status using repository pattern.
    This endpoint will be removed in the next major version.
    """
    add_deprecation_headers(response)
    try:
        agent = agent_repo.toggle_status(agent_id)
        db.commit()

        if not agent:
            raise HTTPException(
                status_code=404,
                detail=f"Agent with ID {agent_id} not found"
            )

        status = "activated" if agent.is_active else "deactivated"

        return {
            "message": f"Agent '{agent.name}' {status} successfully",
            "agent_id": agent.id,
            "agent_name": agent.name,
            "is_active": agent.is_active,
            "updated_at": agent.updated_at.isoformat()
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error toggling agent status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to toggle agent status: {str(e)}"
        )
