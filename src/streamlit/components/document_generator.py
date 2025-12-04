"""
Document Generator Component
"""
import streamlit as st
import base64
import time
from config.settings import config
from app_lib.api.client import api_client
from services.chromadb_service import chromadb_service
from components.job_status_monitor import JobStatusMonitor


def Document_Generator():
    st.header("Document Generator")
    # ----------------------------
    # Load pipeline_id from URL first (before anything else)
    # ----------------------------
    if "pipeline_id" in st.query_params:
        url_pipeline_id = st.query_params["pipeline_id"]
        if "pipeline_id" not in st.session_state or st.session_state.pipeline_id != url_pipeline_id:
            st.session_state.pipeline_id = url_pipeline_id

    # ----------------------------
    # Check if there's an active pipeline - if yes, show status only
    # ----------------------------
    if "pipeline_id" in st.session_state and st.session_state.pipeline_id:
        pipeline_id = st.session_state.pipeline_id

        st.info(f"Active Pipeline: `{pipeline_id}`")

        # Define completion handler for test plan generation
        def on_test_plan_completed(result_response):
            docs = result_response.get("documents", [])

            if docs and len(docs) > 0:
                primary_doc = docs[0]
                st.success(f"Document ready: **{primary_doc['title']}**")

                # Stats
                st.metric("Sections", primary_doc.get('total_sections', 0))

                # Download buttons
                st.markdown("### Download Options")

                download_col1, download_col2 = st.columns(2)

                with download_col1:
                    # DOCX download (Pandoc format)
                    if 'docx_b64' in primary_doc and primary_doc['docx_b64']:
                        blob = base64.b64decode(primary_doc["docx_b64"])
                        st.download_button(
                            label="Download DOCX",
                            data=blob,
                            file_name=f"{primary_doc['title']}.docx",
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            key="download_completed_docx",
                            type="primary",
                            use_container_width=True
                        )

                with download_col2:
                    # Markdown download
                    if 'content' in primary_doc and primary_doc['content']:
                        st.download_button(
                            label="Download Markdown",
                            data=primary_doc['content'],
                            file_name=f"{primary_doc['title']}.md",
                            mime="text/markdown",
                            key="download_completed_md",
                            type="secondary",
                            use_container_width=True
                        )
            else:
                st.warning("No documents found in result")

        # Define clear handler
        def on_clear():
            if "pipeline_id" in st.session_state:
                del st.session_state.pipeline_id
            if "pipeline_id" in st.query_params:
                del st.query_params["pipeline_id"]

        # Use the reusable JobStatusMonitor component
        monitor = JobStatusMonitor(
            job_id=pipeline_id,
            session_key="pipeline",
            status_endpoint=f"{config.endpoints.doc_gen}/generation-status/{{job_id}}",
            result_endpoint=f"{config.endpoints.doc_gen}/generation-result/{{job_id}}",
            job_name="Test Plan Generation",
            show_metrics=True,
            show_elapsed_time=True,
            allow_cancel=True,
            cancel_endpoint=f"{config.endpoints.doc_gen}/cancel-pipeline/{{job_id}}",
            on_completed=on_test_plan_completed,
            on_clear=on_clear,
            auto_refresh_interval=10,  # Refresh every 10 seconds
            auto_clear_on_complete=False  # Keep results visible for download
        )
        monitor.render()

        # Stop here - don't show form fields when pipeline is active
        st.stop()

    # ----------------------------
    # No active pipeline - show form fields
    # ----------------------------
    st.subheader("Agent Orchestration")

    # Fetch available agent sets
    try:
        agent_sets_response = api_client.get(f"{config.fastapi_url}/api/agent-sets")
        agent_sets = agent_sets_response.get("agent_sets", [])
        active_agent_sets = [s for s in agent_sets if s.get('is_active', True)]
    except Exception as e:
        st.warning(f"Could not load agent sets: {e}")
        active_agent_sets = []

    # Agent set selector
    if active_agent_sets:
        agent_set_options = [s['name'] for s in active_agent_sets]
        selected_agent_set = st.selectbox(
            "Select Agent Pipeline",
            options=agent_set_options,
            key="gen_agent_set",
            help="Choose an agent set to define the orchestration pipeline."
        )

        # Show agent set details
        agent_set = next((s for s in active_agent_sets if s['name'] == selected_agent_set), None)
        if agent_set:
            with st.expander("View Agent Set Configuration"):
                st.write(f"**Description:** {agent_set.get('description', 'No description')}")
                st.write(f"**Type:** {agent_set.get('set_type', 'sequence')}")
                st.write(f"**Usage Count:** {agent_set.get('usage_count', 0)}")
                st.write("**Pipeline Stages:**")
                for idx, stage in enumerate(agent_set.get('set_config', {}).get('stages', []), 1):
                    st.write(f"  {idx}. **{stage.get('stage_name')}** - {len(stage.get('agent_ids', []))} agent(s) ({stage.get('execution_mode')})")
                    if stage.get('description'):
                        st.caption(f"     {stage.get('description')}")
    else:
        st.error("No agent sets available. Please create an agent set in the Agent Set Manager.")
        st.stop()

    # ----------------------------
    # 2) Select source documents
    # ----------------------------
    st.markdown("---")
    st.subheader("Source Documents")

    if "collections" not in st.session_state:
        st.session_state.collections = chromadb_service.get_collections()

    collections = st.session_state.collections

    if not collections:
        st.warning("No collections available. Please upload documents first.")
        st.stop()

    # Pick collection & load source docs
    source_collection = st.selectbox(
        "Select Collection",
        collections,
        key="gen_source_coll",
    )

    if st.button("Load Source Documents", key="gen_load_sources"):
        with st.spinner("Loading source documents..."):
            try:
                documents = chromadb_service.get_documents(source_collection)
                st.session_state.source_docs = [
                    {
                        'document_id': doc.document_id,
                        'document_name': doc.document_name
                    }
                    for doc in documents
                ]
                st.success(f"Loaded {len(documents)} source documents")
            except Exception as e:
                st.error(f"Failed to load source documents: {e}")

    source_docs = st.session_state.get("source_docs", [])
    source_map = {d["document_name"]: d["document_id"] for d in source_docs}
    selected_sources = st.multiselect(
        "Select Source Document(s)",
        list(source_map.keys()),
        key="gen_sources"
    )
    source_doc_ids = [source_map[name] for name in selected_sources]

    # ----------------------------
    # 3) Let user name the output file
    # ----------------------------
    out_name = st.text_input(
        "Output file name (no extension):",
        value="Generated_Test_Plan",
        key="gen_filename"
    ).strip()

    # ----------------------------
    # 4) Export Options
    # ----------------------------
    st.markdown("---")
    st.subheader("Export Options")

    # Export format info
    st.info("Export Format: **Pandoc** (Professional formatting with TOC)")

    # Pandoc export options
    pandoc_col1, pandoc_col2 = st.columns(2)

    with pandoc_col1:
        include_toc = st.checkbox(
            "Include Table of Contents",
            value=True,
            key="gen_include_toc"
        )

    with pandoc_col2:
        number_sections = st.checkbox(
            "Number Sections Automatically",
            value=True,
            key="gen_number_sections"
        )

    st.markdown("---")
    # ----------------------------
    # Resume Existing Pipeline Section
    # ----------------------------
    with st.expander("Resume Existing Generation", expanded=False):
        st.write("If you refreshed the page or came back later, you can resume your generation here.")

        # Show list of pipelines
        try:
            pipelines_response = api_client.get(
                f"{config.endpoints.doc_gen}/list-pipelines",
                timeout=10
            )
            pipelines = pipelines_response.get("pipelines", [])

            if pipelines:
                st.write(f"**Select from {len(pipelines)} recent pipeline(s):**")

                # Create a table of pipelines
                for pipeline in pipelines[:10]:  # Show last 10
                    status = pipeline.get("status", "unknown")
                    pipeline_id = pipeline.get("pipeline_id", "")
                    doc_title = pipeline.get("doc_title", "Untitled")
                    created_at = pipeline.get("created_at", "")

                    # Calculate elapsed time
                    try:
                        from datetime import datetime
                        created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        elapsed = datetime.now() - created.replace(tzinfo=None)
                        minutes = int(elapsed.total_seconds() / 60)
                        if minutes < 60:
                            time_str = f"{minutes}m ago"
                        else:
                            hours = minutes // 60
                            time_str = f"{hours}h {minutes % 60}m ago"
                    except:
                        time_str = created_at[:19] if created_at else "Unknown"

                    # Status emoji
                    status_emoji = {
                        "completed": "✅",
                        "processing": "⏳",
                        "queued": "📝",
                        "failed": "❌",
                        "cancelling": "🛑",
                        "initializing": "⏳"
                    }.get(status.lower(), "❓")

                    col1, col2, col3 = st.columns([4, 3, 2])
                    with col1:
                        st.write(f"{status_emoji} **{doc_title}**")
                        st.caption(f"{pipeline_id[:20]}...")
                    with col2:
                        st.write(f"**{status.upper()}**")
                        st.caption(time_str)
                    with col3:
                        button_label = "View" if status.lower() == "completed" else "Resume"
                        button_type = "primary" if status.lower() in ["processing", "queued", "initializing"] else "secondary"
                        if st.button(button_label, key=f"resume_{pipeline_id}", type=button_type, use_container_width=True):
                            st.session_state.pipeline_id = pipeline_id
                            st.query_params["pipeline_id"] = pipeline_id
                            st.rerun()

                    st.markdown("---")

            else:
                st.info("No pipelines found. Start a new generation below.")

        except Exception as e:
            st.warning(f"Could not load pipelines: {e}")
            st.info("Start a new generation below.")


    # ----------------------------
    # Generate Document Button
    # ----------------------------
    st.markdown("---")
    if st.button("Generate Documents (Background)", type="primary", key="generate_docs_async"):
        if not source_doc_ids:
            st.error("You must select at least one source document.")
        else:
            payload = {
                "source_collections": [source_collection],
                "source_doc_ids": source_doc_ids,
                "use_rag": True,
                "top_k": 5,
                "doc_title": out_name,
                "export_format": "pandoc",  # Always use Pandoc for professional formatting
                "include_toc": include_toc,
                "number_sections": number_sections
            }

            # Add agent_set_id
            agent_set = next((s for s in active_agent_sets if s['name'] == selected_agent_set), None)
            if agent_set:
                payload["agent_set_id"] = agent_set['id']
                st.info(f"Using agent set: **{selected_agent_set}**")

            try:
                # Call async endpoint
                response = api_client.post(
                    f"{config.endpoints.doc_gen}/generate_documents_async",
                    data=payload,
                    timeout=30  # Quick timeout - just starting the task
                )

                pipeline_id = response.get("pipeline_id")
                if pipeline_id:
                    st.session_state.pipeline_id = pipeline_id
                    st.query_params["pipeline_id"] = pipeline_id
                    st.success(f"Generation started!")
                    st.info(f"Pipeline ID: `{pipeline_id}`")
                    st.info("Refreshing to show progress...")
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("Failed to start generation: No pipeline ID returned")

            except Exception as e:
                st.error(f"Failed to start generation: {e}")
