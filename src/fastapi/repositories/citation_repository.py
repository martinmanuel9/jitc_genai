"""
Citation Repository

This module provides data access layer for RAGCitation operations.
Handles tracking document citations for explainability and audit trails.
"""

from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional, Dict, Any
import logging

from models.citation import RAGCitation
from models.response import AgentResponse
from repositories.base import BaseRepository

logger = logging.getLogger("CITATION_REPOSITORY")


class CitationRepository(BaseRepository[RAGCitation]):
    """
    Repository for managing RAGCitation database operations.

    Extends BaseRepository to provide:
    - Standard CRUD operations
    - Bulk citation creation
    - Citation retrieval by response/session
    - Quality tier filtering
    """

    def __init__(self, db: Session):
        """
        Initialize the citation repository.

        Args:
            db: SQLAlchemy database session
        """
        super().__init__(RAGCitation, db)

    def bulk_create_citations(
        self,
        agent_response_id: int,
        metadata_list: List[Dict[str, Any]]
    ) -> bool:
        """
        Create multiple citations in bulk for a response.

        Args:
            agent_response_id: Agent response identifier
            metadata_list: List of citation metadata dictionaries

        Returns:
            True if successful, False otherwise

        Example metadata structure:
            {
                'document_index': 1,
                'distance': 0.234,
                'similarity_score': 0.876,  # Optional for backward compatibility
                'similarity_percentage': 87.6,  # Optional
                'excerpt': 'First 300 chars...',
                'full_length': 1500,
                'quality_tier': 'High',
                'metadata': {
                    'document_name': 'file.pdf',
                    'page_number': 5,
                    'section_title': 'Chapter 2'
                }
            }
        """
        try:
            citations = []
            for meta in metadata_list:
                doc_metadata = meta.get('metadata', {})

                # Extract page number from multiple possible keys
                page_num = doc_metadata.get('page_number') or doc_metadata.get('page')

                # Extract section from multiple possible keys
                section = (
                    doc_metadata.get('section_title') or
                    doc_metadata.get('section_name') or
                    doc_metadata.get('section')
                )

                # Extract source file/document name
                source = doc_metadata.get('document_name') or doc_metadata.get('source')

                citation = RAGCitation(
                    agent_response_id=agent_response_id,
                    document_index=meta['document_index'],
                    distance=meta['distance'],
                    similarity_score=meta.get('similarity_score'),
                    similarity_percentage=meta.get('similarity_percentage'),
                    excerpt=meta['excerpt'],
                    full_length=meta['full_length'],
                    source_file=source,
                    page_number=page_num,
                    section_name=section,
                    metadata_json=doc_metadata if doc_metadata else None,
                    quality_tier=meta.get('quality_tier', 'Unknown')
                )
                citations.append(citation)

            self.bulk_create(citations)
            logger.info(f"Successfully logged {len(citations)} citations for response {agent_response_id}")
            return True
        except Exception as e:
            logger.error(f"Error logging RAG citations: {e}")
            self.db.rollback()
            return False

    def get_by_response_id(self, agent_response_id: int) -> List[Dict[str, Any]]:
        """
        Get all citations for a specific agent response.

        Args:
            agent_response_id: Agent response identifier

        Returns:
            List of citation dictionaries
        """
        try:
            citations = self.db.query(RAGCitation).filter(
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
            logger.error(f"Error retrieving RAG citations for response {agent_response_id}: {e}")
            return []

    def get_by_session_id(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get all citations for all responses in a session.

        Args:
            session_id: Session identifier

        Returns:
            List of citation dictionaries with response info
        """
        try:
            # Join citations with responses to get session context
            citations = self.db.query(RAGCitation, AgentResponse).join(
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
            logger.error(f"Error retrieving session citations for {session_id}: {e}")
            return []

    def get_by_quality_tier(
        self,
        quality_tier: str,
        limit: int = 100
    ) -> List[RAGCitation]:
        """
        Get citations by quality tier.

        Args:
            quality_tier: Quality tier ('Excellent', 'High', 'Good', 'Fair', 'Low')
            limit: Maximum number of citations

        Returns:
            List of RAGCitation objects
        """
        return self.get_by_filter({"quality_tier": quality_tier}, limit=limit)

    def get_top_citations(
        self,
        agent_response_id: int,
        limit: int = 5
    ) -> List[RAGCitation]:
        """
        Get top N citations by similarity (lowest distance) for a response.

        Args:
            agent_response_id: Agent response identifier
            limit: Number of top citations to retrieve

        Returns:
            List of RAGCitation objects ordered by distance (ascending)
        """
        try:
            return self.db.query(RAGCitation).filter(
                RAGCitation.agent_response_id == agent_response_id
            ).order_by(RAGCitation.distance.asc()).limit(limit).all()
        except Exception as e:
            logger.error(f"Error retrieving top citations: {e}")
            return []
