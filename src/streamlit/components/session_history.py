"""
Session History Component

Developer/Admin dashboard for tracking:
- User behavior patterns
- Document generation success rates
- RAG effectiveness
- Agent usage statistics
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from config.settings import config
from app_lib.api.client import api_client


def render_session_history():
    """Main entry point for session history dashboard"""
    st.header("Session History & Analytics")
    st.caption("Developer/Admin dashboard for monitoring system usage and effectiveness")

    # Time range selector
    col1, col2 = st.columns([3, 1])
    with col1:
        time_range = st.selectbox(
            "Time Range",
            ["Last 24 Hours", "Last 7 Days", "Last 30 Days", "All Time"],
            index=1  # Default to 7 days
        )

    with col2:
        if st.button("Refresh Data", type="primary"):
            st.cache_data.clear()
            st.rerun()

    # Convert time range to days
    days_map = {
        "Last 24 Hours": 1,
        "Last 7 Days": 7,
        "Last 30 Days": 30,
        "All Time": 9999
    }
    days = days_map[time_range]

    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "Overview",
        "Recent Sessions",
        "Agent Performance",
        "RAG Effectiveness"
    ])

    with tab1:
        render_overview_tab(days)

    with tab2:
        render_recent_sessions_tab(days)

    with tab3:
        render_agent_performance_tab(days)

    with tab4:
        render_rag_effectiveness_tab(days)


def render_overview_tab(days: int):
    """Overview dashboard with key metrics"""
    st.subheader("System Overview")

    try:
        # Fetch analytics data
        analytics = api_client.get(
            f"{config.fastapi_url}/api/analytics/session-analytics?days={days}",
            timeout=10
        )

        session_stats = analytics.get("session_statistics", {})
        rag_stats = analytics.get("rag_statistics", {})
        agent_activity = analytics.get("agent_activity", [])

        # Key Metrics Row
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            total_sessions = sum(session_stats.get("by_session_type", {}).values())
            st.metric("Total Sessions", total_sessions)

        with col2:
            avg_time = session_stats.get("avg_response_time_ms", 0)
            st.metric("Avg Response Time", f"{avg_time/1000:.1f}s")

        with col3:
            rag_rate = rag_stats.get("rag_usage_rate", 0)
            st.metric("RAG Usage Rate", f"{rag_rate:.1f}%")

        with col4:
            total_rag = rag_stats.get("total_responses", 0)
            st.metric("Total Responses", total_rag)

        st.markdown("---")

        # Session Type Breakdown
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Session Types")
            session_types = session_stats.get("by_session_type", {})
            if session_types:
                df_sessions = pd.DataFrame([
                    {"Type": k.replace("_", " ").title(), "Count": v}
                    for k, v in session_types.items()
                ])
                st.dataframe(df_sessions, hide_index=True, use_container_width=True)
            else:
                st.info("No session data available")

        with col2:
            st.subheader("Analysis Methods")
            analysis_types = session_stats.get("by_analysis_type", {})
            if analysis_types:
                df_analysis = pd.DataFrame([
                    {"Method": k.replace("_", " ").title(), "Count": v}
                    for k, v in analysis_types.items()
                ])
                st.dataframe(df_analysis, hide_index=True, use_container_width=True)
            else:
                st.info("No analysis data available")

        st.markdown("---")

        # Top Active Agents
        st.subheader("Most Active Agents")
        if agent_activity:
            df_agents = pd.DataFrame(agent_activity)
            df_agents = df_agents.rename(columns={
                "agent_name": "Agent Name",
                "response_count": "Responses"
            })
            st.dataframe(
                df_agents[["Agent Name", "Responses"]],
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("No agent activity data available")

    except Exception as e:
        st.error(f"Failed to load analytics: {e}")


def render_recent_sessions_tab(days: int):
    """Recent sessions list with details"""
    st.subheader("Recent Sessions")

    # Filter options
    col1, col2 = st.columns(2)
    with col1:
        session_type_filter = st.selectbox(
            "Filter by Type",
            ["All", "Single Agent", "Multi Agent Debate", "RAG Analysis", "RAG Debate"],
            key="session_type_filter"
        )

    with col2:
        limit = st.number_input("Max Sessions", min_value=10, max_value=500, value=50, step=10)

    try:
        # Map UI selection to enum value
        type_map = {
            "All": None,
            "Single Agent": "single_agent",
            "Multi Agent Debate": "multi_agent_debate",
            "RAG Analysis": "rag_analysis",
            "RAG Debate": "rag_debate"
        }

        session_type_param = type_map.get(session_type_filter)

        # Fetch session history
        url = f"{config.fastapi_url}/api/analytics/session-history?limit={limit}"
        if session_type_param:
            url += f"&session_type={session_type_param}"

        history = api_client.get(url, timeout=10)
        sessions = history.get("sessions", [])

        if not sessions:
            st.info("No sessions found for the selected criteria")
            return

        st.caption(f"Showing {len(sessions)} most recent sessions")

        # Display sessions
        for idx, session in enumerate(sessions):
            with st.expander(
                f"**{session.get('session_type', 'unknown').replace('_', ' ').title()}** - "
                f"{session.get('user_query', 'No query')[:60]}... "
                f"({session.get('status', 'unknown')})",
                expanded=(idx == 0)  # Expand first session
            ):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.write(f"**Session ID:** {session.get('session_id', 'N/A')}")
                    st.write(f"**Type:** {session.get('session_type', 'N/A').replace('_', ' ').title()}")
                    st.write(f"**Analysis:** {session.get('analysis_type', 'N/A').replace('_', ' ').title()}")

                with col2:
                    st.write(f"**Status:** {session.get('status', 'N/A')}")
                    st.write(f"**Agents:** {session.get('agent_count', 0)}")
                    response_time = session.get('total_response_time_ms', 0)
                    st.write(f"**Response Time:** {response_time/1000:.2f}s" if response_time else "**Response Time:** N/A")

                with col3:
                    created = session.get('created_at', 'N/A')
                    st.write(f"**Created:** {created}")
                    completed = session.get('completed_at', 'Not completed')
                    st.write(f"**Completed:** {completed}")
                    collection = session.get('collection_name', 'N/A')
                    st.write(f"**Collection:** {collection}")

                # Query and results
                st.markdown("**User Query:**")
                st.text(session.get('user_query', 'No query available'))

                if session.get('overall_result'):
                    st.markdown("**Results Summary:**")
                    st.json(session['overall_result'])

                if session.get('error_message'):
                    st.error(f"**Error:** {session['error_message']}")

                # View detailed responses
                if st.button(f"View Full Details", key=f"details_{session.get('session_id')}"):
                    view_session_details(session.get('session_id'))

    except Exception as e:
        st.error(f"Failed to load session history: {e}")


def view_session_details(session_id: str):
    """Display detailed session information"""
    try:
        details = api_client.get(
            f"{config.fastapi_url}/api/analytics/session-details/{session_id}",
            timeout=10
        )

        st.subheader(f"Session Details: {session_id}")

        # Responses
        responses = details.get('responses', [])
        if responses:
            st.markdown(f"**{len(responses)} Agent Response(s):**")

            for idx, response in enumerate(responses, 1):
                with st.container():
                    st.markdown(f"**Response {idx}** - Agent: {response.get('agent_name', 'Unknown')}")
                    st.write(f"Model: {response.get('model_used', 'N/A')} | "
                            f"Time: {response.get('response_time_ms', 0)/1000:.2f}s | "
                            f"RAG: {'Yes' if response.get('rag_used') else 'No'}")

                    if response.get('rag_used'):
                        st.write(f"Documents found: {response.get('documents_found', 0)}")

                    st.text_area(
                        "Response Text",
                        response.get('response_text', 'No response'),
                        height=150,
                        key=f"response_{idx}"
                    )
                    st.markdown("---")

        # Citations
        citations = details.get('citations', [])
        if citations:
            st.markdown(f"**{len(citations)} Citation(s):**")
            for citation in citations:
                st.write(f"- {citation.get('document_name', 'Unknown')} "
                        f"(Relevance: {citation.get('similarity_score', 0):.2f})")

    except Exception as e:
        st.error(f"Failed to load session details: {e}")


def render_agent_performance_tab(days: int):
    """Agent performance metrics"""
    st.subheader("Agent Performance")
    st.caption("Understand which agents are most effective and frequently used")

    try:
        # Get all agents with performance data
        agents_response = api_client.get(
            f"{config.fastapi_url}/api/test-plan-agents",
            timeout=10
        )
        agents = agents_response.get("agents", [])

        if not agents:
            st.info("No agents found")
            return

        # Build performance table
        performance_data = []
        for agent in agents:
            # Get detailed performance for each agent
            try:
                perf = api_client.get(
                    f"{config.fastapi_url}/api/analytics/agent-performance/{agent['id']}",
                    timeout=10
                )

                metrics = perf.get("performance_metrics", {})
                performance_data.append({
                    "Agent Name": agent['name'],
                    "Type": agent.get('agent_type', 'N/A'),
                    "Model": agent.get('model_name', 'N/A'),
                    "Total Uses": metrics.get('total_responses', 0),
                    "Avg Time (s)": f"{metrics.get('avg_response_time_ms', 0)/1000:.2f}",
                    "RAG Usage %": f"{metrics.get('rag_usage_rate', 0):.1f}",
                    "Status": "Active" if agent.get('is_active') else "Inactive"
                })
            except:
                # Agent might not have performance data yet
                performance_data.append({
                    "Agent Name": agent['name'],
                    "Type": agent.get('agent_type', 'N/A'),
                    "Model": agent.get('model_name', 'N/A'),
                    "Total Uses": 0,
                    "Avg Time (s)": "N/A",
                    "RAG Usage %": "N/A",
                    "Status": "Active" if agent.get('is_active') else "Inactive"
                })

        # Display as dataframe
        df_perf = pd.DataFrame(performance_data)
        df_perf = df_perf.sort_values('Total Uses', ascending=False)

        st.dataframe(
            df_perf,
            hide_index=True,
            use_container_width=True
        )

        # Insights
        st.markdown("---")
        st.subheader("Key Insights")

        col1, col2 = st.columns(2)

        with col1:
            # Most used agent
            if not df_perf.empty:
                most_used = df_perf.iloc[0]
                st.metric(
                    "Most Used Agent",
                    most_used['Agent Name'],
                    f"{most_used['Total Uses']} uses"
                )

        with col2:
            # Average usage
            avg_uses = df_perf['Total Uses'].mean() if not df_perf.empty else 0
            st.metric("Avg Uses per Agent", f"{avg_uses:.1f}")

    except Exception as e:
        st.error(f"Failed to load agent performance: {e}")


def render_rag_effectiveness_tab(days: int):
    """RAG effectiveness metrics"""
    st.subheader("RAG Effectiveness Analysis")
    st.caption("Evaluate retrieval quality and document relevance")

    try:
        # Get RAG statistics
        analytics = api_client.get(
            f"{config.fastapi_url}/api/analytics/session-analytics?days={days}",
            timeout=10
        )

        rag_stats = analytics.get("rag_statistics", {})

        # Key RAG Metrics
        col1, col2, col3 = st.columns(3)

        with col1:
            total_responses = rag_stats.get("total_responses", 0)
            st.metric("Total Responses", total_responses)

        with col2:
            rag_responses = rag_stats.get("rag_responses", 0)
            st.metric("RAG-Enhanced", rag_responses)

        with col3:
            rag_rate = rag_stats.get("rag_usage_rate", 0)
            st.metric("RAG Usage Rate", f"{rag_rate:.1f}%")

        st.markdown("---")

        # Get recent RAG sessions
        history = api_client.get(
            f"{config.fastapi_url}/api/analytics/session-history?limit=100",
            timeout=10
        )
        sessions = history.get("sessions", [])

        # Filter RAG sessions
        rag_sessions = [s for s in sessions if 'rag' in s.get('session_type', '').lower()]

        if rag_sessions:
            st.subheader("Recent RAG Sessions")

            rag_data = []
            for session in rag_sessions[:20]:  # Show top 20
                rag_data.append({
                    "Query": session.get('user_query', 'N/A')[:60] + "...",
                    "Type": session.get('session_type', 'N/A').replace('_', ' ').title(),
                    "Collection": session.get('collection_name', 'N/A'),
                    "Time (s)": f"{session.get('total_response_time_ms', 0)/1000:.2f}",
                    "Status": session.get('status', 'N/A')
                })

            df_rag = pd.DataFrame(rag_data)
            st.dataframe(df_rag, hide_index=True, use_container_width=True)
        else:
            st.info("No RAG sessions found in the selected time range")

        # RAG Effectiveness Insights
        st.markdown("---")
        st.subheader("Effectiveness Insights")

        if total_responses > 0:
            non_rag = total_responses - rag_responses

            col1, col2 = st.columns(2)

            with col1:
                st.write("**Response Distribution:**")
                distribution_data = pd.DataFrame({
                    "Type": ["RAG-Enhanced", "Direct LLM"],
                    "Count": [rag_responses, non_rag]
                })
                st.dataframe(distribution_data, hide_index=True)

            with col2:
                st.write("**Usage Analysis:**")
                if rag_rate > 70:
                    st.success(f"High RAG adoption ({rag_rate:.1f}%)")
                elif rag_rate > 40:
                    st.info(f"Moderate RAG adoption ({rag_rate:.1f}%)")
                else:
                    st.warning(f"Low RAG adoption ({rag_rate:.1f}%)")

                st.write(f"Users are leveraging document context in {rag_rate:.1f}% of queries")
        else:
            st.info("No response data available for analysis")

    except Exception as e:
        st.error(f"Failed to load RAG effectiveness data: {e}")


# Main component export
def Session_History():
    """Main entry point (compatible with Home.py naming)"""
    render_session_history()
