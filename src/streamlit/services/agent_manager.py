"""
AgentManager - Centralized agent management for Streamlit components.

This service provides a unified interface for loading and managing agents
across the application, with built-in error handling, session state management,
and consistent UI components.
"""

import streamlit as st
from app_lib.api.client import api_client
from config.settings import config
import logging
import traceback
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class AgentManager:
    """Centralized agent management for Streamlit components"""

    @staticmethod
    def load_agents(session_key: str = "agents_data", timeout: int = 10) -> List[Dict[str, Any]]:
        """
        Load agents from the API.

        Args:
            session_key: Session state key to store agents
            timeout: Request timeout in seconds

        Returns:
            List of agent dictionaries
        """
        try:
            # Use new unified agent API endpoint
            agent_data = api_client.get(
                f"{config.fastapi_url}/api/test-plan-agents",
                timeout=timeout
            )
            agents = agent_data.get("agents", [])
            st.session_state[session_key] = agents
            return agents
        except Exception as e:
            logger.error(f"Failed to load agents: {e}")
            st.session_state[session_key] = []
            raise

    @staticmethod
    def ensure_agents_loaded(session_key: str = "agents_data") -> List[Dict[str, Any]]:
        """
        Ensure agents are loaded into session state.

        This method checks if agents are already loaded in session state,
        and if not, fetches them from the API.

        Args:
            session_key: Session state key to check/store agents

        Returns:
            List of agent dictionaries
        """
        if session_key not in st.session_state:
            try:
                return AgentManager.load_agents(session_key=session_key)
            except Exception as e:
                logger.error(f"Failed to auto-load agents: {e}")
                st.session_state[session_key] = []

        return st.session_state.get(session_key, [])

    @staticmethod
    def refresh_agents_button(
        button_text: str = "Refresh Agent List",
        key: str = "refresh_agents",
        session_key: str = "agents_data",
        show_traceback: bool = False,
        show_empty_warning: bool = True,
        show_count: bool = True,
        use_container_width: bool = False,
        timeout: int = 10
    ) -> bool:
        """
        Render button to load agents with standardized UI.

        Args:
            button_text: Button label
            key: Streamlit key for button
            session_key: Session state key to store agents
            show_traceback: Show detailed error traceback
            show_empty_warning: Show warning when no agents found
            show_count: Show agent count in success message
            use_container_width: Use full container width
            timeout: Request timeout in seconds

        Returns:
            True if agents were loaded successfully
        """
        if st.button(button_text, key=key, use_container_width=use_container_width):
            try:
                with st.spinner("Loading agents from database..."):
                    agents = AgentManager.load_agents(
                        session_key=session_key,
                        timeout=timeout
                    )

                    if agents:
                        if show_count:
                            st.success(f"Loaded {len(agents)} agent(s)")
                        else:
                            st.success("Agents loaded successfully")
                        return True
                    else:
                        if show_empty_warning:
                            st.warning("No agents found. Please create agents first.")
                        return False

            except Exception as e:
                logger.error(f"Error loading agents: {e}")
                st.error(f"Error loading agents: {str(e)}")

                if show_traceback:
                    with st.expander("Error Details"):
                        st.code(traceback.format_exc())
                return False

        return False

    @staticmethod
    def get_agents(session_key: str = "agents_data") -> List[Dict[str, Any]]:
        """
        Get agents from session state.

        Args:
            session_key: Session state key where agents are stored

        Returns:
            List of agent dictionaries (empty list if not loaded)
        """
        return st.session_state.get(session_key, [])

    @staticmethod
    def get_agent_by_id(agent_id: int, session_key: str = "agents_data") -> Optional[Dict[str, Any]]:
        """
        Get a specific agent by ID from session state.

        Args:
            agent_id: Agent ID to find
            session_key: Session state key where agents are stored

        Returns:
            Agent dictionary if found, None otherwise
        """
        agents = AgentManager.get_agents(session_key=session_key)
        for agent in agents:
            if agent.get("id") == agent_id:
                return agent
        return None

    @staticmethod
    def get_active_agents(session_key: str = "agents_data") -> List[Dict[str, Any]]:
        """
        Get only active agents from session state.

        Args:
            session_key: Session state key where agents are stored

        Returns:
            List of active agent dictionaries
        """
        agents = AgentManager.get_agents(session_key=session_key)
        return [agent for agent in agents if agent.get("is_active", True)]

    @staticmethod
    def display_agent_metrics(session_key: str = "agents_data"):
        """
        Display agent metrics in a metric widget.

        Args:
            session_key: Session state key where agents are stored
        """
        agents = AgentManager.get_agents(session_key=session_key)
        if agents:
            total_agents = len(agents)
            active_agents = len(AgentManager.get_active_agents(session_key=session_key))
            st.metric("Total Agents", total_agents, delta=f"{active_agents} active")
        else:
            st.metric("Total Agents", 0)

    @staticmethod
    def agent_selectbox(
        label: str = "Select Agent",
        key: str = "select_agent",
        session_key: str = "agents_data",
        only_active: bool = True,
        name_format: str = "{name} ({model})"
    ) -> Optional[Dict[str, Any]]:
        """
        Render a selectbox to choose an agent.

        Args:
            label: Label for the selectbox
            key: Streamlit key for selectbox
            session_key: Session state key where agents are stored
            only_active: Show only active agents
            name_format: Format string for agent display name (can use {name}, {model}, {id})

        Returns:
            Selected agent dictionary, or None if no agents available
        """
        if only_active:
            agents = AgentManager.get_active_agents(session_key=session_key)
        else:
            agents = AgentManager.get_agents(session_key=session_key)

        if not agents:
            st.warning("No agents available. Please create agents first.")
            return None

        # Format agent names
        agent_names = [
            name_format.format(
                name=agent.get("name", "Unknown"),
                model=agent.get("model_name", "Unknown"),
                id=agent.get("id", "N/A")
            )
            for agent in agents
        ]

        selected_index = st.selectbox(
            label,
            range(len(agents)),
            format_func=lambda i: agent_names[i],
            key=key
        )

        return agents[selected_index] if selected_index is not None else None


# Export singleton instance for convenience
agent_manager = AgentManager()
