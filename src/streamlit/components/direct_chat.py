import streamlit as st
import time
from config.settings import config
from config.constants import MODEL_KEY_MAP as model_key_map, MODEL_DESCRIPTIONS as model_descriptions
from app_lib.api.client import api_client
from services.chromadb_service import chromadb_service
from services.chat_service import chat_service
from components.upload_documents import render_upload_component, browse_documents
from components.history import Chat_History
from components.shared.pipeline_components import (
    display_citations,
    PipelineRAGConfig,
    render_rag_config,
    render_agent_set_selector,
    render_pipeline_status,
    render_pipeline_result,
    build_pipeline_payload,
    render_recent_pipelines
)
from typing import List, Dict, Any, Optional

CHROMADB_API = config.endpoints.vectordb

@st.cache_data(show_spinner=False)
def fetch_collections():
    return chromadb_service.get_collections()

def Direct_Chat():
    if "collections" not in st.session_state:
        st.session_state.collections = fetch_collections()

    collections = st.session_state.collections
    chat_tab, pipeline_tab, doc_upload_tab, history_tab = st.tabs([
        "Chat with AI", "Agent Pipeline", "Upload Documents", "Chat History"
    ])

    with chat_tab:
        col1, col2 = st.columns([2, 1])
        with col1:
            mode = st.selectbox("Select AI Model:", list(model_key_map.keys()), key="chat_model")
            if model_key_map[mode] in model_descriptions:
                st.info(model_descriptions[model_key_map[mode]])

        use_rag = st.checkbox("Use RAG (Retrieval Augmented Generation)", key="chat_use_rag")
        collection_name = None
        document_id = None

        if use_rag:
            if collections:
                collection_name = st.selectbox(
                    "Document Collection:", collections, key="chat_coll"
                )

                # Option to filter by specific document
                filter_by_doc = st.checkbox(
                    "Filter by specific document?",
                    key="filter_by_document",
                    help="Enable this to search within a specific document instead of the entire collection"
                )

                if filter_by_doc:
                    # Show document browser
                    browse_documents(key_prefix="chat_doc_browse")

                    # Document selector
                    if "documents" in st.session_state and st.session_state.documents:
                        doc_options = {}
                        for doc in st.session_state.documents:
                            if hasattr(doc, 'document_name'):
                                doc_name = doc.document_name
                                doc_id_val = doc.document_id
                            else:
                                doc_name = doc.get('document_name', 'Unknown')
                                doc_id_val = doc.get('id', doc.get('document_id', ''))
                            if doc_id_val:
                                display_name = f"{doc_name} (ID: {doc_id_val[:8]}...)"
                                doc_options[display_name] = doc_id_val

                        if doc_options:
                            selected_display = st.selectbox(
                                "Select Document:",
                                options=list(doc_options.keys()),
                                key="chat_document_selector"
                            )
                            document_id = doc_options[selected_display]
                            st.info(f" Will search within: {selected_display}")
                        else:
                            st.warning("No documents found in this collection.")
                    else:
                        st.info("Load documents using the button above to see available documents.")
            else:
                st.warning("No collections available. Upload docs first.")

        user_input = st.text_area(
            "Ask your question:", height=100,
            placeholder="e.g. Summarize the latest uploaded document"
        )

        if st.button("Get Analysis", type="primary", key="chat_button"):
            if not user_input:
                st.warning("Please enter a question.")
            elif use_rag and not collection_name:
                st.error("Please select a collection for RAG mode.")
            else:
                with st.spinner(f"{mode} is analyzing..."):
                    try:
                        # If document_id is set, use document evaluation endpoint
                        # Otherwise use regular chat endpoint
                        if document_id:
                            # Document-specific evaluation
                            data = chat_service.evaluate_document(
                                document_id=document_id,
                                collection_name=collection_name,
                                prompt=user_input,
                                model_name=model_key_map[mode],
                                top_k=5
                            )
                            answer = data.get("response", "")
                            rt_ms = data.get("response_time_ms", 0)
                            session_id = data.get("session_id", "N/A")
                            formatted_citations = data.get("formatted_citations", "")

                            st.success("Analysis Complete (Document-Specific)")

                            # Debug information
                            st.info(f"Response length: {len(answer) if answer else 0} characters")

                            if answer and len(answer.strip()) > 0:
                                st.markdown("### Analysis Results")
                                st.markdown(answer)
                            else:
                                st.warning("No response generated or response is empty.")
                                st.write("**Full response data:**")
                                st.json(data)

                            st.caption(f"Response time: {rt_ms/1000:.2f}s")
                            st.caption(f"Session ID: {session_id}")
                            display_citations(formatted_citations)
                        else:
                            # Regular chat (with optional RAG across entire collection)
                            response = chat_service.send_message(
                                query=user_input,
                                model=model_key_map[mode],
                                use_rag=use_rag,
                                collection_name=collection_name
                            )
                            st.success("Analysis Complete:")
                            st.markdown(response.response)
                            if response.response_time_ms:
                                st.caption(f"Response time: {response.response_time_ms/1000:.2f}s")
                            if hasattr(response, 'session_id') and response.session_id:
                                st.caption(f"Session ID: {response.session_id}")

                            # Display citations if available (RAG mode)
                            formatted_citations = getattr(response, 'formatted_citations', '') or ''
                            display_citations(formatted_citations)
                    except Exception as e:
                        st.error(f"Request failed: {e}")

    with pipeline_tab:
        _render_agent_pipeline_tab(collections)

    with doc_upload_tab:
        st.header("Upload Documents for RAG")
        render_upload_component(
            available_collections=collections,
            load_collections_func=lambda: st.session_state.collections,
            create_collection_func=chromadb_service.create_collection,
            upload_endpoint=f"{CHROMADB_API}/documents/upload-and-process",
            job_status_endpoint=f"{CHROMADB_API}/jobs/{{job_id}}",
            key_prefix="eval"
        )

    with history_tab:
        Chat_History(key_prefix="direct_chat")


def _render_agent_pipeline_tab(collections: List[str]):
    """
    Render the Agent Pipeline tab for running agent set pipelines with RAG support.
    """
    st.subheader("Agent Set Pipeline with RAG")
    st.caption("Run a complete agent pipeline on your query, enhanced with document context from your collections")

    # Check for active pipeline
    if "direct_chat_pipeline_id" in st.session_state and st.session_state.direct_chat_pipeline_id:
        render_pipeline_status(
            pipeline_id=st.session_state.direct_chat_pipeline_id,
            session_key="direct_chat_pipeline_id",
            key_prefix="dc_pipeline"
        )
        return

    # --- Agent Set Selection ---
    agent_set = render_agent_set_selector(key_prefix="dc_pipeline")
    if not agent_set:
        return

    st.markdown("---")

    # --- RAG Configuration ---
    rag_config = render_rag_config(collections, key_prefix="dc_pipeline")

    st.markdown("---")

    # --- Query Input ---
    st.subheader("Your Query")
    user_query = st.text_area(
        "Enter your question or content to analyze",
        height=150,
        placeholder="e.g., Generate test cases for the authentication requirements...",
        key="dc_pipeline_query"
    )

    # --- Processing Options ---
    col1, col2 = st.columns(2)
    with col1:
        title = st.text_input(
            "Result Title",
            value="Agent Pipeline Analysis",
            key="dc_pipeline_title"
        )
    with col2:
        section_mode = st.selectbox(
            "Section Mode",
            ["single", "auto"],
            key="dc_pipeline_section_mode",
            help="'single': Treats entire input as one block - all agents process the whole text together. Best for short queries. "
                 "'auto': Automatically detects sections (via headers, numbered lists) and processes each separately before consolidating results. Best for longer documents with distinct parts."
        )

    st.markdown("---")

    # --- Run Button ---
    if st.button("Run Agent Pipeline", type="primary", key="dc_run_pipeline"):
        if not user_query or len(user_query.strip()) < 10:
            st.error("Please enter a query (at least 10 characters)")
            return

        if not agent_set:
            st.error("Please select an agent set")
            return

        if rag_config.use_rag and not rag_config.collection_name:
            st.error("Please select a collection for RAG context")
            return

        # Build payload using shared function
        payload = build_pipeline_payload(
            text_input=user_query,
            agent_set_id=agent_set['id'],
            title=title,
            section_mode=section_mode,
            rag_config=rag_config
        )

        try:
            with st.spinner("Starting agent pipeline..."):
                response = api_client.post(
                    f"{config.fastapi_url}/api/agent-pipeline/run-async",
                    data=payload,
                    timeout=30
                )

            pipeline_id = response.get("pipeline_id")
            if pipeline_id:
                st.session_state.direct_chat_pipeline_id = pipeline_id
                st.success(f"Pipeline started: {pipeline_id}")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Failed to start pipeline")
        except Exception as e:
            st.error(f"Failed to run pipeline: {e}")

    # --- Resume Existing Pipeline ---
    st.markdown("---")
    with st.expander("Resume Existing Pipeline", expanded=False):
        render_recent_pipelines(
            key_prefix="dc_pipeline",
            session_key="direct_chat_pipeline_id"
        )

