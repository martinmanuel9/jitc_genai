import os
import uuid
import time
from typing import Dict, List, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.orm import Session
from datetime import datetime

# New architecture imports
from core.database import SessionLocal
from models.agent import ComplianceAgent
from models.session import DebateSession
from models.enums import SessionType, AnalysisType
from repositories.session_repository import SessionRepository
from repositories.response_repository import ResponseRepository, ComplianceRepository

from langchain.output_parsers import PydanticOutputParser
from schemas import ComplianceResultSchema
from services.llm_invoker import LLMInvoker
from repositories.chat_repository import ChatRepository

class AgentService:
    """AgentService using LangChain for compliance verification and debate."""

    def __init__(self):
        self.compliance_agents: List[Dict[str, Any]] = []
        
        try:
            from services.llm_service import LLMService
            self.llm_service = LLMService()
            print("Using LLMService (same as Direct Chat)")
            
            # Test that it works
            test_llm = self.llm_service.get_llm_service("gpt-4")
            print("LLMService connection verified")
            
        except Exception as e:
            print(f"LLMService failed, falling back to llm_utils: {e}")
            self.llm_service = None
        
        if not self.llm_service:
            self.llms = {}
        
        try:
            self.compliance_parser = PydanticOutputParser(pydantic_object=ComplianceResultSchema)
            print("Compliance parser initialized")
        except Exception as e:
            print(f"Failed to initialize compliance parser: {e}")
        

    
    def get_llm_for_agent(self, model_name: str):
        """Get LLM using the same method as Direct Chat"""
        model_name = model_name.lower()
        
        # Try LLMService first (same as Direct Chat)
        if self.llm_service:
            try:
                return self.llm_service.get_llm_service(model_name)
            except Exception as e:
                print(f"LLMService failed for {model_name}, using fallback: {e}")
        
        # Fallback to llm_utils (also same as Direct Chat)
        if hasattr(self, 'llms') and model_name in self.llms:
            return self.llms[model_name]
        
        # Last resort - direct llm_utils call
        try:
            from services.llm_utils import get_llm
            return get_llm(model_name)
        except Exception as e:
            raise ValueError(f"Cannot get LLM for model {model_name}: {e}")
        
    def load_selected_compliance_agents(self, agent_ids: List[int]) -> None:
        """Load agents - NO CHANGE needed here"""
        session = SessionLocal()
        try:
            self.compliance_agents = []
            agents = session.query(ComplianceAgent).filter(ComplianceAgent.id.in_(agent_ids)).all()
            for agent in agents:
                model_name = agent.model_name.lower().strip()
                
                # Store raw prompts for direct LLM calls (no complex chains)
                self.compliance_agents.append({
                    "id": agent.id,
                    "name": agent.name,
                    "model_name": model_name,
                    "system_prompt": agent.system_prompt,
                    "user_prompt_template": agent.user_prompt_template
                })
                
            print(f"Loaded {len(self.compliance_agents)} agents")
        finally:
            session.close()

    def run_compliance_check(self, data_sample: str, agent_ids: List[int], db: Session) -> Dict[str, Any]:
        """Main compliance check - WORKS with unified LLM path"""
        session_id = str(uuid.uuid4())
        start_time = time.time()

        # Create session repository and log session start
        session_repo = SessionRepository(db)
        session_type = SessionType.MULTI_AGENT_DEBATE if len(agent_ids) > 1 else SessionType.SINGLE_AGENT
        session_repo.create_session(
            session_id=session_id,
            session_type=session_type,
            analysis_type=AnalysisType.DIRECT_LLM,
            user_query=data_sample
        )
        
        self.load_selected_compliance_agents(agent_ids)
        
        # Run parallel checks first
        results = self.run_parallel_checks(data_sample, session_id, db)
        
        # Set up debate sessions
        for idx, agent in enumerate(self.compliance_agents):
            db.add(DebateSession(session_id=session_id, compliance_agent_id=agent["id"], debate_order=idx + 1))
        db.commit()
        
        # Run debate
        debate_results = self.run_debate(session_id, data_sample, db)

        total_time = int((time.time() - start_time) * 1000)

        # Complete session using repository
        session_repo.complete_session(
            session_id=session_id,
            overall_result={
                "details": results,
                "debate_results": debate_results
            },
            agent_count=len(agent_ids),
            total_response_time_ms=total_time,
            status='completed'
        )

        # Save to chat history for unified history tracking
        try:
            chat_repo = ChatRepository(db)

            # Format response for history display
            agent_names = [agent["name"] for agent in self.compliance_agents]
            model_names = list(set([agent["model_name"] for agent in self.compliance_agents]))

            response_summary = f"**Agent Simulation Results** ({len(agent_ids)} agents)\n\n"
            for idx, (agent_id, result) in enumerate(results.items(), 1):
                agent_name = result.get("agent_name", f"Agent {agent_id}")
                reason = result.get("reason", result.get("raw_text", "No response"))
                response_summary += f"**{idx}. {agent_name}:**\n{reason}\n\n"

            chat_repo.create_chat_entry(
                user_query=data_sample,
                response=response_summary,
                model_used=", ".join(model_names),
                collection_name=None,
                query_type="agent_simulation",
                response_time_ms=total_time,
                session_id=session_id,
                source_documents=None
            )
            db.commit()
        except Exception as e:
            print(f"Warning: Failed to save agent simulation to chat history: {e}")
            # Don't fail the entire operation if chat history save fails
            db.rollback()

        return {
            "details": results,
            "debate_results": debate_results,
            "session_id": session_id
        }

    def run_parallel_checks(self, data_sample: str, session_id: str, db: Session) -> Dict[int, Dict[str, Any]]:
        """Run multiple agents in parallel - WORKS with unified LLM path"""
        results = {}
        with ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(self._invoke_chain, agent, data_sample, session_id, db): i 
                for i, agent in enumerate(self.compliance_agents)
            }
            for future in as_completed(futures):
                idx = futures[future]
                results[idx] = future.result()
        return results

    def _invoke_chain(self, agent: Dict[str, Any], data_sample: str, session_id: str, db: Session) -> Dict[str, Any]:
        """Single agent invocation - uses same LLM path as Direct Chat"""
        start_time = time.time()

        try:
            model_name = agent["model_name"]

            # Build prompt - expects {data_sample} placeholder for document analysis workflow
            formatted_user_prompt = agent["user_prompt_template"].replace("{data_sample}", data_sample)
            full_prompt = f"{agent['system_prompt']}\n\n{formatted_user_prompt}"

            # Call LLM using LLMInvoker
            raw_text = LLMInvoker.invoke(model_name=model_name, prompt=full_prompt)

            response_time_ms = int((time.time() - start_time) * 1000)

            # Log response using repositories
            response_repo = ResponseRepository(db)
            response_repo.create_response(
                session_id=session_id,
                agent_id=agent["id"],
                response_text=raw_text,
                processing_method="direct_llm_unified",
                response_time_ms=response_time_ms,
                model_used=agent["model_name"],
                analysis_summary=raw_text[:200]
            )

            compliance_repo = ComplianceRepository(db)
            compliance_repo.create_result(
                agent_id=agent["id"],
                data_sample=data_sample,
                confidence_score=None,
                reason=raw_text,
                raw_response=raw_text,
                processing_method="direct_llm_unified",
                response_time_ms=response_time_ms,
                model_used=agent["model_name"],
                session_id=session_id
            )
            
            return {
                "agent_id": agent["id"],
                "agent_name": agent["name"],
                "reason": raw_text,
                "confidence": None,
                "method": "direct_llm_unified"
            }
            
        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Error processing with agent {agent['name']}: {str(e)}"
            print(f"Error in _invoke_chain: {e}")
            
            return {
                "agent_id": agent["id"],
                "agent_name": agent["name"],
                "reason": error_msg,
                "confidence": None,
                "method": "error"
            }

    def run_debate(self, session_id: str, data_sample: str, db: Session) -> Dict[str, str]:
        """Run debate sequence - WORKS with unified LLM path"""
        agents = self._load_debate_agents(session_id)
        results = {}
        
        print(f"Starting debate with {len(agents)} agents")
        
        with ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(self._debate, agent, data_sample, session_id, db, idx+1): agent["name"] 
                for idx, agent in enumerate(agents)
            }
            for future in as_completed(futures):
                name = futures[future]
                results[name] = future.result()
                
        print(f"Debate completed: {len(results)} responses")
        return results

    def _load_debate_agents(self, session_id: str) -> List[Dict[str, Any]]:
        """Load debate agents in order - NO CHANGE needed"""
        session = SessionLocal()
        debate_agents = []
        try:
            records = session.query(DebateSession).filter(
                DebateSession.session_id == session_id
            ).order_by(DebateSession.debate_order).all()
            
            for record in records:
                agent = record.compliance_agent
                model_name = agent.model_name.lower()
                
                debate_agents.append({
                    "id": agent.id,
                    "name": agent.name,
                    "model_name": model_name,
                    "system_prompt": agent.system_prompt,
                    "user_prompt_template": agent.user_prompt_template
                })
                
        finally:
            session.close()
        return debate_agents

    def _debate(self, agent: Dict[str, Any], data_sample: str, session_id: str, db: Session, sequence_order: int = None) -> str:
        """Single debate round - WORKS with unified LLM path"""
        start_time = time.time()

        try:
            model_name = agent["model_name"]

            # Build prompt for debate context
            formatted_user_prompt = agent["user_prompt_template"].replace("{data_sample}", data_sample)
            full_prompt = f"{agent['system_prompt']}\n\n{formatted_user_prompt}"

            # Call LLM using LLMInvoker
            response_text = LLMInvoker.invoke(model_name=model_name, prompt=full_prompt)

            response_time_ms = int((time.time() - start_time) * 1000)

            # Log debate response using repositories
            response_repo = ResponseRepository(db)
            response_repo.create_response(
                session_id=session_id,
                agent_id=agent["id"],
                response_text=response_text,
                processing_method="debate_unified",
                response_time_ms=response_time_ms,
                model_used=agent["model_name"],
                sequence_order=sequence_order
            )

            compliance_repo = ComplianceRepository(db)
            compliance_repo.create_result(
                agent_id=agent["id"],
                data_sample=data_sample,
                confidence_score=None,
                reason="Debate response",
                raw_response=response_text,
                processing_method="debate_unified",
                response_time_ms=response_time_ms,
                model_used=agent["model_name"],
                session_id=session_id
            )
            
            return response_text
            
        except Exception as e:
            error_msg = f"Error during debate with {agent['name']}: {str(e)}"
            print(f"Error in _debate: {e}")
            return error_msg