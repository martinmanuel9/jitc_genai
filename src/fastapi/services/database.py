# ============================================================================
# DEPRECATED: This file contains legacy code and is deprecated.
# ============================================================================
#
# This file is maintained for backward compatibility only. All code has been
# refactored into the new data layer architecture (Phases 1-11).
#
# NEW ARCHITECTURE LOCATIONS:
#
# 1. INFRASTRUCTURE (Database, Config, Dependencies)
#    - Database setup → core/database.py
#    - Configuration → core/config.py
#    - Dependency injection → core/dependencies.py
#    - Exceptions → core/exceptions.py
#
# 2. ORM MODELS (SQLAlchemy models organized by domain)
#    - Base classes → models/base.py
#    - Enums → models/enums.py
#    - Agent models → models/agent.py
#    - Session models → models/session.py
#    - Response models → models/response.py
#    - Citation models → models/citation.py
#    - Chat models → models/chat.py
#    - Compliance models → models/compliance.py
#
# 3. DATA ACCESS (Repository Pattern)
#    - Base repository → repositories/base.py
#    - Agent repository → repositories/agent_repository.py
#    - Session repository → repositories/session_repository.py
#    - Response repository → repositories/response_repository.py
#    - Citation repository → repositories/citation_repository.py
#    - Chat repository → repositories/chat_repository.py
#    - Compliance repository → repositories/compliance_repository.py
#    - Unit of Work → repositories/unit_of_work.py
#
# 4. BUSINESS LOGIC (Service Layer)
#    - Session service → services/session_service.py
#    - Compliance service → services/compliance_service.py
#    - Citation service → services/citation_service.py
#    - LLM service → services/llm_service.py (updated)
#
# 5. EXTERNAL SERVICES (Singleton clients)
#    - ChromaDB → integrations/chromadb_client.py
#    - Redis → integrations/redis_client.py
#
# MIGRATION GUIDE:
#    See DEPRECATED_CODE.md for complete migration guide with examples.
#    See DATA_LAYER_MIGRATION_COMPLETE.md for architecture overview.
#
# REMOVAL TIMELINE:
#    - Phase 12 (Current): Deprecation warnings added
#    - Phase 13: Update all imports to new locations
#    - Phase 15: Remove this file completely
#
# ============================================================================

import warnings
import os
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from sqlalchemy import Index
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, ForeignKey,
    Text, Float, Boolean, JSON, Enum, text
)
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from datetime import datetime, timezone
import enum

# Issue deprecation warning when this module is imported
warnings.warn(
    "services.database is deprecated. Use the new architecture: "
    "core/ for infrastructure, models/ for ORM, repositories/ for data access, "
    "services/ for business logic. See DEPRECATED_CODE.md for migration guide.",
    DeprecationWarning,
    stacklevel=2
)


# Database connection setup - handles both direct DATABASE_URL and component-based setup
def get_database_url() -> str:
    """
    Get database URL from environment variables.
    Supports both direct DATABASE_URL and individual components.
    Updated to work with AWS Secrets Manager variable names.
    """
    db_username = os.getenv("DB_USERNAME", "postgres")
    db_password = os.getenv("DB_PASSWORD")
    
    # Try both DB_ENDPOINT (AWS style) and DB_HOST (Docker style)
    db_endpoint = os.getenv("DB_ENDPOINT")
    db_host = os.getenv("DB_HOST")
    
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME") or os.getenv("DBNAME") or os.getenv("POSTGRES_DB", "rag_memory")
    
    # # Debug: Print what we found (without password)
    # print(f"Database config found:")
    # print(f"  DB_USERNAME: {db_username}")
    # print(f"  DB_PASSWORD: {'***' if db_password else 'NOT SET'}")
    # print(f"  DB_ENDPOINT: {os.getenv('DB_ENDPOINT', 'NOT SET')}")
    # print(f"  DB_HOST: {os.getenv('DB_HOST', 'NOT SET')}")
    # print(f"  DB_PORT: {db_port}")
    # print(f"  DB_NAME: {db_name}")
    # print(f"  DBNAME: {os.getenv('DBNAME', 'NOT SET')}")
    
    if db_endpoint:
        if ':' in db_endpoint:
            parts = db_endpoint.rsplit(':', 1)
            potential_host = parts[0]
            potential_port = parts[1]
            
            try:
                int(potential_port)
                db_host = potential_host
                if os.getenv("DB_PORT") is None:
                    db_port = potential_port
                print(f"Detected port in endpoint: {potential_port}, using host: {db_host}")
            except ValueError:
                db_host = db_endpoint
                print(f"No valid port in endpoint, using full endpoint as host: {db_host}")
        else:
            db_host = db_endpoint
            print(f"No port in endpoint, using as host: {db_host}")
    
    missing = []
    if not db_username:
        missing.append("DB_USERNAME")
    if not db_password:
        missing.append("DB_PASSWORD") 
    if not db_host:
        missing.append("DB_HOST or DB_ENDPOINT")
    if not db_name:
        missing.append("DB_NAME or DBNAME")
    
    if missing:
        print(f"ERROR: Database configuration incomplete. Missing: {', '.join(missing)}")
        
        print("All DB_* environment variables:")
        for key, value in os.environ.items():
            if key.startswith('DB_'):
                print(f"  {key}: {'***' if 'PASSWORD' in key else value}")
        
        raise ValueError(f"Database configuration incomplete. Missing: {', '.join(missing)}")
    
    constructed_url = f"postgresql://{db_username}:{db_password}@{db_host}/{db_name}"
    print(f"Constructed DATABASE_URL: postgresql://{db_username}:***@{db_host}/{db_name}")
    return constructed_url

DATABASE_URL = get_database_url()

# Enhanced connection configuration with pooling and optimized retry logic
engine_config = {
    'pool_size': 20,          # Increased from default 5
    'max_overflow': 30,       # Allow burst connections
    'pool_timeout': 10,       # Reduced from 30 seconds
    'pool_recycle': 3600,     # Recycle connections after 1 hour
    'pool_pre_ping': True,    # Verify connections before use
    'echo': False,            # Disable query logging for performance
}

# Optimized retry logic with exponential backoff
retry_delays = [1, 2, 3, 5, 8]  # Reduced from 5-second fixed delay
for i, delay in enumerate(retry_delays):
    try:
        engine = create_engine(DATABASE_URL, **engine_config)
        # Test connection with shorter timeout
        conn = engine.connect()
        conn.execute(text("SELECT 1"))  # Simple health check
        conn.close()
        print(f"Database connection established successfully on attempt {i+1}")
        break
    except OperationalError as e:
        print(f"Database not ready (attempt {i+1}/{len(retry_delays)}): {e}")
        if i < len(retry_delays) - 1:  # Don't sleep on last attempt
            print(f"Retrying in {delay} seconds...")
            time.sleep(delay)
else:
    raise Exception(f"Could not connect to the database after {len(retry_delays)} attempts")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Add connection health check function
def get_database_health():
    """Check database connection health"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            return {"status": "healthy", "connection_pool": engine.pool.status()}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

# ChromaDB client initialization - lazy loading
import chromadb

CHROMA_HOST = os.getenv("CHROMA_HOST", "chromadb")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))

_chroma_client = None

def get_chroma_client():
    """Get or create ChromaDB client with lazy initialization."""
    global _chroma_client
    if _chroma_client is None:
        try:
            _chroma_client = chromadb.HttpClient(
                host=CHROMA_HOST,
                port=CHROMA_PORT
            )
            heartbeat = _chroma_client.heartbeat()
            print(f" ChromaDB connected at {CHROMA_HOST}:{CHROMA_PORT}: {heartbeat}")
        except Exception as e:
            print(f" ChromaDB connection failed: {e}")
            return None
    return _chroma_client

# For backward compatibility - lazy proxy
class LazyChromaClient:
    def __getattr__(self, name):
        client = get_chroma_client()
        if client is None:
            raise RuntimeError("ChromaDB client not available")
        return getattr(client, name)

    def __bool__(self):
        return get_chroma_client() is not None

chroma_client = LazyChromaClient()

Base = declarative_base()

# Tables
class ChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, index=True)
    user_query = Column(Text)
    response = Column(Text)
    model_used = Column(String)
    collection_name = Column(String)
    query_type = Column(String)
    response_time_ms = Column(Integer)
    timestamp = Column(DateTime, default=datetime.now(timezone.utc), index=True)
    session_id = Column(String, index=True)
    source_documents = Column(JSON)

class Agent(Base):
    __tablename__ = "agents"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    model_name = Column(String, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), index=True , onupdate=datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)

class ComplianceAgent(Base):
    __tablename__ = "compliance_agents"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    model_name = Column(String, nullable=False)
    system_prompt = Column(Text, nullable=False)
    user_prompt_template = Column(Text, nullable=False)
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=300)
    use_structured_output = Column(Boolean, default=False)
    output_schema = Column(JSON)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), index=True , onupdate=datetime.now(timezone.utc))
    created_by = Column(String)
    is_active = Column(Boolean, default=True)
    total_queries = Column(Integer, default=0)
    avg_response_time_ms = Column(Float)
    success_rate = Column(Float)
    chain_type = Column(String, default='basic')
    memory_enabled = Column(Boolean, default=False)
    tools_enabled = Column(JSON)


class ComplianceSequence(Base):
    __tablename__ = "compliance_sequence"
    id = Column(Integer, primary_key=True, index=True)
    compliance_agent_id = Column(Integer, ForeignKey("compliance_agents.id"), nullable=False)
    sequence_order = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), index=True)
    compliance_agent = relationship("ComplianceAgent", back_populates="sequences")

ComplianceAgent.sequences = relationship(
    "ComplianceSequence", order_by=ComplianceSequence.sequence_order,
    back_populates="compliance_agent"
)

class DebateSession(Base):
    __tablename__ = "debate_sessions"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True, nullable=False)
    compliance_agent_id = Column(Integer, ForeignKey("compliance_agents.id"), nullable=False)
    debate_order = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), index=True)
    status = Column(String, default='active')
    initial_data = Column(Text)
    agent_response = Column(Text)
    response_time_ms = Column(Integer)
    compliance_agent = relationship("ComplianceAgent", back_populates="debate_sessions")

ComplianceAgent.debate_sessions = relationship(
    "DebateSession", order_by=DebateSession.debate_order,
    back_populates="compliance_agent"
)

class ComplianceResult(Base):
    __tablename__ = "compliance_results"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, index=True)
    agent_id = Column(Integer, ForeignKey("compliance_agents.id"), nullable=False)
    data_sample = Column(Text, nullable=False)
    # compliant = Column(Boolean)
    confidence_score = Column(Float)
    reason = Column(Text)
    raw_response = Column(Text)
    processing_method = Column(String)
    response_time_ms = Column(Integer)
    model_used = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc), index=True)
    agent = relationship("ComplianceAgent")
    

class SessionType(enum.Enum):
    SINGLE_AGENT = "single_agent"
    MULTI_AGENT_DEBATE = "multi_agent_debate"
    RAG_ANALYSIS = "rag_analysis"
    RAG_DEBATE = "rag_debate"
    COMPLIANCE_CHECK = "compliance_check"

class AnalysisType(enum.Enum):
    DIRECT_LLM = "direct_llm"
    RAG_ENHANCED = "rag_enhanced"
    HYBRID = "hybrid"

# Enhanced AgentSession model to track all types of agent interactions
class AgentSession(Base):
    __tablename__ = "agent_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, nullable=False, index=True)
    session_type = Column(Enum(SessionType), nullable=False)
    analysis_type = Column(Enum(AnalysisType), nullable=False)
    
    # Input data
    user_query = Column(Text, nullable=False)
    collection_name = Column(String, nullable=True)  # For RAG sessions
    
    # Session metadata
    created_at = Column(DateTime, default=datetime.now(timezone.utc), index=True)
    completed_at = Column(DateTime, nullable=True)
    total_response_time_ms = Column(Integer, nullable=True)
    
    # Session status
    status = Column(String, default='active')  # active, completed, failed
    error_message = Column(Text, nullable=True)
    
    # Results summary
    overall_result = Column(JSON, nullable=True)  # Summary of all agent responses
    agent_count = Column(Integer, default=0)
    
    # Relationships
    agent_responses = relationship("AgentResponse", back_populates="session", cascade="all, delete-orphan")

# Individual agent responses within a session
class AgentResponse(Base):
    __tablename__ = "agent_responses"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("agent_sessions.session_id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(Integer, ForeignKey("compliance_agents.id", ondelete="CASCADE"), nullable=False)

    # Response details
    response_text = Column(Text, nullable=False)
    processing_method = Column(String, nullable=False)  # langchain, rag_enhanced, direct_llm, etc.
    response_time_ms = Column(Integer, nullable=True)

    # Sequence information (for debates)
    sequence_order = Column(Integer, nullable=True)  # Order in debate sequence

    # RAG information
    rag_used = Column(Boolean, default=False)
    documents_found = Column(Integer, default=0)
    rag_context = Column(Text, nullable=True)  # The retrieved context

    # Compliance/Analysis results
    # compliant = Column(Boolean, nullable=True)
    confidence_score = Column(Float, nullable=True)
    analysis_summary = Column(Text, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.now(timezone.utc), index=True)
    model_used = Column(String, nullable=False)

    # Relationships
    session = relationship("AgentSession", back_populates="agent_responses")
    agent = relationship("ComplianceAgent")
    citations = relationship("RAGCitation", back_populates="agent_response", cascade="all, delete-orphan")


# RAG Citation tracking for explainability and audit trail
class RAGCitation(Base):
    __tablename__ = "rag_citations"

    id = Column(Integer, primary_key=True, index=True)
    agent_response_id = Column(Integer, ForeignKey("agent_responses.id", ondelete="CASCADE"), nullable=False)
    document_index = Column(Integer, nullable=False)  # Position in retrieved results (1-based)

    # Distance metrics (ChromaDB uses distance, lower is better)
    distance = Column(Float, nullable=False)  # ChromaDB distance metric (lower = better match)

    # Legacy similarity metrics (deprecated, kept for backward compatibility)
    similarity_score = Column(Float, nullable=True)  # Deprecated: Use distance instead
    similarity_percentage = Column(Float, nullable=True)  # Deprecated: Use distance instead

    # Document content
    excerpt = Column(Text, nullable=False)  # First 300 chars of document
    full_length = Column(Integer, nullable=False)  # Total document length

    # Source metadata (from ChromaDB)
    source_file = Column(String, nullable=True)  # Filename or source identifier
    page_number = Column(Integer, nullable=True)  # Page number if applicable
    section_name = Column(String, nullable=True)  # Section/chapter name
    metadata_json = Column(JSON, nullable=True)  # Full metadata object

    # Quality assessment (no threshold filtering, all docs included)
    quality_tier = Column(String, nullable=True)  # Excellent, High, Good, Fair, Low

    # Timestamps
    created_at = Column(DateTime, default=datetime.now(timezone.utc), index=True)

    # Relationships
    agent_response = relationship("AgentResponse", back_populates="citations")

# Utilities
# DEPRECATED: This init_db() is no longer used. Use core.database.init_db() instead.
# def init_db():
#     Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def update_agent_performance(agent_id: int, response_time_ms: int, success: bool = True):
    """Update agent performance metrics with optimized database access"""
    try:
        with SessionLocal() as db:  # Use context manager
            agent = db.query(ComplianceAgent).filter(ComplianceAgent.id == agent_id).first()
            if agent:
                agent.total_queries = (agent.total_queries or 0) + 1
                
                if agent.avg_response_time_ms is None:
                    agent.avg_response_time_ms = response_time_ms
                else:
                    total_time = agent.avg_response_time_ms * (agent.total_queries - 1) + response_time_ms
                    agent.avg_response_time_ms = total_time / agent.total_queries

                if agent.success_rate is None:
                    agent.success_rate = 1.0 if success else 0.0
                else:
                    total_successes = agent.success_rate * (agent.total_queries - 1) + (1 if success else 0)
                    agent.success_rate = total_successes / agent.total_queries

                db.commit()
                print(f"Updated performance for agent {agent_id}: queries={agent.total_queries}, avg_time={agent.avg_response_time_ms:.1f}ms")
    except Exception as e:
        print(f"Performance update error for agent {agent_id}: {e}")
        # No need for explicit rollback with context manager


def log_compliance_result(agent_id: int, data_sample: str,
                            confidence_score: Optional[float], reason: str,
                            raw_response: str, processing_method: str,
                            response_time_ms: int, model_used: str,
                            session_id: Optional[str] = None):
    db = SessionLocal()
    try:
        result = ComplianceResult(
            session_id=session_id,
            agent_id=agent_id,
            data_sample=data_sample,
            confidence_score=confidence_score,
            reason=reason,
            raw_response=raw_response,
            processing_method=processing_method,
            response_time_ms=response_time_ms,
            model_used=model_used
        )
        db.add(result)
        db.commit()
        update_agent_performance(agent_id, response_time_ms, True)  # Fix the call
    except Exception as e:
        print(f"Log result error: {e}")
        db.rollback()
    finally:
        db.close()

def log_agent_session(session_id: str, session_type: SessionType, analysis_type: AnalysisType, 
                        user_query: str, collection_name: str = None) -> None:
    """Log the start of an agent session"""
    db = SessionLocal()
    try:
        session = AgentSession(
            session_id=session_id,
            session_type=session_type,
            analysis_type=analysis_type,
            user_query=user_query,
            collection_name=collection_name,
            status='active'
        )
        db.add(session)
        db.commit()
    except Exception as e:
        print(f"Error logging agent session: {e}")
        db.rollback()
    finally:
        db.close()

# def log_agent_response(session_id: str, agent_id: int, response_text: str, 
#                         processing_method: str, response_time_ms: int, model_used: str,
#                         sequence_order: int = None, rag_used: bool = False, 
#                         documents_found: int = 0, rag_context: str = None,
#                         compliant: bool = None, confidence_score: float = None,
#                         analysis_summary: str = None) -> None:
def log_agent_response(session_id: str, agent_id: int, response_text: str,
                        processing_method: str, response_time_ms: int, model_used: str,
                        sequence_order: int = None, rag_used: bool = False,
                        documents_found: int = 0, rag_context: str = None,
                        confidence_score: float = None,
                        analysis_summary: str = None) -> Optional[int]:
    """Log an individual agent response and return the response ID"""
    db = SessionLocal()
    try:
        response = AgentResponse(
            session_id=session_id,
            agent_id=agent_id,
            response_text=response_text,
            processing_method=processing_method,
            response_time_ms=response_time_ms,
            sequence_order=sequence_order,
            rag_used=rag_used,
            documents_found=documents_found,
            rag_context=rag_context,
            # compliant=compliant,
            confidence_score=confidence_score,
            analysis_summary=analysis_summary,
            model_used=model_used
        )
        db.add(response)
        db.commit()
        db.refresh(response)  # Get the generated ID
        return response.id
    except Exception as e:
        print(f"Error logging agent response: {e}")
        db.rollback()
        return None
    finally:
        db.close()

def complete_agent_session(session_id: str, overall_result: dict, agent_count: int, 
                            total_response_time_ms: int = None, status: str = 'completed',
                            error_message: str = None) -> None:
    """Mark an agent session as completed and log summary"""
    db = SessionLocal()
    try:
        session = db.query(AgentSession).filter(AgentSession.session_id == session_id).first()
        if session:
            session.completed_at = datetime.now(timezone.utc)
            session.overall_result = overall_result
            session.agent_count = agent_count
            session.total_response_time_ms = total_response_time_ms
            session.status = status
            session.error_message = error_message
            db.commit()
    except Exception as e:
        print(f"Error completing agent session: {e}")
        db.rollback()
    finally:
        db.close()

def get_session_history(limit: int = 50, session_type: SessionType = None):
    """Get recent agent session history"""
    db = SessionLocal()
    try:
        query = db.query(AgentSession).order_by(AgentSession.created_at.desc())
        
        if session_type:
            query = query.filter(AgentSession.session_type == session_type)
            
        sessions = query.limit(limit).all()
        
        result = []
        for session in sessions:
            session_data = {
                "session_id": session.session_id,
                "session_type": session.session_type.value,
                "analysis_type": session.analysis_type.value,
                "user_query": session.user_query[:200] + "..." if len(session.user_query) > 200 else session.user_query,
                "collection_name": session.collection_name,
                "created_at": session.created_at,
                "completed_at": session.completed_at,
                "status": session.status,
                "agent_count": session.agent_count,
                "total_response_time_ms": session.total_response_time_ms
            }
            result.append(session_data)
        
        return result
    except Exception as e:
        print(f"Error getting session history: {e}")
        return []
    finally:
        db.close()

def get_session_details(session_id: str):
    """Get detailed information about a specific session"""
    db = SessionLocal()
    try:
        session = db.query(AgentSession).filter(AgentSession.session_id == session_id).first()
        if not session:
            return None

        # Get all agent responses for this session
        responses = db.query(AgentResponse).filter(
            AgentResponse.session_id == session_id
        ).order_by(AgentResponse.sequence_order.asc(), AgentResponse.created_at.asc()).all()

        session_data = {
            "session_info": {
                "session_id": session.session_id,
                "session_type": session.session_type.value,
                "analysis_type": session.analysis_type.value,
                "user_query": session.user_query,
                "collection_name": session.collection_name,
                "created_at": session.created_at,
                "completed_at": session.completed_at,
                "status": session.status,
                "error_message": session.error_message,
                "overall_result": session.overall_result,
                "agent_count": session.agent_count,
                "total_response_time_ms": session.total_response_time_ms
            },
            "agent_responses": []
        }

        for response in responses:
            response_data = {
                "agent_id": response.agent_id,
                "agent_name": response.agent.name if response.agent else "Unknown",
                "response_text": response.response_text,
                "processing_method": response.processing_method,
                "response_time_ms": response.response_time_ms,
                "sequence_order": response.sequence_order,
                "rag_used": response.rag_used,
                "documents_found": response.documents_found,
                # "compliant": response.compliant,
                "confidence_score": response.confidence_score,
                "model_used": response.model_used,
                "created_at": response.created_at
            }
            session_data["agent_responses"].append(response_data)

        return session_data
    except Exception as e:
        print(f"Error getting session details: {e}")
        return None
    finally:
        db.close()


# RAG Citation logging functions
def log_rag_citations(agent_response_id: int, metadata_list: List[Dict[str, Any]]) -> bool:
    """
    Log RAG citation metadata for explainability and audit trail.

    Args:
        agent_response_id: The ID of the agent response this citation belongs to
        metadata_list: List of citation metadata dicts from RAG service

    Returns:
        True if successful, False otherwise
    """
    db = SessionLocal()
    try:
        citations = []
        for meta in metadata_list:
            doc_metadata = meta.get('metadata', {})

            # Extract page number from multiple possible keys
            page_num = doc_metadata.get('page_number') or doc_metadata.get('page')

            # Extract section from multiple possible keys
            section = doc_metadata.get('section_title') or doc_metadata.get('section_name') or doc_metadata.get('section')

            # Extract source file/document name
            source = doc_metadata.get('document_name') or doc_metadata.get('source')

            citation = RAGCitation(
                agent_response_id=agent_response_id,
                document_index=meta['document_index'],
                distance=meta['distance'],
                # Legacy fields - set to None for new distance-based approach
                similarity_score=meta.get('similarity_score'),  # Optional for backward compatibility
                similarity_percentage=meta.get('similarity_percentage'),  # Optional for backward compatibility
                excerpt=meta['excerpt'],
                full_length=meta['full_length'],
                source_file=source,
                page_number=page_num,
                section_name=section,
                metadata_json=doc_metadata if doc_metadata else None,
                quality_tier=meta.get('quality_tier', 'Unknown')
            )
            citations.append(citation)

        db.bulk_save_objects(citations)
        db.commit()
        print(f"Successfully logged {len(citations)} citations for response {agent_response_id}")
        return True
    except Exception as e:
        print(f"Error logging RAG citations: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def get_rag_citations(agent_response_id: int) -> List[Dict[str, Any]]:
    """
    Get all RAG citations for a specific agent response.

    Args:
        agent_response_id: The ID of the agent response

    Returns:
        List of citation dictionaries
    """
    db = SessionLocal()
    try:
        citations = db.query(RAGCitation).filter(
            RAGCitation.agent_response_id == agent_response_id
        ).order_by(RAGCitation.document_index).all()

        result = []
        for citation in citations:
            result.append({
                "document_index": citation.document_index,
                "similarity_score": citation.similarity_score,
                "similarity_percentage": citation.similarity_percentage,
                "distance": citation.distance,
                "excerpt": citation.excerpt,
                "full_length": citation.full_length,
                "source_file": citation.source_file,
                "page_number": citation.page_number,
                "section_name": citation.section_name,
                "metadata": citation.metadata_json,
                "quality_tier": citation.quality_tier,
                "created_at": citation.created_at
            })

        return result
    except Exception as e:
        print(f"Error retrieving RAG citations: {e}")
        return []
    finally:
        db.close()


def get_session_citations(session_id: str) -> List[Dict[str, Any]]:
    """
    Get all RAG citations for all responses in a session.

    Args:
        session_id: The session ID

    Returns:
        List of citation dictionaries with response info
    """
    db = SessionLocal()
    try:
        # Join citations with responses to get session context
        citations = db.query(RAGCitation, AgentResponse).join(
            AgentResponse, RAGCitation.agent_response_id == AgentResponse.id
        ).filter(
            AgentResponse.session_id == session_id
        ).order_by(
            AgentResponse.created_at,
            RAGCitation.document_index
        ).all()

        result = []
        for citation, response in citations:
            result.append({
                "agent_response_id": citation.agent_response_id,
                "agent_id": response.agent_id,
                "document_index": citation.document_index,
                "similarity_score": citation.similarity_score,
                "similarity_percentage": citation.similarity_percentage,
                "distance": citation.distance,
                "excerpt": citation.excerpt,
                "full_length": citation.full_length,
                "source_file": citation.source_file,
                "page_number": citation.page_number,
                "section_name": citation.section_name,
                "metadata": citation.metadata_json,
                "quality_tier": citation.quality_tier,
                "created_at": citation.created_at
            })

        return result
    except Exception as e:
        print(f"Error retrieving session citations: {e}")
        return []
    finally:
        db.close()


# Composite indexes for better query performance
Index('idx_chat_session_timestamp', ChatHistory.session_id, ChatHistory.timestamp)
Index('idx_chat_model_type', ChatHistory.model_used, ChatHistory.query_type)
Index('idx_compliance_session_agent', ComplianceResult.session_id, ComplianceResult.agent_id)
Index('idx_compliance_agent_created', ComplianceResult.agent_id, ComplianceResult.created_at)
Index('idx_citation_response_id', RAGCitation.agent_response_id)
Index('idx_citation_similarity', RAGCitation.similarity_score.desc())
Index('idx_citation_quality_tier', RAGCitation.quality_tier)
