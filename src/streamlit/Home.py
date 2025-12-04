import streamlit as st
import os
import nest_asyncio
import torch
import logging

from config.settings import config
from config.env import env

# Components - migrated to use new architecture internally
from components.healthcheck_sidebar import Healthcheck_Sidebar
from components.direct_chat import Direct_Chat
from components.agent_sim import Agent_Sim
from components.document_generator import Document_Generator
from components.test_card_viewer import TestCardViewer
from components.agent_manager import render_unified_agent_manager
from components.session_history import Session_History

torch.classes.__path__ = []
nest_asyncio.apply()

# Configure logging to suppress benign WebSocket errors
# These errors occur when users refresh/close the page during auto-refresh
# and are properly handled by Tornado's async exception handler
class WebSocketErrorFilter(logging.Filter):
    def filter(self, record):
        # Suppress WebSocketClosedError and StreamClosedError
        if 'WebSocketClosedError' in str(record.msg) or 'StreamClosedError' in str(record.msg):
            return False
        if 'tornado.websocket' in record.name and 'exception' in str(record.msg).lower():
            return False
        return True

# Apply filter to root logger and Streamlit loggers
for logger_name in ['', 'streamlit', 'tornado.application']:
    logger = logging.getLogger(logger_name)
    logger.addFilter(WebSocketErrorFilter())

# Use centralized config instead of duplicate endpoint definitions
FASTAPI = config.endpoints.base
CHROMADB_API = config.endpoints.vectordb
CHAT_ENDPOINT = config.endpoints.chat
HISTORY_ENDPOINT = config.endpoints.history
HEALTH_ENDPOINT = config.endpoints.health
OPEN_AI_API_KEY = env.openai_api_key

# THIS MUST BE THE VERY FIRST STREAMLIT COMMAND
st.set_page_config(page_title="AI Assistant", layout="wide", page_icon="🤖")

st.title("AI Assistant")

# Initialize session state
if 'health_status' not in st.session_state:
    st.session_state.health_status = None
if 'available_models' not in st.session_state:
    st.session_state.available_models = []
if 'collections' not in st.session_state:
    st.session_state.collections = []
if 'agents_data' not in st.session_state:
    st.session_state.agents_data = []
if 'debate_sequence' not in st.session_state:
    st.session_state.debate_sequence = []
if 'upload_progress' not in st.session_state:
    st.session_state.upload_progress = {}

# ----------------------------------------------------------------------
# SIDEBAR - SYSTEM STATUS & CONTROLS
# ----------------------------------------------------------------------
Healthcheck_Sidebar()

# ----------------------------------------------------------------------
# MAIN INTERFACE
# ----------------------------------------------------------------------
# Chat mode selection
chat_mode = st.radio(
    "Select Mode:",
    ["Direct Chat", "AI Agent Simulation", "Agent & Orchestration Manager", "Document Generator", "Test Card Viewer"],
    horizontal=True
)

# ----------------------------------------------------------------------
# DIRECT CHAT MODE
# ----------------------------------------------------------------------
if chat_mode == "Direct Chat":
    st.markdown("---")
    Direct_Chat()

# ----------------------------------------------------------------------
# AI AGENT SIMULATION MODE
# ----------------------------------------------------------------------
elif chat_mode == "AI Agent Simulation":
    st.markdown("---")
    Agent_Sim()

# ----------------------------------------------------------------------
# UNIFIED AGENT & ORCHESTRATION MANAGER MODE
# ----------------------------------------------------------------------
elif chat_mode == "Agent & Orchestration Manager":
    st.markdown("---")
    render_unified_agent_manager()

# ----------------------------------------------------------------------
# DOCUMENT GENERATOR MODE
# ----------------------------------------------------------------------
elif chat_mode == "Document Generator":
    st.markdown("---")
    Document_Generator()

# ----------------------------------------------------------------------
# TEST CARD VIEWER MODE (Phase 3)
# ----------------------------------------------------------------------
elif chat_mode == "Test Card Viewer":
    st.markdown("---")
    TestCardViewer()

# ----------------------------------------------------------------------
# SESSION HISTORY & ANALYTICS MODE
# ----------------------------------------------------------------------
# elif chat_mode == "Session History":
#     st.markdown("---")
#     Session_History()


# Footer
st.markdown("---")
st.caption("This application processes documents and provide GenAI capabilitites. Ensure all data is handled according to your organization's data protection policies.")
