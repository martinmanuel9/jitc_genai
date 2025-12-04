from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
# New dependency injection imports
from core.dependencies import get_db, get_rag_service, get_rag_assessment_service
from services.rag_service import RAGService
from services.rag_assessment_service import RAGAssessmentService
from schemas import (
    RAGCheckRequest, RAGDebateSequenceRequest, RAGAssessmentResponse,
    RAGAssessmentRequest, RAGAnalyticsRequest, RAGBenchmarkRequest,
    RAGMetricsExportRequest
)
import logging

# Get logger without configuring (let uvicorn handle logging configuration)
logger = logging.getLogger("RAG_API_LOGGER")

rag_api_router = APIRouter(prefix="/rag", tags=["rag"])


@rag_api_router.post("/check")
async def rag_check(
    request: RAGCheckRequest,
    rag_service: RAGService = Depends(get_rag_service),
    db: Session = Depends(get_db)):
    try:
        result = rag_service.run_rag_check(
            query_text=request.query_text,
            collection_name=request.collection_name,
            agent_ids=request.agent_ids,
            db=db
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@rag_api_router.post("/debate-sequence")
async def rag_debate_sequence(
    request: RAGDebateSequenceRequest,
    rag_service: RAGService = Depends(get_rag_service),
    db: Session = Depends(get_db)):
    try:
        session_id, chain, formatted_citations = rag_service.run_rag_debate_sequence(
            db=db,
            session_id=request.session_id,
            agent_ids=request.agent_ids,
            query_text=request.query_text,
            collection_name=request.collection_name
        )
        return {
            "session_id": session_id,
            "debate_chain": chain,
            "formatted_citations": formatted_citations
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@rag_api_router.post("/assessment", response_model=RAGAssessmentResponse)
async def rag_assessment(
    request: RAGAssessmentRequest,
    rag_assessment_service: RAGAssessmentService = Depends(get_rag_assessment_service)):
    """
    Perform comprehensive RAG assessment with performance and quality metrics.
    """
    try:
        logger.info(f"RAG assessment requested for query: {request.query[:100]}...")
        
        response, performance_metrics, quality_assessment, alignment_assessment, classification_metrics = rag_assessment_service.assess_rag_query(
            query=request.query,
            collection_name=request.collection_name,
            model_name=request.model_name,
            top_k=request.top_k,
            include_quality_assessment=request.include_quality_assessment,
            include_alignment_assessment=request.include_alignment_assessment,
            include_classification_metrics=request.include_classification_metrics
        )
        
        # Convert dataclasses to response models
        from dataclasses import asdict
        
        performance_response = RAGAssessmentResponse.model_validate({
            "response": response,
            "performance_metrics": asdict(performance_metrics),
            "quality_assessment": asdict(quality_assessment) if quality_assessment else None,
            "alignment_assessment": asdict(alignment_assessment) if alignment_assessment else None,
            "classification_metrics": asdict(classification_metrics) if classification_metrics else None
        })
        
        return performance_response
        
    except Exception as e:
        logger.error(f"RAG assessment failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"RAG assessment failed: {str(e)}")
    
@rag_api_router.post("/analytics")
async def get_rag_analytics(
    request: RAGAnalyticsRequest,
    rag_assessment_service: RAGAssessmentService = Depends(get_rag_assessment_service)):
    """
    Get comprehensive RAG performance analytics for specified time period.
    """
    try:
        analytics = rag_assessment_service.get_performance_analytics(
            time_period_hours=request.time_period_hours,
            collection_name=request.collection_name
        )

        return analytics

    except Exception as e:
        logger.error(f"RAG analytics failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"RAG analytics failed: {str(e)}")

@rag_api_router.post("/benchmark")
async def rag_benchmark(
    request: RAGBenchmarkRequest,
    rag_assessment_service: RAGAssessmentService = Depends(get_rag_assessment_service)):
    """
    Benchmark different RAG configurations on a set of queries.
    """
    try:
        logger.info(f"RAG benchmark requested for {len(request.query_set)} queries on collection: {request.collection_name}")

        benchmark_results = rag_assessment_service.benchmark_rag_configuration(
            query_set=request.query_set,
            collection_name=request.collection_name,
            configurations=request.configurations
        )

        return benchmark_results

    except Exception as e:
        logger.error(f"RAG benchmark failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"RAG benchmark failed: {str(e)}")

@rag_api_router.get("/collection-performance/{collection_name}")
async def get_collection_performance(
    collection_name: str,
    rag_assessment_service: RAGAssessmentService = Depends(get_rag_assessment_service)):
    """
    Get performance metrics specific to a collection.
    """
    try:
        performance_data = rag_assessment_service.get_collection_performance(collection_name)
        return performance_data

    except Exception as e:
        logger.error(f"Collection performance analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Collection performance analysis failed: {str(e)}")

@rag_api_router.post("/export-metrics")
async def export_rag_metrics(
    request: RAGMetricsExportRequest,
    rag_assessment_service: RAGAssessmentService = Depends(get_rag_assessment_service)):
    """
    Export RAG metrics data for external analysis.
    """
    try:
        export_data = rag_assessment_service.export_metrics(
            format=request.format,
            time_period_hours=request.time_period_hours
        )
        
        return export_data
        
    except Exception as e:
        logger.error(f"RAG metrics export failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"RAG metrics export failed: {str(e)}")


@rag_api_router.get("/assessment-demo")
async def rag_assessment_demo():
    """
    Demo endpoint showing example usage of RAG Assessment Service.
    """
    return {
        "demo": "RAG Assessment Service",
        "description": "Comprehensive RAG performance monitoring and quality evaluation",
        "key_features": [
            "Performance metrics tracking (response time, retrieval time, generation time)",
            "Quality assessment (relevance, coherence, factual accuracy, completeness)",
            "Analytics and benchmarking across time periods",
            "Collection-specific performance analysis",
            "Configuration benchmarking and optimization",
            "Metrics export for external analysis"
        ],
        "example_usage": {
            "assess_single_query": {
                "endpoint": "POST /rag/assessment",
                "payload": {
                    "query": "What are the key legal implications of this contract?",
                    "collection_name": "legal_contracts",
                    "model_name": "gpt-3.5-turbo",
                    "top_k": 5,
                    "include_quality_assessment": True
                }
            },
            "get_analytics": {
                "endpoint": "POST /rag/analytics",
                "payload": {
                    "time_period_hours": 24,
                    "collection_name": "legal_contracts"
                }
            },
            "benchmark_configs": {
                "endpoint": "POST /rag/benchmark",
                "payload": {
                    "query_set": [
                        "Analyze this contract for risks",
                        "What are the compliance requirements?"
                    ],
                    "collection_name": "legal_docs",
                    "configurations": [
                        {"model_name": "gpt-3.5-turbo", "top_k": 5},
                        {"model_name": "gpt-4", "top_k": 3},
                        {"model_name": "gpt-4o", "top_k": 5}
                        
                    ]
                }
            }
        }
    }