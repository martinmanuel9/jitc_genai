"""
JSON Test Plan Generator Component

Streamlit UI for generating test plans in JSON format and converting to test cards.
"""

import streamlit as st
from config.settings import config
from app_lib.api.client import api_client

def JSON_Test_Plan_Generator():
    """Generate test plans in JSON format for better structure and test card generation"""
    st.info("""
    **Workflow**: Generate test plans.
    """)

    st.subheader("Generate Test Plan")

    # Load agent sets (no timeout)
    active_agent_sets = []
    try:
        agent_sets_response = api_client.get(
            f"{config.fastapi_url}/api/agent-sets",
            timeout=None
        )
        agent_sets = agent_sets_response.get("agent_sets", [])
        active_agent_sets = [s for s in agent_sets if s.get('is_active', True)]
    except Exception as e:
        st.error(f"Could not load agent sets: {e}")
        if st.button("Retry"):
            st.rerun()
        return

    if not active_agent_sets:
        st.error("No agent sets available. Please create an agent set first.")
        return

    # Initialize session state for download
    if 'json_download_docx' not in st.session_state:
        st.session_state.json_download_docx = None
    if 'json_download_filename' not in st.session_state:
        st.session_state.json_download_filename = None

    # Form for generation
    with st.form("json_generation_form"):
        col1, col2 = st.columns(2)

        with col1:
            # Agent set selection
            agent_set_names = [s['name'] for s in active_agent_sets]
            selected_agent_set = st.selectbox(
                "Select Agent Pipeline",
                options=agent_set_names,
                key="json_agent_set"
            )

            agent_set = next((s for s in active_agent_sets if s['name'] == selected_agent_set), None)

            # Document title
            doc_title = st.text_input(
                "Test Plan Title",
                key="json_title"
            )

        with col2:
            # Model profile selection (Speed vs Quality)
            model_profile = st.radio(
                "Processing Mode",
                options=["fast", "balanced", "quality"],
                format_func=lambda x: {
                    "fast": "Fast (Draft) - llama3.2:3b ~10-30s/section",
                    "balanced": "Balanced - phi3:mini ~30-60s/section",
                    "quality": "Quality (Production) - gpt-oss:latest ~2-5min/section"
                }.get(x, x),
                index=0,
                key="json_model_profile",
                help="Fast: Quick drafts. Balanced: Good quality, moderate speed. Quality: Best results, slower. Processing will run to completion without timeout."
            )

            # Show profile-based chunk settings
            profile_chunks = {"fast": 10, "balanced": 5, "quality": 3}
            default_chunks = profile_chunks.get(model_profile, 5)

            # Advanced options expander
            with st.expander("Advanced Options"):
                sectioning_strategy = st.selectbox(
                    "Sectioning Strategy",
                    options=["by_chunks", "auto", "by_metadata"],
                    key="json_strategy",
                    help="by_chunks: Group document chunks. auto: Auto-detect sections. by_metadata: Use document metadata."
                )

                chunks_per_section = st.number_input(
                    "Chunks per Section",
                    min_value=1,
                    max_value=20,
                    value=default_chunks,
                    key="json_chunks",
                    help=f"Recommended for {model_profile} profile: {default_chunks}"
                )

        # Source documents
        st.markdown("### Source Documents")
        
        # Load collections (exclude output collections)
        try:
            from services.chromadb_service import chromadb_service
            all_collections = chromadb_service.get_collections()
            # Filter out output collections that should not be used as sources
            output_collections = {"test_plan_drafts", "generated_test_plan", "json_test_plans", "generated_documents"}
            collections = [c for c in all_collections if c not in output_collections]
        except Exception:
            collections = []

        if not collections:
            st.warning("No source document collections available. Please upload documents first.")
            st.form_submit_button("Generate", disabled=True)
            return

        source_collection = st.selectbox(
            "Select Source Collection",
            options=collections,
            key="json_collection",
            help="Select the collection containing your source requirements documents (NOT draft/generated collections)"
        )
        
        # Load and select documents
        if st.form_submit_button("Load Documents", type="secondary", key="json_load"):
            try:
                docs = chromadb_service.get_documents(source_collection)
                st.session_state.json_source_docs = [
                    {
                        'document_id': doc.document_id,
                        'document_name': doc.document_name
                    }
                    for doc in docs
                ]
                st.success(f"Loaded {len(docs)} documents")
            except Exception as e:
                st.error(f"Failed to load documents: {e}")
        
        source_docs = st.session_state.get("json_source_docs", [])
        source_map = {d["document_name"]: d["document_id"] for d in source_docs}
        
        selected_sources = st.multiselect(
            "Select Source Documents",
            options=list(source_map.keys()),
            key="json_sources"
        )
        
        source_doc_ids = [source_map[name] for name in selected_sources]
        
        # Generate button
        generate_button = st.form_submit_button(
            "Generate Test Plan",
            type="primary",
            key="json_generate"
        )
        
        if generate_button:
            if not source_doc_ids:
                st.error("Please select at least one source document")
            elif not agent_set:
                st.error("Please select an agent set")
            else:
                # Create placeholders for progress display
                progress_container = st.container()
                with progress_container:
                    st.markdown("### Generation Progress")
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    section_progress = st.empty()

                try:
                    import time
                    import threading

                    # Estimate time based on profile and document count
                    profile_times = {"fast": 30, "balanced": 60, "quality": 180}
                    estimated_time = profile_times.get(model_profile, 60) * len(source_doc_ids)

                    status_text.info(f"Starting test plan generation (estimated: {estimated_time//60}m {estimated_time%60}s)...")
                    section_progress.markdown(f"**Profile:** {model_profile.title()} | **Documents:** {len(source_doc_ids)}")

                    payload = {
                        "source_collections": [source_collection],
                        "source_doc_ids": source_doc_ids,
                        "doc_title": doc_title,
                        "agent_set_id": agent_set['id'],
                        "sectioning_strategy": sectioning_strategy,
                        "chunks_per_section": chunks_per_section,
                        "model_profile": model_profile
                    }

                    start_time = time.time()
                    response_container = {"response": None, "error": None}

                    def generate_in_thread():
                        try:
                            result = api_client.post(
                                f"{config.fastapi_url}/api/json-test-plans/generate",
                                data=payload,
                                timeout=1800  # 30 minute timeout
                            )
                            response_container["response"] = result
                        except Exception as e:
                            response_container["error"] = e

                    # Start generation in background thread
                    thread = threading.Thread(target=generate_in_thread)
                    thread.start()

                    # Show animated progress while waiting
                    stages = [
                        "Extracting document sections...",
                        "Analyzing requirements...",
                        "Generating test procedures...",
                        "Synthesizing test plan...",
                        "Finalizing output..."
                    ]
                    stage_idx = 0

                    while thread.is_alive():
                        elapsed = int(time.time() - start_time)

                        # Calculate progress based on elapsed time vs estimated
                        progress_pct = min(elapsed / max(estimated_time, 1), 0.95)
                        progress_bar.progress(progress_pct)

                        # Cycle through stage messages
                        if elapsed > 0 and elapsed % 15 == 0:
                            stage_idx = min(stage_idx + 1, len(stages) - 1)

                        current_stage = stages[stage_idx]
                        mins, secs = divmod(elapsed, 60)

                        status_text.info(f"⏳ {current_stage} ({mins}m {secs}s elapsed)")
                        section_progress.markdown(f"**Progress:** ~{int(progress_pct * 100)}% complete")

                        time.sleep(1)

                    # Wait for thread to complete
                    thread.join(timeout=5)

                    # Check for errors
                    if response_container["error"]:
                        raise response_container["error"]

                    response = response_container["response"]
                    if not response:
                        raise Exception("No response received from server")

                    # Get final metadata for completion message
                    final_metadata = {}
                    final_sections = []
                    if response and response.get("success"):
                        test_plan_data = response.get("test_plan", {})
                        final_metadata = test_plan_data.get("test_plan", {}).get("metadata", {})
                        final_sections = test_plan_data.get("test_plan", {}).get("sections", [])

                    # Clear progress display with final stats
                    progress_bar.progress(1.0)
                    status_text.success("✅ Generation complete!")
                    section_progress.markdown(f"**Total Sections Generated:** {len(final_sections)} sections with {final_metadata.get('total_test_procedures', 0)} test procedures")

                    if response.get("success"):
                        test_plan = response.get("test_plan", {})
                        st.session_state.json_test_plan = test_plan

                        metadata = test_plan.get("test_plan", {}).get("metadata", {})
                        sections = test_plan.get("test_plan", {}).get("sections", [])

                        # Store download data in session state
                        docx_b64 = response.get("docx_b64")
                        if docx_b64:
                            import base64
                            st.session_state.json_download_docx = base64.b64decode(docx_b64)
                            st.session_state.json_download_filename = f"{metadata.get('title', doc_title)}.docx"

                        # Simple success message and guidance
                        st.success(f"✅ Test plan generated with {len(sections)} sections!")
                        st.info("💡 Navigate to **JSON Test Plan Side-by-Side Editor** to view and edit sections")

                    else:
                        st.error(f"Generation failed: {response.get('error', 'Unknown error')}")

                except Exception as e:
                    st.error(f"Failed to generate test plan: {e}")

    # Download button outside form
    if st.session_state.json_download_docx is not None:
        st.markdown("---")
        st.markdown("### Download Test Plan")
        st.download_button(
            label="📥 Download DOCX",
            data=st.session_state.json_download_docx,
            file_name=st.session_state.json_download_filename,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary",
            key="json_download_button"
        )


if __name__ == "__main__":
    JSON_Test_Plan_Generator()
