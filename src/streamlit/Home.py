import streamlit as st
import nest_asyncio
import torch
import logging

from config.settings import config

# Components - migrated to use new architecture internally
from components.healthcheck_sidebar import Healthcheck_Sidebar
from components.direct_chat import Direct_Chat
from components.json_test_plan_generator import JSON_Test_Plan_Generator
from components.upload_documents import render_upload_component
from services.chromadb_service import chromadb_service

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
CHROMADB_API = config.endpoints.vectordb

# THIS MUST BE THE VERY FIRST STREAMLIT COMMAND
st.set_page_config(page_title="Test Planning Workflow", layout="wide", page_icon="T")

st.title("Test Planning Workflow")
st.caption("Upload standards, generate plans, edit sections, and build test cards.")

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
workflow_tab, chat_tab = st.tabs(["Workflow", "Chat"])


with workflow_tab:
    st.subheader("Workflow Steps")
    step_upload, step_generate = st.tabs([
        "1. Upload Standards",
        "2. Generate Test Plan (JSON)",
    ])

    with step_upload:
        try:
            st.session_state.collections = chromadb_service.get_collections()
        except Exception:
            st.session_state.collections = st.session_state.get("collections", [])

        render_upload_component(
            available_collections=st.session_state.collections,
            load_collections_func=chromadb_service.get_collections,
            create_collection_func=chromadb_service.create_collection,
            upload_endpoint=f"{CHROMADB_API}/documents/upload-and-process",
            job_status_endpoint=f"{CHROMADB_API}/jobs/{{job_id}}",
            key_prefix="home_upload"
        )

    with step_generate:
        JSON_Test_Plan_Generator()

with chat_tab:
    Direct_Chat()

# ----------------------------------------------------------------------
# SESSION HISTORY & ANALYTICS MODE
# ----------------------------------------------------------------------
# elif chat_mode == "Session History":
#     st.markdown("---")
#     Session_History()


# Footer
st.markdown("---")
st.caption("This application processes documents and provides GenAI capabilities. Ensure all data is handled according to your organization's data protection policies.")
