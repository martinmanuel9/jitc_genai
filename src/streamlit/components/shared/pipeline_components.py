"""
Shared Pipeline Components Module

This module provides reusable components for agent pipeline functionality,
consolidating the best features from both agent_set_pipeline.py and direct_chat.py.

All functions use key_prefix parameter to avoid duplicate widget keys when used
in different tabs.
"""

import streamlit as st
import time
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from config.settings import config
from app_lib.api.client import api_client
from components.upload_documents import browse_documents


@dataclass
class PipelineRAGConfig:
    """
    Configuration for RAG (Retrieval-Augmented Generation) in pipeline execution.

    Attributes:
        use_rag: Whether to use RAG context from documents
        collection_name: Name of the ChromaDB collection to retrieve from
        document_id: Optional specific document ID to filter by
        top_k: Number of relevant document chunks to retrieve
    """
    use_rag: bool = False
    collection_name: Optional[str] = None
    document_id: Optional[str] = None
    top_k: int = 5


def display_citations(formatted_citations: str = ""):
    """
    Display formatted citations from the RAG service.

    The formatted_citations already contain all relevant information including:
    - Source document names and page numbers
    - Relevance quality tiers and distance scores
    - Contextual excerpts from the documents
    - Document position information

    Args:
        formatted_citations: Pre-formatted citation text from RAG service
    """
    if not formatted_citations:
        return

    st.divider()
    with st.expander("Sources and Citations", expanded=True):
        st.markdown(formatted_citations)


def render_rag_config(collections: List[str], key_prefix: str = "") -> PipelineRAGConfig:
    """
    Render the RAG configuration UI and return configuration object.

    This renders a checkbox to enable RAG, collection selector, top_k slider,
    and optional document filter using browse_documents.

    Args:
        collections: List of available ChromaDB collection names
        key_prefix: Prefix for widget keys to ensure uniqueness

    Returns:
        PipelineRAGConfig object with user-selected configuration
    """
    def pref(k):
        """Helper to add prefix to keys"""
        return f"{key_prefix}_{k}" if key_prefix else k

    st.subheader("RAG Context (Optional)")
    use_rag = st.checkbox(
        "Use RAG Context from Documents",
        value=True,
        key=pref("use_rag"),
        help="Enhance agent analysis with relevant context from your document collections"
    )

    rag_collection = None
    rag_document_id = None
    rag_top_k = 5

    if use_rag:
        if collections:
            rag_collection = st.selectbox(
                "Document Collection",
                collections,
                key=pref("collection"),
                help="Select the collection to retrieve context from"
            )

            col1, col2 = st.columns(2)
            with col1:
                rag_top_k = st.slider(
                    "Number of context chunks",
                    min_value=1,
                    max_value=20,
                    value=5,
                    key=pref("top_k"),
                    help="Number of relevant document chunks to include as context"
                )

            with col2:
                filter_by_doc = st.checkbox(
                    "Filter by specific document",
                    key=pref("filter_doc")
                )

            if filter_by_doc:
                browse_documents(key_prefix=pref("browse"))
                if "documents" in st.session_state and st.session_state.documents:
                    doc_options = {}
                    for doc in st.session_state.documents:
                        doc_name = doc.get('document_name', 'Unknown') if isinstance(doc, dict) else getattr(doc, 'document_name', 'Unknown')
                        doc_id_val = doc.get('document_id', doc.get('id', '')) if isinstance(doc, dict) else getattr(doc, 'document_id', '')
                        if doc_id_val:
                            display_name = f"{doc_name} (ID: {doc_id_val[:8]}...)"
                            doc_options[display_name] = doc_id_val

                    if doc_options:
                        selected_display = st.selectbox(
                            "Select Document:",
                            options=list(doc_options.keys()),
                            key=pref("document")
                        )
                        rag_document_id = doc_options[selected_display]
        else:
            st.warning("No collections available. Upload documents first.")
            use_rag = False

    return PipelineRAGConfig(
        use_rag=use_rag,
        collection_name=rag_collection,
        document_id=rag_document_id,
        top_k=rag_top_k
    )


def render_agent_set_selector(key_prefix: str = "") -> Optional[Dict[str, Any]]:
    """
    Render agent set selection UI with usage metrics and pipeline configuration.

    Fetches available agent sets from the API and displays a dropdown selector.
    Shows usage count metric and expandable pipeline configuration details.

    Args:
        key_prefix: Prefix for widget keys to ensure uniqueness

    Returns:
        Selected agent set dictionary or None if no selection or error
    """
    def pref(k):
        """Helper to add prefix to keys"""
        return f"{key_prefix}_{k}" if key_prefix else k

    # Fetch available agent sets
    try:
        agent_sets_response = api_client.get(f"{config.fastapi_url}/api/agent-sets")
        agent_sets = agent_sets_response.get("agent_sets", [])
        active_agent_sets = [s for s in agent_sets if s.get('is_active', True)]
    except Exception as e:
        st.warning(f"Could not load agent sets: {e}")
        active_agent_sets = []

    if not active_agent_sets:
        st.error("No agent sets available. Please create an agent set in the Agent & Orchestration Manager.")
        return None

    # Agent set selector with usage metric
    col1, col2 = st.columns([2, 1])

    with col1:
        agent_set_options = [s['name'] for s in active_agent_sets]
        selected_agent_set_name = st.selectbox(
            "Select Agent Set Pipeline",
            options=agent_set_options,
            key=pref("agent_set"),
            help="Choose an agent set to process your text through its stages"
        )

    with col2:
        agent_set = next((s for s in active_agent_sets if s['name'] == selected_agent_set_name), None)
        if agent_set:
            st.metric("Usage Count", agent_set.get('usage_count', 0))

    # Show agent set details
    if agent_set:
        with st.expander("View Pipeline Configuration", expanded=False):
            st.write(f"**Description:** {agent_set.get('description', 'No description')}")
            st.write(f"**Type:** {agent_set.get('set_type', 'sequence')}")

            stages = agent_set.get('set_config', {}).get('stages', [])
            st.write(f"**Pipeline Stages ({len(stages)}):**")
            for idx, stage in enumerate(stages, 1):
                stage_name = stage.get('stage_name', f'Stage {idx}')
                agent_count = len(stage.get('agent_ids', []))
                exec_mode = stage.get('execution_mode', 'parallel')
                st.write(f"  {idx}. **{stage_name}** - {agent_count} agent(s) ({exec_mode})")
                if stage.get('description'):
                    st.caption(f"     {stage.get('description')}")

    return agent_set


def render_pipeline_status(
    pipeline_id: str,
    session_key: str,
    key_prefix: str = ""
) -> bool:
    """
    Render pipeline status UI with progress tracking and control buttons.

    Shows pipeline status (QUEUED, PROCESSING, COMPLETED, FAILED), handles
    progress bar, refresh, and cancel buttons. Auto-refreshes for active pipelines.

    Args:
        pipeline_id: The pipeline ID to check status for
        session_key: Session state key to delete when starting new (e.g., "agent_pipeline_id")
        key_prefix: Prefix for widget keys to ensure uniqueness

    Returns:
        True if pipeline is still active (QUEUED/PROCESSING), False if completed/failed
    """
    def pref(k):
        """Helper to add prefix to keys"""
        return f"{key_prefix}_{k}" if key_prefix else k

    st.info(f"Active Pipeline: `{pipeline_id}`")

    try:
        status_response = api_client.get(
            f"{config.fastapi_url}/api/agent-pipeline/status/{pipeline_id}",
            timeout=10
        )

        status = status_response.get("status", "UNKNOWN")
        progress = status_response.get("progress", 0)
        progress_message = status_response.get("progress_message", "")

        # Status indicator
        status_emoji = {
            "COMPLETED": "✅",
            "PROCESSING": "⏳",
            "QUEUED": "📝",
            "FAILED": "❌"
        }.get(status, "❓")

        st.write(f"**Status:** {status_emoji} {status}")

        if status in ["PROCESSING", "QUEUED"]:
            st.progress(progress / 100)
            st.caption(progress_message)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Refresh Status", key=pref("refresh_status")):
                    st.rerun()
            with col2:
                if st.button("Cancel & Start New", key=pref("cancel_pipeline")):
                    if session_key in st.session_state:
                        del st.session_state[session_key]
                    st.rerun()

            # Auto-refresh
            time.sleep(5)
            st.rerun()
            return True

        elif status == "COMPLETED":
            st.success("Pipeline completed!")

            # Get full result
            result_response = api_client.get(
                f"{config.fastapi_url}/api/agent-pipeline/result/{pipeline_id}",
                timeout=30
            )

            render_pipeline_result(result_response, key_prefix=key_prefix)

            if st.button("Start New Pipeline", key=pref("start_new")):
                if session_key in st.session_state:
                    del st.session_state[session_key]
                st.rerun()

            return False

        elif status == "FAILED":
            st.error(f"Pipeline failed: {status_response.get('error', 'Unknown error')}")

            if st.button("Start New Pipeline", key=pref("start_new_after_fail")):
                if session_key in st.session_state:
                    del st.session_state[session_key]
                st.rerun()

            return False

    except Exception as e:
        st.error(f"Failed to get pipeline status: {e}")
        if st.button("Clear & Start New", key=pref("clear_failed")):
            if session_key in st.session_state:
                del st.session_state[session_key]
            st.rerun()
        return False

    return False


def render_pipeline_result(
    result: Dict[str, Any],
    key_prefix: str = "",
    show_section_details: bool = True
):
    """
    Display pipeline execution results with metrics and outputs.

    Shows summary metrics, consolidated output with download button,
    citations if RAG was used, and optionally section-by-section details.

    Args:
        result: Pipeline result dictionary from API
        key_prefix: Prefix for widget keys to ensure uniqueness
        show_section_details: Whether to show detailed section-by-section results
    """
    def pref(k):
        """Helper to add prefix to keys"""
        return f"{key_prefix}_{k}" if key_prefix else k

    st.markdown("### Pipeline Results")

    # Summary metrics
    rag_used = result.get("rag_context_used", False)
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Sections", result.get("total_sections", 0))
    with col2:
        st.metric("Stages Executed", result.get("total_stages_executed", 0))
    with col3:
        st.metric("Agents Executed", result.get("total_agents_executed", 0))
    with col4:
        processing_time = result.get("processing_time", 0)
        st.metric("Processing Time", f"{processing_time:.1f}s")
    with col5:
        st.metric("RAG Context", "Yes" if rag_used else "No")

    if rag_used:
        st.caption(f"RAG Collection: {result.get('rag_collection', 'N/A')}")

    st.markdown("---")

    # Consolidated output
    st.subheader("Consolidated Output")
    consolidated = result.get("consolidated_output", "")

    # Download button
    st.download_button(
        label="Download as Markdown",
        data=consolidated,
        file_name=f"{result.get('title', 'result')}.md",
        mime="text/markdown",
        key=pref("download_consolidated")
    )

    # Show consolidated output in expander
    with st.expander("View Full Output", expanded=True):
        st.markdown(consolidated)

    # Display citations if RAG was used and citations are available
    if rag_used:
        formatted_citations = result.get("formatted_citations", "")
        if formatted_citations:
            display_citations(formatted_citations)

    # Section-by-section results
    if show_section_details:
        section_results = result.get("section_results", [])
        if section_results:
            st.markdown("---")
            st.subheader("Section Details")

            # Global counter for unique keys across all agent outputs
            agent_output_counter = 0

            for idx, section in enumerate(section_results):
                section_title = section.get("section_title", f"Section {idx + 1}")

                with st.expander(f"**{section_title}**", expanded=False):
                    # Section content preview
                    content_preview = section.get("section_content_preview", section.get("section_content", "")[:200])
                    st.caption(f"Content preview: {content_preview}...")

                    # Stage results
                    stage_results = section.get("stage_results", [])
                    for stage_idx, stage in enumerate(stage_results):
                        stage_name = stage.get("stage_name", "Unknown Stage")
                        st.markdown(f"**{stage_name.title()} Stage** ({stage.get('execution_mode', 'parallel')})")

                        # Agent results
                        agent_results = stage.get("agent_results", [])
                        for agent_idx, agent in enumerate(agent_results):
                            agent_name = agent.get("agent_name", "Unknown")
                            success = agent.get("success", True)
                            status_icon = "✅" if success else "❌"

                            with st.container():
                                st.write(f"{status_icon} **{agent_name}** ({agent.get('model_name', 'Unknown')})")
                                if success:
                                    output = agent.get("output", "")
                                    st.text_area(
                                        f"Output from {agent_name}",
                                        value=output,
                                        height=150,
                                        key=pref(f"agent_output_{agent_output_counter}"),
                                        disabled=True
                                    )
                                    agent_output_counter += 1
                                else:
                                    st.error(f"Error: {agent.get('error', 'Unknown error')}")

                        st.markdown("---")


def render_recent_pipelines(key_prefix: str = "", session_key: str = "pipeline_id"):
    """
    Display a list of recent pipelines for resumption or viewing.

    Fetches recent pipelines from the API and displays them with status,
    progress, and action buttons to resume or view completed pipelines.

    Args:
        key_prefix: Prefix for widget keys to ensure uniqueness
        session_key: Session state key to set when resuming a pipeline
    """
    def pref(k):
        """Helper to add prefix to keys"""
        return f"{key_prefix}_{k}" if key_prefix else k

    try:
        response = api_client.get(
            f"{config.fastapi_url}/api/agent-pipeline/list",
            timeout=10
        )
        pipelines = response.get("pipelines", [])

        if not pipelines:
            st.info("No recent pipelines found.")
            return

        st.write(f"**{len(pipelines)} recent pipeline(s):**")

        for pipeline in pipelines[:10]:
            pipeline_id = pipeline.get("pipeline_id", "")
            status = pipeline.get("status", "UNKNOWN")
            title = pipeline.get("title", "Untitled")
            agent_set_name = pipeline.get("agent_set_name", "Unknown")
            progress = pipeline.get("progress", 0)

            # Status emoji
            status_emoji = {
                "COMPLETED": "✅",
                "PROCESSING": "⏳",
                "QUEUED": "📝",
                "FAILED": "❌"
            }.get(status, "❓")

            col1, col2, col3 = st.columns([3, 2, 1])

            with col1:
                st.write(f"{status_emoji} **{title}**")
                st.caption(f"Agent Set: {agent_set_name}")

            with col2:
                st.write(f"**{status}**")
                if status in ["PROCESSING", "QUEUED"]:
                    st.progress(progress / 100)

            with col3:
                button_label = "View" if status == "COMPLETED" else "Resume"
                if st.button(button_label, key=pref(f"resume_{pipeline_id}")):
                    st.session_state[session_key] = pipeline_id
                    st.rerun()

            st.markdown("---")

    except Exception as e:
        st.warning(f"Could not load recent pipelines: {e}")


def build_pipeline_payload(
    text_input: str,
    agent_set_id: int,
    title: str,
    section_mode: str,
    rag_config: PipelineRAGConfig
) -> Dict[str, Any]:
    """
    Build the payload dictionary for agent pipeline API calls.

    Constructs a properly formatted payload including RAG configuration
    if enabled.

    Args:
        text_input: The text content to process
        agent_set_id: ID of the agent set to use
        title: Title for the pipeline run
        section_mode: Section processing mode ("auto" or "single")
        rag_config: RAG configuration object

    Returns:
        Dictionary payload ready for API submission
    """
    payload = {
        "text_input": text_input,
        "agent_set_id": agent_set_id,
        "title": title,
        "section_mode": section_mode
    }

    if rag_config.use_rag:
        payload["use_rag"] = True
        payload["rag_collection"] = rag_config.collection_name
        payload["rag_document_id"] = rag_config.document_id
        payload["rag_top_k"] = rag_config.top_k

    return payload
