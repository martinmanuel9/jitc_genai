"""
Unified Review Workflow Component

Provides consistent review/publish workflow UI for both test plans and test cards.
Workflow: DRAFT → REVIEWED → PUBLISHED

This component standardizes:
- Status badges with consistent colors
- Action buttons with consistent labels
- Progress tracking with consistent display
- Status update callbacks
"""

import streamlit as st
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Any
from enum import Enum


class ReviewStatus(Enum):
    """Standard review statuses for both test plans and test cards"""
    DRAFT = "DRAFT"
    REVIEWED = "REVIEWED"
    PUBLISHED = "PUBLISHED"


# Status configuration - colors and labels
STATUS_CONFIG = {
    ReviewStatus.DRAFT.value: {
        "color": "#ffc107",      # Yellow/Amber
        "bg_color": "#fff3cd",
        "label": "Draft",
        "icon": "📝",
        "description": "Pending review"
    },
    ReviewStatus.REVIEWED.value: {
        "color": "#28a745",      # Green
        "bg_color": "#d4edda",
        "label": "Reviewed",
        "icon": "✅",
        "description": "Approved, ready to publish"
    },
    ReviewStatus.PUBLISHED.value: {
        "color": "#0066cc",      # Blue
        "bg_color": "#cce5ff",
        "label": "Published",
        "icon": "🚀",
        "description": "Final, ready for execution"
    }
}


def render_status_badge(status: str, size: str = "normal") -> None:
    """
    Render a status badge with consistent styling.

    Args:
        status: Current status (DRAFT, REVIEWED, PUBLISHED)
        size: Badge size - "small", "normal", or "large"
    """
    config = STATUS_CONFIG.get(status, STATUS_CONFIG[ReviewStatus.DRAFT.value])

    font_sizes = {"small": "0.75em", "normal": "0.85em", "large": "1em"}
    paddings = {"small": "2px 6px", "normal": "4px 10px", "large": "6px 14px"}

    font_size = font_sizes.get(size, "0.85em")
    padding = paddings.get(size, "4px 10px")

    st.markdown(
        f'''<span style="
            background: {config['color']};
            color: white;
            padding: {padding};
            border-radius: 4px;
            font-size: {font_size};
            font-weight: 600;
            display: inline-block;
        ">{config['icon']} {config['label']}</span>''',
        unsafe_allow_html=True
    )


def render_status_actions(
    current_status: str,
    entity_type: str,
    entity_id: str,
    on_status_change: Callable[[str, str], bool],
    key_prefix: str = ""
) -> Optional[str]:
    """
    Render action buttons for status transitions.

    Args:
        current_status: Current status (DRAFT, REVIEWED, PUBLISHED)
        entity_type: "test_plan" or "test_card"
        entity_id: Unique identifier for the entity
        on_status_change: Callback function(new_status, entity_id) -> success
        key_prefix: Optional prefix for button keys

    Returns:
        New status if changed, None otherwise
    """
    entity_label = "Test Plan" if entity_type == "test_plan" else "Test Card"
    button_key = f"{key_prefix}_{entity_type}_{entity_id}"

    cols = st.columns(3)
    new_status = None

    with cols[0]:
        # Mark as Reviewed button
        can_review = current_status == ReviewStatus.DRAFT.value
        if st.button(
            "✅ Mark Reviewed",
            key=f"review_{button_key}",
            disabled=not can_review,
            use_container_width=True,
            help=f"Approve this {entity_label.lower()} after review"
        ):
            if on_status_change(ReviewStatus.REVIEWED.value, entity_id):
                new_status = ReviewStatus.REVIEWED.value
                st.success(f"{entity_label} marked as Reviewed")

    with cols[1]:
        # Publish button
        can_publish = current_status in [ReviewStatus.DRAFT.value, ReviewStatus.REVIEWED.value]
        if st.button(
            "Publish",
            key=f"publish_{button_key}",
            disabled=current_status == ReviewStatus.PUBLISHED.value,
            use_container_width=True,
            help=f"Publish this {entity_label.lower()} for execution"
        ):
            if on_status_change(ReviewStatus.PUBLISHED.value, entity_id):
                new_status = ReviewStatus.PUBLISHED.value
                st.success(f"{entity_label} Published")

    with cols[2]:
        # Reset to Draft button
        can_reset = current_status != ReviewStatus.DRAFT.value
        if st.button(
            "↩️ Reset Draft",
            key=f"reset_{button_key}",
            disabled=not can_reset,
            use_container_width=True,
            help=f"Return this {entity_label.lower()} to draft status"
        ):
            if on_status_change(ReviewStatus.DRAFT.value, entity_id):
                new_status = ReviewStatus.DRAFT.value
                st.success(f"{entity_label} reset to Draft")

    return new_status


def render_progress_tracker(
    items: List[Dict[str, Any]],
    entity_type: str,
    status_field: str = "review_status"
) -> Dict[str, int]:
    """
    Render a progress tracker showing counts and progress bar.

    Args:
        items: List of items with status field
        entity_type: "test_plan" or "test_card"
        status_field: Field name containing the status

    Returns:
        Dict with counts: {"draft": n, "reviewed": n, "published": n, "total": n}
    """
    entity_label = "Test Plans" if entity_type == "test_plan" else "Test Cards"

    # Count statuses
    counts = {
        "draft": 0,
        "reviewed": 0,
        "published": 0,
        "total": len(items)
    }

    for item in items:
        status = item.get(status_field, "DRAFT")
        if isinstance(item.get("metadata"), dict):
            status = item.get("metadata", {}).get(status_field, status)

        status = str(status).upper()
        if status == ReviewStatus.DRAFT.value:
            counts["draft"] += 1
        elif status == ReviewStatus.REVIEWED.value:
            counts["reviewed"] += 1
        elif status == ReviewStatus.PUBLISHED.value:
            counts["published"] += 1
        else:
            counts["draft"] += 1  # Default to draft

    # Display metrics
    metric_cols = st.columns(4)

    with metric_cols[0]:
        st.metric(
            "Draft",
            counts["draft"],
            help="Items pending review"
        )

    with metric_cols[1]:
        st.metric(
            "Reviewed",
            counts["reviewed"],
            help="Items approved, ready to publish"
        )

    with metric_cols[2]:
        st.metric(
            "Published",
            counts["published"],
            help="Items published and ready for execution"
        )

    with metric_cols[3]:
        st.metric(
            "Total",
            counts["total"],
            help=f"Total {entity_label.lower()}"
        )

    # Progress bar
    if counts["total"] > 0:
        # Progress = (reviewed + published) / total
        progress = (counts["reviewed"] + counts["published"]) / counts["total"]

        # Color based on progress
        if progress == 0:
            progress_text = "No items reviewed yet"
        elif progress < 0.5:
            progress_text = f"{progress:.0%} reviewed/published"
        elif progress < 1.0:
            progress_text = f"{progress:.0%} complete"
        else:
            progress_text = "All items published!"

        st.progress(progress, text=progress_text)

    return counts


def render_review_workflow_panel(
    current_status: str,
    entity_type: str,
    entity_id: str,
    on_status_change: Callable[[str, str], bool],
    items_for_progress: Optional[List[Dict]] = None,
    key_prefix: str = "",
    show_progress: bool = True,
    expanded: bool = True
) -> Optional[str]:
    """
    Render a complete review workflow panel with status, actions, and optional progress.

    Args:
        current_status: Current status of the selected item
        entity_type: "test_plan" or "test_card"
        entity_id: Unique identifier for the entity
        on_status_change: Callback function(new_status, entity_id) -> success
        items_for_progress: Optional list of all items for progress tracking
        key_prefix: Optional prefix for widget keys
        show_progress: Whether to show progress tracker
        expanded: Whether expander is expanded by default

    Returns:
        New status if changed, None otherwise
    """
    entity_label = "Test Plan" if entity_type == "test_plan" else "Test Card"

    with st.expander(f"📋 {entity_label} Review Status", expanded=expanded):
        # Current status badge
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("**Current Status:**")
        with col2:
            render_status_badge(current_status, size="normal")

        st.markdown("---")

        # Action buttons
        st.markdown("**Change Status:**")
        new_status = render_status_actions(
            current_status=current_status,
            entity_type=entity_type,
            entity_id=entity_id,
            on_status_change=on_status_change,
            key_prefix=key_prefix
        )

        # Progress tracker (if items provided)
        if show_progress and items_for_progress:
            st.markdown("---")
            st.markdown(f"**{entity_label} Progress:**")
            render_progress_tracker(
                items=items_for_progress,
                entity_type=entity_type
            )

        return new_status


def render_inline_status_selector(
    current_status: str,
    entity_type: str,
    entity_id: str,
    on_status_change: Callable[[str, str], bool],
    key_prefix: str = ""
) -> Optional[str]:
    """
    Render a compact inline status selector (badge + dropdown).

    Args:
        current_status: Current status
        entity_type: "test_plan" or "test_card"
        entity_id: Unique identifier
        on_status_change: Callback function
        key_prefix: Key prefix for widgets

    Returns:
        New status if changed, None otherwise
    """
    cols = st.columns([1, 2])

    with cols[0]:
        render_status_badge(current_status, size="small")

    with cols[1]:
        status_options = [s.value for s in ReviewStatus]
        current_index = status_options.index(current_status) if current_status in status_options else 0

        new_status = st.selectbox(
            "Status",
            options=status_options,
            index=current_index,
            format_func=lambda s: STATUS_CONFIG.get(s, {}).get("label", s),
            key=f"status_select_{key_prefix}_{entity_type}_{entity_id}",
            label_visibility="collapsed"
        )

        if new_status != current_status:
            if on_status_change(new_status, entity_id):
                return new_status

    return None


# Helper function to create status change callback
def create_chromadb_status_updater(
    api_client,
    config,
    collection_name: str = "test_cards"
) -> Callable[[str, str], bool]:
    """
    Create a callback function for updating status in ChromaDB.

    Args:
        api_client: API client instance
        config: Config with fastapi_url
        collection_name: ChromaDB collection name

    Returns:
        Callback function that updates status
    """
    def update_status(new_status: str, document_id: str) -> bool:
        try:
            # Get current document
            response = api_client.get(
                f"{config.fastapi_url}/api/vectordb/documents",
                params={"collection_name": collection_name},
                timeout=30
            )

            if not response:
                return False

            # Find the document
            ids = response.get("ids", [])
            docs = response.get("documents", [])
            metas = response.get("metadatas", [])

            doc_index = None
            for i, doc_id in enumerate(ids):
                if doc_id == document_id:
                    doc_index = i
                    break

            if doc_index is None:
                st.error(f"Document {document_id} not found")
                return False

            # Update metadata
            updated_metadata = dict(metas[doc_index]) if doc_index < len(metas) else {}
            updated_metadata["review_status"] = new_status
            updated_metadata["updated_at"] = datetime.now(timezone.utc).isoformat()

            # Sanitize metadata for ChromaDB
            sanitized_metadata = {}
            for key, value in updated_metadata.items():
                if value is None:
                    sanitized_metadata[key] = ""
                elif isinstance(value, (dict, list)):
                    import json
                    sanitized_metadata[key] = json.dumps(value)
                elif isinstance(value, bool):
                    sanitized_metadata[key] = str(value).lower()
                else:
                    sanitized_metadata[key] = value

            # Delete and re-add (more reliable than upsert)
            try:
                api_client.post(
                    f"{config.fastapi_url}/api/vectordb/documents/remove",
                    data={
                        "collection_name": collection_name,
                        "ids": [document_id]
                    },
                    timeout=30,
                    show_errors=False
                )
            except Exception:
                pass

            # Add updated document
            add_response = api_client.post(
                f"{config.fastapi_url}/api/vectordb/documents/add",
                data={
                    "collection_name": collection_name,
                    "documents": [docs[doc_index] if doc_index < len(docs) else ""],
                    "ids": [document_id],
                    "metadatas": [sanitized_metadata]
                },
                timeout=30
            )

            return add_response is not None

        except Exception as e:
            st.error(f"Failed to update status: {e}")
            return False

    return update_status
