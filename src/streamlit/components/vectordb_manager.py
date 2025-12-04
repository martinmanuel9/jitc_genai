import streamlit as st
import pandas as pd
from typing import List, Dict, Optional
from config.settings import config
from app_lib.api.client import api_client
from services.chromadb_service import chromadb_service

VECTORDB_API = config.endpoints.vectordb


def render_vectordb_manager(key_prefix: str = "vectordb"):
    """
    Comprehensive vector database file management component.

    Provides full CRUD operations for:
    - Collections (create, delete)
    - Documents (reconstruct, delete multiple)
    - Bulk operations

    Args:
        key_prefix: Unique prefix for Streamlit widget keys
    """
        # Main tabs
    tab_collections, tab_documents = st.tabs([
        "Collections",
        "Documents"
    ])

    # Tab 1: Collection Management
    with tab_collections:
        render_collection_management(key_prefix)

    # Tab 2: Document Management
    with tab_documents:
        render_document_management(key_prefix)


def render_collection_management(key_prefix: str):
    """Manage collections: create, delete"""
    st.subheader("Collection Management")

    # Header with Refresh and Create buttons
    col1, col2, col3 = st.columns([2, 1, 1])
    with col2:
        if st.button("Refresh", key=f"{key_prefix}_refresh_collections", use_container_width=True):
            st.session_state.pop(f"{key_prefix}_collections", None)
            st.rerun()
    with col3:
        if st.button("Create New", key=f"{key_prefix}_show_create_form", use_container_width=True):
            st.session_state[f"{key_prefix}_show_create_form"] = True
            st.rerun()

    # Create collection form (popup style)
    if st.session_state.get(f"{key_prefix}_show_create_form", False):
        with st.expander("Create New Collection", expanded=True):
            new_collection_name = st.text_input(
                "Collection Name",
                key=f"{key_prefix}_new_collection_name",
                placeholder="e.g., legal_contracts"
            )

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Create", key=f"{key_prefix}_create_collection_btn", type="primary", use_container_width=True):
                    if new_collection_name:
                        try:
                            result = chromadb_service.create_collection(new_collection_name)
                            st.success(f"Collection '{new_collection_name}' created!")
                            st.session_state.pop(f"{key_prefix}_collections", None)
                            st.session_state.pop(f"{key_prefix}_show_create_form", None)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to create: {e}")
                    else:
                        st.warning("Please enter a collection name")
            with col2:
                if st.button("Cancel", key=f"{key_prefix}_cancel_create", use_container_width=True):
                    st.session_state.pop(f"{key_prefix}_show_create_form", None)
                    st.rerun()

    collections = get_collections_cached(key_prefix)

    if not collections:
        st.info("No collections found. Click 'Create New' to get started.")
        return

    st.markdown("### Collections")
    st.success(f"Found {len(collections)} collection(s)")

    # Display each collection with action buttons
    for collection_name in collections:
        # Get document count
        docs = get_documents_in_collection(collection_name, key_prefix)
        doc_count = len(docs.get('ids', [])) if docs else 0

        # Get unique documents
        doc_groups = group_documents_by_name(docs) if docs else {}
        unique_count = len(doc_groups)

        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])

            with col1:
                st.markdown(f"**{collection_name}**")
                st.caption(f"{unique_count} documents, {doc_count} sections")

            with col2:
                if st.button("View Details", key=f"{key_prefix}_view_{collection_name}", use_container_width=True):
                    st.session_state[f"{key_prefix}_view_collection"] = collection_name
                    st.rerun()

            with col3:
                if st.button("Delete", key=f"{key_prefix}_delete_{collection_name}", type="primary", use_container_width=True):
                    st.session_state[f"{key_prefix}_delete_collection"] = collection_name
                    st.rerun()

            st.divider()

    # View collection details popup
    if f"{key_prefix}_view_collection" in st.session_state:
        view_collection = st.session_state[f"{key_prefix}_view_collection"]
        st.markdown("---")

        with st.container():
            st.subheader(f"Collection: {view_collection}")

            # Get detailed stats
            docs = get_documents_in_collection(view_collection, key_prefix)
            doc_count = len(docs.get('ids', [])) if docs else 0
            doc_groups = group_documents_by_name(docs) if docs else {}
            unique_count = len(doc_groups)

            # Display metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Unique Documents", unique_count)
            with col2:
                st.metric("Total Sections", doc_count)
            with col3:
                avg_sections = doc_count / unique_count if unique_count > 0 else 0
                st.metric("Avg Sections/Doc", f"{avg_sections:.1f}")

            # Document list
            if doc_groups:
                st.markdown("#### Documents in Collection")
                for doc_name, doc_list in doc_groups.items():
                    st.markdown(f"- **{doc_name}** ({len(doc_list)} sections)")

            # Close button
            if st.button("Close", key=f"{key_prefix}_close_view"):
                st.session_state.pop(f"{key_prefix}_view_collection")
                st.rerun()

    # Delete collection confirmation popup
    if f"{key_prefix}_delete_collection" in st.session_state:
        delete_collection = st.session_state[f"{key_prefix}_delete_collection"]
        st.markdown("---")

        with st.container():
            st.error(f"Delete Collection: {delete_collection}")
            st.warning("This will permanently delete all documents in the collection! This action cannot be undone.")

            # Get collection stats
            docs = get_documents_in_collection(delete_collection, key_prefix)
            doc_count = len(docs.get('ids', [])) if docs else 0
            doc_groups = group_documents_by_name(docs) if docs else {}
            unique_count = len(doc_groups)

            st.markdown(f"- **{unique_count}** unique documents")
            st.markdown(f"- **{doc_count}** total sections")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Confirm Delete", key=f"{key_prefix}_confirm_delete", type="primary", use_container_width=True):
                    try:
                        response = api_client.delete(
                            f"{VECTORDB_API}/collection",
                            params={"collection_name": delete_collection}
                        )
                        st.success(f"Deleted collection '{delete_collection}'")
                        st.session_state.pop(f"{key_prefix}_collections", None)
                        st.session_state.pop(f"{key_prefix}_docs_{delete_collection}", None)
                        st.session_state.pop(f"{key_prefix}_delete_collection", None)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to delete: {e}")
            with col2:
                if st.button("Cancel", key=f"{key_prefix}_cancel_delete", use_container_width=True):
                    st.session_state.pop(f"{key_prefix}_delete_collection")
                    st.rerun()


def render_document_management(key_prefix: str):
    """Manage documents within collections"""
    st.subheader("Document Management")

    collections = get_collections_cached(key_prefix)

    if not collections:
        st.info("No collections available. Create a collection first.")
        return

    # Collection selector
    col1, col2 = st.columns([3, 1])
    with col1:
        selected_collection = st.selectbox(
            "Select Collection",
            collections,
            key=f"{key_prefix}_doc_collection_selector"
        )
    with col2:
        st.write("")  # Spacing
        st.write("")  # Spacing
        if st.button("Refresh", key=f"{key_prefix}_refresh_docs"):
            st.session_state.pop(f"{key_prefix}_docs_{selected_collection}", None)
            st.rerun()

    if not selected_collection:
        return

    # Load documents
    docs = get_documents_in_collection(selected_collection, key_prefix)

    if not docs or not docs.get('ids'):
        st.info(f"No documents found in '{selected_collection}'")
        return

    # Group by document_name and document_id
    doc_groups = group_documents_by_document_id(docs)

    if not doc_groups:
        st.info(f"No documents found in '{selected_collection}'")
        return

    st.success(f"Found {len(doc_groups)} unique document(s)")

    # Initialize selection state
    if f"{key_prefix}_selected_docs" not in st.session_state:
        st.session_state[f"{key_prefix}_selected_docs"] = []

    # Document filter
    search_filter = st.text_input(
        "Filter documents",
        key=f"{key_prefix}_doc_filter",
        placeholder="Search by document name..."
    )

    st.divider()

    # Display documents with multi-select
    st.markdown("### Documents")

    # Select/Deselect All
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Select All", key=f"{key_prefix}_select_all"):
            st.session_state[f"{key_prefix}_selected_docs"] = list(doc_groups.keys())
            st.rerun()
    with col2:
        if st.button("Deselect All", key=f"{key_prefix}_deselect_all"):
            st.session_state[f"{key_prefix}_selected_docs"] = []
            st.rerun()

    # Display document list
    for doc_key, doc_info in doc_groups.items():
        doc_name = doc_info['name']
        doc_id = doc_info['id']
        chunk_count = doc_info['chunk_count']

        # Apply filter
        if search_filter and search_filter.lower() not in doc_name.lower():
            continue

        with st.container():
            col1, col2 = st.columns([3, 1])

            with col1:
                # Checkbox for selection
                is_selected = doc_key in st.session_state[f"{key_prefix}_selected_docs"]
                if st.checkbox(
                    f"{doc_name}",
                    value=is_selected,
                    key=f"{key_prefix}_checkbox_{doc_key}"
                ):
                    if doc_key not in st.session_state[f"{key_prefix}_selected_docs"]:
                        st.session_state[f"{key_prefix}_selected_docs"].append(doc_key)
                else:
                    if doc_key in st.session_state[f"{key_prefix}_selected_docs"]:
                        st.session_state[f"{key_prefix}_selected_docs"].remove(doc_key)

                # Show metadata in a subtle way
                st.caption(f"{chunk_count} sections")

            with col2:
                # Reconstruct button
                if st.button("View", key=f"{key_prefix}_reconstruct_{doc_key}"):
                    st.session_state[f"{key_prefix}_reconstruct_doc"] = {
                        "document_id": doc_id,
                        "document_name": doc_name,
                        "collection": selected_collection
                    }
                    st.rerun()

    # Bulk delete selected documents
    selected_count = len(st.session_state[f"{key_prefix}_selected_docs"])
    if selected_count > 0:
        st.divider()
        st.warning(f"{selected_count} document(s) selected")

        if st.button(f"Delete {selected_count} Selected Document(s)", key=f"{key_prefix}_delete_selected", type="primary"):
            # Collect all chunk IDs for selected documents
            all_chunk_ids = []
            for doc_key in st.session_state[f"{key_prefix}_selected_docs"]:
                if doc_key in doc_groups:
                    all_chunk_ids.extend(doc_groups[doc_key]['chunk_ids'])

            if all_chunk_ids:
                try:
                    response = api_client.post(
                        f"{VECTORDB_API}/documents/remove",
                        data={
                            "collection_name": selected_collection,
                            "ids": all_chunk_ids
                        }
                    )
                    st.success(f"Deleted {selected_count} document(s) ({len(all_chunk_ids)} sections)")
                    st.session_state[f"{key_prefix}_selected_docs"] = []
                    st.session_state.pop(f"{key_prefix}_docs_{selected_collection}", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to delete: {e}")

    # Reconstruct document dialog
    if f"{key_prefix}_reconstruct_doc" in st.session_state:
        reconstruct_data = st.session_state[f"{key_prefix}_reconstruct_doc"]
        st.divider()
        st.subheader(f"{reconstruct_data['document_name']}")

        try:
            # Call reconstruction endpoint
            response = api_client.get(
                f"{VECTORDB_API}/documents/reconstruct/{reconstruct_data['document_id']}",
                params={"collection_name": reconstruct_data['collection']}
            )

            # Display metadata
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Sections", response.get('total_chunks', 0))
            with col2:
                st.metric("Collection", reconstruct_data['collection'])
            with col3:
                metadata = response.get('metadata', {})
                st.metric("Total Images", metadata.get('total_images', 0))

            # Display reconstructed content
            st.markdown("### Reconstructed Document")

            reconstructed_content = response.get('reconstructed_content', '')

            # Display as markdown
            st.markdown(reconstructed_content)

            # Display images if available
            images = response.get('images', [])
            if images:
                st.divider()
                st.markdown("### Images")

                for idx, img in enumerate(images, 1):
                    with st.expander(f"Image {idx}: {img.get('filename', 'Unknown')}", expanded=False):
                        col1, col2 = st.columns([2, 1])

                        with col1:
                            # Try to display image
                            if img.get('exists', False):
                                storage_path = img.get('storage_path', '')
                                # Convert to URL path
                                filename = storage_path.split('/')[-1] if '/' in storage_path else storage_path
                                image_url = f"{VECTORDB_API}/images/{filename}"

                                try:
                                    st.image(image_url, caption=img.get('filename', ''))
                                except:
                                    st.warning("Image preview not available")

                        with col2:
                            st.markdown(f"**Filename**: {img.get('filename', 'N/A')}")
                            st.markdown(f"**Exists**: {'' if img.get('exists', False) else ''}")

                            if img.get('description'):
                                st.markdown("**Description**:")
                                st.caption(img.get('description'))

            # Close button
            if st.button("Close", key=f"{key_prefix}_close_reconstruct"):
                st.session_state.pop(f"{key_prefix}_reconstruct_doc")
                st.rerun()

        except Exception as e:
            st.error(f"Failed to reconstruct document: {e}")
            if st.button("Close", key=f"{key_prefix}_close_reconstruct_error"):
                st.session_state.pop(f"{key_prefix}_reconstruct_doc")
                st.rerun()


# Helper functions
def get_collections_cached(key_prefix: str) -> List[str]:
    """Get collections with caching"""
    cache_key = f"{key_prefix}_collections"

    if cache_key not in st.session_state:
        try:
            st.session_state[cache_key] = chromadb_service.get_collections()
        except Exception as e:
            st.error(f"Failed to load collections: {e}")
            return []

    return st.session_state[cache_key]


def get_documents_in_collection(collection_name: str, key_prefix: str) -> Optional[Dict]:
    """Get all documents in a collection with caching"""
    cache_key = f"{key_prefix}_docs_{collection_name}"

    if cache_key not in st.session_state:
        try:
            response = api_client.get(
                f"{VECTORDB_API}/documents",
                params={"collection_name": collection_name}
            )
            st.session_state[cache_key] = response
        except Exception as e:
            st.error(f"Failed to load documents: {e}")
            return None

    return st.session_state[cache_key]


def group_documents_by_name(docs: Dict) -> Dict[str, List[Dict]]:
    """Group document sections by document_name"""
    groups = {}

    if not docs or not docs.get('ids'):
        return groups

    for idx, doc_id in enumerate(docs['ids']):
        metadata = docs['metadatas'][idx] if docs['metadatas'] and idx < len(docs['metadatas']) else {}
        doc_name = metadata.get('document_name', 'Unknown')

        if doc_name not in groups:
            groups[doc_name] = []

        groups[doc_name].append({
            'id': doc_id,
            'metadata': metadata
        })

    return groups


def group_documents_by_document_id(docs: Dict) -> Dict[str, Dict]:
    """
    Group sections by unique document (using document_id).
    Returns dict with composite key (doc_name + doc_id) to handle documents with same name.
    """
    groups = {}

    if not docs or not docs.get('ids'):
        return groups

    for idx, chunk_id in enumerate(docs['ids']):
        metadata = docs['metadatas'][idx] if docs['metadatas'] and idx < len(docs['metadatas']) else {}

        doc_name = metadata.get('document_name', 'Unknown')
        doc_id = metadata.get('document_id', chunk_id.split('_')[0] if '_' in chunk_id else 'unknown')

        # Create composite key to handle documents with same name
        key = f"{doc_name}||{doc_id}"

        if key not in groups:
            groups[key] = {
                'name': doc_name,
                'id': doc_id,
                'chunk_ids': [],
                'chunk_count': 0
            }

        groups[key]['chunk_ids'].append(chunk_id)
        groups[key]['chunk_count'] += 1

    return groups
