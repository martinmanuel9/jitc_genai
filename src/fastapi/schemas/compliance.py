"""
Compliance-related Pydantic schemas.

This module contains schemas for:
- Compliance checking requests and responses
- Compliance result structures
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class ComplianceCheckRequest(BaseModel):
    """
    Request schema for compliance checking.

    Attributes:
        data_sample: Legal content to analyze for compliance
        agent_ids: List of agent IDs to use for multi-agent analysis
    """
    data_sample: str = Field(..., min_length=1, description="Legal content to analyze")
    agent_ids: List[int] = Field(..., min_items=1, description="List of agent IDs to use for analysis")


class ComplianceCheckResponse(BaseModel):
    """
    Response schema for compliance checking.

    Attributes:
        agent_responses: Dictionary mapping agent names to their responses
        overall_compliance: Overall compliance determination
        session_id: Session identifier for tracking
        debate_results: Results from multi-agent debate (if applicable)
    """
    agent_responses: Dict[str, str]
    overall_compliance: bool
    session_id: Optional[str] = None
    debate_results: Optional[Dict[str, Any]] = None


class ComplianceResultSchema(BaseModel):
    """
    Structured compliance result schema.

    This schema is used by agent services for parsing compliance results.

    Attributes:
        agent_responses: Dictionary of agent responses
        overall_compliance: Overall compliance determination
        session_id: Session identifier
        debate_results: Multi-agent debate results
    """
    agent_responses: Dict[str, str]
    overall_compliance: bool
    session_id: Optional[str] = None
    debate_results: Optional[Dict[str, Any]] = None
