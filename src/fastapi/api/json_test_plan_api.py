"""
JSON Test Plan API Endpoints

Provides REST endpoints for JSON-based test plan generation and manipulation.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import json
import uuid
import os
import redis
from datetime import datetime
import logging

from services.json_test_plan_service import JSONTestPlanService
from services.generate_docs_service import DocumentService
from services.llm_service import LLMService
from services.rag_service import RAGService
from services.agent_service import AgentService
from core.dependencies import document_service_dep
from repositories.agent_set_repository import AgentSetRepository
from sqlalchemy.orm import Session
from core.database import get_db
from config.model_profiles import get_model_profile, get_all_profiles, get_profile_choices, estimate_processing_time

logger = logging.getLogger(__name__)

# Create router
json_test_plan_router = APIRouter(prefix="/json-test-plans", tags=["json_test_plans"])


# ============================================================================
# Request/Response Models
# ============================================================================

class GenerateJSONTestPlanRequest(BaseModel):
    """Request to generate test plan in JSON format"""
    source_collections: Optional[List[str]] = None
    source_doc_ids: Optional[List[str]] = None
    doc_title: Optional[str] = "Comprehensive Test Plan"
    agent_set_id: int
    sectioning_strategy: Optional[str] = None  # Will be set by profile if not specified
    chunks_per_section: Optional[int] = None  # Will be set by profile if not specified
    model_profile: Optional[str] = "fast"  # fast, balanced, or quality


class JSONTestPlanResponse(BaseModel):
    """Response with JSON test plan"""
    success: bool
    test_plan: Dict[str, Any]
    message: str = ""
    error: Optional[str] = None
    processing_status: str = "COMPLETED"


class JSONTestPlanListResponse(BaseModel):
    """Response with list of JSON test plans"""
    test_plans: List[Dict[str, Any]]
    total_count: int
    message: str = ""


class TestCardExtractRequest(BaseModel):
    """Request to extract test cards from JSON test plan"""
    test_plan: Dict[str, Any]


class TestCardExtractResponse(BaseModel):
    """Response with extracted test cards"""
    test_cards: List[Dict[str, Any]]
    total_cards: int
    section_ids: List[str]


class MarkdownExportRequest(BaseModel):
    """Request to export JSON test plan as markdown"""
    test_plan: Dict[str, Any]


class MarkdownExportResponse(BaseModel):
    """Response with markdown export"""
    markdown: str
    title: str


class ValidateJSONTestPlanRequest(BaseModel):
    """Request to validate JSON test plan"""
    test_plan: Dict[str, Any]


class ValidateJSONTestPlanResponse(BaseModel):
    """Response from validation"""
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []


# ============================================================================
# Endpoints
# ============================================================================

@json_test_plan_router.get("/profiles")
async def get_available_profiles():
    """
    Get available model profiles for test plan generation.

    Returns profiles with their settings and recommendations.
    """
    profiles = get_profile_choices()
    return {
        "profiles": profiles,
        "default": "fast",
        "description": "Model profiles control the trade-off between speed and quality"
    }


@json_test_plan_router.post("/estimate-time")
async def estimate_generation_time(
    num_sections: int,
    num_actors: int = 3,
    model_profile: str = "fast"
):
    """
    Estimate processing time for a generation job.

    Args:
        num_sections: Number of document sections
        num_actors: Number of actor agents (typically 2-4)
        model_profile: Model profile to use (fast, balanced, quality)

    Returns:
        Time estimates and recommendations
    """
    estimate = estimate_processing_time(num_sections, num_actors, model_profile)
    return estimate


@json_test_plan_router.post("/generate", response_model=JSONTestPlanResponse)
async def generate_json_test_plan(
    req: GenerateJSONTestPlanRequest,
    doc_service: DocumentService = Depends(document_service_dep),
    db: Session = Depends(get_db)
):
    """
    Generate test plan directly in JSON format.
    
    This endpoint:
    1. Generates test plan using multi-agent service
    2. Converts result to JSON structure
    3. Returns structured JSON for test card generation
    
    Args:
        req: Generation request with source documents and agent set
        
    Returns:
        JSON test plan structure
    """
    try:
        # Get model profile settings
        profile = get_model_profile(req.model_profile)
        logger.info(f"Generating JSON test plan: {req.doc_title} with profile '{profile.display_name}' (model: {profile.model_name})")

        # Use profile settings if not explicitly specified
        sectioning_strategy = req.sectioning_strategy or profile.sectioning_strategy
        chunks_per_section = req.chunks_per_section or profile.chunks_per_section

        # Validate agent set
        agent_set_repo = AgentSetRepository()
        agent_set = agent_set_repo.get_by_id(req.agent_set_id, db)

        if not agent_set:
            raise HTTPException(
                status_code=404,
                detail=f"Agent set {req.agent_set_id} not found"
            )

        if not agent_set.is_active:
            raise HTTPException(
                status_code=400,
                detail=f"Agent set {agent_set.name} is inactive"
            )

        # Generate markdown-based test plan first
        pipeline_id = f"pipeline_{uuid.uuid4().hex[:12]}"
        docs = doc_service.generate_test_plan(
            source_collections=req.source_collections or [],
            source_doc_ids=req.source_doc_ids or [],
            doc_title=req.doc_title,
            agent_set_id=req.agent_set_id,
            sectioning_strategy=sectioning_strategy,
            chunks_per_section=chunks_per_section,
            pipeline_id=pipeline_id,
            model_profile=req.model_profile  # Pass profile to service
        )
        
        if not docs or len(docs) == 0:
            raise ValueError("No test plan generated")
        
        # Convert result to JSON
        doc = docs[0]
        final_test_plan = doc.get("_final_test_plan")  # If service stores the object
        
        if final_test_plan:
            json_test_plan = JSONTestPlanService.final_test_plan_to_json(final_test_plan)
        else:
            # Create minimal JSON structure if conversion not available
            json_test_plan = {
                "test_plan": {
                    "metadata": {
                        "title": req.doc_title,
                        "pipeline_id": pipeline_id,
                        "doc_title": req.doc_title,
                        "generated_at": datetime.now().isoformat(),
                        "processing_status": "COMPLETED",
                        "total_sections": doc.get("meta", {}).get("total_sections", 0),
                        "total_requirements": doc.get("meta", {}).get("total_requirements", 0),
                        "total_test_procedures": doc.get("meta", {}).get("total_test_procedures", 0),
                        "agent_set_id": req.agent_set_id,
                        "agent_configuration": "multi_agent_gpt4_pipeline"
                    },
                    "sections": []
                }
            }
        
        # Validate JSON structure
        is_valid, validation_msg = JSONTestPlanService.validate_json_test_plan(json_test_plan)
        
        return JSONTestPlanResponse(
            success=True,
            test_plan=json_test_plan,
            message=f"Successfully generated JSON test plan with {len(json_test_plan.get('test_plan', {}).get('sections', []))} sections",
            processing_status="COMPLETED"
        )
    
    except Exception as e:
        logger.error(f"Failed to generate JSON test plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Test plan generation failed: {str(e)}")


@json_test_plan_router.post("/extract-test-cards", response_model=TestCardExtractResponse)
async def extract_test_cards(req: TestCardExtractRequest):
    """
    Extract individual test cards from JSON test plan.
    
    Converts each test procedure into a separate test card document.
    
    Args:
        req: Request with JSON test plan
        
    Returns:
        List of test card objects ready for ChromaDB storage
    """
    try:
        logger.info("Extracting test cards from JSON test plan")
        
        # Validate JSON structure
        is_valid, validation_msg = JSONTestPlanService.validate_json_test_plan(req.test_plan)
        if not is_valid:
            raise ValueError(f"Invalid test plan JSON: {validation_msg}")
        
        # Extract test cards
        test_cards = JSONTestPlanService.extract_test_cards_from_json(req.test_plan)
        
        # Get section IDs for reference
        sections = req.test_plan.get("test_plan", {}).get("sections", [])
        section_ids = [s.get("section_id") for s in sections]
        
        logger.info(f"Extracted {len(test_cards)} test cards from {len(sections)} sections")
        
        return TestCardExtractResponse(
            test_cards=test_cards,
            total_cards=len(test_cards),
            section_ids=section_ids
        )
    
    except Exception as e:
        logger.error(f"Failed to extract test cards: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Test card extraction failed: {str(e)}")


@json_test_plan_router.post("/to-markdown", response_model=MarkdownExportResponse)
async def convert_to_markdown(req: MarkdownExportRequest):
    """
    Convert JSON test plan to markdown format.
    
    Useful for document export and display in markdown viewers.
    
    Args:
        req: Request with JSON test plan
        
    Returns:
        Markdown formatted test plan
    """
    try:
        logger.info("Converting JSON test plan to markdown")
        
        # Validate JSON structure
        is_valid, validation_msg = JSONTestPlanService.validate_json_test_plan(req.test_plan)
        if not is_valid:
            raise ValueError(f"Invalid test plan JSON: {validation_msg}")
        
        # Convert to markdown
        markdown = JSONTestPlanService.json_to_markdown(req.test_plan)
        title = req.test_plan.get("test_plan", {}).get("metadata", {}).get("title", "Test Plan")
        
        return MarkdownExportResponse(
            markdown=markdown,
            title=title
        )
    
    except Exception as e:
        logger.error(f"Failed to convert to markdown: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Markdown conversion failed: {str(e)}")


@json_test_plan_router.post("/validate", response_model=ValidateJSONTestPlanResponse)
async def validate_json_test_plan(req: ValidateJSONTestPlanRequest):
    """
    Validate JSON test plan structure.
    
    Checks if the JSON conforms to the expected schema.
    
    Args:
        req: Request with JSON test plan to validate
        
    Returns:
        Validation result with any errors or warnings
    """
    try:
        is_valid, message = JSONTestPlanService.validate_json_test_plan(req.test_plan)
        
        errors = [] if is_valid else [message]
        
        # Additional validations
        warnings = []
        sections = req.test_plan.get("test_plan", {}).get("sections", [])
        metadata = req.test_plan.get("test_plan", {}).get("metadata", {})
        
        if len(sections) == 0:
            warnings.append("Test plan has no sections")
        
        total_procedures = sum(
            len(s.get("test_procedures", []))
            for s in sections
        )
        
        if total_procedures == 0:
            warnings.append("Test plan has no test procedures")
        
        if metadata.get("total_test_procedures", 0) != total_procedures:
            warnings.append(
                f"Metadata test procedure count ({metadata.get('total_test_procedures', 0)}) "
                f"does not match actual count ({total_procedures})"
            )
        
        return ValidateJSONTestPlanResponse(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings
        )
    
    except Exception as e:
        logger.error(f"Validation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@json_test_plan_router.post("/merge")
async def merge_json_test_plans(test_plans: List[Dict[str, Any]]):
    """
    Merge multiple JSON test plans into a single test plan.
    
    Useful for combining test plans from different sources or agent sets.
    
    Args:
        test_plans: List of JSON test plan dictionaries
        
    Returns:
        Merged JSON test plan
    """
    try:
        if not test_plans or len(test_plans) == 0:
            raise ValueError("At least one test plan required for merging")
        
        logger.info(f"Merging {len(test_plans)} test plans")
        
        # Validate all plans
        for idx, plan in enumerate(test_plans):
            is_valid, msg = JSONTestPlanService.validate_json_test_plan(plan)
            if not is_valid:
                raise ValueError(f"Test plan {idx} is invalid: {msg}")
        
        # Merge
        merged = JSONTestPlanService.merge_json_sections(*test_plans)
        
        return {
            "success": True,
            "test_plan": merged,
            "message": f"Successfully merged {len(test_plans)} test plans"
        }
    
    except Exception as e:
        logger.error(f"Failed to merge test plans: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Merge failed: {str(e)}")


@json_test_plan_router.get("/schema")
async def get_json_schema():
    """
    Get the JSON schema for test plans.
    
    Useful for understanding the structure and validating test plans.
    
    Returns:
        JSON schema definition
    """
    return {
        "schema": {
            "type": "object",
            "properties": {
                "test_plan": {
                    "type": "object",
                    "properties": {
                        "metadata": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "pipeline_id": {"type": "string"},
                                "doc_title": {"type": "string"},
                                "generated_at": {"type": "string", "format": "date-time"},
                                "processing_status": {"type": "string"},
                                "total_sections": {"type": "integer"},
                                "total_requirements": {"type": "integer"},
                                "total_test_procedures": {"type": "integer"},
                                "agent_set_id": {"type": "integer"},
                                "agent_configuration": {"type": "string"}
                            },
                            "required": ["title", "pipeline_id", "processing_status"]
                        },
                        "sections": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "section_id": {"type": "string"},
                                    "section_title": {"type": "string"},
                                    "section_index": {"type": "integer"},
                                    "synthesized_rules": {"type": "string"},
                                    "actor_count": {"type": "integer"},
                                    "dependencies": {"type": "array", "items": {"type": "string"}},
                                    "conflicts": {"type": "array", "items": {"type": "string"}},
                                    "test_procedures": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "id": {"type": "string"},
                                                "requirement_id": {"type": "string"},
                                                "title": {"type": "string"},
                                                "objective": {"type": "string"},
                                                "setup": {"type": "string"},
                                                "steps": {"type": "array", "items": {"type": "string"}},
                                                "expected_results": {"type": "string"},
                                                "pass_criteria": {"type": "string"},
                                                "fail_criteria": {"type": "string"},
                                                "type": {"type": "string"},
                                                "priority": {"type": "string"},
                                                "estimated_duration_minutes": {"type": "integer"}
                                            }
                                        }
                                    }
                                },
                                "required": ["section_id", "section_title", "test_procedures"]
                            }
                        }
                    },
                    "required": ["metadata", "sections"]
                }
            },
            "required": ["test_plan"]
        }
    }
