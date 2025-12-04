# services/agent_pipeline_service.py
"""
Agent Pipeline Service - Run agent set pipelines on direct text input.

This service provides a general-purpose interface for executing agent set pipelines
on any user-provided text, without requiring documents to be stored in ChromaDB.

Architecture:
1. User provides raw text input
2. Text is optionally split into sections (or treated as single section)
3. Agent set stages are executed in order (Actor → Critic → QA, etc.)
4. Results are aggregated and returned

Key Features:
- Supports both sync and async execution
- Redis pipeline tracking for progress monitoring
- Reuses agent execution patterns from MultiAgentTestPlanService
- Flexible section splitting (auto, manual, none)
"""

import json
import logging
import os
import re
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import redis
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.llm_invoker import LLMInvoker
from services.llm_service import LLMService
from services.rag_service import RAGService
from repositories.agent_set_repository import AgentSetRepository
from repositories.test_plan_agent_repository import TestPlanAgentRepository
from core.database import get_db

logger = logging.getLogger(__name__)


@dataclass
class AgentExecutionResult:
    """Result from a single agent execution"""
    agent_id: int
    agent_name: str
    agent_type: str
    model_name: str
    section_title: str
    output: str
    processing_time: float
    success: bool = True
    error: Optional[str] = None


@dataclass
class StageResult:
    """Result from executing a pipeline stage"""
    stage_name: str
    execution_mode: str
    agent_results: List[AgentExecutionResult]
    combined_output: str
    processing_time: float


@dataclass
class SectionResult:
    """Result from processing a single section through all stages"""
    section_title: str
    section_content: str
    stage_results: List[StageResult]
    final_output: str
    processing_time: float


@dataclass
class PipelineResult:
    """Final result from the complete agent pipeline"""
    pipeline_id: str
    title: str
    input_text_preview: str
    total_sections: int
    total_stages_executed: int
    total_agents_executed: int
    section_results: List[SectionResult]
    consolidated_output: str
    processing_status: str  # COMPLETED, FAILED, ABORTED
    processing_time: float
    agent_set_name: str
    agent_set_id: int
    rag_context_used: bool = False
    rag_collection: Optional[str] = None
    formatted_citations: str = ""  # Formatted citations for explainability
    rag_metadata: List[Dict[str, Any]] = field(default_factory=list)  # Raw metadata for citations
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class AgentPipelineService:
    """
    Service for running agent set pipelines on direct text input.

    This is a general-purpose service that can process any text through
    a configured agent set pipeline without requiring ChromaDB documents.
    """

    def __init__(self, llm_service: LLMService = None, rag_service: RAGService = None):
        self.llm_service = llm_service
        self.rag_service = rag_service or RAGService()

        # Redis setup for pipeline tracking
        redis_host = os.getenv("REDIS_HOST", "redis")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

        # Pipeline retention (7 days default)
        self.pipeline_ttl_seconds = int(os.getenv("PIPELINE_TTL_SECONDS", str(60 * 60 * 24 * 7)))

        # ChromaDB/VectorDB URL for RAG
        self.chroma_url = os.getenv("CHROMA_URL", "http://chromadb:8000")
        self.fastapi_url = os.getenv("FASTAPI_URL", "http://fastapi:9020")

        logger.info("AgentPipelineService initialized")
        self._test_redis_connection()

    def _test_redis_connection(self):
        """Test Redis connection"""
        try:
            self.redis_client.ping()
            logger.info("AgentPipelineService: Redis connection successful")
        except Exception as e:
            logger.error(f"AgentPipelineService: Redis connection failed: {e}")

    def run_pipeline(
        self,
        text_input: str,
        agent_set_id: int,
        title: str = "Agent Pipeline Result",
        section_mode: str = "auto",  # auto, single, manual
        manual_sections: Optional[Dict[str, str]] = None,
        pipeline_id: Optional[str] = None,
        # RAG parameters
        use_rag: bool = False,
        rag_collection: Optional[str] = None,
        rag_document_id: Optional[str] = None,
        rag_top_k: int = 5
    ) -> PipelineResult:
        """
        Run an agent set pipeline on the provided text input.

        Args:
            text_input: Raw text to process (user's query/prompt)
            agent_set_id: ID of the agent set to use
            title: Title for the pipeline result
            section_mode: How to split the text:
                - "auto": Automatically detect and split sections
                - "single": Treat entire text as one section
                - "manual": Use provided manual_sections dict
            manual_sections: Dict mapping section titles to content (for manual mode)
            pipeline_id: Optional pre-generated pipeline ID
            use_rag: Whether to use RAG context from ChromaDB
            rag_collection: Collection name for RAG retrieval
            rag_document_id: Optional specific document ID to filter RAG results
            rag_top_k: Number of top documents to retrieve for RAG context

        Returns:
            PipelineResult with all outputs
        """
        start_time = time.time()

        # Generate pipeline ID if not provided
        if pipeline_id is None:
            pipeline_id = f"agent_pipeline_{uuid.uuid4().hex[:12]}"

        logger.info(f"=== STARTING AGENT PIPELINE: {pipeline_id} ===")
        logger.info(f"Text input length: {len(text_input)} chars")
        logger.info(f"Section mode: {section_mode}")
        logger.info(f"RAG enabled: {use_rag}, Collection: {rag_collection}")

        # RAG context will be prepended to text_input
        rag_context = ""
        rag_context_used = False
        formatted_citations = ""
        rag_metadata = []

        try:
            # 0. Fetch RAG context if enabled
            if use_rag and rag_collection:
                rag_context, formatted_citations, rag_metadata = self._fetch_rag_context(
                    query=text_input,
                    collection_name=rag_collection,
                    document_id=rag_document_id,
                    top_k=rag_top_k
                )
                if rag_context:
                    rag_context_used = True
                    logger.info(f"RAG context retrieved: {len(rag_context)} chars")
                    logger.info(f"Citations generated: {len(formatted_citations)} chars")

            # 1. Load agent set configuration
            agent_set_config = self._load_agent_set_configuration(agent_set_id)
            if not agent_set_config:
                raise ValueError(f"Agent set {agent_set_id} not found or invalid")

            agent_set_name = agent_set_config.get('name', 'Unknown')
            logger.info(f"Using agent set: {agent_set_name} (ID: {agent_set_id})")

            # 2. Prepare the content - combine RAG context with user input
            if rag_context:
                combined_input = f"""## Reference Context (from {rag_collection})

{rag_context}

---

## User Query/Content

{text_input}"""
            else:
                combined_input = text_input

            # 3. Split text into sections
            sections = self._prepare_sections(combined_input, section_mode, manual_sections)
            logger.info(f"Processing {len(sections)} section(s)")

            # 3. Initialize Redis pipeline tracking
            self._initialize_pipeline(pipeline_id, title, agent_set_name, len(sections))

            # 4. Process each section through all stages
            section_results = []
            total_agents_executed = 0
            total_stages_executed = 0

            for section_idx, (section_title, section_content) in enumerate(sections.items()):
                logger.info(f"Processing section {section_idx + 1}/{len(sections)}: {section_title}")

                # Update progress
                self._update_pipeline_progress(
                    pipeline_id,
                    f"Processing section {section_idx + 1}/{len(sections)}: {section_title}",
                    (section_idx / len(sections)) * 100
                )

                # Process section through all stages
                section_result = self._process_section(
                    pipeline_id,
                    section_title,
                    section_content,
                    agent_set_config
                )
                section_results.append(section_result)

                # Track totals
                total_stages_executed += len(section_result.stage_results)
                for stage_result in section_result.stage_results:
                    total_agents_executed += len(stage_result.agent_results)

            # 5. Consolidate all outputs
            consolidated_output = self._consolidate_outputs(title, section_results)

            # 6. Mark pipeline as completed
            processing_time = time.time() - start_time
            self._update_pipeline_metadata(pipeline_id, {
                "status": "COMPLETED",
                "completed_at": datetime.now().isoformat(),
                "processing_time": str(processing_time)
            })

            logger.info(f"Pipeline {pipeline_id} completed in {processing_time:.2f}s")

            return PipelineResult(
                pipeline_id=pipeline_id,
                title=title,
                input_text_preview=text_input[:500] + "..." if len(text_input) > 500 else text_input,
                total_sections=len(sections),
                total_stages_executed=total_stages_executed,
                total_agents_executed=total_agents_executed,
                section_results=section_results,
                consolidated_output=consolidated_output,
                processing_status="COMPLETED",
                processing_time=processing_time,
                agent_set_name=agent_set_name,
                agent_set_id=agent_set_id,
                rag_context_used=rag_context_used,
                rag_collection=rag_collection if rag_context_used else None,
                formatted_citations=formatted_citations,
                rag_metadata=rag_metadata
            )

        except Exception as e:
            logger.error(f"Pipeline {pipeline_id} failed: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")

            processing_time = time.time() - start_time
            self._update_pipeline_metadata(pipeline_id, {
                "status": "FAILED",
                "error": str(e),
                "failed_at": datetime.now().isoformat()
            })

            return PipelineResult(
                pipeline_id=pipeline_id,
                title=title,
                input_text_preview=text_input[:500] + "..." if len(text_input) > 500 else text_input,
                total_sections=0,
                total_stages_executed=0,
                total_agents_executed=0,
                section_results=[],
                consolidated_output=f"Pipeline failed: {str(e)}",
                processing_status="FAILED",
                processing_time=processing_time,
                agent_set_name="Unknown",
                agent_set_id=agent_set_id,
                rag_context_used=False,
                rag_collection=None
            )

    def _fetch_rag_context(
        self,
        query: str,
        collection_name: str,
        document_id: Optional[str] = None,
        top_k: int = 5
    ) -> tuple[str, str, List[Dict[str, Any]]]:
        """
        Fetch RAG context from ChromaDB for the given query.

        Args:
            query: The user's query to search for relevant context
            collection_name: ChromaDB collection to search
            document_id: Optional specific document ID to filter results
            top_k: Number of top results to retrieve

        Returns:
            Tuple of (context_string, formatted_citations, metadata_list)
        """
        try:
            # Build filter for document_id if specified
            where_filter = None
            if document_id:
                where_filter = {"document_id": document_id}

            # Use RAGService directly to get documents with full metadata
            docs, found, metadata_list = self.rag_service.get_relevant_documents(
                query=query,
                collection_name=collection_name,
                top_k=top_k,
                where=where_filter,
                include_metadata=True
            )

            if not found or not docs:
                logger.info("No RAG context found for query")
                return "", "", []

            # Format the context for use in prompts
            context_parts = []
            for idx, (doc, meta) in enumerate(zip(docs, metadata_list or [{}] * len(docs)), 1):
                source = ""
                meta_dict = meta.get('metadata', {}) if isinstance(meta, dict) else {}
                if meta_dict:
                    doc_name = meta_dict.get("document_name", meta_dict.get("source", "Unknown"))
                    page = meta_dict.get("page", meta_dict.get("page_number", ""))
                    source = f"[Source: {doc_name}"
                    if page:
                        source += f", Page {page}"
                    source += "]"

                context_parts.append(f"### Context {idx} {source}\n{doc}")

            context = "\n\n".join(context_parts)
            logger.info(f"Retrieved {len(docs)} RAG context chunks")

            # Generate formatted citations using RAGService's citation formatter
            formatted_citations = self.rag_service._format_document_citations(metadata_list)

            return context, formatted_citations, metadata_list

        except Exception as e:
            logger.error(f"Error fetching RAG context: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return "", "", []

    def _load_agent_set_configuration(self, agent_set_id: int) -> Optional[Dict[str, Any]]:
        """Load agent set configuration from database"""
        db = None
        try:
            db = next(get_db())
            repo = AgentSetRepository()
            agent_set = repo.get_by_id(agent_set_id, db)

            if not agent_set:
                logger.error(f"Agent set {agent_set_id} not found")
                return None

            if not agent_set.is_active:
                logger.error(f"Agent set {agent_set_id} is inactive")
                return None

            return {
                'id': agent_set.id,
                'name': agent_set.name,
                'description': agent_set.description,
                'set_type': agent_set.set_type,
                'set_config': agent_set.set_config
            }

        except Exception as e:
            logger.error(f"Failed to load agent set {agent_set_id}: {e}")
            return None
        finally:
            if db:
                db.close()

    def _prepare_sections(
        self,
        text_input: str,
        section_mode: str,
        manual_sections: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """
        Prepare text sections based on the specified mode.

        Returns:
            Dict mapping section titles to content
        """
        if section_mode == "manual" and manual_sections:
            return manual_sections

        if section_mode == "single":
            return {"Full Content": text_input}

        # Auto mode: try to detect natural sections
        sections = self._extract_natural_sections(text_input)

        if len(sections) <= 1:
            # No natural sections found, use full text
            return {"Full Content": text_input}

        return sections

    def _extract_natural_sections(self, text: str) -> Dict[str, str]:
        """Extract sections based on document structure (headers, numbered sections, etc.)"""
        sections = {}
        lines = text.split('\n')
        current_section_title = "Introduction"
        current_section_content = []

        for line in lines:
            line_clean = line.strip()

            # Check for section headers - various patterns
            is_section_header = False
            header_title = ""

            if line_clean:
                # Pattern 1: Numbered sections (1., 1.1, 1.1.1, etc.)
                if re.match(r'^\d+(\.\d+)*\.?\s+[A-Z]', line_clean):
                    is_section_header = True
                    header_title = line_clean
                # Pattern 2: Markdown headers
                elif line_clean.startswith('#'):
                    is_section_header = True
                    header_title = line_clean.lstrip('#').strip()
                # Pattern 3: ALL CAPS headers (concise, not sentences)
                elif (line_clean.isupper() and
                      len(line_clean.split()) <= 8 and
                      len(line_clean) > 5 and
                      not line_clean.endswith('.')):
                    is_section_header = True
                    header_title = line_clean
                # Pattern 4: Keywords like APPENDIX, CHAPTER, SECTION
                elif line_clean.startswith(('APPENDIX', 'CHAPTER', 'SECTION', 'PART')):
                    is_section_header = True
                    header_title = line_clean

            if is_section_header and current_section_content:
                # Save previous section
                sections[current_section_title] = '\n'.join(current_section_content)
                current_section_title = header_title
                current_section_content = [line]
            elif is_section_header and not current_section_content:
                # First section header
                current_section_title = header_title
                current_section_content = [line]
            else:
                current_section_content.append(line)

        # Add the last section
        if current_section_content:
            sections[current_section_title] = '\n'.join(current_section_content)

        return sections

    def _process_section(
        self,
        pipeline_id: str,
        section_title: str,
        section_content: str,
        agent_set_config: Dict[str, Any]
    ) -> SectionResult:
        """Process a single section through all pipeline stages"""
        section_start_time = time.time()

        stages = agent_set_config.get('set_config', {}).get('stages', [])
        stage_results = []
        all_stage_outputs: Dict[str, List[AgentExecutionResult]] = {}

        for stage_idx, stage in enumerate(stages):
            stage_name = stage.get('stage_name', f'stage_{stage_idx}')
            logger.info(f"  Executing stage: {stage_name}")

            # Execute stage
            stage_result = self._execute_stage(
                stage,
                section_title,
                section_content,
                all_stage_outputs
            )
            stage_results.append(stage_result)

            # Store outputs for context building
            all_stage_outputs[stage_name] = stage_result.agent_results

        # Generate final output for this section
        final_output = self._generate_section_output(section_title, stage_results)

        return SectionResult(
            section_title=section_title,
            section_content=section_content,
            stage_results=stage_results,
            final_output=final_output,
            processing_time=time.time() - section_start_time
        )

    def _execute_stage(
        self,
        stage: Dict[str, Any],
        section_title: str,
        section_content: str,
        all_stage_outputs: Dict[str, List[AgentExecutionResult]] = None
    ) -> StageResult:
        """Execute a single stage from agent set configuration"""
        stage_start_time = time.time()

        agent_ids = stage.get('agent_ids', [])
        execution_mode = stage.get('execution_mode', 'parallel')
        stage_name = stage.get('stage_name', 'unnamed_stage')

        logger.info(f"    Executing stage '{stage_name}' with {len(agent_ids)} agent(s) in {execution_mode} mode")

        # Build context variables from previous stage outputs
        context_vars = self._build_context_vars(all_stage_outputs)

        results = []

        if execution_mode == 'parallel':
            results = self._execute_agents_parallel(agent_ids, section_title, section_content, context_vars)
        elif execution_mode == 'sequential':
            results = self._execute_agents_sequential(agent_ids, section_title, section_content, context_vars)
        else:
            # Default to parallel
            results = self._execute_agents_parallel(agent_ids, section_title, section_content, context_vars)

        # Combine outputs
        combined_output = "\n\n".join([r.output for r in results if r.success])

        return StageResult(
            stage_name=stage_name,
            execution_mode=execution_mode,
            agent_results=results,
            combined_output=combined_output,
            processing_time=time.time() - stage_start_time
        )

    def _build_context_vars(self, all_stage_outputs: Dict[str, List[AgentExecutionResult]]) -> Dict[str, str]:
        """Build context variables from previous stage outputs"""
        context_vars = {}

        if not all_stage_outputs:
            return context_vars

        # Build actor_outputs from actor stage
        if 'actor' in all_stage_outputs:
            actor_results = all_stage_outputs['actor']
            actor_outputs_text = "\n\n".join([
                f"## Actor Agent {idx + 1} ({result.agent_name}) Output:\n{result.output}"
                for idx, result in enumerate(actor_results) if result.success
            ])
            context_vars['actor_outputs'] = actor_outputs_text
            context_vars['actor_outputs_summary'] = actor_outputs_text

        # Build critic_output from critic stage
        if 'critic' in all_stage_outputs:
            critic_results = all_stage_outputs['critic']
            if critic_results and critic_results[0].success:
                context_vars['critic_output'] = critic_results[0].output
                context_vars['synthesized_rules'] = critic_results[0].output

        # Build general context string
        all_outputs_text = ""
        for stage_key, outputs in all_stage_outputs.items():
            all_outputs_text += f"\n\n=== {stage_key.upper()} Stage Outputs ===\n\n"
            for idx, result in enumerate(outputs, 1):
                if result.success:
                    all_outputs_text += f"Agent {idx} ({result.agent_name}) Output:\n{result.output}\n\n"
        context_vars['context'] = all_outputs_text
        context_vars['previous_sections_summary'] = ""

        return context_vars

    def _execute_agents_parallel(
        self,
        agent_ids: List[int],
        section_title: str,
        section_content: str,
        context_vars: Dict[str, str]
    ) -> List[AgentExecutionResult]:
        """Execute agents in parallel"""
        results = []

        with ThreadPoolExecutor(max_workers=min(len(agent_ids), 5)) as executor:
            futures = []
            for agent_id in agent_ids:
                future = executor.submit(
                    self._execute_agent_by_id,
                    agent_id, section_title, section_content, context_vars
                )
                futures.append(future)

            for future in as_completed(futures):
                try:
                    result = future.result(timeout=300)  # 5 minute timeout
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.error(f"Agent execution failed: {e}")

        return results

    def _execute_agents_sequential(
        self,
        agent_ids: List[int],
        section_title: str,
        section_content: str,
        context_vars: Dict[str, str]
    ) -> List[AgentExecutionResult]:
        """Execute agents sequentially, each building on previous results"""
        results = []

        for agent_id in agent_ids:
            result = self._execute_agent_by_id(agent_id, section_title, section_content, context_vars)
            if result:
                results.append(result)
                # Update context with latest result for next agent
                if result.success:
                    context_vars['context'] = context_vars.get('context', '') + f"\n\nPrevious Agent ({result.agent_name}) Output:\n{result.output}\n\n"

        return results

    def _execute_agent_by_id(
        self,
        agent_id: int,
        section_title: str,
        section_content: str,
        context_vars: Dict[str, str] = None
    ) -> Optional[AgentExecutionResult]:
        """Execute a single agent by database ID"""
        db = None
        try:
            # Load agent from database
            db = next(get_db())
            repo = TestPlanAgentRepository()
            agent = repo.get_by_id(agent_id, db)

            if not agent:
                logger.error(f"Agent ID {agent_id} not found in database")
                return None

            if not agent.is_active:
                logger.warning(f"Agent ID {agent_id} ({agent.name}) is inactive, skipping")
                return None

            # Copy agent data before closing session
            agent_name = agent.name
            agent_type = agent.agent_type
            agent_model_name = agent.model_name
            agent_system_prompt = agent.system_prompt
            agent_user_prompt_template = agent.user_prompt_template
            agent_temperature = agent.temperature
            agent_max_tokens = agent.max_tokens

            # Close database session BEFORE making LLM call
            db.close()
            db = None

            start_time = time.time()

            # Prepare prompt based on agent's template
            format_vars = {
                'section_title': section_title,
                'section_content': section_content,
                'context': context_vars.get('context', '') if context_vars else '',
                'actor_outputs': context_vars.get('actor_outputs', '') if context_vars else '',
                'critic_output': context_vars.get('critic_output', '') if context_vars else '',
                'actor_outputs_summary': context_vars.get('actor_outputs_summary', '') if context_vars else '',
                'synthesized_rules': context_vars.get('synthesized_rules', '') if context_vars else '',
                'previous_sections_summary': context_vars.get('previous_sections_summary', '') if context_vars else '',
            }

            # Use simple string replacement to avoid issues with JSON in templates
            user_prompt = agent_user_prompt_template
            for key, value in format_vars.items():
                user_prompt = user_prompt.replace(f'{{{key}}}', str(value))

            logger.info(f"      Executing agent: {agent_name} (ID: {agent_id}, Type: {agent_type}, Model: {agent_model_name})")

            # Dynamic token limit adjustment
            adjusted_max_tokens = self._calculate_safe_max_tokens(
                model_name=agent_model_name,
                system_prompt=agent_system_prompt,
                user_prompt=user_prompt,
                requested_max_tokens=agent_max_tokens
            )

            # Execute via LLM
            response = LLMInvoker.invoke(
                model_name=agent_model_name,
                prompt=user_prompt,
                system_prompt=agent_system_prompt,
                temperature=agent_temperature,
                max_tokens=adjusted_max_tokens
            )

            processing_time = time.time() - start_time

            return AgentExecutionResult(
                agent_id=agent_id,
                agent_name=agent_name,
                agent_type=agent_type,
                model_name=agent_model_name,
                section_title=section_title,
                output=response,
                processing_time=processing_time,
                success=True
            )

        except Exception as e:
            import traceback
            logger.error(f"Failed to execute agent ID {agent_id}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")

            return AgentExecutionResult(
                agent_id=agent_id,
                agent_name="Unknown",
                agent_type="Unknown",
                model_name="Unknown",
                section_title=section_title,
                output="",
                processing_time=0,
                success=False,
                error=str(e)
            )
        finally:
            if db is not None:
                db.close()

    def _calculate_safe_max_tokens(
        self,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
        requested_max_tokens: int
    ) -> int:
        """Calculate safe max_tokens based on model context window and input size"""
        MODEL_CONTEXT_LIMITS = {
            'gpt-4': 8192,
            'gpt-4-turbo': 128000,
            'gpt-4o': 128000,
            'gpt-3.5-turbo': 16385,
            'llama3.1:8b': 8192,
            'llama3.2:3b': 8192,
        }

        context_limit = MODEL_CONTEXT_LIMITS.get(model_name, 8192)

        # Estimate tokens (rough: 4 chars per token)
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model(model_name if model_name in MODEL_CONTEXT_LIMITS else 'gpt-4')
            input_tokens = len(encoding.encode(system_prompt + user_prompt))
        except Exception:
            total_chars = len(system_prompt) + len(user_prompt)
            input_tokens = total_chars // 4

        safety_margin = 100
        available_tokens = context_limit - input_tokens - safety_margin

        return min(requested_max_tokens, max(available_tokens, 100))

    def _generate_section_output(self, section_title: str, stage_results: List[StageResult]) -> str:
        """Generate formatted output for a section"""
        output_parts = [f"## {section_title}\n"]

        for stage_result in stage_results:
            output_parts.append(f"\n### {stage_result.stage_name.title()} Stage Output\n")
            output_parts.append(stage_result.combined_output)

        return "\n".join(output_parts)

    def _consolidate_outputs(self, title: str, section_results: List[SectionResult]) -> str:
        """Consolidate all section outputs into a final document"""
        output_parts = [f"# {title}\n"]
        output_parts.append(f"Generated at: {datetime.now().isoformat()}\n")
        output_parts.append(f"Total sections processed: {len(section_results)}\n")
        output_parts.append("\n---\n")

        for section_result in section_results:
            output_parts.append(section_result.final_output)
            output_parts.append("\n---\n")

        return "\n".join(output_parts)

    # Redis pipeline management methods
    def _initialize_pipeline(self, pipeline_id: str, title: str, agent_set_name: str, total_sections: int):
        """Initialize Redis pipeline tracking"""
        try:
            self.redis_client.hset(f"agent_pipeline:{pipeline_id}:meta", mapping={
                "status": "PROCESSING",
                "title": title,
                "agent_set_name": agent_set_name,
                "total_sections": str(total_sections),
                "created_at": datetime.now().isoformat(),
                "progress": "0",
                "progress_message": "Initializing pipeline..."
            })
            self.redis_client.expire(f"agent_pipeline:{pipeline_id}:meta", self.pipeline_ttl_seconds)
        except Exception as e:
            logger.warning(f"Failed to initialize pipeline in Redis: {e}")

    def _update_pipeline_progress(self, pipeline_id: str, message: str, progress: float):
        """Update pipeline progress in Redis"""
        try:
            self.redis_client.hset(f"agent_pipeline:{pipeline_id}:meta", mapping={
                "progress": str(int(progress)),
                "progress_message": message,
                "last_updated_at": datetime.now().isoformat()
            })
        except Exception as e:
            logger.warning(f"Failed to update pipeline progress: {e}")

    def _update_pipeline_metadata(self, pipeline_id: str, updates: Dict[str, str]):
        """Update pipeline metadata in Redis"""
        try:
            self.redis_client.hset(f"agent_pipeline:{pipeline_id}:meta", mapping=updates)
        except Exception as e:
            logger.warning(f"Failed to update pipeline metadata: {e}")

    def get_pipeline_status(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """Get pipeline status from Redis"""
        try:
            meta = self.redis_client.hgetall(f"agent_pipeline:{pipeline_id}:meta")
            if meta:
                return {
                    "pipeline_id": pipeline_id,
                    "status": meta.get("status", "UNKNOWN"),
                    "title": meta.get("title", ""),
                    "agent_set_name": meta.get("agent_set_name", ""),
                    "total_sections": int(meta.get("total_sections", 0)),
                    "progress": int(meta.get("progress", 0)),
                    "progress_message": meta.get("progress_message", ""),
                    "created_at": meta.get("created_at", ""),
                    "completed_at": meta.get("completed_at", ""),
                    "error": meta.get("error", "")
                }
            return None
        except Exception as e:
            logger.error(f"Failed to get pipeline status: {e}")
            return None
