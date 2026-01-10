"""
JSON Test Plan Generator Component

Streamlit UI for generating test plans in JSON format and converting to test cards.
"""

import streamlit as st
import json
from config.settings import config
from app_lib.api.client import api_client


def JSON_Test_Plan_Generator():
    """Generate test plans in JSON format for better structure and test card generation"""
    st.header("JSON Test Plan Generator")
    
    st.info("""
    ✨ **New Feature**: Generate test plans as structured JSON documents.
    
    Benefits:
    - Each section is a separate JSON object
    - Easier test card generation
    - Better data structure for processing
    - Support for programmatic manipulation
    """)
    
    # Tabs for different workflows
    tab1, tab2, tab3, tab4 = st.tabs([
        "Generate JSON Plan",
        "Extract Test Cards",
        "Manage JSON",
        "Export to Markdown"
    ])
    
    # ============================================================================
    # TAB 1: Generate JSON Test Plan
    # ============================================================================
    with tab1:
        st.subheader("Generate Test Plan in JSON Format")
        
        # Load agent sets
        try:
            agent_sets_response = api_client.get(f"{config.fastapi_url}/api/agent-sets")
            agent_sets = agent_sets_response.get("agent_sets", [])
            active_agent_sets = [s for s in agent_sets if s.get('is_active', True)]
        except Exception as e:
            st.warning(f"Could not load agent sets: {e}")
            active_agent_sets = []
        
        if not active_agent_sets:
            st.error("No agent sets available. Please create an agent set first.")
            return
        
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
                    value="JSON Test Plan",
                    key="json_title"
                )
            
            with col2:
                # Sectioning strategy
                sectioning_strategy = st.selectbox(
                    "Sectioning Strategy",
                    options=["auto", "by_metadata", "by_chunks"],
                    key="json_strategy"
                )
                
                # Chunks per section
                chunks_per_section = st.number_input(
                    "Chunks per Section",
                    min_value=1,
                    max_value=20,
                    value=5,
                    key="json_chunks"
                )
            
            # Source documents
            st.markdown("### Source Documents")
            
            # Load collections
            try:
                from services.chromadb_service import chromadb_service
                collections = chromadb_service.get_collections()
            except:
                collections = []
            
            if not collections:
                st.warning("No document collections available. Please upload documents first.")
                st.form_submit_button("Generate", disabled=True)
                return
            
            source_collection = st.selectbox(
                "Select Collection",
                options=collections,
                key="json_collection"
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
                "Generate JSON Test Plan",
                type="primary",
                key="json_generate"
            )
            
            if generate_button:
                if not source_doc_ids:
                    st.error("Please select at least one source document")
                elif not agent_set:
                    st.error("Please select an agent set")
                else:
                    with st.spinner("Generating JSON test plan..."):
                        try:
                            payload = {
                                "source_collections": [source_collection],
                                "source_doc_ids": source_doc_ids,
                                "doc_title": doc_title,
                                "agent_set_id": agent_set['id'],
                                "sectioning_strategy": sectioning_strategy,
                                "chunks_per_section": chunks_per_section
                            }
                            
                            response = api_client.post(
                                f"{config.fastapi_url}/api/json-test-plans/generate",
                                data=payload,
                                timeout=600  # 10 minute timeout
                            )
                            
                            if response.get("success"):
                                test_plan = response.get("test_plan", {})
                                st.session_state.json_test_plan = test_plan
                                
                                metadata = test_plan.get("test_plan", {}).get("metadata", {})
                                sections = test_plan.get("test_plan", {}).get("sections", [])
                                
                                st.success("✓ JSON test plan generated successfully!")
                                
                                # Display metrics
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.metric("Sections", metadata.get("total_sections", 0))
                                with col2:
                                    st.metric("Requirements", metadata.get("total_requirements", 0))
                                with col3:
                                    st.metric("Test Procedures", metadata.get("total_test_procedures", 0))
                                with col4:
                                    st.metric("Status", metadata.get("processing_status", "UNKNOWN"))
                                
                                # Show section preview
                                st.markdown("### Section Preview")
                                for section in sections[:3]:  # Show first 3
                                    with st.expander(f"📋 {section.get('section_title')}"):
                                        st.write(f"**Section ID**: {section.get('section_id')}")
                                        st.write(f"**Test Procedures**: {len(section.get('test_procedures', []))}")
                                        
                                        if section.get('dependencies'):
                                            st.write(f"**Dependencies**: {', '.join(section.get('dependencies'))}")
                                
                                if len(sections) > 3:
                                    st.info(f"... and {len(sections) - 3} more sections")
                            else:
                                st.error(f"Generation failed: {response.get('error', 'Unknown error')}")
                        
                        except Exception as e:
                            st.error(f"Failed to generate test plan: {e}")
    
    # ============================================================================
    # TAB 2: Extract Test Cards
    # ============================================================================
    with tab2:
        st.subheader("Extract Test Cards from JSON Plan")
        
        if "json_test_plan" not in st.session_state:
            st.info("Generate a JSON test plan first using the 'Generate JSON Plan' tab")
        else:
            test_plan = st.session_state.json_test_plan
            
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.success("✓ JSON test plan loaded")
                metadata = test_plan.get("test_plan", {}).get("metadata", {})
                st.write(f"**Title**: {metadata.get('title')}")
                st.write(f"**Sections**: {metadata.get('total_sections')}")
            
            with col2:
                if st.button("Extract Test Cards", type="primary"):
                    with st.spinner("Extracting test cards..."):
                        try:
                            response = api_client.post(
                                f"{config.fastapi_url}/api/json-test-plans/extract-test-cards",
                                data={"test_plan": test_plan},
                                timeout=60
                            )
                            
                            if response:
                                test_cards = response.get("test_cards", [])
                                st.session_state.extracted_test_cards = test_cards
                                
                                st.success(f"✓ Extracted {len(test_cards)} test cards")
                                
                                # Show test card summary
                                st.markdown("### Test Cards Summary")
                                
                                # Group by section
                                cards_by_section = {}
                                for card in test_cards:
                                    section_id = card.get("section_id", "unknown")
                                    if section_id not in cards_by_section:
                                        cards_by_section[section_id] = []
                                    cards_by_section[section_id].append(card)
                                
                                for section_id, cards in cards_by_section.items():
                                    with st.expander(f"Section {section_id} ({len(cards)} cards)"):
                                        for card in cards:
                                            st.write(f"- **{card.get('test_id')}**: {card.get('title')}")
                        
                        except Exception as e:
                            st.error(f"Failed to extract test cards: {e}")
    
    # ============================================================================
    # TAB 3: Manage JSON
    # ============================================================================
    with tab3:
        st.subheader("Manage JSON Test Plan")
        
        if "json_test_plan" not in st.session_state:
            st.info("Generate a JSON test plan first")
        else:
            test_plan = st.session_state.json_test_plan
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("Validate JSON", type="secondary"):
                    try:
                        response = api_client.post(
                            f"{config.fastapi_url}/api/json-test-plans/validate",
                            data={"test_plan": test_plan},
                            timeout=10
                        )
                        
                        if response.get("is_valid"):
                            st.success("✓ JSON structure is valid")
                        else:
                            st.error(f"✗ Validation failed: {', '.join(response.get('errors', []))}")
                        
                        if response.get("warnings"):
                            for warning in response.get("warnings", []):
                                st.warning(warning)
                    
                    except Exception as e:
                        st.error(f"Validation error: {e}")
            
            with col2:
                if st.button("View Schema", type="secondary"):
                    try:
                        response = api_client.get(
                            f"{config.fastapi_url}/api/json-test-plans/schema",
                            timeout=10
                        )
                        
                        if response:
                            with st.expander("JSON Schema"):
                                st.json(response.get("schema"))
                    
                    except Exception as e:
                        st.error(f"Failed to fetch schema: {e}")
            
            # Raw JSON viewer
            st.markdown("### Raw JSON")
            
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("Download JSON"):
                    json_str = json.dumps(test_plan, indent=2)
                    st.download_button(
                        label="Download",
                        data=json_str,
                        file_name="test_plan.json",
                        mime="application/json"
                    )
            
            with st.expander("View Raw JSON (click to expand)"):
                st.json(test_plan)
    
    # ============================================================================
    # TAB 4: Export to Markdown
    # ============================================================================
    with tab4:
        st.subheader("Export to Markdown")
        
        if "json_test_plan" not in st.session_state:
            st.info("Generate a JSON test plan first")
        else:
            test_plan = st.session_state.json_test_plan
            
            if st.button("Convert to Markdown", type="primary"):
                with st.spinner("Converting to markdown..."):
                    try:
                        response = api_client.post(
                            f"{config.fastapi_url}/api/json-test-plans/to-markdown",
                            data={"test_plan": test_plan},
                            timeout=60
                        )
                        
                        if response:
                            markdown = response.get("markdown", "")
                            title = response.get("title", "Test Plan")
                            
                            col1, col2 = st.columns([3, 1])
                            with col2:
                                st.download_button(
                                    label="Download MD",
                                    data=markdown,
                                    file_name=f"{title}.md",
                                    mime="text/markdown"
                                )
                            
                            st.markdown("### Preview")
                            st.markdown(markdown[:2000] + "..." if len(markdown) > 2000 else markdown)
                    
                    except Exception as e:
                        st.error(f"Failed to convert: {e}")


if __name__ == "__main__":
    JSON_Test_Plan_Generator()
