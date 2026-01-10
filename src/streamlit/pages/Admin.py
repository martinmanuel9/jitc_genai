import streamlit as st
import torch

from components.healthcheck_sidebar import Healthcheck_Sidebar
from components.agent_manager import render_unified_agent_manager
from components.agent_sim import Agent_Sim

torch.classes.__path__ = []

# Page configuration (must be first Streamlit command)
st.set_page_config(page_title="Admin", layout="wide", page_icon="A")

# SIDEBAR - SYSTEM STATUS & CONTROLS
Healthcheck_Sidebar()

st.title("Admin")
st.caption("Manage prompts, agents, orchestration settings, and run AI simulations.")

# Create tabs for Agent Management and AI Simulation
mgmt_tab, sim_tab = st.tabs(["Agent Management", "AI Simulation"])

# === AGENT MANAGEMENT TAB ===
with mgmt_tab:
    st.header("Agent & Agent Set Management")
    st.caption("Create, edit, and manage individual agents and agent orchestration pipelines.")
    render_unified_agent_manager()

# === AI SIMULATION TAB ===
with sim_tab:
    st.header("AI Simulation & Testing")
    st.caption("Test and simulate agent behavior with various scenarios and inputs.")
    Agent_Sim()
