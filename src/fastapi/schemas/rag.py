"""
RAG (Retrieval-Augmented Generation) Pydantic schemas.

This module contains schemas for:
- RAG check and debate requests
- RAG assessment and evaluation
- RAG performance metrics
- RAG quality and alignment assessments
- RAG analytics and benchmarking
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# ============================================================================
# RAG Check and Debate Schemas
# ============================================================================

class RAGCheckRequest(BaseModel):
    """
    Request schema for RAG-enhanced compliance checking.

    Attributes:
        query_text: Legal query for RAG analysis
        collection_name: ChromaDB collection to query
        agent_ids: List of agent IDs to use for RAG analysis
    """
    query_text: str = Field(..., min_length=1, description="Legal query for RAG analysis")
    collection_name: str = Field(..., description="ChromaDB collection name")
    agent_ids: List[int] = Field(..., min_items=1, description="List of agent IDs to use for RAG analysis")


class RAGCheckResponse(BaseModel):
    """
    Response schema for RAG check.

    Attributes:
        agent_responses: Dictionary mapping agent names to responses
        collection_used: ChromaDB collection that was queried
        processing_time: Total processing time in seconds
    """
    agent_responses: Dict[str, str]
    collection_used: str
    processing_time: Optional[float] = None


class RAGDebateSequenceRequest(BaseModel):
    """
    Request schema for multi-agent RAG debate.

    Attributes:
        query_text: Legal content for multi-agent debate
        collection_name: ChromaDB collection to query
        agent_ids: List of agent IDs for debate sequence
        session_id: Optional session ID for continuing a debate
    """
    query_text: str = Field(..., min_length=1, description="Legal content for multi-agent debate")
    collection_name: str = Field(..., description="ChromaDB collection name")
    agent_ids: List[int] = Field(..., min_items=1, description="List of agent IDs for debate sequence")
    session_id: Optional[str] = Field(None, description="Optional session ID for continuing a debate")


class RAGDebateSequenceResponse(BaseModel):
    """
    Response schema for RAG debate sequence.

    Attributes:
        session_id: Session identifier
        debate_chain: List of debate turns with agent responses
        final_consensus: Final consensus reached (if any)
    """
    session_id: str
    debate_chain: List[Dict[str, Any]]
    final_consensus: Optional[str] = None


# ============================================================================
# RAG Evaluation Schemas
# ============================================================================

class EvaluateRequest(BaseModel):
    """
    Request schema for RAG evaluation.

    Attributes:
        document_id: Document identifier
        collection_name: ChromaDB collection name
        prompt: Evaluation prompt
        top_k: Number of documents to retrieve
        model_name: LLM model to use
    """
    document_id: str = Field(...)
    collection_name: str = Field(...)
    prompt: str = Field(...)
    top_k: int = Field(5)
    model_name: str = Field(...)


class EvaluateResponse(BaseModel):
    """
    Response schema for RAG evaluation.

    Attributes:
        document_id: Document identifier
        collection_name: Collection used
        prompt: Evaluation prompt
        model_name: Model used
        response: Generated response
        response_time_ms: Response time in milliseconds
        session_id: Session identifier
        citations: List of citations with metadata (optional)
        formatted_citations: Human-readable citation text (optional)
    """
    document_id: str
    collection_name: str
    prompt: str
    model_name: str
    response: str
    response_time_ms: int
    session_id: str
    citations: Optional[List[Dict[str, Any]]] = Field(None, description="List of citation metadata")
    formatted_citations: Optional[str] = Field(None, description="Human-readable formatted citations")


# ============================================================================
# RAG Assessment Schemas
# ============================================================================

class RAGAssessmentRequest(BaseModel):
    """
    Request schema for comprehensive RAG assessment.

    Attributes:
        query: Query for RAG assessment
        collection_name: ChromaDB collection name
        model_name: Model to use for generation
        top_k: Number of documents to retrieve (1-20)
        include_quality_assessment: Include quality metrics
        include_alignment_assessment: Include alignment metrics
        include_classification_metrics: Include classification metrics
    """
    query: str = Field(..., min_length=1, description="Query for RAG assessment")
    collection_name: str = Field(..., description="ChromaDB collection name")
    model_name: str = Field(default="gpt-3.5-turbo", description="Model to use for generation")
    top_k: int = Field(default=5, ge=1, le=20, description="Number of documents to retrieve")
    include_quality_assessment: bool = Field(default=True, description="Include quality assessment")
    include_alignment_assessment: bool = Field(default=True, description="Include alignment assessment")
    include_classification_metrics: bool = Field(default=True, description="Include classification metrics")


class RAGPerformanceMetricsResponse(BaseModel):
    """
    RAG performance metrics response.

    Attributes:
        session_id: Session identifier
        query: Original query
        collection_name: Collection used
        retrieval_time_ms: Time to retrieve documents (ms)
        generation_time_ms: Time to generate response (ms)
        total_time_ms: Total processing time (ms)
        documents_retrieved: Number of documents retrieved
        documents_used: Number of documents actually used
        relevance_score: Average relevance score
        context_length: Context length in characters
        response_length: Response length in characters
        model_name: Model used
        success: Whether operation succeeded
        error_message: Error message (if failed)
        timestamp: Timestamp
    """
    session_id: str
    query: str
    collection_name: str
    retrieval_time_ms: float
    generation_time_ms: float
    total_time_ms: float
    documents_retrieved: int
    documents_used: int
    relevance_score: float
    context_length: int
    response_length: int
    model_name: str
    success: bool
    error_message: Optional[str] = None
    timestamp: datetime


class RAGQualityAssessmentResponse(BaseModel):
    """
    RAG quality assessment metrics.

    Attributes:
        session_id: Session identifier
        relevance_score: How relevant is the response (0.0-1.0)
        coherence_score: How coherent is the response (0.0-1.0)
        factual_accuracy: Factual accuracy score (0.0-1.0)
        completeness_score: How complete is the response (0.0-1.0)
        context_utilization: How well context was used (0.0-1.0)
        overall_quality: Overall quality score (0.0-1.0)
        assessment_method: Method used for assessment
        assessor_model: Model used for assessment
        timestamp: Timestamp
    """
    session_id: str
    relevance_score: float
    coherence_score: float
    factual_accuracy: float
    completeness_score: float
    context_utilization: float
    overall_quality: float
    assessment_method: str
    assessor_model: Optional[str] = None
    timestamp: datetime


class RAGAlignmentAssessmentResponse(BaseModel):
    """
    RAG alignment assessment metrics.

    Attributes:
        session_id: Session identifier
        intent_alignment_score: Intent alignment (0.0-1.0)
        query_coverage_score: Query coverage (0.0-1.0)
        instruction_adherence_score: Instruction adherence (0.0-1.0)
        answer_type_classification: Actual answer type
        expected_answer_type: Expected answer type
        answer_type_match: Whether answer type matches
        tone_consistency_score: Tone consistency (0.0-1.0)
        scope_accuracy_score: Scope accuracy (0.0-1.0)
        missing_elements: List of missing elements
        extra_elements: List of extra elements
        assessment_confidence: Assessment confidence (0.0-1.0)
        timestamp: Timestamp
    """
    session_id: str
    intent_alignment_score: float
    query_coverage_score: float
    instruction_adherence_score: float
    answer_type_classification: str
    expected_answer_type: str
    answer_type_match: bool
    tone_consistency_score: float
    scope_accuracy_score: float
    missing_elements: List[str]
    extra_elements: List[str]
    assessment_confidence: float
    timestamp: datetime


class RAGClassificationMetricsResponse(BaseModel):
    """
    RAG classification metrics.

    Attributes:
        session_id: Session identifier
        query_classification: Query classification
        response_classification: Response classification
        classification_confidence: Classification confidence (0.0-1.0)
        domain_relevance: Domain relevance
        complexity_level: Complexity level
        information_density: Information density (0.0-1.0)
        actionability_score: Actionability score (0.0-1.0)
        specificity_score: Specificity score (0.0-1.0)
        citation_quality: Citation quality (0.0-1.0)
        timestamp: Timestamp
    """
    session_id: str
    query_classification: str
    response_classification: str
    classification_confidence: float
    domain_relevance: str
    complexity_level: str
    information_density: float
    actionability_score: float
    specificity_score: float
    citation_quality: float
    timestamp: datetime


class RAGAssessmentResponse(BaseModel):
    """
    Comprehensive RAG assessment response.

    Attributes:
        response: Generated response text
        performance_metrics: Performance metrics
        quality_assessment: Quality assessment (optional)
        alignment_assessment: Alignment assessment (optional)
        classification_metrics: Classification metrics (optional)
    """
    response: str
    performance_metrics: RAGPerformanceMetricsResponse
    quality_assessment: Optional[RAGQualityAssessmentResponse] = None
    alignment_assessment: Optional[RAGAlignmentAssessmentResponse] = None
    classification_metrics: Optional[RAGClassificationMetricsResponse] = None


# ============================================================================
# RAG Analytics and Benchmarking Schemas
# ============================================================================

class RAGAnalyticsRequest(BaseModel):
    """
    Request schema for RAG analytics.

    Attributes:
        time_period_hours: Analysis period in hours (1-8760)
        collection_name: Filter by collection name
    """
    time_period_hours: int = Field(default=24, ge=1, le=8760, description="Analysis period in hours")
    collection_name: Optional[str] = Field(None, description="Filter by collection name")


class RAGBenchmarkRequest(BaseModel):
    """
    Request schema for RAG benchmarking.

    Attributes:
        query_set: Set of test queries
        collection_name: Collection to test against
        configurations: List of configurations to test
    """
    query_set: List[str] = Field(..., min_items=1, description="Set of test queries")
    collection_name: str = Field(..., description="Collection to test against")
    configurations: List[Dict[str, Any]] = Field(..., min_items=1, description="List of configurations to test")


class CollectionPerformanceRequest(BaseModel):
    """
    Request schema for collection performance analysis.

    Attributes:
        collection_name: Collection name to analyze
    """
    collection_name: str = Field(..., description="Collection name to analyze")


class RAGMetricsExportRequest(BaseModel):
    """
    Request schema for exporting RAG metrics.

    Attributes:
        format: Export format (json, csv, etc.)
        time_period_hours: Export period in hours (1-8760)
    """
    format: str = Field(default="json", description="Export format")
    time_period_hours: int = Field(default=24, ge=1, le=8760, description="Export period in hours")
