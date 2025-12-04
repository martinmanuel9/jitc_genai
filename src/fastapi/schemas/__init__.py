"""
Pydantic schemas package.

This package contains all Pydantic models for request/response validation,
organized by domain:
- agent: Agent creation, updates, and responses
- compliance: Compliance checking schemas
- rag: RAG (Retrieval-Augmented Generation) schemas
- chat: Chat history schemas
- common: Shared/common schemas (pagination, errors, base responses)

Usage:
    from schemas import CreateAgentRequest, RAGCheckRequest, ComplianceCheckRequest
    from schemas.common import PaginatedResponse, ErrorResponse
"""

# Common schemas
from schemas.common import (
    BaseResponse,
    ErrorResponse,
    PaginationParams,
    PaginatedResponse,
    HealthCheckResponse,
    BulkOperationResponse,
)

# Agent schemas
from schemas.agent import (
    CreateAgentRequest,
    UpdateAgentRequest,
    CreateAgentResponse,
    UpdateAgentResponse,
    AgentResponse,
    GetAgentsResponse,
    AgentPerformanceMetrics,
)

# Compliance schemas
from schemas.compliance import (
    ComplianceCheckRequest,
    ComplianceCheckResponse,
    ComplianceResultSchema,
)

# RAG schemas
from schemas.rag import (
    # Check and Debate
    RAGCheckRequest,
    RAGCheckResponse,
    RAGDebateSequenceRequest,
    RAGDebateSequenceResponse,

    # Evaluation
    EvaluateRequest,
    EvaluateResponse,

    # Assessment
    RAGAssessmentRequest,
    RAGAssessmentResponse,
    RAGPerformanceMetricsResponse,
    RAGQualityAssessmentResponse,
    RAGAlignmentAssessmentResponse,
    RAGClassificationMetricsResponse,

    # Analytics
    RAGAnalyticsRequest,
    RAGBenchmarkRequest,
    CollectionPerformanceRequest,
    RAGMetricsExportRequest,
)

# Chat schemas
from schemas.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatHistoryRequest,
    ChatHistoryResponse,
    ChatSessionSummary,
    ChatSessionListResponse,
)

# Export all schemas
__all__ = [
    # Common
    "BaseResponse",
    "ErrorResponse",
    "PaginationParams",
    "PaginatedResponse",
    "HealthCheckResponse",
    "BulkOperationResponse",

    # Agent
    "CreateAgentRequest",
    "UpdateAgentRequest",
    "CreateAgentResponse",
    "UpdateAgentResponse",
    "AgentResponse",
    "GetAgentsResponse",
    "AgentPerformanceMetrics",

    # Compliance
    "ComplianceCheckRequest",
    "ComplianceCheckResponse",
    "ComplianceResultSchema",

    # RAG
    "RAGCheckRequest",
    "RAGCheckResponse",
    "RAGDebateSequenceRequest",
    "RAGDebateSequenceResponse",
    "EvaluateRequest",
    "EvaluateResponse",
    "RAGAssessmentRequest",
    "RAGAssessmentResponse",
    "RAGPerformanceMetricsResponse",
    "RAGQualityAssessmentResponse",
    "RAGAlignmentAssessmentResponse",
    "RAGClassificationMetricsResponse",
    "RAGAnalyticsRequest",
    "RAGBenchmarkRequest",
    "CollectionPerformanceRequest",
    "RAGMetricsExportRequest",

    # Chat
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "ChatHistoryRequest",
    "ChatHistoryResponse",
    "ChatSessionSummary",
    "ChatSessionListResponse",
]
