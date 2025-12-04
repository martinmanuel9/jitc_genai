import streamlit as st
from config.settings import config
from app_lib.api.client import api_client
from components.upload_documents import browse_documents
from components.single_agent_analysis import single_agent_analysis
from components.multi_agent_sequence import multi_agent_sequence_debate
from components.document_debate import document_based_debate
from components.agent_set_pipeline import agent_set_pipeline


def Agent_Sim():
    # Use centralized config for endpoints
    FASTAPI_API = config.endpoints.agent
    # Display collections
    collections = st.session_state.collections

    # Load agents with enhanced error handling
    col1_load, col2_load = st.columns([1, 2])

    with col1_load:
        if st.button("Refresh Agent List"):
            try:
                with st.spinner("Loading agents from database..."):
                    agent_data = api_client.get(f"{FASTAPI_API}/get-agents", timeout=10)
                    st.session_state.agents_data = agent_data.get("agents", [])
                    st.success(f"Loaded {len(st.session_state.agents_data)} agents")
            except Exception as e:
                st.error(f"Error loading agents: {e}")
    
    with col2_load:
        if st.session_state.agents_data:
            total_agents = len(st.session_state.agents_data)
            active_agents = sum(1 for agent in st.session_state.agents_data if agent.get("is_active", True))
            st.metric("Total Agents", total_agents, delta=f"{active_agents} active")

    # Check if we have agents data
    if st.session_state.agents_data:
        agents = st.session_state.agents_data
        
        # Create agent choices dictionary for selection
        agent_choices = {f"{agent['name']} ({agent['model_name']})": agent["id"] for agent in agents}
        
        # Enhanced agents display
        agents_table_data = []
        for agent in agents:
            agents_table_data.append({
                "ID": agent.get("id", "N/A"),
                "Name": agent.get("name", "Unknown"),
                "Model": agent.get("model_name", "Unknown"),
                "Queries": agent.get("total_queries", 0),
                "Avg Response": f"{agent.get('avg_response_time_ms', 0):.0f}ms" if agent.get('avg_response_time_ms') else "N/A",
                "Success Rate": f"{agent.get('success_rate', 0)*100:.1f}%" if agent.get('success_rate') else "N/A",
                "Status": "Active" if agent.get("is_active", True) else "Inactive",
                "Created": agent.get("created_at", "Unknown")[:10] if agent.get("created_at") else "Unknown",
                "System Prompt": agent.get("system_prompt", "")[:100] + ("..." if len(agent.get("system_prompt", "")) > 100 else ""),
                "User Template": agent.get("user_prompt_template", "")[:100] + ("..." if len(agent.get("user_prompt_template", "")) > 100 else "")
            })
        
        # Display agents table
        st.dataframe(agents_table_data, use_container_width=True, height=400)
        
        st.markdown("---")

        # Tabbed interface for different analysis types
        pipeline_tab, analysis_tab, document_tab, sequence_tab = st.tabs([
            "Agent Set Pipeline",
            "Single Agent Analysis",
            "Document-Based Debate",
            "Multi-Agent Sequence"
        ])

        # === AGENT SET PIPELINE TAB ===
        with pipeline_tab:
            agent_set_pipeline()

        # === SINGLE AGENT ANALYSIS TAB ===
        with analysis_tab:
            single_agent_analysis(agents, agent_choices, collections)

        # === DOCUMENT-BASED DEBATE TAB ===
        with document_tab:
            document_based_debate(agents, agent_choices, collections)

        # === MULTI-AGENT SEQUENCE TAB ===
        with sequence_tab:
            multi_agent_sequence_debate(agents, agent_choices, collections)

    else:
        # No agents available
        st.info("Click 'Refresh Agent List' to load your specialized agents")
        st.markdown("""
        **No agents found!** 
        
        To use Agent Simulation mode:
        1. Go to the 'Create Agent' tab
        2. Create some specialized agents
        3. Come back here to simulate multi-agent analysis
        """)

