"""
RAG Assessment Service (RAG-AS)
Comprehensive RAG performance monitoring, evaluation, and analytics service.
"""

import os
import time
import uuid
import json
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict

from services.rag_service import RAGService
from services.llm_service import LLMService
import logging

logger = logging.getLogger("RAG_ASSESSMENT_SERVICE")

@dataclass
class RAGPerformanceMetrics:
    """Individual RAG operation performance metrics"""
    session_id: str
    query: str
    collection_name: str
    retrieval_time_ms: float
    generation_time_ms: float
    total_time_ms: float
    documents_retrieved: int
    documents_used: int
    relevance_score: float
    context_length: int
    response_length: int
    model_name: str
    success: bool
    error_message: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)

@dataclass
class RAGAlignmentAssessment:
    """RAG output alignment with original request assessment"""
    session_id: str
    intent_alignment_score: float  # 0-1 scale: Does output match user intent?
    query_coverage_score: float  # 0-1 scale: How well does output cover query requirements?
    instruction_adherence_score: float  # 0-1 scale: Follows given instructions/constraints
    answer_type_classification: str  # "direct_answer", "analysis", "summary", "explanation", "comparison"
    expected_answer_type: str  # What type was expected based on query
    answer_type_match: bool  # Does actual match expected?
    tone_consistency_score: float  # 0-1 scale: Maintains appropriate tone
    scope_accuracy_score: float  # 0-1 scale: Stays within requested scope
    missing_elements: List[str]  # Key elements from query not addressed
    extra_elements: List[str]  # Additional elements provided beyond request
    assessment_confidence: float  # 0-1 scale: Confidence in alignment assessment
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)

@dataclass
class RAGQualityAssessment:
    """RAG quality assessment metrics"""
    session_id: str
    relevance_score: float  # 0-1 scale
    coherence_score: float  # 0-1 scale
    factual_accuracy: float  # 0-1 scale
    completeness_score: float  # 0-1 scale
    context_utilization: float  # 0-1 scale
    overall_quality: float  # 0-1 scale
    assessment_method: str  # "automated", "human", "hybrid"
    assessor_model: Optional[str] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)

@dataclass
class RAGClassificationMetrics:
    """Classification and categorization metrics for RAG outputs"""
    session_id: str
    query_classification: str  # "factual", "analytical", "procedural", "comparative", "evaluative"
    response_classification: str  # Classification of actual response type
    classification_confidence: float  # 0-1 scale: Confidence in classification
    domain_relevance: str  # "legal", "technical", "business", "general", "mixed"
    complexity_level: str  # "simple", "moderate", "complex", "expert"
    information_density: float  # 0-1 scale: Information content ratio
    actionability_score: float  # 0-1 scale: How actionable is the response?
    specificity_score: float  # 0-1 scale: Level of specific details provided
    citation_quality: float  # 0-1 scale: Quality of references to source documents
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)

class RAGAssessmentService:
    """
    Comprehensive RAG Assessment Service for performance monitoring and quality evaluation.
    """
    
    def __init__(self, rag_service: RAGService = None, llm_service: LLMService = None):
        self.rag_service = rag_service or RAGService()
        self.llm_service = llm_service or LLMService()
        
        # In-memory metrics storage (consider moving to database for production)
        self.performance_metrics: Dict[str, RAGPerformanceMetrics] = {}
        self.quality_assessments: Dict[str, RAGQualityAssessment] = {}
        self.alignment_assessments: Dict[str, RAGAlignmentAssessment] = {}
        self.classification_metrics: Dict[str, RAGClassificationMetrics] = {}
        
        # Assessment configuration
        self.assessment_models = {
            "relevance": "gpt-3.5-turbo",
            "coherence": "gpt-3.5-turbo", 
            "factual": "gpt-4",
            "quality": "gpt-3.5-turbo"
        }
        
    def assess_rag_query(
        self,
        query: str,
        collection_name: str,
        model_name: str = "gpt-3.5-turbo",
        top_k: int = 5,
        include_quality_assessment: bool = True,
        include_alignment_assessment: bool = True,
        include_classification_metrics: bool = True,
        session_id: str = None
    ) -> Tuple[str, RAGPerformanceMetrics, Optional[RAGQualityAssessment], Optional[RAGAlignmentAssessment], Optional[RAGClassificationMetrics]]:
        """
        Perform a RAG query with comprehensive performance and quality assessment.
        
        Returns:
            Tuple of (response, performance_metrics, quality_assessment, alignment_assessment, classification_metrics)
        """
        if not session_id:
            session_id = str(uuid.uuid4())
        
        logger.info(f"Starting RAG assessment for session {session_id}")
        
        # Start overall timing
        start_time = time.time()
        
        try:
            # Phase 1: Document Retrieval with timing
            retrieval_start = time.time()
            
            # Get retrieval results from RAG service
            response, total_time_ms = self.rag_service.process_query_with_rag(
                query_text=query,
                collection_name=collection_name,
                model_name=model_name,
                top_k=top_k
            )
            
            retrieval_time = (time.time() - retrieval_start) * 1000
            
            # Phase 2: Extract retrieval metrics (would need to modify RAG service for detailed metrics)
            # For now, using available data
            documents_retrieved = top_k  # Assumption based on top_k
            documents_used = min(top_k, 5)  # Assumption
            context_length = len(query) + 1000  # Rough estimate
            response_length = len(response)
            
            # Calculate performance metrics
            total_time = (time.time() - start_time) * 1000
            generation_time = total_time - retrieval_time
            
            performance_metrics = RAGPerformanceMetrics(
                session_id=session_id,
                query=query,
                collection_name=collection_name,
                retrieval_time_ms=retrieval_time,
                generation_time_ms=generation_time,
                total_time_ms=total_time,
                documents_retrieved=documents_retrieved,
                documents_used=documents_used,
                relevance_score=0.8,  # Would calculate based on retrieval scores
                context_length=context_length,
                response_length=response_length,
                model_name=model_name,
                success=True
            )
            
            # Store performance metrics
            self.performance_metrics[session_id] = performance_metrics
            
            # Phase 3: Quality Assessment (if requested)
            quality_assessment = None
            if include_quality_assessment:
                quality_assessment = self._assess_response_quality(
                    session_id=session_id,
                    query=query,
                    response=response,
                    context_length=context_length
                )
                self.quality_assessments[session_id] = quality_assessment
            
            # Phase 4: Alignment Assessment (if requested)
            alignment_assessment = None
            if include_alignment_assessment:
                alignment_assessment = self._assess_output_alignment(
                    session_id=session_id,
                    query=query,
                    response=response
                )
                self.alignment_assessments[session_id] = alignment_assessment
            
            # Phase 5: Classification Metrics (if requested)
            classification_metrics = None
            if include_classification_metrics:
                classification_metrics = self._assess_classification_metrics(
                    session_id=session_id,
                    query=query,
                    response=response,
                    context_length=context_length
                )
                self.classification_metrics[session_id] = classification_metrics
            
            logger.info(f"RAG assessment completed for session {session_id}")
            return response, performance_metrics, quality_assessment, alignment_assessment, classification_metrics
            
        except Exception as e:
            logger.error(f"RAG assessment failed for session {session_id}: {str(e)}")
            
            # Create error metrics
            total_time = (time.time() - start_time) * 1000
            performance_metrics = RAGPerformanceMetrics(
                session_id=session_id,
                query=query,
                collection_name=collection_name,
                retrieval_time_ms=0,
                generation_time_ms=0,
                total_time_ms=total_time,
                documents_retrieved=0,
                documents_used=0,
                relevance_score=0,
                context_length=len(query),
                response_length=0,
                model_name=model_name,
                success=False,
                error_message=str(e)
            )
            
            self.performance_metrics[session_id] = performance_metrics
            return str(e), performance_metrics, None, None, None
    
    def _assess_response_quality(
        self,
        session_id: str,
        query: str,
        response: str,
        context_length: int
    ) -> RAGQualityAssessment:
        """
        Assess the quality of a RAG response using automated evaluation.
        """
        try:
            # Relevance Assessment
            relevance_score = self._assess_relevance(query, response)
            
            # Coherence Assessment
            coherence_score = self._assess_coherence(response)
            
            # Factual Accuracy Assessment (simplified)
            factual_accuracy = self._assess_factual_accuracy(response)
            
            # Completeness Assessment
            completeness_score = self._assess_completeness(query, response)
            
            # Context Utilization
            context_utilization = min(len(response) / (context_length * 0.1), 1.0)
            
            # Overall Quality Score (weighted average)
            overall_quality = (
                relevance_score * 0.3 +
                coherence_score * 0.2 +
                factual_accuracy * 0.2 +
                completeness_score * 0.2 +
                context_utilization * 0.1
            )
            
            return RAGQualityAssessment(
                session_id=session_id,
                relevance_score=relevance_score,
                coherence_score=coherence_score,
                factual_accuracy=factual_accuracy,
                completeness_score=completeness_score,
                context_utilization=context_utilization,
                overall_quality=overall_quality,
                assessment_method="automated",
                assessor_model=self.assessment_models["quality"]
            )
            
        except Exception as e:
            logger.error(f"Quality assessment failed for session {session_id}: {str(e)}")
            
            # Return default assessment on error
            return RAGQualityAssessment(
                session_id=session_id,
                relevance_score=0.5,
                coherence_score=0.5,
                factual_accuracy=0.5,
                completeness_score=0.5,
                context_utilization=0.5,
                overall_quality=0.5,
                assessment_method="automated",
                assessor_model="error"
            )
    
    def _assess_relevance(self, query: str, response: str) -> float:
        """Assess how relevant the response is to the query."""
        try:
            # Simple keyword overlap approach (can be enhanced with semantic similarity)
            query_words = set(query.lower().split())
            response_words = set(response.lower().split())
            
            if len(query_words) == 0:
                return 0.0
            
            overlap = len(query_words.intersection(response_words))
            relevance = overlap / len(query_words)
            
            # Cap at 1.0 and add some complexity adjustment
            return min(relevance * 1.2, 1.0)
            
        except:
            return 0.5
    
    def _assess_coherence(self, response: str) -> float:
        """Assess the coherence and readability of the response."""
        try:
            # Simple heuristics for coherence (can be enhanced with NLP models)
            sentences = response.split('.')
            
            if len(sentences) < 2:
                return 0.7  # Single sentence responses
            
            # Check for reasonable sentence lengths
            avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
            
            # Coherence based on sentence length consistency
            if 10 <= avg_sentence_length <= 30:
                coherence = 0.9
            elif 5 <= avg_sentence_length <= 40:
                coherence = 0.7
            else:
                coherence = 0.5
            
            return coherence
            
        except:
            return 0.5
    
    def _assess_factual_accuracy(self, response: str) -> float:
        """Assess factual accuracy (simplified version)."""
        try:
            # Simple heuristics (in production, would use fact-checking models)
            confidence_indicators = ['definitely', 'certainly', 'clearly', 'obviously']
            uncertainty_indicators = ['might', 'could', 'possibly', 'perhaps', 'maybe']
            
            confidence_count = sum(1 for indicator in confidence_indicators if indicator in response.lower())
            uncertainty_count = sum(1 for indicator in uncertainty_indicators if indicator in response.lower())
            
            # Higher uncertainty suggests more cautious, potentially more accurate responses
            if uncertainty_count > confidence_count:
                return 0.8
            elif confidence_count > uncertainty_count * 2:
                return 0.6  # Too confident might be less accurate
            else:
                return 0.7
                
        except:
            return 0.5
    
    def _assess_output_alignment(
        self,
        session_id: str,
        query: str,
        response: str
    ) -> RAGAlignmentAssessment:
        """
        Assess how well the RAG output aligns with the original user request and intent.
        """
        try:
            # Intent alignment - does the response address the user's underlying intent?
            intent_alignment_score = self._assess_intent_alignment(query, response)
            
            # Query coverage - how well does the response cover all aspects of the query?
            query_coverage_score = self._assess_query_coverage(query, response)
            
            # Instruction adherence - does the response follow any specific instructions?
            instruction_adherence_score = self._assess_instruction_adherence(query, response)
            
            # Answer type classification and matching
            expected_answer_type = self._classify_expected_answer_type(query)
            actual_answer_type = self._classify_actual_answer_type(response)
            answer_type_match = expected_answer_type == actual_answer_type
            
            # Tone consistency - maintains appropriate professional tone
            tone_consistency_score = self._assess_tone_consistency(query, response)
            
            # Scope accuracy - stays within requested scope
            scope_accuracy_score = self._assess_scope_accuracy(query, response)
            
            # Missing and extra elements analysis
            missing_elements = self._identify_missing_elements(query, response)
            extra_elements = self._identify_extra_elements(query, response)
            
            # Overall assessment confidence
            assessment_confidence = self._calculate_alignment_confidence(
                intent_alignment_score, query_coverage_score, instruction_adherence_score
            )
            
            return RAGAlignmentAssessment(
                session_id=session_id,
                intent_alignment_score=intent_alignment_score,
                query_coverage_score=query_coverage_score,
                instruction_adherence_score=instruction_adherence_score,
                answer_type_classification=actual_answer_type,
                expected_answer_type=expected_answer_type,
                answer_type_match=answer_type_match,
                tone_consistency_score=tone_consistency_score,
                scope_accuracy_score=scope_accuracy_score,
                missing_elements=missing_elements,
                extra_elements=extra_elements,
                assessment_confidence=assessment_confidence
            )
            
        except Exception as e:
            logger.error(f"Alignment assessment failed for session {session_id}: {str(e)}")
            
            # Return default assessment on error
            return RAGAlignmentAssessment(
                session_id=session_id,
                intent_alignment_score=0.5,
                query_coverage_score=0.5,
                instruction_adherence_score=0.5,
                answer_type_classification="unknown",
                expected_answer_type="unknown",
                answer_type_match=False,
                tone_consistency_score=0.5,
                scope_accuracy_score=0.5,
                missing_elements=["assessment_error"],
                extra_elements=[],
                assessment_confidence=0.0
            )
    
    def _assess_classification_metrics(
        self,
        session_id: str,
        query: str,
        response: str,
        context_length: int
    ) -> RAGClassificationMetrics:
        """
        Assess classification and categorization metrics for the RAG output.
        """
        try:
            # Query and response classification
            query_classification = self._classify_query_type(query)
            response_classification = self._classify_response_type(response)
            classification_confidence = self._calculate_classification_confidence(query, response)
            
            # Domain relevance classification
            domain_relevance = self._classify_domain_relevance(query, response)
            
            # Complexity level assessment
            complexity_level = self._assess_complexity_level(query, response)
            
            # Information density calculation
            information_density = self._calculate_information_density(response)
            
            # Actionability score
            actionability_score = self._assess_actionability(response)
            
            # Specificity score
            specificity_score = self._assess_specificity(response)
            
            # Citation quality (if references to source documents exist)
            citation_quality = self._assess_citation_quality(response)
            
            return RAGClassificationMetrics(
                session_id=session_id,
                query_classification=query_classification,
                response_classification=response_classification,
                classification_confidence=classification_confidence,
                domain_relevance=domain_relevance,
                complexity_level=complexity_level,
                information_density=information_density,
                actionability_score=actionability_score,
                specificity_score=specificity_score,
                citation_quality=citation_quality
            )
            
        except Exception as e:
            logger.error(f"Classification metrics failed for session {session_id}: {str(e)}")
            
            # Return default metrics on error
            return RAGClassificationMetrics(
                session_id=session_id,
                query_classification="unknown",
                response_classification="unknown",
                classification_confidence=0.0,
                domain_relevance="general",
                complexity_level="unknown",
                information_density=0.5,
                actionability_score=0.5,
                specificity_score=0.5,
                citation_quality=0.5
            )
    
    # Helper methods for alignment assessment
    def _assess_intent_alignment(self, query: str, response: str) -> float:
        """Assess if the response aligns with the user's underlying intent."""
        try:
            # Identify intent keywords and check if response addresses them
            intent_keywords = self._extract_intent_keywords(query)
            response_lower = response.lower()
            
            matches = sum(1 for keyword in intent_keywords if keyword.lower() in response_lower)
            return min(matches / max(len(intent_keywords), 1) * 1.2, 1.0)
        except:
            return 0.5
    
    def _assess_query_coverage(self, query: str, response: str) -> float:
        """Assess how well the response covers all aspects of the query."""
        try:
            # Break query into components and check coverage
            query_components = self._extract_query_components(query)
            coverage_count = 0
            
            for component in query_components:
                if any(word.lower() in response.lower() for word in component.split()):
                    coverage_count += 1
            
            return coverage_count / max(len(query_components), 1)
        except:
            return 0.5
    
    def _assess_instruction_adherence(self, query: str, response: str) -> float:
        """Assess adherence to specific instructions in the query."""
        try:
            # Check for instruction keywords
            instruction_indicators = ["please", "should", "must", "need to", "required", "analyze", "summarize", "explain", "compare"]
            instructions_found = [word for word in instruction_indicators if word in query.lower()]
            
            if not instructions_found:
                return 0.8  # No specific instructions, moderate score
            
            # Simple heuristic: if response is substantial and relevant, likely follows instructions
            if len(response) > 100 and self._assess_relevance(query, response) > 0.6:
                return 0.9
            else:
                return 0.5
        except:
            return 0.5
    
    def _classify_expected_answer_type(self, query: str) -> str:
        """Classify the expected answer type based on the query."""
        try:
            query_lower = query.lower()
            
            if any(word in query_lower for word in ["what is", "define", "definition", "meaning"]):
                return "direct_answer"
            elif any(word in query_lower for word in ["analyze", "analysis", "evaluate", "assessment"]):
                return "analysis"
            elif any(word in query_lower for word in ["summarize", "summary", "overview"]):
                return "summary"
            elif any(word in query_lower for word in ["explain", "how", "why", "describe"]):
                return "explanation"
            elif any(word in query_lower for word in ["compare", "contrast", "difference", "versus"]):
                return "comparison"
            else:
                return "analysis"  # Default to analysis for legal/business contexts
        except:
            return "unknown"
    
    def _classify_actual_answer_type(self, response: str) -> str:
        """Classify the actual answer type based on the response content."""
        try:
            response_lower = response.lower()
            
            # Look for structural indicators
            if len(response.split('.')) <= 3 and len(response) < 200:
                return "direct_answer"
            elif any(word in response_lower for word in ["analysis shows", "analyzing", "evaluation", "assessment"]):
                return "analysis"
            elif any(word in response_lower for word in ["summary", "overview", "in summary", "to summarize"]):
                return "summary"
            elif any(word in response_lower for word in ["explanation", "this is because", "the reason"]):
                return "explanation"
            elif any(word in response_lower for word in ["compared to", "difference", "contrast", "while"]):
                return "comparison"
            else:
                return "analysis"  # Default classification
        except:
            return "unknown"
    
    def _assess_tone_consistency(self, query: str, response: str) -> float:
        """Assess if the response maintains appropriate tone."""
        try:
            # Simple professional tone check
            unprofessional_indicators = ["lol", "omg", "wtf", "damn", "shit"]
            professional_indicators = ["analysis", "assessment", "evaluation", "consideration", "examination"]
            
            unprofessional_count = sum(1 for word in unprofessional_indicators if word in response.lower())
            professional_count = sum(1 for word in professional_indicators if word in response.lower())
            
            if unprofessional_count > 0:
                return 0.2
            elif professional_count > 0:
                return 0.9
            else:
                return 0.7  # Neutral tone
        except:
            return 0.5
    
    def _assess_scope_accuracy(self, query: str, response: str) -> float:
        """Assess if the response stays within the requested scope."""
        try:
            # Check if response length is appropriate for query complexity
            query_words = len(query.split())
            response_words = len(response.split())
            
            # Expected response length based on query complexity
            if query_words < 10:
                expected_range = (50, 300)
            elif query_words < 20:
                expected_range = (100, 500)
            else:
                expected_range = (200, 800)
            
            if expected_range[0] <= response_words <= expected_range[1]:
                return 0.9
            elif response_words < expected_range[0] * 0.5:
                return 0.4  # Too brief
            elif response_words > expected_range[1] * 2:
                return 0.6  # Too verbose
            else:
                return 0.7
        except:
            return 0.5
    
    def _identify_missing_elements(self, query: str, response: str) -> List[str]:
        """Identify key elements from the query that are not addressed in the response."""
        try:
            missing = []
            
            # Extract key concepts from query
            key_concepts = self._extract_key_concepts(query)
            
            for concept in key_concepts:
                if concept.lower() not in response.lower():
                    missing.append(concept)
            
            return missing[:5]  # Limit to top 5 missing elements
        except:
            return []
    
    def _identify_extra_elements(self, query: str, response: str) -> List[str]:
        """Identify additional elements provided beyond the request."""
        try:
            extra = []
            
            # Simple heuristic: if response is much longer than expected, likely has extra elements
            query_words = len(query.split())
            response_words = len(response.split())
            
            if response_words > query_words * 10:  # Response much longer than query suggests
                extra.append("extensive_additional_context")
            
            # Check for common extra elements
            if "background" in response.lower() and "background" not in query.lower():
                extra.append("background_information")
            
            if "recommendation" in response.lower() and "recommend" not in query.lower():
                extra.append("recommendations")
            
            return extra
        except:
            return []
    
    def _calculate_alignment_confidence(self, intent_score: float, coverage_score: float, adherence_score: float) -> float:
        """Calculate overall confidence in the alignment assessment."""
        try:
            # Weighted average with higher weight on intent and coverage
            confidence = (intent_score * 0.4 + coverage_score * 0.4 + adherence_score * 0.2)
            return confidence
        except:
            return 0.5
    
    # Helper methods for classification metrics
    def _classify_query_type(self, query: str) -> str:
        """Classify the query type."""
        try:
            query_lower = query.lower()
            
            if any(word in query_lower for word in ["what", "define", "definition", "is"]):
                return "factual"
            elif any(word in query_lower for word in ["analyze", "evaluate", "assess", "review"]):
                return "analytical"
            elif any(word in query_lower for word in ["how to", "steps", "process", "procedure"]):
                return "procedural"
            elif any(word in query_lower for word in ["compare", "contrast", "versus", "difference"]):
                return "comparative"
            elif any(word in query_lower for word in ["judge", "rate", "score", "quality"]):
                return "evaluative"
            else:
                return "analytical"  # Default for legal/business contexts
        except:
            return "unknown"
    
    def _classify_response_type(self, response: str) -> str:
        """Classify the response type."""
        try:
            response_lower = response.lower()
            
            if any(word in response_lower for word in ["the answer is", "definition", "defined as"]):
                return "factual"
            elif any(word in response_lower for word in ["analysis", "evaluation", "assessment"]):
                return "analytical"
            elif any(word in response_lower for word in ["step 1", "first", "process", "procedure"]):
                return "procedural"
            elif any(word in response_lower for word in ["compared to", "versus", "difference"]):
                return "comparative"
            elif any(word in response_lower for word in ["rating", "score", "quality", "judgment"]):
                return "evaluative"
            else:
                return "analytical"
        except:
            return "unknown"
    
    def _calculate_classification_confidence(self, query: str, response: str) -> float:
        """Calculate confidence in the classification."""
        try:
            # Higher confidence for clear indicators
            query_indicators = self._count_classification_indicators(query)
            response_indicators = self._count_classification_indicators(response)
            
            total_indicators = query_indicators + response_indicators
            
            if total_indicators >= 3:
                return 0.9
            elif total_indicators >= 2:
                return 0.7
            elif total_indicators >= 1:
                return 0.5
            else:
                return 0.3
        except:
            return 0.5
    
    def _classify_domain_relevance(self, query: str, response: str) -> str:
        """Classify the domain relevance."""
        try:
            combined_text = (query + " " + response).lower()
            
            legal_terms = sum(1 for term in ["contract", "legal", "law", "compliance", "regulation"] if term in combined_text)
            technical_terms = sum(1 for term in ["system", "technical", "software", "api", "database"] if term in combined_text)
            business_terms = sum(1 for term in ["business", "revenue", "profit", "market", "strategy"] if term in combined_text)
            
            if legal_terms >= 2:
                return "legal"
            elif technical_terms >= 2:
                return "technical"
            elif business_terms >= 2:
                return "business"
            elif legal_terms + technical_terms + business_terms >= 2:
                return "mixed"
            else:
                return "general"
        except:
            return "general"
    
    def _assess_complexity_level(self, query: str, response: str) -> str:
        """Assess the complexity level of the query and response."""
        try:
            # Simple complexity assessment based on length and vocabulary
            query_words = len(query.split())
            response_words = len(response.split())
            avg_word_length = sum(len(word) for word in response.split()) / max(len(response.split()), 1)
            
            complexity_score = (query_words * 0.3 + response_words * 0.5 + avg_word_length * 0.2) / 100
            
            if complexity_score < 0.3:
                return "simple"
            elif complexity_score < 0.6:
                return "moderate"
            elif complexity_score < 0.9:
                return "complex"
            else:
                return "expert"
        except:
            return "moderate"
    
    def _calculate_information_density(self, response: str) -> float:
        """Calculate the information density of the response."""
        try:
            words = response.split()
            if not words:
                return 0.0
            
            # Count information-rich words (longer than 4 characters, not common words)
            common_words = {"this", "that", "with", "have", "will", "been", "from", "they", "know", "want"}
            info_words = [word for word in words if len(word) > 4 and word.lower() not in common_words]
            
            density = len(info_words) / len(words)
            return min(density, 1.0)
        except:
            return 0.5
    
    def _assess_actionability(self, response: str) -> float:
        """Assess how actionable the response is."""
        try:
            actionable_indicators = ["should", "must", "recommend", "suggest", "consider", "action", "step", "implement"]
            response_lower = response.lower()
            
            actionable_count = sum(1 for indicator in actionable_indicators if indicator in response_lower)
            
            # Normalize score
            return min(actionable_count / 3.0, 1.0)
        except:
            return 0.5
    
    def _assess_specificity(self, response: str) -> float:
        """Assess the level of specific details provided."""
        try:
            specific_indicators = ["specific", "particular", "exactly", "precisely", "detailed", "section", "clause", "paragraph"]
            numbers_count = len([word for word in response.split() if any(char.isdigit() for char in word)])
            response_lower = response.lower()
            
            specific_count = sum(1 for indicator in specific_indicators if indicator in response_lower)
            specificity_score = (specific_count + numbers_count * 0.5) / max(len(response.split()) / 20, 1)
            
            return min(specificity_score, 1.0)
        except:
            return 0.5
    
    def _assess_citation_quality(self, response: str) -> float:
        """Assess the quality of references to source documents."""
        try:
            citation_indicators = ["according to", "as stated in", "document shows", "source", "reference", "section", "page"]
            response_lower = response.lower()
            
            citation_count = sum(1 for indicator in citation_indicators if indicator in response_lower)
            
            # Simple scoring
            if citation_count >= 3:
                return 0.9
            elif citation_count >= 2:
                return 0.7
            elif citation_count >= 1:
                return 0.5
            else:
                return 0.2
        except:
            return 0.5
    
    # Additional helper methods
    def _extract_intent_keywords(self, query: str) -> List[str]:
        """Extract intent-related keywords from the query."""
        # Simple keyword extraction
        important_words = [word for word in query.split() if len(word) > 3 and word.lower() not in {"this", "that", "with", "have", "from", "they", "what", "where", "when"}]
        return important_words[:5]  # Top 5 important words
    
    def _extract_query_components(self, query: str) -> List[str]:
        """Extract main components/topics from the query."""
        # Simple sentence/phrase splitting
        components = []
        if "and" in query.lower():
            components.extend(query.split(" and "))
        if "," in query:
            components.extend(query.split(","))
        
        if not components:
            components = [query]
        
        return [comp.strip() for comp in components if comp.strip()]
    
    def _extract_key_concepts(self, query: str) -> List[str]:
        """Extract key concepts from the query."""
        # Simple concept extraction based on word importance
        words = query.split()
        key_concepts = [word for word in words if len(word) > 4]
        return key_concepts[:3]  # Top 3 key concepts
    
    def _count_classification_indicators(self, text: str) -> int:
        """Count classification indicator words in text."""
        indicators = ["analyze", "compare", "evaluate", "assess", "explain", "define", "summarize", "describe"]
        return sum(1 for indicator in indicators if indicator in text.lower())
    
    def _assess_completeness(self, query: str, response: str) -> float:
        """Assess how completely the response addresses the query."""
        try:
            # Simple length and coverage assessment
            query_length = len(query.split())
            response_length = len(response.split())
            
            # Expect response to be proportional to query complexity
            expected_ratio = max(5, query_length * 2)
            
            if response_length >= expected_ratio:
                return 1.0
            elif response_length >= expected_ratio * 0.7:
                return 0.8
            elif response_length >= expected_ratio * 0.4:
                return 0.6
            else:
                return 0.4
                
        except:
            return 0.5
    
    def get_performance_analytics(
        self,
        time_period_hours: int = 24,
        collection_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive RAG performance analytics.
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=time_period_hours)
        
        # Filter metrics by time and collection
        filtered_metrics = [
            metric for metric in self.performance_metrics.values()
            if metric.timestamp >= cutoff_time and 
            (collection_name is None or metric.collection_name == collection_name)
        ]
        
        if not filtered_metrics:
            return {
                "message": "No metrics found for the specified period",
                "period_hours": time_period_hours,
                "collection_name": collection_name
            }
        
        # Performance statistics
        successful_queries = [m for m in filtered_metrics if m.success]
        failed_queries = [m for m in filtered_metrics if not m.success]
        
        response_times = [m.total_time_ms for m in successful_queries]
        retrieval_times = [m.retrieval_time_ms for m in successful_queries]
        generation_times = [m.generation_time_ms for m in successful_queries]
        
        # Quality statistics
        quality_scores = [
            self.quality_assessments[m.session_id].overall_quality
            for m in successful_queries
            if m.session_id in self.quality_assessments
        ]
        
        analytics = {
            "assessment_period": {
                "hours": time_period_hours,
                "start_time": cutoff_time.isoformat(),
                "end_time": datetime.now(timezone.utc).isoformat(),
                "collection_filter": collection_name
            },
            "query_statistics": {
                "total_queries": len(filtered_metrics),
                "successful_queries": len(successful_queries),
                "failed_queries": len(failed_queries),
                "success_rate": len(successful_queries) / len(filtered_metrics) if filtered_metrics else 0
            },
            "performance_metrics": {
                "response_time_ms": {
                    "mean": statistics.mean(response_times) if response_times else 0,
                    "median": statistics.median(response_times) if response_times else 0,
                    "min": min(response_times) if response_times else 0,
                    "max": max(response_times) if response_times else 0,
                    "std_dev": statistics.stdev(response_times) if len(response_times) > 1 else 0
                },
                "retrieval_time_ms": {
                    "mean": statistics.mean(retrieval_times) if retrieval_times else 0,
                    "median": statistics.median(retrieval_times) if retrieval_times else 0
                },
                "generation_time_ms": {
                    "mean": statistics.mean(generation_times) if generation_times else 0,
                    "median": statistics.median(generation_times) if generation_times else 0
                }
            },
            "quality_metrics": {
                "overall_quality": {
                    "mean": statistics.mean(quality_scores) if quality_scores else 0,
                    "median": statistics.median(quality_scores) if quality_scores else 0,
                    "samples": len(quality_scores)
                }
            },
            "usage_patterns": {
                "collections_used": list(set(m.collection_name for m in filtered_metrics)),
                "models_used": list(set(m.model_name for m in filtered_metrics)),
                "avg_documents_retrieved": statistics.mean([m.documents_retrieved for m in successful_queries]) if successful_queries else 0,
                "avg_response_length": statistics.mean([m.response_length for m in successful_queries]) if successful_queries else 0
            }
        }
        
        return analytics
    
    def get_collection_performance(self, collection_name: str) -> Dict[str, Any]:
        """Get performance metrics specific to a collection."""
        collection_metrics = [
            metric for metric in self.performance_metrics.values()
            if metric.collection_name == collection_name
        ]
        
        if not collection_metrics:
            return {
                "collection_name": collection_name,
                "message": "No metrics found for this collection"
            }
        
        successful_queries = [m for m in collection_metrics if m.success]
        
        return {
            "collection_name": collection_name,
            "total_queries": len(collection_metrics),
            "successful_queries": len(successful_queries),
            "success_rate": len(successful_queries) / len(collection_metrics),
            "avg_response_time_ms": statistics.mean([m.total_time_ms for m in successful_queries]) if successful_queries else 0,
            "avg_documents_retrieved": statistics.mean([m.documents_retrieved for m in successful_queries]) if successful_queries else 0,
            "recent_queries": [
                {
                    "session_id": m.session_id,
                    "query": m.query[:100] + "..." if len(m.query) > 100 else m.query,
                    "success": m.success,
                    "response_time_ms": m.total_time_ms,
                    "timestamp": m.timestamp.isoformat()
                }
                for m in sorted(collection_metrics, key=lambda x: x.timestamp, reverse=True)[:10]
            ]
        }
    
    def benchmark_rag_configuration(
        self,
        query_set: List[str],
        collection_name: str,
        configurations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Benchmark different RAG configurations on a set of queries.
        
        Args:
            query_set: List of test queries
            collection_name: Collection to test against
            configurations: List of config dicts with keys like 'model_name', 'top_k', etc.
        """
        benchmark_results = {}
        
        for i, config in enumerate(configurations):
            config_id = f"config_{i}"
            config_metrics = []
            
            for query in query_set:
                try:
                    response, performance, quality = self.assess_rag_query(
                        query=query,
                        collection_name=collection_name,
                        model_name=config.get('model_name', 'gpt-3.5-turbo'),
                        top_k=config.get('top_k', 5),
                        include_quality_assessment=True
                    )
                    
                    config_metrics.append({
                        "query": query,
                        "performance": asdict(performance),
                        "quality": asdict(quality) if quality else None
                    })
                    
                except Exception as e:
                    logger.error(f"Benchmark query failed for config {config_id}: {str(e)}")
            
            # Aggregate results for this configuration
            if config_metrics:
                avg_response_time = statistics.mean([m["performance"]["total_time_ms"] for m in config_metrics])
                avg_quality = statistics.mean([
                    m["quality"]["overall_quality"] for m in config_metrics 
                    if m["quality"] is not None
                ])
                
                benchmark_results[config_id] = {
                    "configuration": config,
                    "results": {
                        "queries_tested": len(config_metrics),
                        "avg_response_time_ms": avg_response_time,
                        "avg_quality_score": avg_quality,
                        "detailed_results": config_metrics
                    }
                }
        
        return {
            "benchmark_timestamp": datetime.now(timezone.utc).isoformat(),
            "collection_name": collection_name,
            "query_count": len(query_set),
            "configurations_tested": len(configurations),
            "results": benchmark_results
        }
    
    def export_metrics(
        self,
        format: str = "json",
        time_period_hours: int = 24
    ) -> Dict[str, Any]:
        """Export metrics data for external analysis."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=time_period_hours)
        
        # Filter metrics by time
        filtered_performance = {
            k: asdict(v) for k, v in self.performance_metrics.items()
            if v.timestamp >= cutoff_time
        }
        
        filtered_quality = {
            k: asdict(v) for k, v in self.quality_assessments.items()
            if v.timestamp >= cutoff_time
        }
        
        export_data = {
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "period_hours": time_period_hours,
            "format": format,
            "performance_metrics": filtered_performance,
            "quality_assessments": filtered_quality,
            "summary": {
                "total_sessions": len(filtered_performance),
                "successful_sessions": sum(1 for m in filtered_performance.values() if m['success']),
                "quality_assessments_count": len(filtered_quality)
            }
        }
        
        return export_data