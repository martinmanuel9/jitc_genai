"""
Agent Set Pipeline Component

This component provides a UI for running agent set pipelines on direct text input.
It allows users to paste text content and process it through a selected agent set pipeline
without requiring the content to be stored in ChromaDB first.
"""

import streamlit as st
import time
from config.settings import config
from app_lib.api.client import api_client
from components.shared.pipeline_components import (
    display_citations,
    render_rag_config,
    render_agent_set_selector,
    render_pipeline_status,
    render_pipeline_result,
    render_recent_pipelines,
    build_pipeline_payload
)


def agent_set_pipeline():
    """
    Agent Set Pipeline - Run agent pipelines on direct text input
    """
    st.subheader("Agent Set Pipeline")
    st.caption("Run a complete agent set pipeline on any text content")

    # ----------------------------
    # Check if there's an active pipeline - if yes, show status only
    # ----------------------------
    if "agent_pipeline_id" in st.session_state and st.session_state.agent_pipeline_id:
        pipeline_id = st.session_state.agent_pipeline_id
        render_pipeline_status(
            pipeline_id=pipeline_id,
            session_key="agent_pipeline_id",
            key_prefix="pipeline"
        )
        return

    # ----------------------------
    # No active pipeline - show form
    # ----------------------------

    # Agent set selector (using shared component)
    agent_set = render_agent_set_selector(key_prefix="pipeline")
    if not agent_set:
        return

    st.markdown("---")

    # RAG Configuration (NEW!)
    collections = st.session_state.get("collections", [])
    rag_config = render_rag_config(collections, key_prefix="pipeline")

    st.markdown("---")

    # Text input section
    st.subheader("Input Content")

    input_method = st.radio(
        "Input Method",
        ["Paste Text", "Upload File"],
        horizontal=True,
        key="pipeline_input_method"
    )

    text_input = ""

    if input_method == "Paste Text":
        text_input = st.text_area(
            "Paste your content here",
            height=300,
            placeholder="Enter or paste the text content you want to process through the agent pipeline...",
            key="pipeline_text_input"
        )
    else:
        uploaded_file = st.file_uploader(
            "Upload a text file",
            type=['txt', 'md', 'json', 'csv'],
            key="pipeline_file_upload"
        )
        if uploaded_file:
            text_input = uploaded_file.read().decode('utf-8')
            st.text_area(
                "File Content Preview",
                value=text_input[:2000] + ("..." if len(text_input) > 2000 else ""),
                height=200,
                disabled=True
            )
            st.caption(f"Total characters: {len(text_input)}")

    # Section mode
    st.markdown("---")
    st.subheader("Processing Options")

    col1, col2 = st.columns(2)

    with col1:
        section_mode = st.selectbox(
            "Section Mode",
            ["auto", "single"],
            key="pipeline_section_mode",
            help="'auto': Automatically detects sections (via markdown headers, numbered lists, or keywords) and processes each separately before consolidating results. Best for longer documents with distinct parts. "
                 "'single': Treats entire input as one block - all agents process the whole text together. Best for short content or when you want unified processing."
        )

    with col2:
        title = st.text_input(
            "Result Title",
            value="Agent Pipeline Analysis",
            key="pipeline_title"
        )

    # Execution mode
    run_mode = st.radio(
        "Execution Mode",
        ["Background (Async)", "Synchronous (Wait)"],
        horizontal=True,
        key="pipeline_run_mode",
        help="'Background (Async)': Returns immediately with a pipeline ID. The pipeline runs in the background while you can do other things. Poll for status and retrieve results when complete. Best for longer pipelines to avoid timeouts. "
             "'Synchronous (Wait)': Blocks and waits for the pipeline to complete. Returns full results immediately. Best for shorter pipelines when you need results right away."
    )

    st.markdown("---")

    # Run button
    if st.button("Run Agent Pipeline", type="primary", key="run_agent_pipeline"):
        if not text_input or len(text_input.strip()) < 10:
            st.error("Please provide text content (at least 10 characters)")
            return

        if not agent_set:
            st.error("Please select an agent set")
            return

        # Build payload using shared function (with RAG support)
        payload = build_pipeline_payload(
            text_input=text_input,
            agent_set_id=agent_set['id'],
            title=title,
            section_mode=section_mode,
            rag_config=rag_config
        )

        try:
            if run_mode == "Background (Async)":
                # Async mode - start pipeline and show progress
                with st.spinner("Starting pipeline..."):
                    response = api_client.post(
                        f"{config.fastapi_url}/api/agent-pipeline/run-async",
                        data=payload,
                        timeout=30
                    )

                pipeline_id = response.get("pipeline_id")
                if pipeline_id:
                    st.session_state.agent_pipeline_id = pipeline_id
                    st.success(f"Pipeline started: {pipeline_id}")
                    st.info("Refreshing to show progress...")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Failed to start pipeline: No pipeline ID returned")
            else:
                # Sync mode - wait for completion
                with st.spinner("Running pipeline... This may take several minutes."):
                    response = api_client.post(
                        f"{config.fastapi_url}/api/agent-pipeline/run",
                        data=payload,
                        timeout=600  # 10 minute timeout for sync
                    )

                render_pipeline_result(response, key_prefix="pipeline")

        except Exception as e:
            st.error(f"Failed to run pipeline: {e}")

    # Resume existing pipeline section
    st.markdown("---")
    with st.expander("Resume Existing Pipeline", expanded=False):
        render_recent_pipelines(key_prefix="pipeline", session_key="agent_pipeline_id")
