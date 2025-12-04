import streamlit as st
import torch
from components.vectordb_manager import render_vectordb_manager
from components.healthcheck_sidebar import Healthcheck_Sidebar

torch.classes.__path__ = []

# SIDEBAR - SYSTEM STATUS & CONTROLS
Healthcheck_Sidebar()

# Page configuration
st.set_page_config(page_title="Vector Database Manager", layout="wide")

# Page header
st.title("Vector Database Manager")
# Render the vector database manager component
render_vectordb_manager(key_prefix="db_manager")
