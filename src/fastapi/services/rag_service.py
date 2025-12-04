import os
import uuid
import time
import hashlib
import json
import logging
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import chromadb
from langchain_core.prompts import ChatPromptTemplate
from langchain.schema import Document
from langchain_huggingface import HuggingFaceEmbeddings
from services.llm_utils import get_llm
from services.llm_invoker import LLMInvoker

from core.database import SessionLocal
from models.agent import ComplianceAgent
from models.enums import SessionType, AnalysisType
from repositories.session_repository import SessionRepository
from repositories.response_repository import ResponseRepository, ComplianceRepository
from repositories.citation_repository import CitationRepository
# Note: Function calls to log_agent_session, log_agent_response, etc.
# need to be migrated to use repository methods (similar to agent_service.py)
from repositories.chat_repository import ChatRepository
from services.database import (
    log_agent_session,
    complete_agent_session,
    log_agent_response,
    log_compliance_result,
    log_rag_citations
)

logger = logging.getLogger("RAG_SERVICE_LOGGER")

class RAGService:
    def __init__(self, max_retries: int = 5, retry_delay: int = 3):
        # Replace HTTP URL with direct client
        self.chroma_host = os.getenv("CHROMA_HOST", "chromadb")
        self.chroma_port = int(os.getenv("CHROMA_PORT", "8000"))
        self._chroma_client = None
        self._max_retries = max_retries
        self._retry_delay = retry_delay

        # Embedding function (keep existing)
        self.embedding_function = HuggingFaceEmbeddings(
            model_name="sentence-transformers/multi-qa-mpnet-base-dot-v1"
        )

        self.n_results = int(os.getenv("N_RESULTS", "5"))

    @property
    def chroma_client(self):
        """Lazy initialization of ChromaDB client with retry logic."""
        if self._chroma_client is None:
            import time
            last_error = None
            for attempt in range(self._max_retries):
                try:
                    self._chroma_client = chromadb.HttpClient(
                        host=self.chroma_host,
                        port=self.chroma_port,
                        headers=self._get_auth_headers()
                    )
                    # Test the connection
                    self._chroma_client.heartbeat()
                    logger.info(f"ChromaDB connected at {self.chroma_host}:{self.chroma_port}")
                    break
                except Exception as e:
                    last_error = e
                    if attempt < self._max_retries - 1:
                        logger.warning(f"ChromaDB connection attempt {attempt + 1} failed: {e}. Retrying in {self._retry_delay}s...")
                        time.sleep(self._retry_delay)
                    else:
                        logger.error(f"Failed to connect to ChromaDB after {self._max_retries} attempts: {e}")
                        raise
        return self._chroma_client
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers if configured"""
        auth_token = os.getenv("CHROMA_AUTH_TOKEN")
        if auth_token:
            return {"Authorization": f"Bearer {auth_token}"}
        return {}

    @lru_cache(maxsize=1000)
    def _get_cached_embedding(self, query_hash: str, query: str) -> List[float]:
        """
        Generate and cache query embeddings.
        Uses LRU cache with query hash as key for better performance.
        """
        logger.debug(f"Generating embedding for query: {query[:50]}...")
        embedding = self.embedding_function.embed_query(query)
        return embedding

    def _generate_query_hash(self, query: str) -> str:
        """Generate a hash for query caching."""
        return hashlib.md5(query.encode('utf-8')).hexdigest()

    def _extract_excerpt(self, doc_text: str, max_length: int = 1500) -> str:
        """
        Extract a meaningful excerpt from document text.

        Args:
            doc_text: Full document text
            max_length: Maximum length of excerpt (default 1500 chars)

        Returns:
            Excerpt string suitable for citation
        """
        if not doc_text:
            return ""

        if len(doc_text) <= max_length:
            return doc_text.strip()

        lines = doc_text.split('\n')
        substantial_lines = [line for line in lines if len(line.strip()) > 40]

        if substantial_lines:
            excerpt_text = '\n'.join(substantial_lines)
            if len(excerpt_text) > max_length:
                truncated = excerpt_text[:max_length]
                last_period = truncated.rfind('.')
                if last_period > max_length - 200:
                    return excerpt_text[:last_period + 1] + "\n\n[...continued]"
                return truncated + "...\n\n[...continued]"
            return excerpt_text.strip()

        return doc_text[:max_length].strip() + "\n\n[...continued]"

    def _get_quality_tier_from_distance(self, distance: float) -> str:
        """
        Categorize document quality based on distance score.
        Lower distance = better match. No filtering - just informational tiers.

        ChromaDB uses L2 (Euclidean) distance by default where:
        - Distance 0 = perfect match
        - Typical good matches: 0-10
        - Fair matches: 10-30
        - Poor matches: 30+

        Args:
            distance: Distance score from ChromaDB (lower is better)

        Returns:
            Quality tier: "Excellent", "High", "Good", "Fair", "Low"
        """
        if distance <= 5:
            return "Excellent"
        elif distance <= 15:
            return "High"
        elif distance <= 30:
            return "Good"
        elif distance <= 50:
            return "Fair"
        else:
            return "Low"

    def _explain_distance_score(self, distance: float) -> str:
        """
        Provide a human-readable explanation of the distance score.

        Args:
            distance: Distance score from ChromaDB

        Returns:
            Explanation string
        """
        if distance <= 5:
            return "Very similar - highly relevant to your query"
        elif distance <= 15:
            return "Similar - relevant to your query"
        elif distance <= 30:
            return "Moderately similar - may contain relevant information"
        elif distance <= 50:
            return "Somewhat related - limited relevance"
        else:
            return "Distant match - may not be directly relevant"

    def _extract_smart_excerpt(self, doc_text: str, doc_metadata: Dict[str, Any]) -> str:
        """
        Extract a smart, context-aware excerpt from the document.

        Instead of arbitrary character limits, this uses the full chunk text
        since ChromaDB chunks are already semantically meaningful units
        (typically 1000 chars with 200 char overlap, broken at sentence boundaries).

        For very long chunks, we provide a focused excerpt with ellipsis.

        Args:
            doc_text: The full chunk text from ChromaDB
            doc_metadata: Metadata about the chunk

        Returns:
            Context-aware excerpt suitable for legal citation
        """
        # For chunks under 2000 chars, use the full text (it's already a coherent unit)
        if len(doc_text) <= 2000:
            return doc_text.strip()

        # For longer chunks, extract a focused excerpt
        # Try to find the most substantial content (avoid headers/footers)
        lines = doc_text.split('\n')

        # Filter out very short lines (likely headers/footers)
        substantial_lines = [line for line in lines if len(line.strip()) > 40]

        if substantial_lines:
            # Take first ~1500 chars of substantial content
            excerpt_text = '\n'.join(substantial_lines)
            if len(excerpt_text) > 1500:
                # Find a good breaking point (sentence or paragraph)
                truncated = excerpt_text[:1500]
                last_period = truncated.rfind('.')
                last_newline = truncated.rfind('\n\n')

                if last_period > 1000:
                    excerpt_text = excerpt_text[:last_period + 1] + "\n\n[...continued]"
                elif last_newline > 1000:
                    excerpt_text = excerpt_text[:last_newline] + "\n\n[...continued]"
                else:
                    excerpt_text = truncated + "...\n\n[...continued]"

            return excerpt_text.strip()

        # Fallback: use first 1500 chars with ellipsis
        return doc_text[:1500].strip() + "\n\n[...continued]"

    def _format_legal_citation(self, doc_metadata: Dict[str, Any], doc_num: int) -> str:
        """
        Format a single document citation in legal/academic style.
        Similar to Bluebook citation format for legal documents.

        Args:
            doc_metadata: Metadata dict containing document information
            doc_num: Citation number (for reference in text)

        Returns:
            Formatted citation string (e.g., "[1] MIL-STD-188-203-1A, at 13")
        """
        doc_name = doc_metadata.get('document_name', doc_metadata.get('source', 'Unknown'))
        page_num = doc_metadata.get('page_number', doc_metadata.get('page'))

        # Base citation with document name
        citation = f"[{doc_num}] {doc_name}"

        # Add page number if available (legal citation style)
        if page_num:
            citation += f", at {page_num}"

        # Add section if available
        section = doc_metadata.get('section_title', doc_metadata.get('section_name'))
        if section and section.strip():
            citation += f", § {section}"

        return citation

    def _format_document_citations(self, metadata_list: List[Dict[str, Any]]) -> str:
        """
        Format document citations in legal/academic research style with:
        1. Formal citation references
        2. Contextual excerpts with highlighted relevance
        3. Source provenance information
        4. Relevance scoring for transparency

        Args:
            metadata_list: List of document metadata dicts

        Returns:
            Formatted citation string for appending to responses
        """
        if not metadata_list:
            return ""

        # Build citation section similar to research paper references
        citations = ["\n\n" + "-"*80]
        citations.append("SOURCES AND CITATIONS")
        citations.append("-"*80 + "\n")
        citations.append("This response is based on the following source documents:\n")

        # Create numbered citations (legal/academic style)
        for meta in metadata_list:
            doc_num = meta['document_index']
            distance = meta['distance']
            doc_metadata = meta.get('metadata', {})
            quality_tier = meta.get('quality_tier', 'Unknown')
            distance_explanation = meta.get('distance_explanation', '')

            # Format legal-style citation
            legal_cite = self._format_legal_citation(doc_metadata, doc_num)

            # Get additional metadata for provenance
            chunk_index = doc_metadata.get('chunk_index', 0)
            total_chunks = doc_metadata.get('total_chunks', 1)
            start_pos = doc_metadata.get('start_position', 0)
            end_pos = doc_metadata.get('end_position', 0)

            # Build comprehensive citation entry
            citation_entry = [f"\n{legal_cite}"]

            # Add relevance assessment
            citation_entry.append(f"   Relevance: {quality_tier} (Distance: {distance:.2f} - {distance_explanation})")

            # Add location within document
            location_info = f"   Location: Chunk {chunk_index + 1} of {total_chunks}"
            if start_pos and end_pos:
                location_info += f" (chars {start_pos}-{end_pos})"
            citation_entry.append(location_info)

            # Add substantive excerpt with context markers
            # Extract excerpt from document_text or metadata
            document_text = meta.get('document_text', '')
            excerpt = meta.get('excerpt', self._extract_excerpt(document_text))
            full_length = meta.get('full_length', doc_metadata.get('full_length', len(document_text)))

            # Indicate if excerpt is from beginning, middle, or end
            position_indicator = ""
            if start_pos == 0:
                position_indicator = "[Beginning of document] "
            elif end_pos and full_length and end_pos >= full_length - 100:
                position_indicator = "[End of document] "
            elif start_pos and full_length:
                position_indicator = f"[Position {start_pos:,} of {full_length:,} chars] "

            citation_entry.append(f"\n   Excerpt:")
            if position_indicator:
                citation_entry.append(f"   {position_indicator}")

            # Format excerpt with better readability
            if excerpt:
                excerpt_lines = excerpt.split('\n')
                cleaned_lines = []
                for line in excerpt_lines:
                    stripped = line.strip()
                    if stripped:
                        cleaned_lines.append(f"   | {stripped}")

                if cleaned_lines:
                    citation_entry.append('\n'.join(cleaned_lines[:15]))
                    if len(cleaned_lines) > 15:
                        citation_entry.append(f"   | ... ({len(cleaned_lines) - 15} more lines)")
            else:
                citation_entry.append("   | [No excerpt available]")

            # Add timestamp if available
            timestamp = doc_metadata.get('timestamp')
            if timestamp:
                citation_entry.append(f"\n   Indexed: {timestamp}")

            citations.append('\n'.join(citation_entry))

        # Add footer with explanation
        citations.append("\n" + "-"*80)
        citations.append("CITATION GUIDE:")
        citations.append("Citations follow [number] Document Name, at page format\n")
        citations.append("Relevance tiers: Excellent > High > Good > Fair > Low \n")
        citations.append("Distance scores: Lower values indicate better semantic matches \n")
        citations.append("Excerpts show the specific content used to generate this response\n")
        citations.append("-"*80)

        return "\n".join(citations)

    def _validate_collection_name(self, collection_name: str) -> bool:
        """
        Validate collection name to prevent injection attacks.
        Collection names should only contain alphanumeric characters, hyphens, and underscores.
        """
        import re
        if not collection_name or not isinstance(collection_name, str):
            return False
        # Allow alphanumeric, hyphens, underscores, and dots (common in collection names)
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', collection_name):
            logger.warning(f"Invalid collection name format: {collection_name}")
            return False
        if len(collection_name) > 255:  # Reasonable max length
            logger.warning(f"Collection name too long: {len(collection_name)} characters")
            return False
        return True

    def run_rag_chain(
        self,
        query: str,
        collection_name: str,
        model_name: str,
        top_k: Optional[int] = None,
        where: Optional[Dict] = None,
        include_citations: bool = True
    ) -> Tuple[str, int, List[Dict[str, Any]], str]:
        """
        1) Pulls the top-k docs from ChromaDB via your API
        2) Stuffs them into a LangChain QA chain
        3) Returns (answer, response_time_ms, metadata_list, formatted_citations)

        Args:
            query: The search query
            collection_name: Name of the collection to search
            model_name: LLM model to use for generation
            top_k: Number of documents to retrieve (optional, uses self.n_results if not specified)
            where: Optional filter dict for document filtering (e.g., {"document_name": "contract.pdf"})
            include_citations: If True, returns citation metadata separately

        Returns:
            Tuple of (answer, response_time_ms, metadata_list, formatted_citations)
        """
        # 1) fetch docs with metadata
        docs, found, metadata_list = self.get_relevant_documents(
            query=query,
            collection_name=collection_name,
            top_k=top_k,
            where=where,
            include_metadata=True
        )
        if not found:
            return "No relevant documents found.", 0, [], ""

        # 2) wrap for LangChain
        lc_docs = [Document(page_content=d) for d in docs]

        # 3) build a modern LCEL QA chain
        llm = get_llm(model_name=model_name)

        # Create prompt template for question answering
        prompt = ChatPromptTemplate.from_template("""Answer the question based on the following context:

{context}

Question: {question}

Answer:""")

        # Create the chain using LCEL (LangChain Expression Language)
        chain = (
            {
                "context": lambda x: "\n\n".join([doc.page_content for doc in x["documents"]]),
                "question": lambda x: x["question"]
            }
            | prompt
            | llm
        )

        start = time.time()
        result = chain.invoke({"documents": lc_docs, "question": query})
        # Extract text content from result (handles both string and message types)
        answer = result.content if hasattr(result, 'content') else str(result)
        rt_ms = int((time.time() - start) * 1000)

        # 4) Format citations separately (don't append to answer)
        formatted_citations = ""
        if include_citations and metadata_list:
            formatted_citations = self._format_document_citations(metadata_list)

        return answer, rt_ms, metadata_list, formatted_citations


    def process_query_with_rag(
        self,
        query_text: str,
        collection_name: str,
        model_name: str,
        top_k: Optional[int] = None,
        where: Optional[Dict] = None,
        include_citations: bool = True
    ) -> Tuple[str, int, List[Dict[str, Any]], str]:
        """
        Simple RAG entrypoint that:
            1) Retrieves top-k docs
            2) Runs a 'stuff'-style QA chain
            3) Returns (response, response_time_ms, metadata_list, formatted_citations)

        Args:
            query_text: The user query
            collection_name: Name of the collection to search
            model_name: LLM model to use
            top_k: Number of documents to retrieve (optional)
            where: Optional filter dict for document filtering (e.g., {"document_name": "contract.pdf"})
            include_citations: If True, returns document citations separately

        Returns:
            Tuple of (answer_string, response_time_ms, metadata_list, formatted_citations)
        """

        answer, rt_ms, metadata_list, formatted_citations = self.run_rag_chain(
            query=query_text,
            collection_name=collection_name,
            model_name=model_name,
            top_k=top_k,
            where=where,
            include_citations=include_citations
        )
        logger.info(f"RAG response in rag_service: {answer[:200]}... (took {rt_ms} ms)")

        return answer, rt_ms, metadata_list, formatted_citations
        
        
        
    def test_connection(self) -> bool:
        """Test ChromaDB connection"""
        try:
            heartbeat = self.chroma_client.heartbeat()
            print(f"ChromaDB connected: {heartbeat}")
            return True
        except Exception as e:
            print(f"ChromaDB connection failed: {e}")
            return False

    def list_available_collections(self) -> List[str]:
        """List all available collections via native ChromaDB client"""
        try:
            collections = self.chroma_client.list_collections()
            collection_names = [c.name for c in collections]
            logger.info(f"Available collections: {collection_names}")
            return collection_names
        except Exception as e:
            logger.error(f"Error listing collections: {e}")
            return []


    def get_relevant_documents(
        self,
        query: str,
        collection_name: str,
        top_k: int = None,
        n_results: int = None,
        where: Optional[Dict] = None,
        include_metadata: bool = False
    ):
        """
        Query ChromaDB directly and return results.

        Args:
            query: Search query
            collection_name: Name of collection
            top_k: Number of results (alias for n_results)
            n_results: Number of results
            where: Optional filter
            include_metadata: If True, returns tuple format with metadata for citations

        Returns:
            If include_metadata=True: Tuple of (documents, found, metadata_list)
            If include_metadata=False: Dict with results
        """
        try:
            # Get collection
            collection = self.chroma_client.get_collection(collection_name)

            # Generate query embedding
            query_embedding = self.embedding_function.embed_query(query)

            # Use top_k if provided, otherwise n_results, otherwise default
            num_results = top_k or n_results or self.n_results

            # Query collection (native method - much faster)
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=num_results,
                where=where,
                include=["documents", "metadatas", "distances"]
            )

            documents = results["documents"][0] if results["documents"] else []
            metadatas = results["metadatas"][0] if results["metadatas"] else []
            distances = results["distances"][0] if results["distances"] else []

            # Return tuple format for RAG chain (with metadata for citations)
            if include_metadata:
                found = len(documents) > 0

                # Build metadata list with citation info
                metadata_list = []
                for idx, (doc, meta, dist) in enumerate(zip(documents, metadatas, distances), 1):
                    metadata_list.append({
                        'document_index': idx,
                        'distance': dist,
                        'quality_tier': self._get_quality_tier_from_distance(dist),
                        'distance_explanation': f"Similarity score: {1 - (dist / 100):.2%}",
                        'metadata': meta,
                        'document_text': doc
                    })

                return documents, found, metadata_list

            # Return dict format for API compatibility
            return {
                "status": "success",
                "query": query,
                "collection": collection_name,
                "results": {
                    "ids": results["ids"][0] if results["ids"] else [],
                    "documents": documents,
                    "metadatas": metadatas,
                    "distances": distances
                }
            }
        except Exception as e:
            if include_metadata:
                return [], False, []
            return {
                "status": "error",
                "message": str(e),
                "query": query,
                "collection": collection_name
            }
        
        

    def get_llm_service(self, model_name: str):
        """Get LLM service for the specified model"""
        model_name = model_name.lower()
        if model_name in ["gpt-4", "gpt-3.5", "gpt-3.5-turbo"]:
            return get_llm(model_name=model_name)
        # elif model_name in ["llama", "llama3"]:
        #     return get_llm(model_name=model_name)
        else:
            raise ValueError(f"Unsupported model: {model_name}")

        
    def process_agent_with_rag(self, agent: Dict[str, Any], query_text: str, collection_name: str, session_id: str, db: Session, include_citations: bool = True) -> Dict[str, Any]:
        """
        Process query with agent using RAG via API with document citations.

        Args:
            agent: Agent configuration dict
            query_text: User query
            collection_name: Vector DB collection name
            session_id: Session ID for logging
            db: Database session
            include_citations: If True, includes document citations with similarity scores

        Returns:
            Dict with agent response and metadata
        """
        start_time = time.time()

        try:
            logger.info(f"Processing with agent: {agent['name']} using model: {agent['model_name']}")

            # Try to get relevant documents via API with metadata
            relevant_docs, docs_found, metadata_list = self.get_relevant_documents(
                query=query_text,
                collection_name=collection_name,
                include_metadata=include_citations
            )

            if docs_found and relevant_docs:
                logger.info(f"Using RAG mode with {len(relevant_docs)} documents")

                # Create context from retrieved documents
                context = "\n\n---DOCUMENT SEPARATOR---\n\n".join(relevant_docs)

                # Enhanced RAG prompt
                enhanced_content = f"""KNOWLEDGE BASE CONTEXT:
{context}

USER QUERY: {query_text}

INSTRUCTIONS:
1. Carefully analyze the provided knowledge base context above
2. Use information from the context to inform your analysis of the user query
3. If the context contains relevant information, cite or reference it in your response
4. If the context is not directly relevant, acknowledge this and proceed with your general knowledge
5. Provide a comprehensive analysis that combines context information with your expertise"""

                formatted_user_prompt = agent["user_prompt_template"].replace("{data_sample}", enhanced_content)

                full_prompt = f"{agent['system_prompt']}\n\n{formatted_user_prompt}"

                # Use LLMInvoker for clean invocation
                final_response = LLMInvoker.invoke(model_name=agent['model_name'], prompt=full_prompt)

                response_time_ms = int((time.time() - start_time) * 1000)
                processing_method = f"rag_enhanced_{agent['model_name']}"

                # Append document citations instead of simple info
                if include_citations and metadata_list:
                    citations = self._format_document_citations(metadata_list)
                    final_response = final_response + citations
                else:
                    # Fallback to simple info if citations not requested
                    rag_info = f"\n\n---\n**RAG Information**: Used {len(relevant_docs)} relevant documents from collection '{collection_name}' with {agent['model_name']} model."
                    final_response = final_response + rag_info

            else:
                logger.info(f"Using Direct LLM mode - no relevant documents found")

                formatted_user_prompt = agent["user_prompt_template"].replace("{data_sample}", query_text)
                full_prompt = f"{agent['system_prompt']}\n\n{formatted_user_prompt}"

                # Use LLMInvoker for clean invocation
                final_response = LLMInvoker.invoke(model_name=agent['model_name'], prompt=full_prompt)

                response_time_ms = int((time.time() - start_time) * 1000)
                processing_method = f"direct_{agent['model_name']}"

                direct_info = f"\n\n---\n**Direct LLM Information**: No relevant documents found in collection '{collection_name}'. Used {agent['model_name']} model directly."
                final_response = final_response + direct_info

            # Log agent response and get the response ID
            agent_response_id = log_agent_response(
                session_id=session_id,
                agent_id=agent["id"],
                response_text=final_response,
                processing_method=processing_method,
                response_time_ms=response_time_ms,
                model_used=agent["model_name"],
                rag_used=docs_found,
                documents_found=len(relevant_docs) if docs_found else 0,
                rag_context=context if docs_found and relevant_docs else None
            )

            # Log RAG citations if available and response was logged
            if agent_response_id and include_citations and metadata_list:
                log_rag_citations(agent_response_id, metadata_list)
                logger.info(f"Logged {len(metadata_list)} citations for agent response {agent_response_id}")

            log_compliance_result(
                agent_id=agent["id"],
                data_sample=query_text,
                confidence_score=None,
                reason="RAG analysis completed",
                raw_response=final_response,
                processing_method=processing_method,
                response_time_ms=response_time_ms,
                model_used=agent["model_name"],
                session_id=session_id
            )

            return {
                "agent_id": agent["id"],
                "agent_name": agent["name"],
                "response": final_response,
                "processing_method": processing_method,
                "response_time_ms": response_time_ms,
                "rag_used": docs_found,
                "documents_found": len(relevant_docs) if docs_found else 0
            }

        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            error_response = f"Error processing with agent {agent['name']}: {str(e)}"
            logger.error(f"Error in process_agent_with_rag: {e}", exc_info=True)

            return {
                "agent_id": agent["id"],
                "agent_name": agent["name"],
                "response": error_response,
                "processing_method": "error",
                "response_time_ms": response_time_ms,
                "rag_used": False,
                "documents_found": 0
            }


    def run_rag_check(self, query_text: str, collection_name: str, agent_ids: List[int], db: Session) -> Dict[str, Any]:
        """Run RAG check with multiple agents and enhanced logging"""
        session_id = str(uuid.uuid4())
        start_time = time.time()

        session_type = SessionType.MULTI_AGENT_DEBATE if len(agent_ids) > 1 else SessionType.RAG_ANALYSIS
        log_agent_session(
            session_id=session_id,
            session_type=session_type,
            analysis_type=AnalysisType.RAG_ENHANCED,
            user_query=query_text,
            collection_name=collection_name
        )

        self.load_selected_compliance_agents(agent_ids)

        # Get consolidated citations for the collection query (run once for all agents)
        _, _, metadata_list = self.get_relevant_documents(
            query=query_text,
            collection_name=collection_name,
            include_metadata=True
        )
        formatted_citations = self._format_document_citations(metadata_list) if metadata_list else ""

        results = {}
        with ThreadPoolExecutor() as executor:
            futures = {
                executor.submit(self.process_agent_with_rag, agent, query_text, collection_name, session_id, db): i
                for i, agent in enumerate(self.compliance_agents)
            }
            for future in as_completed(futures):
                idx = futures[future]
                result = future.result()
                results[result["agent_name"]] = result["response"]
        
        total_time = int((time.time() - start_time) * 1000)
        complete_agent_session(
            session_id=session_id,
            overall_result={
                "agent_responses": results,
                "collection_used": collection_name
            },
            agent_count=len(agent_ids),
            total_response_time_ms=total_time,
            status='completed'
        )

        # Save to chat history for unified history tracking
        try:
            chat_repo = ChatRepository(db)

            # Format response for history display
            model_names = list(set([agent["model_name"] for agent in self.compliance_agents]))

            response_summary = f"**RAG Agent Analysis** ({len(agent_ids)} agents, collection: {collection_name})\n\n"
            for idx, (agent_name, response_text) in enumerate(results.items(), 1):
                response_summary += f"**{idx}. {agent_name}:**\n{response_text}\n\n"

            chat_repo.create_chat_entry(
                user_query=query_text,
                response=response_summary,
                model_used=", ".join(model_names),
                collection_name=collection_name,
                query_type="rag_agent",
                response_time_ms=total_time,
                session_id=session_id,
                source_documents=None
            )
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to save RAG agent check to chat history: {e}")
            # Don't fail the entire operation if chat history save fails
            db.rollback()

        return {
            "agent_responses": results,
            "collection_used": collection_name,
            "session_id": session_id,
            "processing_time": total_time,
            "formatted_citations": formatted_citations
        }

    def run_rag_debate_sequence(self, db: Session, session_id: Optional[str], agent_ids: List[int], query_text: str, collection_name: str) -> Tuple[str, List[Dict[str, Any]], str]:
        """Run RAG debate sequence with multiple agents and enhanced logging"""
        if not session_id:
            session_id = str(uuid.uuid4())

        start_time = time.time()

        log_agent_session(
            session_id=session_id,
            session_type=SessionType.RAG_DEBATE,
            analysis_type=AnalysisType.RAG_ENHANCED,
            user_query=query_text,
            collection_name=collection_name
        )

        # Get consolidated citations for the collection query (run once for all agents)
        _, _, metadata_list = self.get_relevant_documents(
            query=query_text,
            collection_name=collection_name,
            include_metadata=True
        )
        formatted_citations = self._format_document_citations(metadata_list) if metadata_list else ""

        # NOTE: DebateSession table was removed in Phase 5
        # Debate sequences no longer need session tracking in a separate table
        # Agent responses are tracked in agent_responses table with session_id

        # Load agents directly by IDs instead of querying debate_sessions
        debate_agents = []
        for agent_id in agent_ids:
            agent = db.query(ComplianceAgent).filter(ComplianceAgent.id == agent_id).first()
            if agent:
                debate_agents.append({
                    "id": agent.id,
                    "name": agent.name,
                    "model_name": agent.model_name,
                    "system_prompt": agent.system_prompt,
                    "user_prompt_template": agent.user_prompt_template,
                    "temperature": agent.temperature
                })
        
        debate_chain = []
        cumulative_context = f"Original user query: {query_text}\n\n"
        
        for i, agent in enumerate(debate_agents):
            print(f"Debate Round {i+1}: Agent {agent['name']}")
            
            # For the first agent, use original query. For subsequent agents, use cumulative context
            current_input = cumulative_context if i > 0 else query_text
            
            # Process with RAG
            result = self.process_agent_with_rag(agent, current_input, collection_name, session_id, db)
            
            agent_response_id = self._update_agent_response_sequence_order(session_id, agent["id"], i + 1)
            
            debate_chain.append({
                "agent_id": agent["id"],
                "agent_name": agent["name"],
                "response": result["response"],
                "processing_method": result["processing_method"],
                "response_time_ms": result["response_time_ms"],
                "rag_used": result["rag_used"],
                "documents_found": result["documents_found"],
                "sequence_order": i + 1
            })
            
            cumulative_context += f"--- Agent {agent['name']} Analysis ---\n{result['response']}\n\n"
        
        total_time = int((time.time() - start_time) * 1000)
        complete_agent_session(
            session_id=session_id,
            overall_result={
                "debate_chain": debate_chain,
                "collection_used": collection_name
            },
            agent_count=len(agent_ids),
            total_response_time_ms=total_time,
            status='completed'
        )

        # Save to chat history for unified history tracking
        try:
            chat_repo = ChatRepository(db)

            # Format response for history display
            model_names = list(set([agent["model_name"] for agent in debate_agents]))

            response_summary = f"**RAG Debate Sequence** ({len(agent_ids)} agents, collection: {collection_name})\n\n"
            for idx, round_result in enumerate(debate_chain, 1):
                agent_name = round_result.get('agent_name', 'Unknown Agent')
                response_text = round_result.get('response', 'No response')
                response_summary += f"**Round {idx}: {agent_name}**\n{response_text}\n\n"

            chat_repo.create_chat_entry(
                user_query=query_text,
                response=response_summary,
                model_used=", ".join(model_names),
                collection_name=collection_name,
                query_type="rag_debate_sequence",
                response_time_ms=total_time,
                session_id=session_id,
                source_documents=None
            )
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to save RAG debate sequence to chat history: {e}")
            # Don't fail the entire operation if chat history save fails
            db.rollback()

        return session_id, debate_chain, formatted_citations

    def load_selected_compliance_agents(self, agent_ids: List[int]):
        """Load selected compliance agents"""
        session = SessionLocal()
        try:
            self.compliance_agents = []
            agents = session.query(ComplianceAgent).filter(ComplianceAgent.id.in_(agent_ids)).all()
            for agent in agents:
                self.compliance_agents.append({
                    "id": agent.id,
                    "name": agent.name,
                    "model_name": agent.model_name.lower(),
                    "system_prompt": agent.system_prompt,
                    "user_prompt_template": agent.user_prompt_template
                })
        finally:
            session.close()

    def load_debate_agents(self, session_id: str) -> List[Dict[str, Any]]:
        """Load debate agents in order"""
        session = SessionLocal()
        try:
            debate_sessions = session.query(DebateSession).filter(
                DebateSession.session_id == session_id
            ).order_by(DebateSession.debate_order).all()
            
            agent_ids = [ds.compliance_agent_id for ds in debate_sessions]
            agents = session.query(ComplianceAgent).filter(ComplianceAgent.id.in_(agent_ids)).all()
            agent_map = {agent.id: agent for agent in agents}
            
            debate_agents = []
            for ds in debate_sessions:
                agent = agent_map.get(ds.compliance_agent_id)
                if agent:
                    debate_agents.append({
                        "id": agent.id,
                        "name": agent.name,
                        "model_name": agent.model_name.lower(),
                        "system_prompt": agent.system_prompt,
                        "user_prompt_template": agent.user_prompt_template,
                        "debate_order": ds.debate_order
                    })
            return debate_agents
        finally:
            session.close()
    
    def _update_agent_response_sequence_order(self, session_id: str, agent_id: int, sequence_order: int):
        """Update the sequence order for an agent response in a debate"""
        db = SessionLocal()
        try:
            # Find the most recent response for this agent in this session
            from models.response import AgentResponse
            response = db.query(AgentResponse).filter(
                AgentResponse.session_id == session_id,
                AgentResponse.agent_id == agent_id
            ).order_by(AgentResponse.created_at.desc()).first()
            
            if response:
                response.sequence_order = sequence_order
                db.commit()
                return response.id
        except Exception as e:
            print(f"Error updating sequence order: {e}")
            db.rollback()
        finally:
            db.close()
        return None

    def query_collection_info(self, collection_name: str) -> Dict:
        """Get collection information"""
        try:
            collection = self.chroma_client.get_collection(collection_name)
            return {
                "name": collection.name,
                "count": collection.count(),
                "metadata": collection.metadata
            }
        except Exception as e:
            return {"error": str(e)}
