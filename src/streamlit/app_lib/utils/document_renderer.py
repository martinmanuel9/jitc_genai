import streamlit as st
import requests
from PIL import Image
from io import BytesIO
from config.settings import config
import re


def clean_markdown_formatting(text: str) -> str:
    """Remove markdown formatting from text for display in alt text and captions."""
    if not text:
        return text

    # Remove markdown headers
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)

    # Remove bold/italic markers
    text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)  # **bold**
    text = re.sub(r'\*([^\*]+)\*', r'\1', text)  # *italic*
    text = re.sub(r'__([^_]+)__', r'\1', text)  # __bold__
    text = re.sub(r'_([^_]+)_', r'\1', text)  # _italic_

    # Remove # Description: prefix if present
    text = re.sub(r'^#?\s*Description:\s*', '', text, flags=re.IGNORECASE)

    # Remove Caption for Figure X: prefix
    text = re.sub(r'^Caption\s+for\s+Figure\s+\d+:\s*', '', text, flags=re.IGNORECASE)

    return text.strip()


def render_reconstructed_document(result: dict):
    """
    Render reconstructed document with inline images properly displayed.

    This function parses the markdown content, extracts image references,
    fetches them from the API, and renders them inline using st.image()
    since st.markdown() has limitations with external image URLs.
    """
    md = result["reconstructed_content"]

    # Use centralized config for API endpoint
    CHROMADB_API = config.endpoints.vectordb

    # Show the document with properly rendered images
    with st.expander("Reconstructed Document Text", expanded=True):
        # Parse markdown to extract image references and text sections
        # Pattern: ![alt text](url)
        image_pattern = r'!\[([^\]]*)\]\(([^\)]+)\)'

        # Split content by images
        parts = re.split(image_pattern, md)

        # Render alternating text and images
        i = 0
        image_counter = 0
        while i < len(parts):
            # Text before image (or final text if no more images)
            if i % 3 == 0:
                text = parts[i].strip()
                if text:
                    st.markdown(text, unsafe_allow_html=True)
                i += 1
            # Image alt text and URL
            elif i % 3 == 1:
                alt_text = parts[i]
                image_url = parts[i+1] if i+1 < len(parts) else ""

                # Clean markdown formatting from alt text
                clean_alt = clean_markdown_formatting(alt_text)

                # Extract filename from URL
                filename = image_url.split('/')[-1] if '/' in image_url else image_url

                # Fetch and display image
                try:
                    # Use FastAPI service URL (works from inside Docker and from host)
                    # Use config.endpoints to get the correct URL
                    image_fetch_url = f"{CHROMADB_API}/images/{filename}"
                    resp = requests.get(image_fetch_url, timeout=5)
                    resp.raise_for_status()
                    image = Image.open(BytesIO(resp.content))

                    # Display image with clean caption
                    st.image(image, caption=clean_alt, use_container_width=True)
                    image_counter += 1

                except Exception as e:
                    # Show placeholder if image can't be fetched
                    st.warning(f" Image not available: {filename}")
                    st.caption(f"Alt text: {clean_alt}")

                i += 2

    # Also show images in separate expander for reference
    if result.get("images"):
        with st.expander(f"Image Gallery ({len(result['images'])} images)"):
            for i, img in enumerate(result["images"], 1):
                st.subheader(f"Image {i}: {img['filename']}")
                col1, col2 = st.columns([1, 2])

                # left: actual image
                with col1:
                    try:
                        resp = requests.get(f"{CHROMADB_API}/images/{img['filename']}", timeout=5)
                        resp.raise_for_status()
                        image = Image.open(BytesIO(resp.content))
                        st.image(image, caption=img['filename'])
                    except Exception as e:
                        st.write(f"Image preview not available: {e}")

                # right: metadata + description
                with col2:
                    st.write(f"**Filename:** `{img['filename']}`")
                    st.write(f"**Storage Path:** `{img.get('storage_path', 'N/A')}`")
                    if img.get("description"):
                        st.text_area("Description", img["description"], height=150, key=f"recon_desc_{i}")
