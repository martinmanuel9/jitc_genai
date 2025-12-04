from typing import Optional, List, Dict, Any, Tuple
from pydantic import Field
from services.rag_service import RAGService
from services.llm_service import LLMService

class EvaluationService:
    def __init__(self, rag: RAGService, llm: LLMService):
        self.rag = rag
        self.llm = llm

    def evaluate_document(
        self,
        document_id: str,
        collection_name: str,
        prompt: str,
        top_k: Optional[int] = Field(5),
        model_name: Optional[str] = Field(...),
        session_id: str = None,
        include_citations: bool = True,
    ) -> Tuple[str, int, List[Dict[str, Any]], str]:
        """
        Evaluate a document using RAG with citation support.

        Args:
            document_id: Document identifier
            collection_name: ChromaDB collection name
            prompt: Evaluation prompt
            top_k: Number of documents to retrieve
            model_name: LLM model to use
            session_id: Session identifier
            include_citations: Whether to include citation metadata

        Returns:
            Tuple of (answer, response_time_ms, metadata_list, formatted_citations)
        """
        # 1) RAG‐fetch the most relevant chunks of your document with metadata
        # Build a query that filters by document_id
        where_filter = {"document_id": document_id} if document_id else None

        # Call with include_metadata=True to get citation data
        documents, found, metadata_list = self.rag.get_relevant_documents(
            query=prompt,
            collection_name=collection_name,
            n_results=top_k,
            where=where_filter,
            include_metadata=True
        )

        if not found or not documents:
            raise Exception(f"No documents found for document_id: {document_id}")

        context = "\n\n".join(documents[:top_k])

        # 2) stitch your user's prompt onto those chunks
        full_prompt = f"""
Here's the relevant context from document `{document_id}`:

{context}

---
Now: {prompt}
""".strip()

        # 3) call LLMService with the specified model
        answer, rt_ms = self.llm.query_model(
            model_name=model_name,
            query=full_prompt,
            collection_name=collection_name,
            query_type="rag",
            session_id=session_id
        )

        # 4) Format citations if requested
        formatted_citations = ""
        if include_citations and metadata_list:
            # Use RAG service's citation formatting
            formatted_citations = self.rag._format_document_citations(metadata_list)

        return answer, rt_ms, metadata_list, formatted_citations
