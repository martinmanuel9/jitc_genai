import os
import time
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from services.llm_utils import get_llm
from services.llm_invoker import LLMInvoker
# from config.model_registry import (
#     list_supported_models,
# )
from llm_config.llm_config import get_model_config
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from typing import Optional
from sqlalchemy.orm import Session

# New imports for repository pattern
from models.chat import ChatHistory
from repositories import ChatRepository

class LLMService:
    def __init__(self, db: Optional[Session] = None):
        """
        Initialize LLM Service.

        Args:
            db: Optional database session. If not provided, creates own sessions
                for backward compatibility with existing code.
        """
        self.db = db
        self.chromadb_dir = os.getenv("CHROMADB_PERSIST_DIRECTORY", "/app/chroma_db_data")
        self.embedding_function = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")
        self.n_results = int(os.getenv("N_RESULTS", "3"))
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.compliance_agents = []

        # Initialize repository if db session provided
        if self.db:
            self.chat_repo = ChatRepository(self.db)
        else:
            self.chat_repo = None

    def get_llm_service(self, model_name: str):
        # Delegate to unified loader; it supports GPT-*, llama, llama2, llama3.1, and common OSS models
        return get_llm(model_name=model_name)

    def get_retriever(self, collection_name: str, metadata_filter: Optional[dict] = None):
        db = Chroma(
            persist_directory=self.chromadb_dir,
            collection_name=collection_name,
            embedding_function=self.embedding_function
        )
        # LangChain Chroma retriever expects "filter" (server API uses "where")
        search_kwargs = {"k": self.n_results}
        if metadata_filter:
            search_kwargs["filter"] = metadata_filter
        return db.as_retriever(search_kwargs=search_kwargs)

    def query_model(
        self,
        model_name: str,
        query: str,
        collection_name: str,
        query_type: str = "rag",
        session_id: Optional[str] = None,
        log_history: bool = True,
        metadata_filter: Optional[dict] = None,
    ) -> str:
        retriever = self.get_retriever(collection_name, metadata_filter=metadata_filter)
        llm = self.get_llm_service(model_name)

        prompt = ChatPromptTemplate.from_template(
            "{context}\n\nQuestion: {input}"
        )
        
        document_chain = create_stuff_documents_chain(llm=llm, prompt=prompt)
        chain = create_retrieval_chain(retriever=retriever, combine_docs_chain=document_chain)

        start_time = time.time()
        result = chain.invoke({"input": query})
        response_time_ms = int((time.time() - start_time) * 1000)

        # Save chat history (optional)
        if log_history:
            history = ChatHistory(
                user_query=query,
                response=result.get("answer", "No response generated."),
                model_used=model_name,
                collection_name=collection_name,
                query_type=query_type,
                response_time_ms=response_time_ms,
                session_id=session_id,
                source_documents=[doc.page_content for doc in result.get("context", [])] if result.get("context") else []
            )

            # Use repository pattern if db session provided, otherwise fall back to old pattern
            if self.chat_repo:
                try:
                    self.chat_repo.create(history)
                    self.db.commit()
                except Exception as e:
                    print(f"Failed to save chat history: {e}")
                    self.db.rollback()
            else:
                # Backward compatibility: create own session
                from core.database import SessionLocal
                session = SessionLocal()
                try:
                    session.add(history)
                    session.commit()
                except Exception as e:
                    print(f"Failed to save chat history: {e}")
                    session.rollback()
                finally:
                    session.close()

        return result.get("answer", "No response generated."), response_time_ms

    def query_direct(self, model_name: str, query: str, session_id: Optional[str] = None, log_history: bool = True) -> str:
        """
        Direct query to LLM without RAG retrieval.
        Used for test plan generation where we analyze section content directly.
        """
        start_time = time.time()

        # Use LLMInvoker for clean invocation
        content = LLMInvoker.invoke(model_name=model_name, prompt=query)
        response_time_ms = int((time.time() - start_time) * 1000)

        # Save to chat history if session_id provided
        if session_id and log_history:
            history = ChatHistory(
                user_query=query[:500],  # Truncate long queries
                response=content[:1000],
                model_used=model_name,
                collection_name="direct_query",  # Use placeholder since it's required
                query_type="direct",
                response_time_ms=response_time_ms,
                session_id=session_id,
                source_documents=[]  # No source documents for direct queries
            )

            # Use repository pattern if db session provided, otherwise fall back to old pattern
            if self.chat_repo:
                try:
                    self.chat_repo.create(history)
                    self.db.commit()
                except Exception as e:
                    print(f"Failed to save chat history for direct query: {e}")
                    self.db.rollback()
            else:
                # Backward compatibility: create own session
                from core.database import SessionLocal
                session = SessionLocal()
                try:
                    session.add(history)
                    session.commit()
                except Exception as e:
                    print(f"Failed to save chat history for direct query: {e}")
                    session.rollback()
                finally:
                    session.close()

        return content, response_time_ms

    def health_check(self):
        """Check service health and model availability."""
        health_status = {
            "status": "healthy",
            "chromadb_status": "connected",
            "models": {},
            "timestamp": time.time()
        }
        try:
            # Test ChromaDB connection
            test_db = Chroma(
                persist_directory=self.chromadb_dir, 
                collection_name="health_check",
                embedding_function=self.embedding_function
            )
            health_status["chromadb_status"] = "connected"
        except Exception as e:
            health_status["chromadb_status"] = f"error: {str(e)}"
            health_status["status"] = "degraded"
        
        # Test available models
        for model_cfg in list_supported_models():
            model = model_cfg.model_id
            try:
                llm = self.get_llm_service(model)
                health_status["models"][model] = "available"
            except Exception as e:
                health_status["models"][model] = "unavailable: %s" % str(e)
                health_status["status"] = "degraded"

        return health_status
