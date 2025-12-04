import streamlit as st
from config.settings import config
from app_lib.api.client import api_client
import base64
from datetime import datetime
import re

# Use centralized config for endpoints
FASTAPI = config.endpoints.api
CHROMADB_API = config.endpoints.vectordb
CHAT_ENDPOINT = config.endpoints.chat
HISTORY_ENDPOINT = config.endpoints.history
EVALUATE_ENDPOINT = f"{config.endpoints.api}/evaluate_doc"


def format_timestamp(timestamp_str: str) -> str:
    """Convert timestamp string to readable format"""
    try:
        # Try parsing ISO format
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        return dt.strftime("%B %d, %Y at %I:%M %p")
    except:
        # Fallback to just cleaning up the string
        return timestamp_str[:19].replace('T', ' at ')


def generate_conversation_title(user_query: str, max_length: int = 60) -> str:
    """
    Generate a meaningful title from the user query.

    Args:
        user_query: The user's question/query
        max_length: Maximum length of the title

    Returns:
        A clean, readable title
    """
    if not user_query:
        return "Untitled Conversation"

    # Clean the query
    query = user_query.strip()

    # Remove common prefixes
    prefixes_to_remove = [
        r'^(please |could you |can you |would you )',
        r'^(summarize |analyze |explain |describe |review |evaluate )',
    ]
    for prefix in prefixes_to_remove:
        query = re.sub(prefix, '', query, flags=re.IGNORECASE)

    # Capitalize first letter
    query = query[0].upper() + query[1:] if query else query

    # Truncate if too long
    if len(query) > max_length:
        query = query[:max_length].rsplit(' ', 1)[0] + '...'

    return query


def get_query_type_badge(rec: dict) -> str:
    """
    Get a colored badge for the query type.

    Args:
        rec: Chat history record

    Returns:
        HTML badge string
    """
    query_type = rec.get('query_type', 'unknown')

    badge_colors = {
        'direct': ('Direct', '#0066cc'),
        'rag': ('RAG', '#00aa00'),
        'rag_agent': ('RAG Agent', '#9933cc'),
        'rag_debate_sequence': ('RAG Debate', '#ff8800'),
        'legal_research': ('Legal Research', '#cc0000'),
        'document_evaluation': ('Document Eval', '#666666'),
    }

    display_type, color = badge_colors.get(query_type, (query_type.replace('_', ' ').title(), '#999999'))

    return f'<span style="color: {color}; font-weight: bold;">{display_type}</span>'


def Chat_History(key_prefix: str = "",):
    def pref(k): return f"{key_prefix}_{k}" if key_prefix else k

    with st.container(border=False, key=pref("history_container")):
        st.header("Chat History")

        # Auto-load history on first visit
        if pref("history_loaded") not in st.session_state:
            st.session_state[pref("history_loaded")] = False

        if not st.session_state[pref("history_loaded")]:
            try:
                with st.spinner("Loading chat history..."):
                    response = api_client.get(HISTORY_ENDPOINT, timeout=10)
                    # Extract data from response (API returns {success, message, timestamp, data})
                    hist = response.get('data', []) if isinstance(response, dict) else response
                    st.session_state[pref("chat_history_data")] = hist
                    st.session_state[pref("history_loaded")] = True

                if not hist:
                    st.info("No history found.")
                else:
                    st.success(f"Loaded {len(hist)} chat entries")
            except Exception as e:
                st.error(f"Failed to load history: {e}")
                st.session_state[pref("history_loaded")] = True  # Mark as loaded even on error to prevent infinite loops

        # Action buttons in a cleaner layout
        col1, col2, col3 = st.columns([2, 2, 3])

        with col1:
            refresh_history = st.button(
                "Refresh History",
                key=pref("refresh_button"),
                use_container_width=True
            )

        with col2:
            export_word = st.button(
                "Export to Word",
                key=pref("export_word_button"),
                use_container_width=True
            )

        st.divider()

        # Handle refreshing chat history
        if refresh_history:
            try:
                with st.spinner("Refreshing chat history..."):
                    response = api_client.get(HISTORY_ENDPOINT, timeout=10)
                    # Extract data from response (API returns {success, message, timestamp, data})
                    hist = response.get('data', []) if isinstance(response, dict) else response
                    st.session_state[pref("chat_history_data")] = hist

                if not hist:
                    st.info("No history found.")
                else:
                    st.success(f"Refreshed! Loaded {len(hist)} chat entries")
            except Exception as e:
                st.error(f"Failed to refresh history: {e}")

        # Display chat history if available
        chat_data = st.session_state.get(pref("chat_history_data"))
        if chat_data:
            # Initialize pagination state
            if pref("current_page") not in st.session_state:
                st.session_state[pref("current_page")] = 1
            if pref("items_per_page") not in st.session_state:
                st.session_state[pref("items_per_page")] = 20
            if pref("custom_titles") not in st.session_state:
                st.session_state[pref("custom_titles")] = {}
            if pref("search_query") not in st.session_state:
                st.session_state[pref("search_query")] = ""

            # Search and filter
            search_query = st.text_input(
                "Search conversations:",
                value=st.session_state[pref("search_query")],
                placeholder="Search by title, question, or response content...",
                key=pref("search_input")
            )
            st.session_state[pref("search_query")] = search_query

            # Filter conversations based on search
            filtered_data = chat_data
            if search_query:
                search_lower = search_query.lower()
                filtered_data = [
                    rec for rec in chat_data
                    if search_lower in rec.get('user_query', '').lower() or
                       search_lower in rec.get('response', '').lower()
                ]
                if not filtered_data:
                    st.warning(f"No conversations found matching '{search_query}'")
                else:
                    st.info(f"Found {len(filtered_data)} conversation(s) matching '{search_query}'")

            # Header with total count
            display_count = len(filtered_data) if search_query else len(chat_data)
            st.subheader(f"Chat History ({display_count} conversation{'s' if display_count != 1 else ''})")

            # Pagination controls
            col1, col2, col3, col4 = st.columns([2, 2, 2, 2])

            with col1:
                items_per_page_options = [10, 20, 50, len(chat_data)]
                items_per_page_labels = ["10 per page", "20 per page", "50 per page", "Show All"]
                selected_index = st.selectbox(
                    "Items per page:",
                    range(len(items_per_page_options)),
                    format_func=lambda x: items_per_page_labels[x],
                    index=1,  # Default to 20
                    key=pref("items_per_page_select")
                )
                items_per_page = items_per_page_options[selected_index]
                st.session_state[pref("items_per_page")] = items_per_page

            # Calculate pagination based on filtered data
            total_pages = max(1, (len(filtered_data) + items_per_page - 1) // items_per_page)
            current_page = st.session_state[pref("current_page")]

            # Ensure current page is within valid range
            if current_page > total_pages:
                current_page = total_pages
                st.session_state[pref("current_page")] = current_page

            with col2:
                st.metric("Page", f"{current_page} of {total_pages}")

            with col3:
                if st.button("Previous", key=pref("prev_page"), disabled=current_page <= 1):
                    st.session_state[pref("current_page")] = max(1, current_page - 1)
                    st.rerun()

            with col4:
                if st.button("Next", key=pref("next_page"), disabled=current_page >= total_pages):
                    st.session_state[pref("current_page")] = min(total_pages, current_page + 1)
                    st.rerun()

            st.markdown("---")

            # Calculate slice for current page
            # Reverse the data first to show newest first
            reversed_data = list(reversed(filtered_data))
            start_idx = (current_page - 1) * items_per_page
            end_idx = min(start_idx + items_per_page, len(reversed_data))
            conversations_to_show = reversed_data[start_idx:end_idx]

            # Display conversations for current page
            for idx, rec in enumerate(conversations_to_show, start=start_idx + 1):
                # Generate unique ID for this conversation (use timestamp + query hash)
                conv_id = f"{rec.get('id', '')}_{rec['timestamp']}"

                # Get custom title if exists, otherwise generate from query
                custom_titles = st.session_state[pref("custom_titles")]
                if conv_id in custom_titles:
                    title = custom_titles[conv_id]
                else:
                    title = generate_conversation_title(rec.get('user_query', ''))

                readable_time = format_timestamp(rec['timestamp'])
                query_type_badge = get_query_type_badge(rec)

                # Create header with title and metadata (plain text for expander)
                header_text = f"{title} - {readable_time}"

                with st.expander(header_text, expanded=False):
                    # Show query type badge and action buttons
                    col_badge, col_edit, col_delete = st.columns([3, 1, 1])

                    with col_badge:
                        st.markdown(query_type_badge, unsafe_allow_html=True)

                    with col_edit:
                        if st.button("Rename", key=pref(f"edit_{conv_id}_{idx}"), use_container_width=True):
                            st.session_state[pref(f"editing_{conv_id}")] = True
                            st.rerun()

                    # Show rename dialog if editing
                    if st.session_state.get(pref(f"editing_{conv_id}"), False):
                        new_title = st.text_input(
                            "New title:",
                            value=title,
                            key=pref(f"new_title_{conv_id}_{idx}")
                        )

                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            if st.button("Save", key=pref(f"save_{conv_id}_{idx}"), use_container_width=True):
                                st.session_state[pref("custom_titles")][conv_id] = new_title
                                st.session_state[pref(f"editing_{conv_id}")] = False
                                st.success(f"Title updated to: {new_title}")
                                st.rerun()

                        with col_cancel:
                            if st.button("Cancel", key=pref(f"cancel_{conv_id}_{idx}"), use_container_width=True):
                                st.session_state[pref(f"editing_{conv_id}")] = False
                                st.rerun()

                        st.divider()

                    # Display conversation metadata
                    meta_col1, meta_col2, meta_col3 = st.columns(3)
                    with meta_col1:
                        model_used = rec.get('model_used', 'N/A')
                        st.caption(f"**Model**: {model_used}")
                    with meta_col2:
                        response_time = rec.get('response_time_ms', 0)
                        if response_time:
                            st.caption(f"**Time**: {response_time/1000:.2f}s")
                    with meta_col3:
                        collection = rec.get('collection_name', '')
                        if collection:
                            st.caption(f"**Collection**: {collection}")

                    st.divider()

                    # Display conversation content
                    st.markdown("**Question:**")
                    st.info(rec['user_query'])

                    st.markdown("**Response:**")
                    st.markdown(rec['response'])

        # Handle export to Word
        if export_word:
            # Get chat history data if not already loaded
            export_data = st.session_state.get(pref("chat_history_data"))
            if not export_data:
                try:
                    with st.spinner("Loading chat history..."):
                        response = api_client.get(HISTORY_ENDPOINT, timeout=10)
                        # Extract data from response
                        export_data = response.get('data', []) if isinstance(response, dict) else response
                        st.session_state[pref("chat_history_data")] = export_data
                except Exception as e:
                    st.error(f"Failed to load history: {e}")
                    export_data = None

            if export_data:
                try:
                    with st.spinner("Generating Word document..."):
                        export_response = api_client.post(
                            f"{FASTAPI}/doc_gen/export-chat-history-word",
                            params={"limit": 100},
                            timeout=30
                        )

                        file_content = export_response.get("content_b64")
                        filename = export_response.get("filename", "chat_history_export.docx")

                        if file_content:
                            doc_bytes = base64.b64decode(file_content)

                            st.success("Document generated successfully!")
                            st.download_button(
                                label=f"Download {filename}",
                                data=doc_bytes,
                                file_name=filename,
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=pref("download_chat"),
                                use_container_width=True
                            )
                        else:
                            st.error("No file content received")
                except Exception as e:
                    st.error(f"Error exporting chat history: {str(e)}")
            else:
                st.warning("No chat history available. Please load history first.")
