"""
Test Plan Version Manager Page

Provides version status management and comparison features.
"""

import streamlit as st
from components.test_plan_version_manager import render_version_manager

st.set_page_config(
    page_title="Version Manager",
    page_icon="📋",
    layout="wide"
)

# Render the version manager component
render_version_manager()
