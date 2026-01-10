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

@st.cache_data(show_spinner=False)
def fetch_model_options():
    if model_key_map:
        return model_key_map, model_descriptions

    try:
        response = api_client.get(
            f"{config.fastapi_url}/api/models",
            timeout=10,
            show_errors=False
        )
    except Exception:
        return {}, {}

    if isinstance(response, list):
        key_map = {}
        descriptions = {}
        for model in response:
            display_name = model.get("display_name")
            model_id = model.get("model_id")
            if not display_name or not model_id:
                continue
            key_map[display_name] = model_id
            description = model.get("description")
            if description:
                descriptions[model_id] = description
        return key_map, descriptions

    return {}, {}

def Direct_Chat():
    collections_error = False
    if "collections" not in st.session_state:
        try:
            st.session_state.collections = fetch_collections()
        except Exception:
            st.session_state.collections = []
            collections_error = True

    # Initialize chat history for the current session
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    collections = st.session_state.collections or []
    model_map, model_descs = fetch_model_options()
    chat_tab, pipeline_tab, doc_upload_tab, history_tab = st.tabs([
        "Chat with AI", "Agent Pipeline", "Upload Documents", "Chat History"
    ])

    with chat_tab:
        if collections_error:
            st.warning("Could not load document folders. RAG options may be limited until the vector DB is reachable.")

        col1, col2 = st.columns([2, 1])
        with col1:
            mode = None
            model_id = None
            if model_map:
                mode = st.selectbox("Select AI Model:", list(model_map.keys()), key="chat_model")
                model_id = model_map.get(mode)
                if model_id and model_id in model_descs:
                    st.info(model_descs[model_id])
            else:
                st.error("No LLMs are available. Check llm_config or /api/models.")

        # Display chat message history
        chat_container = st.container()
        
        with chat_container:
            for message in st.session_state.chat_messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
                    citations = message.get("citations")
                    if citations:
                        display_citations(citations)
        

        use_rag = st.checkbox("Use RAG (Retrieval Augmented Generation)", key="chat_use_rag")
        collection_name = None
        document_id = None

        if use_rag:
            if collections:
                collection_name = st.selectbox(
                    "Document Folder:", collections, key="chat_coll"
                )

                # Option to filter by specific document
                filter_by_doc = st.checkbox(
                    "Filter by specific document?",
                    key="filter_by_document",
                    help="Enable this to search within a specific document instead of the entire folder"
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
                            st.warning("No documents found in this folder.")
                    else:
                        st.info("Load documents using the button above to see available documents.")
            else:
                st.warning("No folders available. Upload docs first.")

        user_input = st.chat_input(
            "Ask your question (press Enter to send)"
        )

        if user_input:
            if not user_input.strip():
                st.warning("Please enter a question.")
                return
            if not model_id:
                st.error("Please select an AI model.")
                return
            if use_rag and not collection_name:
                st.error("Please select a folder for RAG mode.")
                return

            # Add user message to chat history
            st.session_state.chat_messages.append({
                "role": "user",
                "content": user_input
            })

            model_label = mode or "Selected model"
            with st.spinner(f"{model_label} is analyzing..."):
                try:
                    # If document_id is set, use document evaluation endpoint
                    # Otherwise use regular chat endpoint
                    if document_id:
                        # Document-specific evaluation
                        data = chat_service.evaluate_document(
                            document_id=document_id,
                            collection_name=collection_name,
                            prompt=user_input,
                            model_name=model_id,
                            top_k=5
                        )
                        answer = data.get("response", "")
                        rt_ms = data.get("response_time_ms", 0)
                        session_id = data.get("session_id", "N/A")
                        formatted_citations = data.get("formatted_citations", "")

                        if answer and len(answer.strip()) > 0:
                            # Add assistant message to chat history
                            full_response = f"{answer}\n\n_Response time: {rt_ms/1000:.2f}s | Session ID: {session_id}_"
                            st.session_state.chat_messages.append({
                                "role": "assistant",
                                "content": full_response,
                                "citations": formatted_citations
                            })
                            st.success("Analysis Complete (Document-Specific)")
                        else:
                            st.warning("No response generated or response is empty.")
                            st.write("**Full response data:**")
                            st.json(data)
                    else:
                        # Regular chat (with optional RAG across entire collection)
                        response = chat_service.send_message(
                            query=user_input,
                            model=model_id,
                            use_rag=use_rag,
                            collection_name=collection_name
                        )

                        if response.response:
                            # Add assistant message to chat history
                            response_time_str = f"{response.response_time_ms/1000:.2f}s" if response.response_time_ms else "N/A"
                            session_id_str = response.session_id if hasattr(response, 'session_id') and response.session_id else "N/A"

                            formatted_citations = getattr(response, 'formatted_citations', '') or ''
                            full_response = f"{response.response}\n\n_Response time: {response_time_str} | Session ID: {session_id_str}_"

                            st.session_state.chat_messages.append({
                                "role": "assistant",
                                "content": full_response,
                                "citations": formatted_citations
                            })
                            st.success("Analysis Complete")
                        else:
                            st.error("No response received from the model")
                except Exception as e:
                    st.error(f"Request failed: {e}")

            st.rerun()

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
    st.caption("Run a complete agent pipeline on your query, enhanced with document context from your folders")

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
            st.error("Please select a folder for RAG context")
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
