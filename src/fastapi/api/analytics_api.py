# New dependency injection imports
from core.dependencies import get_db, get_session_repository
from core.database import get_db as get_db_session
from models.enums import SessionType, AnalysisType
from models.agent import ComplianceAgent
from models.session import AgentSession
from models.response import AgentResponse
from repositories import SessionRepository
from repositories.test_plan_agent_repository import TestPlanAgentRepository
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
import logging

logger = logging.getLogger("ANALYTICS_API_LOGGER")

analytics_api_router = APIRouter(prefix="/analytics", tags=["analytics"])


@analytics_api_router.get("/session-history")
async def get_agent_session_history(
    limit: int = 50,
    session_type: Optional[str] = None,
    session_repo: SessionRepository = Depends(get_session_repository)
):
    """Get recent agent session history"""
    try:
        # Convert string to enum if provided
        type_filter = None
        if session_type:
            try:
                type_filter = SessionType(session_type)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid session_type. Valid options: {[t.value for t in SessionType]}"
                )

        history = session_repo.get_history(limit=limit, session_type=type_filter)

        return {
            "sessions": history,
            "total_returned": len(history),
            "available_session_types": [t.value for t in SessionType],
            "available_analysis_types": [t.value for t in AnalysisType]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@analytics_api_router.get("/session-details/{session_id}")
async def get_agent_session_details(
    session_id: str,
    session_repo: SessionRepository = Depends(get_session_repository)
):
    """Get detailed information about a specific session"""
    try:
        details = session_repo.get_details(session_id)

        if not details:
            raise HTTPException(
                status_code=404,
                detail=f"Session with ID {session_id} not found"
            )

        return details

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@analytics_api_router.get("/agent-performance/{agent_id}")
async def get_agent_performance_metrics(
    agent_id: int,
    db: Session = Depends(get_db)
) -> dict:
    """Get performance metrics for a specific agent"""
    try:
        # Check if agent exists in TestPlanAgent table
        agent_repo = TestPlanAgentRepository()
        agent = agent_repo.get_by_id(agent_id, db)
        if not agent:
            raise HTTPException(
                status_code=404,
                detail=f"Agent with ID {agent_id} not found"
            )

        # Get agent response statistics
        total_responses = db.query(AgentResponse).filter(
            AgentResponse.agent_id == agent_id
        ).count()

        if total_responses == 0:
            return {
                "agent_id": agent_id,
                "agent_name": agent.name,
                "total_responses": 0,
                "message": "No response data available for this agent"
            }

        responses = db.query(AgentResponse).filter(
            AgentResponse.agent_id == agent_id
        ).all()

        # Response time statistics
        response_times = [r.response_time_ms for r in responses if r.response_time_ms]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0

        # RAG usage statistics
        rag_responses = [r for r in responses if r.rag_used]
        rag_usage_rate = len(rag_responses) / total_responses if total_responses > 0 else 0

        # Processing method breakdown
        method_counts = {}
        for response in responses:
            method = response.processing_method
            method_counts[method] = method_counts.get(method, 0) + 1

        # Recent activity (last 10 responses)
        recent_responses = db.query(AgentResponse).filter(
            AgentResponse.agent_id == agent_id
        ).order_by(AgentResponse.created_at.desc()).limit(10).all()

        recent_activity = []
        for response in recent_responses:
            recent_activity.append({
                "session_id": response.session_id,
                "created_at": response.created_at,
                "processing_method": response.processing_method,
                "response_time_ms": response.response_time_ms,
                "rag_used": response.rag_used,
                "documents_found": response.documents_found,
                "response_preview": response.response_text[:200] + "..." if len(response.response_text) > 200 else response.response_text
            })

        return {
            "agent_id": agent_id,
            "agent_name": agent.name,
            "model_name": agent.model_name,
            "performance_metrics": {
                "total_responses": total_responses,
                "avg_response_time_ms": round(avg_response_time, 2),
                "rag_usage_rate": round(rag_usage_rate * 100, 2),  # as percentage
                "processing_method_breakdown": method_counts
            },
            "recent_activity": recent_activity,
            "agent_info": {
                "created_at": agent.created_at,
                "total_queries": agent.total_queries,
                "success_rate": agent.success_rate,
                "is_active": agent.is_active
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@analytics_api_router.get("/session-analytics")
async def get_session_analytics(days: int = 7, db: Session = Depends(get_db)):
    """Get analytics about agent sessions over the specified number of days"""
    try:
        from datetime import datetime, timedelta, timezone
        from sqlalchemy import func

        # Calculate date range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        # Session counts by type
        session_counts = db.query(
            AgentSession.session_type,
            func.count(AgentSession.id).label('count')
        ).filter(
            AgentSession.created_at >= start_date
        ).group_by(AgentSession.session_type).all()
        
        # Session counts by analysis type
        analysis_counts = db.query(
            AgentSession.analysis_type,
            func.count(AgentSession.id).label('count')
        ).filter(
            AgentSession.created_at >= start_date
        ).group_by(AgentSession.analysis_type).all()
        
        # Average response times
        avg_response_time = db.query(
            func.avg(AgentSession.total_response_time_ms)
        ).filter(
            AgentSession.created_at >= start_date,
            AgentSession.total_response_time_ms.isnot(None)
        ).scalar()
        
        # Most active agents (using unified compliance_agents table)
        active_agents = db.query(
            AgentResponse.agent_id,
            ComplianceAgent.name,
            func.count(AgentResponse.id).label('response_count')
        ).join(
            ComplianceAgent, AgentResponse.agent_id == ComplianceAgent.id
        ).filter(
            AgentResponse.created_at >= start_date
        ).group_by(
            AgentResponse.agent_id, ComplianceAgent.name
        ).order_by(
            func.count(AgentResponse.id).desc()
        ).limit(10).all()
        
        # RAG usage statistics
        total_responses = db.query(AgentResponse).filter(
            AgentResponse.created_at >= start_date
        ).count()
        
        rag_responses = db.query(AgentResponse).filter(
            AgentResponse.created_at >= start_date,
            AgentResponse.rag_used == True
        ).count()
        
        rag_usage_rate = (rag_responses / total_responses * 100) if total_responses > 0 else 0
        
        return {
            "analytics_period": {
                "days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "session_statistics": {
                "by_session_type": {sc.session_type.value: sc.count for sc in session_counts},
                "by_analysis_type": {ac.analysis_type.value: ac.count for ac in analysis_counts},
                "avg_response_time_ms": round(avg_response_time, 2) if avg_response_time else 0
            },
            "agent_activity": [
                {
                    "agent_id": agent.agent_id,
                    "agent_name": agent.name,
                    "response_count": agent.response_count
                }
                for agent in active_agents
            ],
            "rag_statistics": {
                "total_responses": total_responses,
                "rag_responses": rag_responses,
                "rag_usage_rate": round(rag_usage_rate, 2)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 
    