import streamlit as st
import requests
import torch
import os
from components.upload_documents import render_upload_component, browse_documents, view_images, query_documents
from components.healthcheck_sidebar import Healthcheck_Sidebar
from services.chromadb_service import chromadb_service
from config.settings import config
import pandas as pd
from sentence_transformers import SentenceTransformer
import time
import re

torch.classes.__path__ = []

CHROMADB_API = config.endpoints.vectordb


if "collections" not in st.session_state:
    try:
        st.session_state.collections = chromadb_service.get_collections()
    except Exception:
        st.session_state.collections = []

# Initialize embedding model for queries
@st.cache_resource
def load_embedding_model():
    return SentenceTransformer('multi-qa-mpnet-base-dot-v1')


# SIDEBAR - SYSTEM STATUS & CONTROLS
Healthcheck_Sidebar()

# Streamlit app configuration

st.set_page_config(page_title="Document Management", layout="wide")
st.title("Document & Collection Management")


### Document Upload and Management
try:
    collections = chromadb_service.get_collections()
except Exception as e:
    st.warning(f"Unable to connect to FastAPI service. Please ensure the service is running. Error: {str(e)}")
    collections = st.session_state.get("collections", [])

render_upload_component(
    available_collections= collections,
    load_collections_func= chromadb_service.get_collections,
    create_collection_func= chromadb_service.create_collection,
    upload_endpoint=f"{CHROMADB_API}/documents/upload-and-process",
    job_status_endpoint=f"{CHROMADB_API}/jobs/{{job_id}}",
    key_prefix="files_upload"
)

st.divider()

# ---- QUERY DOCUMENTS ----
with st.expander("Query Documents"):
    query_documents(key_prefix="files_query")

# ---- BROWSE DOCUMENTS ----
with st.expander("Browse Documents in Collection"):
    browse_documents(key_prefix="files_browse")

# ---- RECONSTRUCT DOCUMENTS ----
with st.expander("View Processed"):
    view_images(key_prefix="files_reconstruct")