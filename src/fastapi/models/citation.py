"""
RAG citation ORM model.

This module contains the RAGCitation model for tracking document citations
and providing explainability for RAG-enhanced responses.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, JSON, DateTime, Index
from sqlalchemy.orm import relationship

from models.base import Base


class RAGCitation(Base):
    """
    RAG citation model for explainability and audit trails.

    This model stores detailed information about documents retrieved
    and used in RAG-enhanced responses, enabling:
    - Explainability: Show which documents influenced the response
    - Audit trails: Track data lineage for compliance
    - Quality assessment: Evaluate relevance of retrieved documents

    Attributes:
        id: Primary key
        agent_response_id: Foreign key to AgentResponse
        document_index: Position in retrieved results (1-based)
        distance: ChromaDB distance metric (lower = better match)
        similarity_score: Deprecated similarity score (backward compatibility)
        similarity_percentage: Deprecated percentage (backward compatibility)
        excerpt: First 300 chars of the document
        full_length: Total document length in characters
        source_file: Source filename or identifier
        page_number: Page number (if applicable)
        section_name: Section or chapter name
        metadata_json: Full metadata object from ChromaDB
        quality_tier: Quality assessment ('Excellent', 'High', 'Good', 'Fair', 'Low')
        created_at: Citation timestamp

    Relationships:
        agent_response: The AgentResponse this citation belongs to
    """
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


# Composite indexes for better query performance
Index('idx_citation_response_id', RAGCitation.agent_response_id)
Index('idx_citation_similarity', RAGCitation.similarity_score.desc())
Index('idx_citation_quality_tier', RAGCitation.quality_tier)
