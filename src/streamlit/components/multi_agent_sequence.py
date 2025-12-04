import streamlit as st
from config.settings import config
from app_lib.api.client import api_client
from services.chromadb_service import chromadb_service
from components.upload_documents import browse_documents, render_upload_component
from components.shared.pipeline_components import display_citations

# Use centralized config for endpoints
FASTAPI = config.endpoints.api
CHROMADB_API = config.endpoints.vectordb

def multi_agent_sequence_debate(agents, agent_choices, collections):
    st.subheader("Multi-Agent Sequence Debate")
    st.info("Create a sequence of agents that will debate in order, with multiple input options for content.")
    
    # Initialize session state for agent sequence
    if "debate_sequence" not in st.session_state:
        st.session_state["debate_sequence"] = []
    
    # AGENT SEQUENCE BUILDER 
    st.write("**Step 1: Build Agent Sequence**")
    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        
        with col1:
            new_agent_to_add = st.selectbox(
                "Add Agent to Debate Sequence:", 
                ["--Select an Agent--"] + list(agent_choices.keys()), 
                key="sequence_agent_select"
            )
        
        with col2:
            if st.button(" Add to Sequence", key="add_agent_sequence"):
                if new_agent_to_add != "--Select an Agent--" and new_agent_to_add not in st.session_state["debate_sequence"]:
                    st.session_state["debate_sequence"].append(new_agent_to_add)
                    st.success(f"Added {new_agent_to_add}")
                    st.rerun()
                elif new_agent_to_add in st.session_state["debate_sequence"]:
                    st.warning("Agent already in sequence!")
            
            if st.button("Clear All", key="clear_sequence"):
                st.session_state["debate_sequence"] = []
                st.rerun()
        
        # Display current debate sequence
        if st.session_state["debate_sequence"]:
            st.write("**Current Debate Sequence:**")
            for i, agent_name in enumerate(st.session_state["debate_sequence"], 1):
                col1, col2, col3 = st.columns([1, 4, 1])
                with col1:
                    st.write(f"**{i}.**")
                with col2:
                    # Show agent info
                    agent_data = next((agent for agent in agents if f"{agent['name']} ({agent['model_name']})" == agent_name), None)
                    if agent_data:
                        st.write(f"**{agent_data['name']}** using *{agent_data['model_name']}*")
                    else:
                        st.write(f"{agent_name}")
                with col3:
                    if st.button("X", key=f"remove_seq_{i}", help="Remove from sequence"):
                        st.session_state["debate_sequence"].remove(agent_name)
                        st.rerun()
        else:
            st.info("Add agents to create a debate sequence")
    
    # CONTENT INPUT SELECTION 
    st.markdown("---")
    st.write("**Step 2: Choose Content Input Method**")
    
    input_method = st.radio(
        "Select Input Method:",
        ["Direct Text Input", "Upload Document", "Use Existing Document"],
        horizontal=True,
        key="sequence_input_method"
    )
    
    debate_content = None
    collection_for_debate = None

    # DIRECT TEXT INPUT
    if input_method == "Direct Text Input":
        with st.container(border=True):
            st.write("**Direct Text for Debate**")
            debate_content = st.text_area(
                "Content for Multi-Agent Debate:", 
                placeholder="Enter the content that agents will debate about...",
                height=150, 
                key="sequence_debate_content"
            )
            
            # RAG context option
            use_rag_debate = st.checkbox("Add RAG context from collections", key="sequence_rag")
            if use_rag_debate and collections:
                collection_for_debate = st.selectbox(
                    "ChromaDB Collection (for RAG context):", 
                    collections,
                    key="sequence_rag_collection",
                    help="Select a collection to provide additional context"
                )
            elif use_rag_debate:
                st.warning("No collections available. Agents will debate without RAG context.")
    
    # UPLOAD DOCUMENT 
    elif input_method == "Upload Document":
        with st.container(border=True):
            st.write("**Upload Document for Debate**")
            
            # Upload section
            st.write("**Step 2a: Upload Document**")
            render_upload_component(
                available_collections=collections,
                load_collections_func=chromadb_service.get_collections,
                create_collection_func=chromadb_service.create_collection,
                upload_endpoint=f"{CHROMADB_API}/documents/upload-and-process",
                job_status_endpoint=f"{CHROMADB_API}/jobs/{{job_id}}",
                key_prefix="sequence_upload"
            )
            
            st.markdown("---")
            
            # Debate prompt for uploaded document
            st.write("**Step 2b: Debate Prompt**")
            debate_content = st.text_area(
                "Debate Topic/Prompt for Uploaded Document:",
                placeholder="e.g., 'Debate the legal implications and business risks of this contract...'",
                height=100,
                key="sequence_upload_prompt"
            )
            
            # Collection selection for uploaded document
            if collections:
                collection_for_debate = st.selectbox(
                    "Select Collection (where document was uploaded):",
                    collections,
                    key="sequence_upload_collection",
                    help="Choose the collection where you uploaded your document"
                )
            else:
                st.warning("No collections available. Upload a document first.")
    
    # USE EXISTING DOCUMENT
    elif input_method == "Use Existing Document":
        with st.container(border=True):
            st.write("**Use Existing Document for Debate**")

            # Browse and select document
            browse_documents(key_prefix="sequence_browse")

            # Get selected document and collection from session state
            document_id = st.session_state.get('selected_doc_id')
            collection_for_debate = st.session_state.get('selected_collection')

            # Show selection status
            if document_id:
                st.success(f"Document Selected")
                st.code(f"Document ID: {document_id}", language=None)

            st.markdown("---")

            # Debate prompt for existing document
            debate_content = st.text_area(
                "Debate Topic/Prompt for Document:",
                placeholder="e.g., 'Debate the legal implications and business risks of this contract...'",
                height=100,
                key="sequence_existing_prompt"
            )
    
    # START DEBATE 
    st.markdown("---")
    st.write("**Step 3: Start Multi-Agent Debate**")
    
    if st.button("Start Multi-Agent Sequence Debate", type="primary", key="start_sequence_debate"):
        if not debate_content:
            st.warning("Please provide content or debate prompt.")
        elif not st.session_state["debate_sequence"]:
            st.warning("Please add at least one agent to the debate sequence.")
        else:
            # Prepare the debate
            sequence_agent_ids = []
            for agent_name in st.session_state["debate_sequence"]:
                agent_id = agent_choices.get(agent_name)
                if agent_id:
                    sequence_agent_ids.append(agent_id)
            
            if not sequence_agent_ids:
                st.error("Unable to find agent IDs. Please reload agents and try again.")
            else:
                # Show debate setup
                with st.expander("Debate Setup", expanded=True):
                    st.write(f"**Content**: {debate_content[:100]}{'...' if len(debate_content) > 100 else ''}")
                    st.write(f"**Agents in sequence**: {len(sequence_agent_ids)}")
                    st.write(f"**Input Method**: {input_method}")
                    st.write(f"**Using RAG**: {'Yes' if collection_for_debate else 'No'}")
                    if collection_for_debate:
                        st.write(f"**Collection**: {collection_for_debate}")
                
                # Prepare payload based on input method
                if collection_for_debate:
                    # RAG-enhanced debate
                    debate_payload = {
                        "query_text": debate_content,
                        "collection_name": collection_for_debate,
                        "agent_ids": sequence_agent_ids
                    }
                    endpoint = f"{FASTAPI}/rag/debate-sequence"
                    debate_type = "RAG Sequence"
                else:
                    # Direct content debate
                    debate_payload = {
                        "data_sample": debate_content,
                        "agent_ids": sequence_agent_ids
                    }
                    endpoint = f"{FASTAPI}/agent/compliance-check"  # Use compliance check for non-RAG
                    debate_type = "Direct Sequence"
                
                # Execute the debate
                with st.spinner(f"{len(sequence_agent_ids)} agents debating in sequence..."):
                    status_placeholder = st.empty()
                    try:
                        status_placeholder.info(f"Connecting to debate service... ({debate_type})")
                        result = api_client.post(endpoint, data=debate_payload, timeout=300)
                        st.success("Multi-Agent Sequence Debate Complete!")

                        # Display session info
                        session_id = result.get("session_id")
                        if session_id:
                            st.info(f"Debate Session ID: `{session_id}`")

                        # Display debate results
                        st.subheader("Sequential Debate Results")

                        # Handle different response formats
                        if "debate_chain" in result:
                            # Sequential debate format
                            debate_chain = result["debate_chain"]
                            for i, round_result in enumerate(debate_chain, 1):
                                agent_name = round_result.get('agent_name', 'Unknown Agent')
                                response_text = round_result.get("response", "No response")

                                with st.expander(f"Round {i}: {agent_name}", expanded=i<=2):
                                    st.markdown(response_text)

                                    # Show metadata if available
                                    if "agent_id" in round_result:
                                        st.caption(f"Agent ID: {round_result['agent_id']}")

                        elif "details" in result:
                            # Compliance check format (non-sequential)
                            details = result["details"]
                            for idx, analysis in details.items():
                                agent_name = analysis.get("agent_name", f"Agent {idx}")
                                reason = analysis.get("reason", analysis.get("raw_text", "No analysis"))

                                with st.expander(f"{agent_name}", expanded=True):
                                    st.markdown(reason)

                        elif "agent_responses" in result:
                            # Agent responses format
                            agent_responses = result["agent_responses"]
                            for i, (agent_name, response_text) in enumerate(agent_responses.items(), 1):
                                with st.expander(f"Response {i}: {agent_name}", expanded=True):
                                    st.markdown(response_text)

                        else:
                            # Fallback - show raw result
                            st.json(result)

                        # Show response time
                        if "response_time_ms" in result:
                            st.caption(f"Total debate time: {result['response_time_ms']/1000:.2f}s")

                        # Display citations if available (RAG mode)
                        formatted_citations = result.get("formatted_citations", "")
                        if formatted_citations:
                            display_citations(formatted_citations)

                        # Word Export Section
                        st.markdown("---")
                        st.subheader("Export Results")
                        if st.button("Export to Word", type="secondary", key="export_multi_debate"):
                            try:
                                with st.spinner("Generating Word document..."):
                                    # Prepare simulation data for export
                                    simulation_data = {
                                        "type": "multi_agent_sequence",
                                        "query": debate_content,
                                        "debate_chain": result.get("debate_chain", []),
                                        "agent_responses": result.get("agent_responses", {}),
                                        "details": result.get("details", {}),
                                        "session_id": result.get("session_id"),
                                        "response_time_ms": result.get("response_time_ms"),
                                        "agents": []  # This would need to be populated with actual agent data if available
                                    }

                                    # Call FastAPI export endpoint
                                    export_result = api_client.post(
                                        f"{FASTAPI}/doc_gen/export-simulation-word",
                                        data=simulation_data,
                                        timeout=30
                                    )

                                    file_content = export_result.get("content_b64")
                                    filename = export_result.get("filename", "debate_simulation_export.docx")

                                    if file_content:
                                        import base64
                                        doc_bytes = base64.b64decode(file_content)

                                        st.download_button(
                                            label=f"Download {filename}",
                                            data=doc_bytes,
                                            file_name=filename,
                                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                            key="download_multi_debate"
                                        )
                                        st.success("Debate results exported successfully!")
                                    else:
                                        st.error("No file content received")
                            except Exception as e:
                                st.error(f"Error exporting debate results: {str(e)}")

                    except Exception as e:
                        status_placeholder.empty()
                        st.error(f"Sequence debate failed: {str(e)}")
    
    # HELP SECTION 
    with st.expander("How Multi-Agent Sequence Debate Works"):
        st.markdown("""
        **Multi-Agent Sequence Debate Process:**
        
        **Step 1: Build Agent Sequence**
        - Add agents in the order you want them to participate
        - Each agent brings their specialized expertise and configured prompts
        - Agents will analyze/debate in the specified sequence
        
        **Step 2: Content Input Options**
        
        **Direct Text Input:**
        - Enter text directly for immediate debate
        - Optional RAG enhancement from collections
        - Best for: Quick debates on specific topics or pasted content
        
        **Upload Document:**
        - Upload new documents (PDF, DOCX, TXT, etc.)
        - Documents are processed and stored for debate
        - Best for: New documents that need comprehensive multi-perspective analysis
        
        **Use Existing Document:**
        - Select from previously uploaded documents
        - Browse collections and select specific documents
        - Best for: Getting fresh perspectives on existing documents
        
        **Step 3: Sequential Debate**
        - Agents analyze content in the specified order
        - Each agent applies their specialized prompts and models
        - Results show individual perspectives in sequence
        
        **Example Sequence:**
        1. **Risk Analyzer** → Identifies potential risks
        2. **Legal Reviewer** → Analyzes legal implications  
        3. **Business Analyst** → Evaluates business impact
        4. **Compliance Officer** → Reviews regulatory compliance
        
        **Why Sequential Debates:**
        - **Structured Analysis**: Organized flow of different perspectives
        - **Specialized Expertise**: Each agent contributes their domain knowledge
        - **Comprehensive Coverage**: Multiple viewpoints on the same content
        - **Audit Trail**: Clear sequence of analysis for decision-making
        """)
